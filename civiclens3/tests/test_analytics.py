import json
from datetime import date

import pandas as pd

from core.analytics import (
    UNCLASSIFIED, apply_filters, by_location, counted, headline_metrics,
    monthly_trend, to_frame, top_keywords,
)


def row(i, **kw):
    base = dict(id=i, title=f"t{i}", description="d" * 25, category=None, state="Lagos", lga="Ikeja",
                community="GRA", latitude=None, longitude=None, date_observed="2026-09-10",
                created_at="2026-09-10T00:00:00", ai_category=None, ai_summary=None, ai_urgency=None,
                ai_keywords=None, ai_model=None, ai_uncertainty=None, ai_needs_review=None,
                review_status="pending", reviewed_category=None, reviewed_at=None,
                resolution_status="unverified")
    base.update(kw)
    return base


ROWS = [
    row(1, ai_category="Water supply", ai_keywords=json.dumps(["Borehole", "water"])),
    row(2, ai_category="Water supply", reviewed_category="Roads and potholes", review_status="corrected",
        state="Kano", lga="Nassarawa", date_observed="2026-10-02"),
    row(3, review_status="rejected", ai_category="Other"),
    row(4, category="Waste and sanitation", review_status="approved", reviewed_category="Waste and sanitation",
        resolution_status="verified_resolved", ai_keywords=json.dumps(["water"])),
    row(5),  # completely unclassified
]


def test_unclassified_reports_do_not_become_nan():
    """Regression: NaN is truthy and once broke sorting in the dashboard."""
    df = to_frame(ROWS)
    assert df.loc[df["id"] == 5, "effective_category"].iloc[0] == UNCLASSIFIED
    assert all(isinstance(v, str) for v in df["effective_category"])


def test_effective_category_priority():
    df = to_frame(ROWS).set_index("id")
    assert df.loc[2, "effective_category"] == "Roads and potholes"   # reviewer wins
    assert df.loc[4, "effective_category"] == "Waste and sanitation"
    assert df.loc[1, "effective_category"] == "Water supply"          # AI suggestion last


def test_headline_metrics_separate_claims_from_verified():
    m = headline_metrics(to_frame(ROWS), pending_duplicate_flags=2)
    assert m == {"submitted": 5, "awaiting_review": 2, "reviewed": 2, "rejected": 1,
                 "verified_unresolved": 0, "verified_resolved": 1, "possible_duplicates_pending": 2}


def test_counts_exclude_rejected():
    cats = counted(to_frame(ROWS), "effective_category")
    assert "Other" not in set(cats["effective_category"])
    assert cats["reports"].sum() == 4


def test_location_and_trend():
    df = to_frame(ROWS)
    assert by_location(df).iloc[0]["location"] == "Ikeja, Lagos"
    assert list(monthly_trend(df)["month"]) == ["2026-09", "2026-10"]


def test_filters():
    df = to_frame(ROWS)
    assert set(apply_filters(df, states=["Kano"])["id"]) == {2}
    assert set(apply_filters(df, categories=["Water supply"])["id"]) == {1}
    assert set(apply_filters(df, review_statuses=["approved"])["id"]) == {4}
    assert set(apply_filters(df, date_from=date(2026, 10, 1))["id"]) == {2}
    assert len(apply_filters(df)) == 5


def test_top_keywords_lowercased_and_counted_once_per_report():
    top = dict(top_keywords(to_frame(ROWS)))
    assert top["water"] == 2 and top["borehole"] == 1


def test_empty_data_does_not_crash():
    df = to_frame([])
    assert headline_metrics(df)["submitted"] == 0
    assert counted(df, "effective_category").empty
    assert by_location(df).empty and monthly_trend(df).empty
    assert top_keywords(df) == []
