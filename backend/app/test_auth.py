"""
Unit tests for authentication services in VHM24R.

These tests verify that authentication logic works as expected. The
current tests are placeholders and should be extended to cover real
authentication flows when the corresponding services are implemented.
"""

import pytest


def test_password_hashing() -> None:
    """Verify that hashing the same password with the same salt produces consistent results."""
    from backend.app.services.security_service import hash_password, verify_password

    password = "secret"
    salt = "salty"
    hashed = hash_password(password, salt)
    assert verify_password(password, salt, hashed)
