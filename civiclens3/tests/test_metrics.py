import pytest

from core.metrics import accuracy, binary_prf, confusion, macro_f1, per_class_metrics

TRUE = ["a", "a", "a", "b", "b", "c"]
PRED = ["a", "a", "b", "b", "a", "c"]


def test_per_class_values():
    m = per_class_metrics(TRUE, PRED, ["a", "b", "c"])
    assert m["a"]["precision"] == pytest.approx(2 / 3) and m["a"]["recall"] == pytest.approx(2 / 3)
    assert m["b"]["precision"] == pytest.approx(1 / 2) and m["b"]["recall"] == pytest.approx(1 / 2)
    assert m["c"]["f1"] == 1.0 and m["a"]["support"] == 3


def test_macro_f1_and_accuracy():
    m = per_class_metrics(TRUE, PRED, ["a", "b", "c"])
    assert macro_f1(m) == pytest.approx((2 / 3 + 1 / 2 + 1) / 3)
    assert accuracy(TRUE, PRED) == pytest.approx(4 / 6)


def test_never_predicted_class_does_not_divide_by_zero():
    m = per_class_metrics(["a", "b"], ["a", "a"], ["a", "b", "z"])
    assert m["b"]["precision"] == 0.0 and m["z"]["f1"] == 0.0


def test_confusion_counts():
    assert confusion(TRUE, PRED)[("a", "b")] == 1 and confusion(TRUE, PRED)[("b", "a")] == 1


def test_binary_prf():
    r = binary_prf([1, 1, 0, 0, 1], [1, 0, 1, 0, 1])
    assert (r["tp"], r["fp"], r["fn"], r["tn"]) == (2, 1, 1, 1)
    assert r["precision"] == pytest.approx(2 / 3) and r["recall"] == pytest.approx(2 / 3)
