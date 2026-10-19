from datetime import date

import pytest

from core.classifier import ClassificationResult
from core.db import (
    add_duplicate_flag, add_report, get_report, init_db, list_duplicate_flags,
    review_report, save_ai_result, set_flag_status, set_resolution_status,
)
from core.schema import ReportInput, ValidationError
from core.service import check_duplicates, classify_pending, process_report


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "t.db"
    init_db(path)
    return path


def make(title="Pothole on Market Road", desc="A deep pothole on Market Road is damaging cars every day.", **kw):
    base = dict(title=title, description=desc, state="FCT (Abuja)", lga="Bwari",
                community="Dutse", date_observed=date.today())
    base.update(kw)
    return ReportInput(**base)


def ai(category="Roads and potholes"):
    return ClassificationResult(category, "A pothole.", "medium", ["pothole"], "", True, "test-model")


def test_approve_keeps_ai_columns_and_sets_reviewed_category(db):
    rid = add_report(make(), db)
    save_ai_result(rid, ai(), db)
    review_report(rid, "approve", db_path=db)
    row = get_report(rid, db)
    assert row["review_status"] == "approved"
    assert row["reviewed_category"] == "Roads and potholes"
    assert row["ai_category"] == "Roads and potholes" and row["reviewed_at"]


def test_correct_records_reviewer_choice_without_overwriting_ai(db):
    rid = add_report(make(), db)
    save_ai_result(rid, ai("Other"), db)
    review_report(rid, "correct", "Roads and potholes", db)
    row = get_report(rid, db)
    assert row["review_status"] == "corrected"
    assert row["reviewed_category"] == "Roads and potholes"
    assert row["ai_category"] == "Other"  # original suggestion preserved


def test_reject(db):
    rid = add_report(make(), db)
    review_report(rid, "reject", db_path=db)
    assert get_report(rid, db)["review_status"] == "rejected"


def test_approve_without_any_suggestion_is_refused(db):
    rid = add_report(make(), db)
    with pytest.raises(ValidationError):
        review_report(rid, "approve", db_path=db)
    assert get_report(rid, db)["review_status"] == "pending"


@pytest.mark.parametrize("action,category", [("correct", None), ("correct", "Nonsense"), ("delete", None)])
def test_invalid_review_input_refused(db, action, category):
    rid = add_report(make(), db)
    with pytest.raises(ValidationError):
        review_report(rid, action, category, db)


def test_review_unknown_report(db):
    with pytest.raises(LookupError):
        review_report(999, "reject", db_path=db)


def test_resolution_status_validated(db):
    rid = add_report(make(), db)
    set_resolution_status(rid, "verified_resolved", db)
    assert get_report(rid, db)["resolution_status"] == "verified_resolved"
    with pytest.raises(ValidationError):
        set_resolution_status(rid, "fixed!!", db)


def test_duplicate_flag_lifecycle(db):
    a, b = add_report(make(), db), add_report(make(), db)
    assert add_duplicate_flag(b, a, 0.8, ["Same community"], db) is True
    assert add_duplicate_flag(b, a, 0.8, ["Same community"], db) is False  # no double flags
    flags = list_duplicate_flags("pending", db)
    assert len(flags) == 1 and flags[0]["reasons"] == ["Same community"]
    set_flag_status(flags[0]["id"], "dismissed", db)
    assert list_duplicate_flags("pending", db) == []
    with pytest.raises(ValidationError):
        set_flag_status(flags[0]["id"], "maybe", db)
    with pytest.raises(LookupError):
        set_flag_status(999, "dismissed", db)


def test_process_report_flags_duplicate_but_never_deletes(db):
    first = add_report(make(), db)
    process_report(first, None, db)
    second = add_report(make(title="Bad hole on Market Road", desc="A deep pothole on Market Road is damaging cars daily."), db)
    result, matches = process_report(second, None, db)
    assert [m.other_id for m in matches] == [first]
    assert get_report(first, db) and get_report(second, db)  # both still exist
    assert list_duplicate_flags("pending", db)[0]["report_id"] == second


def test_older_reports_are_not_flagged_against_newer_ones(db):
    first = add_report(make(), db)
    add_report(make(), db)
    assert check_duplicates(first, db) == []


def test_classify_pending_also_checks_duplicates(db):
    add_report(make(), db)
    add_report(make(), db)
    assert classify_pending(None, db) == 2
    assert len(list_duplicate_flags(db_path=db)) == 1
