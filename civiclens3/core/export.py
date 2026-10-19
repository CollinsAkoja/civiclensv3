"""CSV export with spreadsheet-formula injection protection."""
import pandas as pd

EXPORT_COLUMNS = [
    "id", "title", "description", "state", "lga", "community", "date_observed",
    "created_at", "category", "ai_category", "ai_urgency", "ai_summary", "ai_model",
    "reviewed_category", "review_status", "resolution_status",
]
RENAMES = {"category": "reporter_category"}
_DANGEROUS_START = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value):
    """Stop text from being run as a formula when the CSV is opened in Excel."""
    if isinstance(value, str) and value.startswith(_DANGEROUS_START):
        return "'" + value
    return value


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    out = df[EXPORT_COLUMNS].copy()
    out["date_observed"] = pd.to_datetime(out["date_observed"], errors="coerce").dt.strftime("%Y-%m-%d")
    out = out.rename(columns=RENAMES)
    # Apply to every column: newer pandas versions do not store text as "object".
    for column in out.columns:
        out[column] = out[column].map(csv_safe)
    return out.to_csv(index=False).encode("utf-8-sig")  # BOM helps Excel read UTF-8
