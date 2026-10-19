"""Classification metrics (pure Python, no scikit-learn needed)."""
from collections import Counter


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def per_class_metrics(y_true: list, y_pred: list, labels: list) -> dict:
    """Precision, recall, F1 and support for each label."""
    out = {}
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        precision, recall = _safe_div(tp, tp + fp), _safe_div(tp, tp + fn)
        out[label] = {
            "precision": precision, "recall": recall,
            "f1": _safe_div(2 * precision * recall, precision + recall),
            "support": tp + fn,
        }
    return out


def macro_f1(metrics: dict) -> float:
    return _safe_div(sum(m["f1"] for m in metrics.values()), len(metrics))


def accuracy(y_true: list, y_pred: list) -> float:
    return _safe_div(sum(t == p for t, p in zip(y_true, y_pred)), len(y_true))


def confusion(y_true: list, y_pred: list) -> Counter:
    """Counter keyed by (true_label, predicted_label)."""
    return Counter(zip(y_true, y_pred))


def binary_prf(y_true: list, y_pred: list) -> dict:
    """Precision, recall, F1 for the positive class (1) plus raw counts."""
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    precision, recall = _safe_div(tp, tp + fp), _safe_div(tp, tp + fn)
    return {"precision": precision, "recall": recall,
            "f1": _safe_div(2 * precision * recall, precision + recall),
            "tp": tp, "fp": fp, "fn": fn, "tn": tn}
