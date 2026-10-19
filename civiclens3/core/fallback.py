"""Rule-based classifier used when the language model is unavailable.

It is deliberately simple: word-prefix keyword matching. It returns a plain
dict in the same shape the LLM must produce, so both go through the same
validation in core/classifier.py.
"""
import re

CATEGORY_KEYWORDS = {
    "Roads and potholes": [
        "pothole", "pot hole", "road", "tarmac", "asphalt", "crater",
        "bridge", "culvert", "speed bump",
    ],
    "Drainage and flooding": [
        "drain", "gutter", "flood", "sewer", "overflow", "stagnant water",
        "blocked channel",
    ],
    "Waste and sanitation": [
        "waste", "refuse", "garbage", "rubbish", "dump", "trash", "litter",
        "sanitation", "toilet", "open defecation", "bad smell",
    ],
    "Water supply": [
        "water supply", "borehole", "tap water", "pipe", "pipeline",
        "no water", "water shortage", "dirty water", "water scheme",
    ],
    "Streetlights and public facilities": [
        "streetlight", "street light", "lamp", "light pole", "bus stop",
        "traffic light", "signpost", "playground", "public facility",
        "public building",
    ],
}

HIGH_URGENCY_WORDS = [
    "collapse", "accident", "injur", "died", "death", "electrocut",
    "live wire", "fallen pole", "outbreak", "cholera", "sinkhole",
    "trapped", "fire", "children",
]


def _matches(text: str, words: list) -> list:
    return [w for w in words if re.search(r"\b" + re.escape(w), text)]


def classify_by_rules(report: dict) -> dict:
    text = f"{report.get('title', '')} {report.get('description', '')}".lower()

    best_category, best_hits = "Other", []
    for category, words in CATEGORY_KEYWORDS.items():
        hits = _matches(text, words)
        if len(hits) > len(best_hits):
            best_category, best_hits = category, hits

    if _matches(text, HIGH_URGENCY_WORDS):
        urgency = "high"
    elif best_hits:
        urgency = "medium"
    else:
        urgency = "low"

    description = " ".join(str(report.get("description", "")).split())
    summary = description[:200]
    if len(description) > 200:
        summary = summary.rsplit(" ", 1)[0] + "..."

    if best_hits:
        note = "Rule-based keyword match; no language model was used."
    else:
        note = "No keywords matched, so the category defaulted to Other."

    return {
        "category": best_category,
        "summary": summary or "No description provided.",
        "suggested_urgency": urgency,
        "keywords": best_hits[:8],
        "confidence_or_uncertainty": note,
        "needs_human_review": True,
    }
