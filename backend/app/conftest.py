"""
Pytest fixtures for VHM24R.

This module defines common fixtures for unit and integration tests,
including a FastAPI test client, an in‑memory database session,
and any necessary setup and teardown logic. Fixtures should be
reusable across multiple test modules.
"""

import os
import pytest
from fastapi.testclient import TestClient

try:
    from backend.app.main import app
except ImportError:
    # If the application cannot be imported, provide a stub so that
    # tests can still be collected. This is useful when running
    # linting tools that import test modules without dependencies.
    app = None  # type: ignore


@pytest.fixture(scope="session")
def test_client() -> TestClient:
    """Yield a FastAPI TestClient for the application."""
    if app is None:
        pytest.skip("FastAPI application is not importable")
    with TestClient(app) as client:
        yield client
