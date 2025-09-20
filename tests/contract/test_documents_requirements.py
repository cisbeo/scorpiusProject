"""Contract test for GET /documents/{id}/requirements endpoint."""

import pytest
from httpx import AsyncClient
import uuid

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_get_document_requirements_success(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test successful retrieval of document requirements."""
    from src.models.procurement_document import ProcurementDocument
    from src.models.extracted_requirements import ExtractedRequirements

    # Create test document with extracted requirements
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

    # Create detailed requirements
    req = ExtractedRequirements(
        document_id=document_id,
        technical_requirements=[
            "Expertise Python avec 5 ans d'expérience",
            "Connaissance approfondie de FastAPI",
            "Maîtrise de PostgreSQL et Redis",
            "Expérience en architecture microservices",
        ],
        functional_requirements=[
            "Système d'authentification multi-facteur",
            "API REST performante",
            "Gestion des droits et permissions",
            "Tableaux de bord en temps réel",
        ],
        administrative_requirements=[
            "Attestation d'assurance RC professionnelle",
            "Extrait Kbis de moins de 3 mois",
            "Certificat de régularité fiscale",
        ],
        financial_requirements=[
            "Chiffre d'affaires minimum 1M EUR",
            "Garantie bancaire de 10% du marché",
        ],
        submission_requirements=[
            "Dossier en format PDF",
            "Signature électronique requise",
            "Dépôt avant le 31/12/2024 à 12h00",
        ],
        evaluation_criteria={
            "technical": 40,
            "price": 30,
            "experience": 20,
            "sustainability": 10,
        },
        extraction_confidence=0.92,
        extracted_at="2024-01-15T10:30:00Z",
    )
    async_db.add(req)
    await async_db.commit()

    response = await client.get(
        f"/api/v1/documents/{document_id}/requirements",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "data" in data
    assert "meta" in data

    requirements_data = data["data"]
    assert requirements_data["document_id"] == document_id
    assert len(requirements_data["technical_requirements"]) == 4
    assert len(requirements_data["functional_requirements"]) == 4
    assert len(requirements_data["administrative_requirements"]) == 3
    assert requirements_data["extraction_confidence"] == 0.92
    assert requirements_data["evaluation_criteria"]["technical"] == 40


@pytest.mark.asyncio
async def test_get_document_requirements_not_processed(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test getting requirements for unprocessed document."""
    from src.models.procurement_document import ProcurementDocument

    # Create document that hasn't been processed yet
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="unprocessed.pdf",
        stored_filename="stored.pdf",
        file_size=1024,
        file_hash="hash",
        upload_user_id="user-id",
        status="uploaded",  # Not processed yet
    )
    async_db.add(doc)
    await async_db.commit()

    response = await client.get(
        f"/api/v1/documents/{document_id}/requirements",
        headers=auth_headers,
    )

    assert response.status_code == 404
    data = response.json()
    assert "errors" in data
    assert "not processed" in data["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_get_document_requirements_processing(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test getting requirements for document being processed."""
    from src.models.procurement_document import ProcurementDocument

    # Create document currently being processed
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="processing.pdf",
        stored_filename="stored.pdf",
        file_size=1024,
        file_hash="hash",
        upload_user_id="user-id",
        status="processing",
    )
    async_db.add(doc)
    await async_db.commit()

    response = await client.get(
        f"/api/v1/documents/{document_id}/requirements",
        headers=auth_headers,
    )

    assert response.status_code == 202  # Accepted - still processing
    data = response.json()
    assert "data" in data
    assert data["data"]["status"] == "processing"
    assert "message" in data["data"]


@pytest.mark.asyncio
async def test_get_document_requirements_failed_extraction(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test getting requirements when extraction failed."""
    from src.models.procurement_document import ProcurementDocument

    # Create document with failed processing
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="failed.pdf",
        stored_filename="stored.pdf",
        file_size=1024,
        file_hash="hash",
        upload_user_id="user-id",
        status="failed",
        processing_error="Could not extract text from PDF",
    )
    async_db.add(doc)
    await async_db.commit()

    response = await client.get(
        f"/api/v1/documents/{document_id}/requirements",
        headers=auth_headers,
    )

    assert response.status_code == 500
    data = response.json()
    assert "errors" in data
    assert "extraction failed" in data["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_get_document_requirements_partial_extraction(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test requirements with partial/low confidence extraction."""
    from src.models.procurement_document import ProcurementDocument
    from src.models.extracted_requirements import ExtractedRequirements

    # Create document with partial extraction
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="partial.pdf",
        stored_filename="stored.pdf",
        file_size=1024,
        file_hash="hash",
        upload_user_id="user-id",
        status="processed",
    )
    async_db.add(doc)

    # Create requirements with low confidence
    req = ExtractedRequirements(
        document_id=document_id,
        technical_requirements=["Some technical requirement"],
        functional_requirements=[],  # Empty - couldn't extract
        administrative_requirements=["Some admin requirement"],
        financial_requirements=[],  # Empty - couldn't extract
        submission_requirements=["Submit before deadline"],
        evaluation_criteria={},  # Empty - couldn't extract
        extraction_confidence=0.45,  # Low confidence
    )
    async_db.add(req)
    await async_db.commit()

    response = await client.get(
        f"/api/v1/documents/{document_id}/requirements",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    requirements_data = data["data"]
    assert requirements_data["extraction_confidence"] == 0.45
    assert "warning" in data["meta"]
    assert "low confidence" in data["meta"]["warning"].lower()


@pytest.mark.asyncio
async def test_get_document_requirements_not_found(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test getting requirements for non-existent document."""
    non_existent_id = str(uuid.uuid4())

    response = await client.get(
        f"/api/v1/documents/{non_existent_id}/requirements",
        headers=auth_headers,
    )

    assert response.status_code == 404
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_get_document_requirements_no_auth(
    client: AsyncClient,
    async_db,
):
    """Test getting requirements without authentication."""
    from src.models.procurement_document import ProcurementDocument

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

    response = await client.get(f"/api/v1/documents/{document_id}/requirements")

    assert response.status_code == 401
    data = response.json()
    assert "errors" in data