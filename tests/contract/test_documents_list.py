"""Contract test for GET /documents endpoint."""

import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_list_documents_success(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test successful document listing with pagination."""
    # Create test documents in database
    from src.models.procurement_document import ProcurementDocument

    for i in range(5):
        doc = ProcurementDocument(
            original_filename=f"document_{i}.pdf",
            stored_filename=f"stored_{i}.pdf",
            file_size=1000 + i * 100,
            file_hash=f"hash_{i}",
            upload_user_id="test-user-id",
            status="processed" if i < 3 else "uploaded",
        )
        async_db.add(doc)
    await async_db.commit()

    response = await client.get(
        "/api/v1/documents?page=1&page_size=3",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "data" in data
    assert "meta" in data
    assert "pagination" in data["meta"]

    documents = data["data"]
    assert len(documents) <= 3  # Respects page_size

    pagination = data["meta"]["pagination"]
    assert pagination["total"] == 5
    assert pagination["page"] == 1
    assert pagination["page_size"] == 3
    assert pagination["total_pages"] == 2


@pytest.mark.asyncio
async def test_list_documents_filter_by_status(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test document listing with status filter."""
    # Create test documents with different statuses
    from src.models.procurement_document import ProcurementDocument

    statuses = ["uploaded", "processing", "processed", "failed"]
    for i, status in enumerate(statuses):
        doc = ProcurementDocument(
            original_filename=f"document_{i}.pdf",
            stored_filename=f"stored_{i}.pdf",
            file_size=1000,
            file_hash=f"hash_{i}",
            upload_user_id="test-user-id",
            status=status,
        )
        async_db.add(doc)
    await async_db.commit()

    response = await client.get(
        "/api/v1/documents?status=processed",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    documents = data["data"]
    assert all(doc["status"] == "processed" for doc in documents)


@pytest.mark.asyncio
async def test_list_documents_search(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test document search by title or reference."""
    from src.models.procurement_document import ProcurementDocument

    documents_data = [
        ("MARCHE-2024-001.pdf", "Marché de services informatiques"),
        ("APPEL-2024-002.pdf", "Consultation pour développement web"),
        ("ACCORD-2024-003.pdf", "Accord-cadre maintenance"),
    ]

    for filename, title in documents_data:
        doc = ProcurementDocument(
            original_filename=filename,
            stored_filename=f"stored_{filename}",
            file_size=1000,
            file_hash=f"hash_{filename}",
            upload_user_id="test-user-id",
            title=title,
            status="processed",
        )
        async_db.add(doc)
    await async_db.commit()

    response = await client.get(
        "/api/v1/documents?search=développement",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    documents = data["data"]
    assert len(documents) >= 1
    assert any("développement" in doc.get("title", "").lower() for doc in documents)


@pytest.mark.asyncio
async def test_list_documents_date_range(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test document listing with date range filter."""
    from src.models.procurement_document import ProcurementDocument

    # Create documents with different submission deadlines
    base_date = datetime.utcnow()
    for i in range(5):
        doc = ProcurementDocument(
            original_filename=f"document_{i}.pdf",
            stored_filename=f"stored_{i}.pdf",
            file_size=1000,
            file_hash=f"hash_{i}",
            upload_user_id="test-user-id",
            submission_deadline=base_date + timedelta(days=i*7),
            status="processed",
        )
        async_db.add(doc)
    await async_db.commit()

    # Filter for documents with deadline in next 14 days
    date_from = base_date.isoformat()
    date_to = (base_date + timedelta(days=14)).isoformat()

    response = await client.get(
        f"/api/v1/documents?date_from={date_from}&date_to={date_to}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    documents = data["data"]
    assert len(documents) >= 2  # Should include at least first 2 documents


@pytest.mark.asyncio
async def test_list_documents_no_auth(client: AsyncClient):
    """Test document listing without authentication."""
    response = await client.get("/api/v1/documents")

    assert response.status_code == 401
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_list_documents_sorting(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test document listing with different sort options."""
    from src.models.procurement_document import ProcurementDocument

    # Create test documents with different dates
    base_date = datetime.utcnow()
    for i in range(3):
        doc = ProcurementDocument(
            original_filename=f"document_{i}.pdf",
            stored_filename=f"stored_{i}.pdf",
            file_size=1000 * (3 - i),  # Decreasing size
            file_hash=f"hash_{i}",
            upload_user_id="test-user-id",
            status="processed",
            created_at=base_date - timedelta(days=i),
        )
        async_db.add(doc)
    await async_db.commit()

    # Test sort by created_at descending (default)
    response = await client.get(
        "/api/v1/documents?sort_by=created_at&sort_order=desc",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    documents = data["data"]
    # Most recent document should be first
    assert documents[0]["original_filename"] == "document_0.pdf"


@pytest.mark.asyncio
async def test_list_documents_empty_result(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test document listing with empty result."""
    response = await client.get(
        "/api/v1/documents?status=nonexistent_status",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["data"] == []
    assert data["meta"]["pagination"]["total"] == 0