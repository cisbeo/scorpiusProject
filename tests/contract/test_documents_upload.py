"""Contract test for POST /documents endpoint."""

import pytest
from httpx import AsyncClient
import io

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_upload_document_success(
    client: AsyncClient,
    auth_headers: dict,
    sample_pdf_file: io.BytesIO,
):
    """Test successful document upload."""
    files = {
        "file": ("test_document.pdf", sample_pdf_file, "application/pdf"),
    }

    response = await client.post(
        "/api/v1/documents",
        files=files,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()

    # Verify response structure
    assert "data" in data
    assert "meta" in data

    document_data = data["data"]
    assert "id" in document_data
    assert document_data["original_filename"] == "test_document.pdf"
    assert "file_size" in document_data
    assert document_data["status"] in ["uploaded", "processing"]
    assert "created_at" in document_data


@pytest.mark.asyncio
async def test_upload_document_no_auth(
    client: AsyncClient,
    sample_pdf_file: io.BytesIO,
):
    """Test document upload without authentication."""
    files = {
        "file": ("test_document.pdf", sample_pdf_file, "application/pdf"),
    }

    response = await client.post(
        "/api/v1/documents",
        files=files,
    )

    assert response.status_code == 401
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_upload_document_file_too_large(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test document upload with file exceeding size limit."""
    # Create a large file (over 50MB limit)
    large_content = b"x" * (52 * 1024 * 1024)  # 52MB
    large_file = io.BytesIO(large_content)

    files = {
        "file": ("large_document.pdf", large_file, "application/pdf"),
    }

    response = await client.post(
        "/api/v1/documents",
        files=files,
        headers=auth_headers,
    )

    assert response.status_code == 413
    data = response.json()
    assert "errors" in data or response.status_code == 413


@pytest.mark.asyncio
async def test_upload_document_invalid_file_type(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test document upload with non-PDF file."""
    # Create a text file instead of PDF
    text_file = io.BytesIO(b"This is a text file, not a PDF")

    files = {
        "file": ("document.txt", text_file, "text/plain"),
    }

    response = await client.post(
        "/api/v1/documents",
        files=files,
        headers=auth_headers,
    )

    assert response.status_code == 400
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_upload_document_no_file(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test document upload without file."""
    response = await client.post(
        "/api/v1/documents",
        headers=auth_headers,
    )

    assert response.status_code == 400
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_upload_document_empty_file(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test document upload with empty file."""
    empty_file = io.BytesIO(b"")

    files = {
        "file": ("empty.pdf", empty_file, "application/pdf"),
    }

    response = await client.post(
        "/api/v1/documents",
        files=files,
        headers=auth_headers,
    )

    assert response.status_code == 400
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_upload_document_invalid_token(
    client: AsyncClient,
    sample_pdf_file: io.BytesIO,
):
    """Test document upload with invalid authentication token."""
    files = {
        "file": ("test_document.pdf", sample_pdf_file, "application/pdf"),
    }

    invalid_headers = {"Authorization": "Bearer invalid.token.here"}

    response = await client.post(
        "/api/v1/documents",
        files=files,
        headers=invalid_headers,
    )

    assert response.status_code == 401
    data = response.json()
    assert "errors" in data