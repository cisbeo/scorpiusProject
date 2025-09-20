"""Contract test for GET /documents/{id} endpoint."""

import pytest
from httpx import AsyncClient
import uuid

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_get_document_success(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test successful document retrieval."""
    from src.models.procurement_document import ProcurementDocument
    from datetime import datetime, timedelta

    # Create test document
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="test_document.pdf",
        stored_filename="stored_test.pdf",
        file_size=2048000,
        file_hash="abc123hash",
        upload_user_id="test-user-id",
        title="Marché public de services",
        reference_number="MP-2024-001",
        buyer_organization="Ministère Test",
        submission_deadline=datetime.utcnow() + timedelta(days=30),
        status="processed",
    )
    async_db.add(doc)
    await async_db.commit()

    response = await client.get(
        f"/api/v1/documents/{document_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "data" in data
    assert "meta" in data

    document_data = data["data"]
    assert document_data["id"] == document_id
    assert document_data["original_filename"] == "test_document.pdf"
    assert document_data["file_size"] == 2048000
    assert document_data["title"] == "Marché public de services"
    assert document_data["reference_number"] == "MP-2024-001"
    assert document_data["buyer_organization"] == "Ministère Test"
    assert document_data["status"] == "processed"


@pytest.mark.asyncio
async def test_get_document_with_requirements(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test document retrieval with extracted requirements."""
    from src.models.procurement_document import ProcurementDocument
    from src.models.extracted_requirements import ExtractedRequirements

    # Create test document with requirements
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="test_document.pdf",
        stored_filename="stored_test.pdf",
        file_size=1024000,
        file_hash="hash123",
        upload_user_id="test-user-id",
        status="processed",
    )
    async_db.add(doc)

    # Add extracted requirements
    req = ExtractedRequirements(
        document_id=document_id,
        technical_requirements=["Python expertise", "FastAPI knowledge"],
        functional_requirements=["User authentication", "API development"],
        administrative_requirements=["Insurance certificate", "Company registration"],
        financial_requirements=["Minimum revenue 1M EUR"],
        submission_requirements=["PDF format", "Digital signature"],
        evaluation_criteria={"technical": 40, "price": 30, "experience": 30},
        extraction_confidence=0.95,
    )
    async_db.add(req)
    await async_db.commit()

    response = await client.get(
        f"/api/v1/documents/{document_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    document_data = data["data"]
    assert "requirements" in document_data
    requirements = document_data["requirements"]
    assert "technical_requirements" in requirements
    assert len(requirements["technical_requirements"]) == 2
    assert requirements["extraction_confidence"] == 0.95


@pytest.mark.asyncio
async def test_get_document_not_found(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test getting non-existent document."""
    non_existent_id = str(uuid.uuid4())

    response = await client.get(
        f"/api/v1/documents/{non_existent_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_get_document_no_auth(
    client: AsyncClient,
    async_db,
):
    """Test document retrieval without authentication."""
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
        status="processed",
    )
    async_db.add(doc)
    await async_db.commit()

    response = await client.get(f"/api/v1/documents/{document_id}")

    assert response.status_code == 401
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_get_document_invalid_uuid(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test getting document with invalid UUID."""
    response = await client.get(
        "/api/v1/documents/not-a-valid-uuid",
        headers=auth_headers,
    )

    assert response.status_code == 400
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_get_document_soft_deleted(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test that soft-deleted documents are not returned."""
    from src.models.procurement_document import ProcurementDocument
    from datetime import datetime

    # Create soft-deleted document
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="deleted.pdf",
        stored_filename="stored.pdf",
        file_size=1024,
        file_hash="hash",
        upload_user_id="user-id",
        status="processed",
        deleted_at=datetime.utcnow(),  # Mark as soft-deleted
    )
    async_db.add(doc)
    await async_db.commit()

    response = await client.get(
        f"/api/v1/documents/{document_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404
    data = response.json()
    assert "errors" in data