from collections import Counter
from datetime import date

import pytest

from core.dataset import load_duplicate_pairs, load_labelled_reports
from core.db import init_db, list_reports
from core.schema import CATEGORIES, ReportInput, validate_report
from core.seed import seed_demo_data


def test_labelled_reports_are_well_formed():
    rows = load_labelled_reports()
    assert len(rows) >= 60
    assert len({r["id"] for r in rows}) == len(rows)
    assert {r["true_category"] for r in rows} <= set(CATEGORIES)
    counts = Counter(r["true_category"] for r in rows)
    assert min(counts.values()) >= 8, "classes should be roughly balanced"


def test_every_labelled_report_passes_input_validation():
    for r in load_labelled_reports():
        validate_report(ReportInput(title=r["title"], description=r["description"], state=r["state"],
                                    lga=r["lga"], community=r["community"], date_observed=date.today()))


def test_test_set_contains_injection_attempts_and_pidgin():
    text = " ".join(r["description"].lower() for r in load_labelled_reports())
    assert "ignore" in text and "don " in text


def test_duplicate_pairs_have_both_labels():
    pairs = load_duplicate_pairs()
    assert {p["same_issue"] for p in pairs} == {0, 1}


def test_seed_loads_once_and_marks_some_reviewed(tmp_path):
    db = tmp_path / "seed.db"
    init_db(db)
    added = seed_demo_data(db)
    rows = list_reports(db)
    assert added == len(rows) >= 60
    assert all(r["ai_category"] for r in rows)
    assert {"pending", "approved"} <= {r["review_status"] for r in rows}
    assert seed_demo_data(db) == 0
