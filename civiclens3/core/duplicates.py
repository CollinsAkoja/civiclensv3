"""Possible-duplicate detection.

Combines text similarity (TF-IDF cosine), category, location, and date.
Reports are only compared within the same state and LGA. Matches are *flagged
for human review*; nothing is merged or deleted automatically.
"""
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from core.schema import effective_category

THRESHOLD = 0.55
MAX_MATCHES = 5

W_TEXT, W_CATEGORY, W_LOCATION, W_DATE = 0.60, 0.15, 0.15, 0.10
DIFFERENT_CATEGORY_PENALTY = 0.4  # multiplier when both categories are known and differ

STOPWORDS = set("""
a an and are as at be been but by for from had has have if in into is it its
near of on or our over that the their there these this those to was we were
when whenever which while with very after before about around since still
again also not no than then them they you your out all any can will would
""".split())

# Small domain vocabulary so different wording about the same thing matches.
SYNONYMS = {
    "gutter": "drain", "drainage": "drain", "channel": "drain",
    "refuse": "waste", "garbage": "waste", "rubbish": "waste", "trash": "waste",
    "dump": "waste", "dirt": "waste",
    "hole": "pothole", "crater": "pothole",
    "tarmac": "road", "street": "road",
    "streetlight": "light", "lamp": "light",
    "pipeline": "pipe", "borehole": "water",
}


def _stem(word: str) -> str:
    if len(word) > 5 and word.endswith("ing"):
        word = word[:-3]
    elif len(word) > 4 and word.endswith("ed"):
        word = word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    return word


def tokenize(text: str) -> list:
    tokens = []
    for word in re.findall(r"[a-z0-9]+", str(text).lower()):
        if len(word) < 3 or word in STOPWORDS:
            continue
        word = _stem(word)
        tokens.append(SYNONYMS.get(word, word))
    return tokens


def _make_idf(documents: list):
    n = len(documents)
    df = Counter()
    for tokens in documents:
        df.update(set(tokens))
    return lambda term: math.log((1 + n) / (1 + df.get(term, 0))) + 1


def _vector(tokens: list, idf) -> dict:
    return {term: count * idf(term) for term, count in Counter(tokens).items()}


def _cosine(a: dict, b: dict) -> float:
    if not a or not b:
        return 0.0
    dot = sum(weight * b.get(term, 0.0) for term, weight in a.items())
    norm = math.sqrt(sum(w * w for w in a.values())) * math.sqrt(sum(w * w for w in b.values()))
    return dot / norm if norm else 0.0


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _norm(text) -> str:
    return " ".join(str(text or "").lower().split())


def _same_area(a: dict, b: dict) -> bool:
    return _norm(a.get("state")) == _norm(b.get("state")) and _norm(a.get("lga")) == _norm(b.get("lga"))


def _as_date(value) -> Optional[date]:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


@dataclass
class DuplicateMatch:
    other_id: int
    score: float
    text_similarity: float
    reasons: List[str] = field(default_factory=list)


def _score(new: dict, other: dict, text_sim: float):
    reasons = [f"Similar wording ({text_sim:.2f})"] if text_sim >= 0.25 else []

    cat_new, cat_old = effective_category(new), effective_category(other)
    if cat_new and cat_old:
        same_category = cat_new == cat_old
        category_part = 1.0 if same_category else 0.0
        if same_category:
            reasons.append("Same category")
    else:
        same_category, category_part = None, 0.5

    location_part = 0.0
    if _norm(new.get("community")) and _norm(new.get("community")) == _norm(other.get("community")):
        location_part = 1.0
        reasons.append("Same community")
    if None not in (new.get("latitude"), new.get("longitude"), other.get("latitude"), other.get("longitude")):
        km = _haversine_km(new["latitude"], new["longitude"], other["latitude"], other["longitude"])
        if km <= 0.3:
            location_part = 1.0
            reasons.append("Coordinates within 300 m")
        elif km <= 1.0:
            location_part = max(location_part, 0.5)
            reasons.append("Coordinates within 1 km")

    date_part = 0.0
    d_new, d_old = _as_date(new.get("date_observed")), _as_date(other.get("date_observed"))
    if d_new and d_old:
        days = abs((d_new - d_old).days)
        if days <= 7:
            date_part = 1.0
            reasons.append("Observed within 7 days")
        elif days <= 30:
            date_part = 0.5
            reasons.append("Observed within 30 days")

    score = (W_TEXT * text_sim + W_CATEGORY * category_part
             + W_LOCATION * location_part + W_DATE * date_part)
    if same_category is False:
        score *= DIFFERENT_CATEGORY_PENALTY
    return score, reasons


def find_duplicates(new: dict, existing: list, threshold: float = THRESHOLD) -> List[DuplicateMatch]:
    """Return existing reports that may describe the same issue as `new`."""
    candidates = [r for r in existing
                  if r.get("id") != new.get("id") and _same_area(new, r)]
    if not candidates:
        return []

    def text_of(report):
        return f"{report.get('title', '')} {report.get('description', '')}"

    corpus = [tokenize(text_of(r)) for r in existing] + [tokenize(text_of(new))]
    idf = _make_idf(corpus)
    new_vec = _vector(corpus[-1], idf)

    matches = []
    for other in candidates:
        text_sim = _cosine(new_vec, _vector(tokenize(text_of(other)), idf))
        score, reasons = _score(new, other, text_sim)
        if score >= threshold:
            matches.append(DuplicateMatch(other["id"], round(score, 3), round(text_sim, 3), reasons))
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:MAX_MATCHES]
