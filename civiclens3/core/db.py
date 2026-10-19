"""SQLite storage for CivicLens AI.

Uses parameterised queries only. No reporter name, phone number or email is
stored. The database location comes from the CIVICLENS_DB environment variable
(default: data/civiclens.db).
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.schema import (
    CATEGORIES, FLAG_STATUSES, RESOLUTION_STATUSES, REVIEW_ACTIONS,
    ReportInput, ValidationError, validate_report,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT,
    state TEXT NOT NULL,
    lga TEXT NOT NULL,
    community TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    date_observed TEXT NOT NULL,
    created_at TEXT NOT NULL,
    -- AI suggestions (always labelled as AI-generated in the interface)
    ai_category TEXT,
    ai_summary TEXT,
    ai_urgency TEXT,
    ai_keywords TEXT,
    ai_model TEXT,
    ai_uncertainty TEXT,
    ai_needs_review INTEGER,
    -- Human review and verification
    review_status TEXT NOT NULL DEFAULT 'pending',
    reviewed_category TEXT,
    reviewed_at TEXT,
    resolution_status TEXT NOT NULL DEFAULT 'unverified'
);

CREATE TABLE IF NOT EXISTS duplicate_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    duplicate_of_id INTEGER NOT NULL,
    score REAL NOT NULL,
    reasons TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    UNIQUE (report_id, duplicate_of_id)
);
"""

# Columns added after the first release. init_db() adds any that an older
# database file is missing, so existing data is kept.
MIGRATION_COLUMNS = [
    ("ai_uncertainty", "TEXT"),
    ("ai_needs_review", "INTEGER"),
    ("reviewed_at", "TEXT"),
]


class DatabaseError(RuntimeError):
    """Raised when a database operation fails."""


def default_db_path() -> Path:
    return Path(os.environ.get("CIVICLENS_DB", Path("data") / "civiclens.db"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_connection(db_path=None):
    path = Path(db_path) if db_path else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        raise DatabaseError(f"Database error: {exc}") from exc
    finally:
        conn.close()


def init_db(db_path=None) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(reports)")}
        for name, col_type in MIGRATION_COLUMNS:
            if name not in existing:
                conn.execute(f"ALTER TABLE reports ADD COLUMN {name} {col_type}")


# ---------------------------------------------------------------- reports
def add_report(report: ReportInput, db_path=None) -> int:
    """Validate and store a report. Returns the new report id."""
    clean = validate_report(report)
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO reports
               (title, description, category, state, lga, community,
                latitude, longitude, date_observed, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                clean.title, clean.description, clean.category, clean.state,
                clean.lga, clean.community, clean.latitude, clean.longitude,
                clean.date_observed.isoformat(), _now(),
            ),
        )
        return cur.lastrowid


def get_report(report_id: int, db_path=None) -> Optional[dict]:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    return dict(row) if row else None


def list_reports(db_path=None) -> list:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM reports ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------------- AI results
def save_ai_result(report_id: int, result, db_path=None) -> None:
    """Store an AI suggestion. Never touches the reviewer's columns."""
    with get_connection(db_path) as conn:
        conn.execute(
            """UPDATE reports SET ai_category = ?, ai_summary = ?, ai_urgency = ?,
                   ai_keywords = ?, ai_model = ?, ai_uncertainty = ?,
                   ai_needs_review = ?
               WHERE id = ?""",
            (
                result.category, result.summary, result.suggested_urgency,
                json.dumps(result.keywords, ensure_ascii=False), result.model,
                result.uncertainty, int(result.needs_human_review), report_id,
            ),
        )


def list_unclassified(db_path=None) -> list:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM reports WHERE ai_category IS NULL ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


# ----------------------------------------------------------- human review
def review_report(report_id: int, action: str, corrected_category: Optional[str] = None,
                  db_path=None) -> None:
    """Approve the AI suggestion, correct the category, or reject the report.

    The AI columns are never modified, so the original suggestion is always
    kept alongside the human decision.
    """
    if action not in REVIEW_ACTIONS:
        raise ValidationError(f"Unknown review action: {action!r}")
    report = get_report(report_id, db_path)
    if report is None:
        raise LookupError(f"No report with id {report_id}")

    reviewed_category = report["reviewed_category"]
    if action == "approve":
        suggestion = report["ai_category"] or report["category"]
        if suggestion is None:
            raise ValidationError("There is no suggested category to approve. Use Correct instead.")
        status, reviewed_category = "approved", suggestion
    elif action == "correct":
        if corrected_category not in CATEGORIES:
            raise ValidationError("Choose one of the allowed categories.")
        status, reviewed_category = "corrected", corrected_category
    else:
        status = "rejected"

    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE reports SET review_status = ?, reviewed_category = ?, reviewed_at = ? WHERE id = ?",
            (status, reviewed_category, _now(), report_id),
        )


def set_resolution_status(report_id: int, status: str, db_path=None) -> None:
    """Record a verified resolution state. Reviewer use only."""
    if status not in RESOLUTION_STATUSES:
        raise ValidationError(f"Unknown resolution status: {status!r}")
    if get_report(report_id, db_path) is None:
        raise LookupError(f"No report with id {report_id}")
    with get_connection(db_path) as conn:
        conn.execute("UPDATE reports SET resolution_status = ? WHERE id = ?", (status, report_id))


# -------------------------------------------------------- duplicate flags
def add_duplicate_flag(report_id: int, duplicate_of_id: int, score: float,
                       reasons: list, db_path=None) -> bool:
    """Record a possible duplicate. Returns False if that pair is already flagged."""
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT OR IGNORE INTO duplicate_flags
               (report_id, duplicate_of_id, score, reasons, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (report_id, duplicate_of_id, float(score),
             json.dumps(reasons, ensure_ascii=False), _now()),
        )
        return cur.rowcount == 1


def list_duplicate_flags(status: Optional[str] = None, db_path=None) -> list:
    query, params = "SELECT * FROM duplicate_flags", ()
    if status is not None:
        query, params = query + " WHERE status = ?", (status,)
    with get_connection(db_path) as conn:
        rows = conn.execute(query + " ORDER BY score DESC, id", params).fetchall()
    flags = [dict(r) for r in rows]
    for flag in flags:
        flag["reasons"] = json.loads(flag["reasons"])
    return flags


def set_flag_status(flag_id: int, status: str, db_path=None) -> None:
    if status not in FLAG_STATUSES:
        raise ValidationError(f"Unknown flag status: {status!r}")
    with get_connection(db_path) as conn:
        cur = conn.execute("UPDATE duplicate_flags SET status = ? WHERE id = ?", (status, flag_id))
        if cur.rowcount == 0:
            raise LookupError(f"No duplicate flag with id {flag_id}")
