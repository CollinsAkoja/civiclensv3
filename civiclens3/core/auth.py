"""Minimal reviewer authentication (shared password, constant-time compare).

This is a prototype safeguard, not a full identity system. For production use
real accounts, hashed credentials and audit logging.
"""
import hmac
from typing import Optional


def verify_password(entered: Optional[str], expected: Optional[str]) -> bool:
    """True only if a password is configured and the entered one matches."""
    if not expected or not entered:
        return False
    return hmac.compare_digest(entered.encode("utf-8"), expected.encode("utf-8"))
