# CivicLens AI

**An AI-assisted platform for reporting, classifying and analysing community infrastructure problems in Nigeria.**
Capstone project, Meta 3MTT AI Skills Development programme.

Residents report problems such as potholes, blocked drains, uncollected waste, water outages and broken
streetlights. A local Llama model suggests a category, summary and urgency. The system flags possible
duplicates. Human reviewers approve, correct or reject the AI's suggestions. A dashboard and exports turn
the organised reports into evidence for community groups and authorities.

> **Status:** all eight planned phases are implemented and tested (99 automated tests).
> The live Llama evaluation must be run on your own machine (see [Evaluation](#evaluation)).

## What it does

| Area | Implemented |
|---|---|
| Submission | Validated form, optional category and approximate coordinates, no personal data collected |
| AI classification | Llama 3.2 via Ollama: category, summary, urgency suggestion, keywords, uncertainty note |
| Safety of AI output | Strict schema validation, retry, rule-based fallback, prompt-injection resistance |
| Duplicate detection | TF-IDF text similarity + category + location + date; flags for human review only |
| Human review | Approve / correct / reject; AI suggestion and human decision stored separately |
| Dashboard | Totals, category, LGA and monthly charts; filters; claims vs verified shown separately |
| Export | Filtered CSV (spreadsheet-formula safe) and a Markdown community report |
| Access control | Reviewer area behind a password; disabled entirely if no password is configured |
| Evaluation | Labelled test set, precision / recall / F1, duplicate-detection metrics |

## Responsible AI and privacy

- **No personal data.** No name, phone number or email is requested or stored. Coordinates are optional and
  rounded to about 110 m. The form asks people not to include personal details in free text.
- **AI output is a suggestion.** It is labelled as AI-generated everywhere it appears, stored in separate
  columns from the reviewer's decision, and never treated as verified. The model's self-reported
  uncertainty is shown as a note, not as a probability.
- **Reports are claims, not facts.** The dashboard keeps "submitted" and "independently verified" apart.
  Only a reviewer can mark a report as verified.
- **Untrusted input.** Report text is wrapped as data in the prompt, tag-breaking text is neutralised, and
  every model answer must match the allowed schema or it is discarded. Test reports include injection
  attempts ("ignore all previous instructions...").
- **Works without AI.** If Ollama is off or the model misbehaves, a rule-based classifier takes over and the
  app says it is in limited mode.
- **Humans decide duplicates.** Possible duplicates are flagged, never merged or deleted automatically.
- **Safe exports.** Cells that start with `=`, `+`, `-` or `@` are neutralised so a report title cannot run as a
  spreadsheet formula.

## Quick start (Windows, PowerShell)

```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
streamlit run app.py
```
If PowerShell blocks activation: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then retry.

### Enable the language model (optional)
1. Install Ollama from ollama.com, then `ollama pull llama3.2:3b` (about 2 GB, suits 8 GB of RAM).
2. Run `python check_ollama.py` to confirm the connection and see a sample classification.
3. Start the app. The sidebar shows "Language model ready" when it is connected.

### Enable the reviewer area
Set a password before starting the app (PowerShell):
```
$env:CIVICLENS_REVIEWER_PASSWORD = "choose-a-long-password"
streamlit run app.py
```
Or copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and edit it.
Without a password the reviewer tab stays locked.

### Try it with demo data
`$env:CIVICLENS_DEMO = "1"` loads 60 synthetic reports into an empty database so the dashboard has something
to show. Never present these as real community data.

## Evaluation

Run `python evaluate.py` (rule-based baseline) or `python evaluate.py --backend llama` (local Llama; allow
roughly 10-30 s per report on a CPU). Results are written to `data/evaluation_results.md`, and mistakes to
`data/errors_<backend>.csv`.

**Baseline results (rule-based classifier, 60 draft-labelled reports):**

| Measure | Result |
|---|---|
| Accuracy | 0.65 |
| Macro-F1 | 0.66 |

**Duplicate detection (20 labelled pairs, threshold 0.55):** precision 0.69, recall 0.90, F1 0.78.
Recall is favoured on purpose: a false alarm costs a reviewer a few seconds, while a missed duplicate distorts
the statistics.

**Llama results:** *add your numbers here after running `python evaluate.py --backend llama`, together with a
short discussion of its mistakes compared with the baseline.*

**Caveats about these numbers**
- The 60 test reports and their labels are a *draft*. Review every label yourself and extend the set to
  150-300 reports before drawing conclusions.
- The test set deliberately includes hard cases (Pidgin English, no obvious keywords, injection attempts),
  so the baseline is not flattering.
- Duplicate-pair categories come from the rule-based classifier, so its errors leak into those results.
- The duplicate threshold was set once on this small set. Treat it as a starting point.

## Project structure

```
app.py                Streamlit app: Submit | Dashboard | Reviewer
check_ollama.py       Live check of the local Llama connection
evaluate.py           Evaluation of classification and duplicate detection
core/schema.py        Allowed values and input validation
core/db.py            SQLite storage, review actions, duplicate flags, auto-migration
core/classifier.py    Prompt, schema validation, LLM-then-fallback pipeline
core/llm_ollama.py    Ollama backend (standard library only)
core/fallback.py      Rule-based classifier (limited mode and baseline)
core/duplicates.py    Possible-duplicate scoring
core/service.py       Classify + duplicate-check + store
core/analytics.py     Pandas summaries for the dashboard
core/export.py        Safe CSV export
core/report.py        Markdown community report
core/auth.py          Reviewer password check
core/metrics.py       Precision / recall / F1 (pure Python)
core/dataset.py       Loaders for the labelled data
core/seed.py          Synthetic demo data
data/                 Labelled test sets and evaluation output (database is git-ignored)
tests/                99 pytest tests
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md). In short: a demo can run on Streamlit Community Cloud in limited mode with
synthetic data, but a real deployment needs an external database, reviewer accounts and a hosted model.

## Known limitations

- The language model is small (3B parameters on CPU). Expect mistakes on vague, very short or heavily Pidgin
  reports, and slow responses on a laptop. Everything is checked by a human reviewer.
- LGA names are free text; spelling variants ("Bwari" vs "Bwari Area Council") prevent duplicate comparison.
- Duplicate detection uses wording overlap and a small synonym list. It can miss reports that use very
  different words and can flag distinct problems on the same street.
- Reviewer access uses one shared password. That suits a prototype, not production.
- No photo uploads, maps or multilingual (Hausa, Yoruba, Igbo) support yet.
- Counts reflect who reports, not necessarily where problems are worst.
- Classification is synchronous: the form waits for the model.

## Licence and model terms

Check the current Llama licence and acceptable-use policy on Meta's site before you deploy or redistribute
anything that uses the model, and cite the exact model tag you used (the app stores it with every AI result).

## Future work

Photo evidence, map view (Folium), Hausa / Yoruba / Igbo / Pidgin support, background classification queue,
per-reviewer accounts with an audit trail, a hosted database, SMS or WhatsApp intake, and consent and
data-protection review with a real pilot community before collecting live reports.
`````````
Author : Collins Akoja Nathaniels
````````