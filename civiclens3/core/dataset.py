"""Loaders for the labelled evaluation data in data/."""
import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPORTS_CSV = DATA_DIR / "test_reports.csv"
PAIRS_CSV = DATA_DIR / "duplicate_pairs.csv"


def load_labelled_reports(path=REPORTS_CSV) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_duplicate_pairs(path=PAIRS_CSV) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["same_issue"] = int(row["same_issue"])
    return rows
