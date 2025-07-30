"""
Integration tests for file upload endpoints.

These tests ensure that file uploads are handled correctly by the
application. At the moment, the tests only verify that the upload
endpoint responds with the expected status code when called with a
sample file.
"""

import io
from typing import Dict

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_upload_sample_csv(test_client: TestClient) -> None:
    """Upload a sample CSV file and verify the response."""
    # Create an in‑memory file to upload
    sample_content = b"id,name\n1,Test\n2,Demo"
    files: Dict[str, tuple[str, bytes, str]] = {
        "files": ("sample.csv", sample_content, "text/csv"),
    }
    response = test_client.post("/upload", files=files)
    assert response.status_code in (200, 202, 201)
