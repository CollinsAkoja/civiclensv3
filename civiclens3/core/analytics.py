"""Pandas helpers behind the dashboard, exports and community report."""
import json
from collections import Counter
from typing import Optional

import pandas as pd

from core.schema import effective_category

REPORT_COLUMNS = [
    "id", "title", "description", "category", "state", "lga", "community",
    "latitude", "longitude", "date_observed", "created_at", "ai_category",
    "ai_summary", "ai_urgency", "ai_keywords", "ai_model", "ai_uncertainty",
    "ai_needs_review", "review_status", "reviewed_category", "reviewed_at",
    "resolution_status",
]
UNCLASSIFIED = "Unclassified"


def _parse_keywords(value) -> list:
    try:
        parsed = json.loads(value) if value else []
    except (TypeError, ValueError):
        return []
    return [str(k).lower() for k in parsed] if isinstance(parsed, list) else []


def to_frame(rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=REPORT_COLUMNS)
    # Computed from the original rows: inside a DataFrame, missing values become
    # NaN, which is truthy and would slip past the "or UNCLASSIFIED" fallback.
    df["effective_category"] = [effective_category(r) or UNCLASSIFIED for r in rows]
    df["date_observed"] = pd.to_datetime(df["date_observed"], errors="coerce")
    df["keywords_list"] = df["ai_keywords"].apply(_parse_keywords)
    return df


def apply_filters(df: pd.DataFrame, states=None, categories=None, review_statuses=None,
                  date_from=None, date_to=None) -> pd.DataFrame:
    out = df
    if states:
        out = out[out["state"].isin(states)]
    if categories:
        out = out[out["effective_category"].isin(categories)]
    if review_statuses:
        out = out[out["review_status"].isin(review_statuses)]
    if date_from is not None:
        out = out[out["date_observed"] >= pd.Timestamp(date_from)]
    if date_to is not None:
        out = out[out["date_observed"] <= pd.Timestamp(date_to)]
    return out


def headline_metrics(df: pd.DataFrame, pending_duplicate_flags: int = 0) -> dict:
    status = df["review_status"]
    resolution = df["resolution_status"]
    return {
        "submitted": int(len(df)),
        "awaiting_review": int((status == "pending").sum()),
        "reviewed": int(status.isin(["approved", "corrected"]).sum()),
        "rejected": int((status == "rejected").sum()),
        "verified_unresolved": int((resolution == "verified_unresolved").sum()),
        "verified_resolved": int((resolution == "verified_resolved").sum()),
        "possible_duplicates_pending": int(pending_duplicate_flags),
    }


def counted(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Reports per value of a column, largest first. Rejected reports are excluded."""
    kept = df[df["review_status"] != "rejected"]
    counts = kept[column].fillna(UNCLASSIFIED).value_counts()
    return counts.rename_axis(column).reset_index(name="reports")


def by_location(df: pd.DataFrame) -> pd.DataFrame:
    kept = df[df["review_status"] != "rejected"]
    if kept.empty:
        return pd.DataFrame(columns=["location", "reports"])
    grouped = kept.groupby(["state", "lga"]).size().reset_index(name="reports")
    grouped["location"] = grouped["lga"] + ", " + grouped["state"]
    return grouped.sort_values("reports", ascending=False)[["location", "reports"]]


def monthly_trend(df: pd.DataFrame) -> pd.DataFrame:
    kept = df[(df["review_status"] != "rejected") & df["date_observed"].notna()]
    if kept.empty:
        return pd.DataFrame(columns=["month", "reports"])
    months = kept["date_observed"].dt.to_period("M").astype(str)
    return months.value_counts().sort_index().rename_axis("month").reset_index(name="reports")


def top_keywords(df: pd.DataFrame, n: int = 10) -> list:
    counter = Counter()
    for keywords in df["keywords_list"]:
        counter.update(set(keywords))
    return counter.most_common(n)
