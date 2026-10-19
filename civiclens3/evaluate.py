"""Phase 7 evaluation: classification and duplicate-detection metrics.

Examples:
    python evaluate.py                      # rule-based baseline only (instant)
    python evaluate.py --backend llama      # local Llama via Ollama (slow on CPU)
    python evaluate.py --backend both --limit 20   # quick trial run
Results are written to data/evaluation_results.md and data/errors_<backend>.csv
"""
import argparse
import csv
import time
from collections import Counter

from core.classifier import FALLBACK_NAME, classify_report
from core.dataset import DATA_DIR, load_duplicate_pairs, load_labelled_reports
from core.duplicates import THRESHOLD, find_duplicates
from core.fallback import classify_by_rules
from core.llm_ollama import OllamaBackend
from core.metrics import accuracy, binary_prf, confusion, macro_f1, per_class_metrics
from core.schema import CATEGORIES


def run_classifier(rows, backend, label):
    preds, used, seconds = [], [], []
    for i, row in enumerate(rows, 1):
        start = time.time()
        result = classify_report(row, backend)
        seconds.append(time.time() - start)
        preds.append(result.category)
        used.append(result.model)
        if backend is not None:
            print(f"  [{label}] {i}/{len(rows)}  {seconds[-1]:.1f}s  -> {result.category}")
    return preds, used, seconds


def evaluate_duplicates(pairs):
    truth, predicted, details = [], [], []
    for pair in pairs:
        base = {"state": "FCT (Abuja)", "lga": "Bwari"}
        a = dict(base, id=1, title=pair["title_a"], description=pair["desc_a"],
                 community=pair["community_a"], date_observed=pair["date_a"])
        b = dict(base, id=2, title=pair["title_b"], description=pair["desc_b"],
                 community=pair["community_b"], date_observed=pair["date_b"])
        a["ai_category"] = classify_by_rules(a)["category"]
        b["ai_category"] = classify_by_rules(b)["category"]
        matches = find_duplicates(b, [a])
        truth.append(pair["same_issue"])
        predicted.append(int(bool(matches)))
        details.append((pair["id"], pair["title_a"], pair["title_b"], pair["same_issue"],
                        matches[0].score if matches else 0.0))
    return binary_prf(truth, predicted), details


def section_for(name, rows, preds, used, seconds, backend_name):
    y_true = [r["true_category"] for r in rows]
    metrics = per_class_metrics(y_true, preds, CATEGORIES)
    lines = [f"## Classification: {name}", "",
             f"- Reports evaluated: {len(rows)}",
             f"- Accuracy: **{accuracy(y_true, preds):.2f}**",
             f"- Macro-F1: **{macro_f1(metrics):.2f}**"]
    if backend_name:
        fallbacks = sum(1 for m in used if m == FALLBACK_NAME)
        lines.append(f"- Reports where the model failed and the rule-based fallback answered: {fallbacks}")
        lines.append(f"- Mean time per report: {sum(seconds) / len(seconds):.1f}s")
    lines += ["", "| Category | Precision | Recall | F1 | Support |", "|---|---|---|---|---|"]
    for label, m in metrics.items():
        lines.append(f"| {label} | {m['precision']:.2f} | {m['recall']:.2f} | {m['f1']:.2f} | {m['support']} |")
    confusions = [(pair, n) for pair, n in confusion(y_true, preds).items() if pair[0] != pair[1]]
    confusions.sort(key=lambda item: -item[1])
    lines += ["", "Most common mistakes (true -> predicted):", ""]
    lines += [f"- {t} -> {p}: {n}" for (t, p), n in confusions[:6]] or ["- none"]
    return "\n".join(lines), [
        (r["id"], r["title"], r["true_category"], p)
        for r, p in zip(rows, preds) if r["true_category"] != p
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["rules", "llama", "both"], default="rules")
    parser.add_argument("--limit", type=int, default=None, help="evaluate only the first N reports")
    args = parser.parse_args()

    rows = load_labelled_reports()
    if args.limit:
        rows = rows[: args.limit]

    parts = ["# CivicLens AI evaluation", "",
             "Labels in `data/test_reports.csv` are a draft: review and correct them yourself, "
             "and extend the set to 150-300 reports before relying on the numbers.", ""]
    jobs = []
    if args.backend in ("rules", "both"):
        jobs.append(("Rule-based baseline", None, None))
    if args.backend in ("llama", "both"):
        llama = OllamaBackend()
        if not llama.is_available():
            raise SystemExit(f"Ollama is not reachable or {llama.name} is not pulled. "
                             f"Run: ollama pull {llama.name}")
        jobs.append((f"Llama ({llama.name})", llama, llama.name))

    for name, backend, backend_name in jobs:
        print(f"Running: {name}")
        preds, used, seconds = run_classifier(rows, backend, name)
        text, errors = section_for(name, rows, preds, used, seconds, backend_name)
        parts += [text, ""]
        slug = "llama" if backend else "rules"
        with open(DATA_DIR / f"errors_{slug}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "title", "true_category", "predicted"])
            w.writerows(errors)

    pairs = load_duplicate_pairs()
    prf, details = evaluate_duplicates(pairs)
    parts += [
        "## Duplicate detection", "",
        f"- Labelled pairs: {len(pairs)} ({sum(p['same_issue'] for p in pairs)} true duplicates)",
        f"- Threshold: {THRESHOLD}",
        f"- Precision: **{prf['precision']:.2f}**, Recall: **{prf['recall']:.2f}**, F1: **{prf['f1']:.2f}**",
        f"- True positives {prf['tp']}, false positives {prf['fp']}, false negatives {prf['fn']}, true negatives {prf['tn']}",
        "",
        "Recall is favoured over precision on purpose: flags go to a human reviewer, "
        "so a false alarm costs a few seconds while a missed duplicate distorts the statistics.",
        "Pair categories here come from the rule-based classifier, so its mistakes affect these results.", "",
        "| Pair | Truth | Score | Report A | Report B |", "|---|---|---|---|---|",
    ]
    for pid, title_a, title_b, truth, score in details:
        parts.append(f"| {pid} | {'duplicate' if truth else 'different'} | {score:.2f} | {title_a} | {title_b} |")

    output = DATA_DIR / "evaluation_results.md"
    output.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"\nWrote {output}")


if __name__ == "__main__":
    main()
