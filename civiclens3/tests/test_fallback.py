import pytest

from core.classifier import validate_classification
from core.fallback import classify_by_rules


def rep(title, description="x" * 30):
    return {"title": title, "description": description}


@pytest.mark.parametrize("title,description,expected", [
    ("Big pothole", "A deep pothole on the main road damaged my tyre.", "Roads and potholes"),
    ("Blocked gutter", "The drain is blocked and the street floods when it rains.", "Drainage and flooding"),
    ("Refuse heap", "Garbage has not been collected for weeks and the dump smells.", "Waste and sanitation"),
    ("No water", "The borehole has stopped and there is no water in the estate.", "Water supply"),
    ("Dark street", "The streetlight near the junction has not worked for months.", "Streetlights and public facilities"),
    ("Noise", "Neighbours play loud music late at night every weekend.", "Other"),
])
def test_categories(title, description, expected):
    assert classify_by_rules(rep(title, description))["category"] == expected


def test_danger_words_raise_urgency():
    out = classify_by_rules(rep("Fallen pole", "A live wire is hanging over the road near the school."))
    assert out["suggested_urgency"] == "high"


def test_unmatched_report_is_low_and_other():
    out = classify_by_rules(rep("Something odd", "There is a thing that bothers me a bit."))
    assert (out["category"], out["suggested_urgency"]) == ("Other", "low")


def test_fallback_output_passes_validation():
    raw = classify_by_rules(rep("Pothole", "A very deep pothole on the road " * 20))
    result = validate_classification(raw, "rule-based-v1")
    assert len(result.summary) <= 300
