"""Synthetic demo data, so a deployed demo is not an empty app.

Every record here is invented (from data/test_reports.csv). Never present it
as real community data.
"""
from datetime import date, timedelta

from core.dataset import load_labelled_reports
from core.db import add_report, list_reports, review_report, set_resolution_status
from core.schema import ReportInput
from core.service import process_report


def seed_demo_data(db_path=None, today: date = None) -> int:
    """Load synthetic reports if the database is empty. Returns how many were added."""
    if list_reports(db_path):
        return 0
    today = today or date.today()
    rows = load_labelled_reports()
    for i, row in enumerate(rows):
        report_id = add_report(ReportInput(
            title=row["title"], description=row["description"], state=row["state"],
            lga=row["lga"], community=row["community"],
            date_observed=today - timedelta(days=(i * 5) % 150),
        ), db_path)
        process_report(report_id, None, db_path)
        if i % 3 == 0:
            review_report(report_id, "approve", db_path=db_path)
            if i % 6 == 0:
                set_resolution_status(report_id, "verified_unresolved", db_path)
            if i % 12 == 0:
                set_resolution_status(report_id, "verified_resolved", db_path)
    return len(rows)
