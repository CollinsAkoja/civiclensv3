from datetime import date, timedelta

import pytest

from core.schema import ReportInput, ValidationError, validate_report


def make(**overrides):
    base = dict(
        title="Large pothole on main road",
        description="A deep pothole has formed near the junction and cars swerve to avoid it.",
        state="FCT (Abuja)",
        lga="Bwari",
        community="Dutse",
        date_observed=date.today(),
    )
    base.update(overrides)
    return ReportInput(**base)


def test_valid_report_passes_and_whitespace_is_cleaned():
    out = validate_report(make(title="  Large   pothole  on road "))
    assert out.title == "Large pothole on road"


def test_short_title_rejected():
    with pytest.raises(ValidationError):
        validate_report(make(title="Hi"))


def test_short_description_rejected():
    with pytest.raises(ValidationError):
        validate_report(make(description="Too short"))


def test_invalid_state_rejected():
    with pytest.raises(ValidationError):
        validate_report(make(state="Atlantis"))


def test_invalid_category_rejected():
    with pytest.raises(ValidationError):
        validate_report(make(category="Aliens"))


def test_future_date_rejected():
    with pytest.raises(ValidationError):
        validate_report(make(date_observed=date.today() + timedelta(days=1)))


def test_coordinates_are_rounded():
    out = validate_report(make(latitude=9.07612345, longitude=7.39987654))
    assert (out.latitude, out.longitude) == (9.076, 7.4)


def test_coordinates_outside_nigeria_rejected():
    with pytest.raises(ValidationError):
        validate_report(make(latitude=51.5, longitude=-0.12))


def test_only_one_coordinate_rejected():
    with pytest.raises(ValidationError):
        validate_report(make(latitude=9.0))
