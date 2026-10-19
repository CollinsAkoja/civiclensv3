"""Allowed values and input validation for CivicLens AI.

Everything a user submits is treated as untrusted input and is checked here
before it reaches the database.
"""
from dataclasses import dataclass
from datetime import date
from typing import Optional

CATEGORIES = [
    "Roads and potholes",
    "Drainage and flooding",
    "Waste and sanitation",
    "Water supply",
    "Streetlights and public facilities",
    "Other",
]

URGENCY_LEVELS = ["low", "medium", "high"]
REVIEW_STATUSES = ["pending", "approved", "corrected", "rejected"]
RESOLUTION_STATUSES = ["unverified", "verified_unresolved", "verified_resolved"]

NIGERIAN_STATES = [
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue",
    "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu",
    "FCT (Abuja)", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina",
    "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo",
    "Osun", "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara",
]

TITLE_MIN, TITLE_MAX = 5, 120
DESC_MIN, DESC_MAX = 20, 2000
TEXT_MAX = 100  # LGA and community names


class ValidationError(ValueError):
    """Raised when a submitted report fails validation."""


@dataclass
class ReportInput:
    title: str
    description: str
    state: str
    lga: str
    community: str
    date_observed: date
    category: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


def _clean(text: Optional[str]) -> str:
    """Trim and collapse whitespace; None becomes an empty string."""
    return " ".join((text or "").split())


def validate_report(data: ReportInput) -> ReportInput:
    """Return a cleaned copy of the report, or raise ValidationError.

    Coordinates are rounded to 3 decimal places (about 110 m) so that stored
    locations are approximate and do not identify a single household.
    """
    errors = []

    title = _clean(data.title)
    description = _clean(data.description)
    lga = _clean(data.lga)
    community = _clean(data.community)

    if not TITLE_MIN <= len(title) <= TITLE_MAX:
        errors.append(f"Title must be {TITLE_MIN}-{TITLE_MAX} characters.")
    if not DESC_MIN <= len(description) <= DESC_MAX:
        errors.append(f"Description must be {DESC_MIN}-{DESC_MAX} characters.")
    if data.state not in NIGERIAN_STATES:
        errors.append("Please choose a valid state.")
    if not lga or len(lga) > TEXT_MAX:
        errors.append(f"Local government area is required (max {TEXT_MAX} characters).")
    if not community or len(community) > TEXT_MAX:
        errors.append(f"Community is required (max {TEXT_MAX} characters).")
    if data.category is not None and data.category not in CATEGORIES:
        errors.append("Category is not one of the allowed options.")
    if not isinstance(data.date_observed, date) or data.date_observed > date.today():
        errors.append("Date observed cannot be in the future.")

    lat, lon = data.latitude, data.longitude
    if (lat is None) != (lon is None):
        errors.append("Provide both latitude and longitude, or neither.")
    elif lat is not None:
        # Rough bounding box for Nigeria.
        if not (4.0 <= lat <= 14.0 and 2.5 <= lon <= 15.0):
            errors.append("Coordinates appear to be outside Nigeria.")
        else:
            lat, lon = round(lat, 3), round(lon, 3)

    if errors:
        raise ValidationError(" ".join(errors))

    return ReportInput(
        title=title,
        description=description,
        state=data.state,
        lga=lga,
        community=community,
        date_observed=data.date_observed,
        category=data.category,
        latitude=lat,
        longitude=lon,
    )


FLAG_STATUSES = ["pending", "confirmed_duplicate", "dismissed"]
REVIEW_ACTIONS = ["approve", "correct", "reject"]


def effective_category(row: dict) -> Optional[str]:
    """Best current category: reviewer's, else reporter's, else the AI suggestion."""
    return row.get("reviewed_category") or row.get("category") or row.get("ai_category")
