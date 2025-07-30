"""
Security service for VHM24R.

This module contains helper functions related to security concerns
such as password hashing, JWT token handling, and other cryptographic
utilities. The current implementation is a placeholder and should
be extended with real cryptographic operations.
"""

import hashlib
import hmac
from typing import Any


def hash_password(password: str, salt: str) -> str:
    """Return a salted SHA256 hash of the given password.

    Args:
        password: Plain‑text password.
        salt: A unique salt string.

    Returns:
        A hexadecimal string representing the hashed password.
    """
    return hashlib.sha256((password + salt).encode()).hexdigest()


def verify_password(password: str, salt: str, hashed: str) -> bool:
    """Verify that a plain password matches a previously hashed value."""
    return hmac.compare_digest(hash_password(password, salt), hashed)
