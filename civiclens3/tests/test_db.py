from datetime import date

import pytest

from core.db import add_report, get_report, init_db, list_reports
from core.schema import ReportInput, ValidationError


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    init_db(path)
    return path


def make(**overrides):
    base = dict(
        title="Blocked drainage after market",
        description="The drain beside the market is full of refuse and floods the road when it rains.",
        state="Lagos",
        lga="Ikeja",
        community="Computer Village",
        date_observed=date.today(),
    )
    base.update(overrides)
    return ReportInput(**base)


def test_add_and_get_report(db):
    new_id = add_report(make(category="Drainage and flooding"), db)
    row = get_report(new_id, db)
    assert row["title"] == "Blocked drainage after market"
    assert row["category"] == "Drainage and flooding"
    assert row["review_status"] == "pending"
    assert row["resolution_status"] == "unverified"
    assert row["ai_summary"] is None


def test_list_reports_newest_first(db):
    a = add_report(make(title="First report title"), db)
    b = add_report(make(title="Second report title"), db)
    assert [r["id"] for r in list_reports(db)] == [b, a]


def test_invalid_report_is_not_saved(db):
    with pytest.raises(ValidationError):
        add_report(make(title="x"), db)
    assert list_reports(db) == []


def test_sql_injection_text_is_stored_as_plain_text(db):
    nasty = "Robert'); DROP TABLE reports;-- is a very bad title"
    new_id = add_report(make(title=nasty), db)
    assert get_report(new_id, db)["title"] == nasty
    assert len(list_reports(db)) == 1
