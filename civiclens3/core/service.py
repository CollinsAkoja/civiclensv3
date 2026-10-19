"""Glue between storage, classification and duplicate detection."""
from core.classifier import ClassificationResult, classify_report
from core.db import (
    add_duplicate_flag, get_report, list_reports, list_unclassified, save_ai_result,
)
from core.duplicates import DuplicateMatch, find_duplicates


def classify_and_store(report_id: int, backend=None, db_path=None) -> ClassificationResult:
    report = get_report(report_id, db_path)
    if report is None:
        raise LookupError(f"No report with id {report_id}")
    result = classify_report(report, backend)
    save_ai_result(report_id, result, db_path)
    return result


def check_duplicates(report_id: int, db_path=None) -> list:
    """Compare a report with earlier ones and store flags for human review."""
    report = get_report(report_id, db_path)
    if report is None:
        raise LookupError(f"No report with id {report_id}")
    earlier = [r for r in list_reports(db_path) if r["id"] < report_id]
    matches = find_duplicates(report, earlier)
    for match in matches:
        add_duplicate_flag(report_id, match.other_id, match.score, match.reasons, db_path)
    return matches


def process_report(report_id: int, backend=None, db_path=None):
    """Classify a new report, then check it for possible duplicates."""
    result = classify_and_store(report_id, backend, db_path)
    matches = check_duplicates(report_id, db_path)
    return result, matches


def classify_pending(backend=None, db_path=None) -> int:
    """Process every report that has no AI suggestion yet. Returns the count."""
    pending = list_unclassified(db_path)
    for report in pending:
        process_report(report["id"], backend, db_path)
    return len(pending)
