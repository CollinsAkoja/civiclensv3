import io

import pandas as pd

from core.analytics import to_frame
from core.export import csv_safe, to_csv_bytes
from core.report import LIMITATIONS, generate_report
from tests.test_analytics import ROWS, row


def test_csv_safe_blocks_formula_injection():
    assert csv_safe("=HYPERLINK('http://evil')") == "'=HYPERLINK('http://evil')"
    assert csv_safe("+1+1") == "'+1+1" and csv_safe("@cmd") == "'@cmd" and csv_safe("-5") == "'-5"
    assert csv_safe("Normal title") == "Normal title"
    assert csv_safe(None) is None and csv_safe(7) == 7


def test_csv_export_contents_and_safety():
    rows = ROWS + [row(6, title='=cmd|" /c calc"!A1', description="x" * 30)]
    data = to_csv_bytes(to_frame(rows))
    out = pd.read_csv(io.BytesIO(data))
    assert len(out) == 6
    assert "reporter_category" in out.columns
    assert out.loc[out["id"] == 6, "title"].iloc[0].startswith("'=")
    assert out["date_observed"].iloc[0] == "2026-09-10"
    for forbidden in ("phone", "name", "email"):
        assert forbidden not in " ".join(out.columns).lower()


def test_report_has_figures_limitations_and_followups():
    text = generate_report(to_frame(ROWS), "No filters applied", pending_duplicate_flags=1)
    assert "Reports submitted: 5" in text
    assert "Awaiting human review: 2" in text
    assert "Verified resolved: 1" in text
    for limitation in LIMITATIONS:
        assert limitation in text
    assert "Suggested follow-up" in text and "flagged possible duplicates" in text
    assert "Verify the most frequently reported concern" in text


def test_report_for_empty_selection():
    text = generate_report(to_frame([]), "state: Atlantis")
    assert "No reports match these filters." in text
    assert "Reports submitted: 0" in text and "Limitations" in text
