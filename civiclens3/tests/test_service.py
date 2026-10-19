import json
import sqlite3
from datetime import date

import pytest

from core.db import add_report, get_report, init_db
from core.schema import ReportInput
from core.service import classify_and_store, classify_pending


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "t.db"
    init_db(path)
    return path


def make(title="Blocked drain on Market Road"):
    return ReportInput(
        title=title,
        description="The drain is blocked with refuse and the road floods whenever it rains.",
        state="Lagos", lga="Ikeja", community="GRA", date_observed=date.today())


def test_classification_is_stored_in_ai_columns_only(db):
    rid = add_report(make(), db)
    classify_and_store(rid, backend=None, db_path=db)
    row = get_report(rid, db)
    assert row["ai_category"] == "Drainage and flooding"
    assert row["ai_model"] == "rule-based-v1"
    assert json.loads(row["ai_keywords"])
    assert row["ai_needs_review"] == 1
    # Human-review columns are untouched
    assert row["review_status"] == "pending" and row["reviewed_category"] is None
    assert row["category"] is None


def test_classify_pending_only_touches_unclassified(db):
    a = add_report(make("First blocked drain report"), db)
    add_report(make("Second blocked drain report"), db)
    classify_and_store(a, None, db)
    assert classify_pending(None, db) == 1
    assert classify_pending(None, db) == 0


def test_old_database_is_migrated(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript("""CREATE TABLE reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
        description TEXT NOT NULL, category TEXT, state TEXT NOT NULL,
        lga TEXT NOT NULL, community TEXT NOT NULL, latitude REAL, longitude REAL,
        date_observed TEXT NOT NULL, created_at TEXT NOT NULL,
        ai_category TEXT, ai_summary TEXT, ai_urgency TEXT, ai_keywords TEXT,
        ai_model TEXT, review_status TEXT NOT NULL DEFAULT 'pending',
        reviewed_category TEXT, resolution_status TEXT NOT NULL DEFAULT 'unverified');
        INSERT INTO reports (title, description, state, lga, community,
            date_observed, created_at) VALUES ('Old', 'Old report text here', 'Lagos',
            'Ikeja', 'GRA', '2026-01-01', '2026-01-01T00:00:00');""")
    conn.commit()
    conn.close()
    init_db(path)
    row = get_report(1, path)
    assert row["title"] == "Old" and "ai_uncertainty" in row
