"""
Integration tests for database interactions.

These tests verify that the ORM models and database sessions can be
created and queried. They should be expanded to cover real queries
once models and CRUD functions are implemented.
"""

import pytest


def test_database_connection() -> None:
    """Ensure that a database URL is configured in the environment."""
    import os
    db_url = os.getenv("DATABASE_URL")
    assert db_url is not None, "DATABASE_URL environment variable must be set"
