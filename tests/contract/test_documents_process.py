"""Contract test for POST /documents/{id}/process endpoint."""

import pytest
from httpx import AsyncClient
import uuid

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_process_document_success(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test successful document processing trigger."""
    from src.models.procurement_document import ProcurementDocument

    # Create test document in uploaded state
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="test_document.pdf",
        stored_filename="stored_test.pdf",
        file_size=1024000,
        file_hash="hash123",
        upload_user_id="test-user-id",
        status="uploaded",  # Ready for processing
    )
    async_db.add(doc)
    await async_db.commit()

    response = await client.post(
        f"/api/v1/documents/{document_id}/process",
        headers=auth_headers,
        json={
            "processing_options": {
                "extract_requirements": True,
                "extract_dates": True,
                "extract_criteria": True,
            }
        },
    )

    assert response.status_code == 202  # Accepted for processing
    data = response.json()

    # Verify response structure
    assert "data" in data
    assert "meta" in data

    process_data = data["data"]
    assert process_data["document_id"] == document_id
    assert process_data["status"] == "processing"
    assert "processing_id" in process_data
    assert "estimated_completion" in process_data


@pytest.mark.asyncio
async def test_process_document_already_processing(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test processing document that's already being processed."""
    from src.models.procurement_document import ProcurementDocument

    # Create document already in processing state
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="test.pdf",
        stored_filename="stored.pdf",
        file_size=1024,
        file_hash="hash",
        upload_user_id="user-id",
        status="processing",  # Already processing
    )
    async_db.add(doc)
    await async_db.commit()

    response = await client.post(
        f"/api/v1/documents/{document_id}/process",
        headers=auth_headers,
    )

    assert response.status_code == 409  # Conflict
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_process_document_already_processed(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test reprocessing an already processed document."""
    from src.models.procurement_document import ProcurementDocument

    # Create already processed document
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="test.pdf",
        stored_filename="stored.pdf",
        file_size=1024,
        file_hash="hash",
        upload_user_id="user-id",
        status="processed",
    )
    async_db.add(doc)
    await async_db.commit()

    response = await client.post(
        f"/api/v1/documents/{document_id}/process",
        headers=auth_headers,
        json={"force_reprocess": True},  # Force reprocessing
    )

    assert response.status_code == 202
    data = response.json()
    assert data["data"]["status"] == "processing"


@pytest.mark.asyncio
async def test_process_document_not_found(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test processing non-existent document."""
    non_existent_id = str(uuid.uuid4())

    response = await client.post(
        f"/api/v1/documents/{non_existent_id}/process",
        headers=auth_headers,
    )

    assert response.status_code == 404
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_process_document_failed_state(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test processing a document in failed state."""
    from src.models.procurement_document import ProcurementDocument

    # Create failed document
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="failed.pdf",
        stored_filename="stored.pdf",
        file_size=1024,
        file_hash="hash",
        upload_user_id="user-id",
        status="failed",
        processing_error="Previous processing failed",
    )
    async_db.add(doc)
    await async_db.commit()

    response = await client.post(
        f"/api/v1/documents/{document_id}/process",
        headers=auth_headers,
        json={"retry": True},  # Retry processing
    )

    assert response.status_code == 202
    data = response.json()
    assert data["data"]["status"] == "processing"


@pytest.mark.asyncio
async def test_process_document_no_auth(
    client: AsyncClient,
    async_db,
):
    """Test document processing without authentication."""
    from src.models.procurement_document import ProcurementDocument

    # Create test document
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="test.pdf",
        stored_filename="stored.pdf",
        file_size=1024,
        file_hash="hash",
        upload_user_id="user-id",
        status="uploaded",
    )
    async_db.add(doc)
    await async_db.commit()

    response = await client.post(f"/api/v1/documents/{document_id}/process")

    assert response.status_code == 401
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_process_document_with_priority(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test document processing with priority setting."""
    from src.models.procurement_document import ProcurementDocument
    from datetime import datetime, timedelta

    # Create urgent document (deadline soon)
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="urgent.pdf",
        stored_filename="stored.pdf",
        file_size=1024,
        file_hash="hash",
        upload_user_id="user-id",
        status="uploaded",
        submission_deadline=datetime.utcnow() + timedelta(days=2),  # Urgent
    )
    async_db.add(doc)
    await async_db.commit()

    response = await client.post(
        f"/api/v1/documents/{document_id}/process",
        headers=auth_headers,
        json={
            "priority": "high",
            "processing_options": {
                "extract_requirements": True,
                "quick_mode": True,  # Fast processing for urgent documents
            }
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert data["data"]["priority"] == "high"