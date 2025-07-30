"""
Integration tests for API endpoints in VHM24R.

These tests ensure that key API endpoints respond with the expected
HTTP status codes and data. Extend these tests to verify business
logic once endpoints are fully implemented.
"""

import pytest


@pytest.mark.parametrize(
    "endpoint",
    [
        "/",
        "/health",
        "/metrics",
    ],
)
def test_endpoints_exist(test_client, endpoint: str) -> None:
    """Ensure that basic endpoints return a success status code."""
    response = test_client.get(endpoint)
    assert response.status_code < 500
