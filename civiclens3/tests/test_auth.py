from core.auth import verify_password


def test_correct_password():
    assert verify_password("s3cret", "s3cret") is True


def test_wrong_empty_or_unconfigured_password():
    assert verify_password("wrong", "s3cret") is False
    assert verify_password("", "s3cret") is False
    assert verify_password(None, "s3cret") is False
    assert verify_password("anything", None) is False
    assert verify_password("", "") is False  # unconfigured must never let people in
