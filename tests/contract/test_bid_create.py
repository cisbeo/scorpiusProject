"""Contract test for POST /bids endpoint."""

import pytest
from httpx import AsyncClient
import uuid

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_create_bid_success(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test successful bid response creation."""
    from src.models.procurement_document import ProcurementDocument

    # Create test document
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="rfp.pdf",
        stored_filename="stored.pdf",
        file_size=1024000,
        file_hash="hash123",
        upload_user_id="test-user-id",
        title="Développement Application Web",
        reference_number="RFP-2024-001",
        status="processed",
    )
    async_db.add(doc)
    await async_db.commit()

    bid_data = {
        "document_id": document_id,
        "executive_summary": "Notre société propose une solution complète pour le développement de votre application web...",
        "technical_response": {
            "architecture": "Microservices avec FastAPI et React",
            "technologies": ["Python", "FastAPI", "PostgreSQL", "React", "Docker"],
            "methodology": "Agile Scrum avec sprints de 2 semaines",
        },
        "commercial_proposal": {
            "total_price": 150000.00,
            "payment_terms": "30% à la signature, 40% à mi-parcours, 30% à la livraison",
            "delivery_timeline": "4 mois",
        },
        "team_composition": [
            {"role": "Chef de projet", "experience": "10 ans", "allocation": "50%"},
            {"role": "Développeur senior", "experience": "8 ans", "allocation": "100%"},
            {"role": "Développeur", "experience": "5 ans", "allocation": "100%"},
        ],
    }

    response = await client.post(
        "/api/v1/bids",
        json=bid_data,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()

    # Verify response structure
    assert "data" in data
    assert "meta" in data

    bid_response_data = data["data"]
    assert "id" in bid_response_data
    assert bid_response_data["document_id"] == document_id
    assert bid_response_data["executive_summary"] == bid_data["executive_summary"]
    assert bid_response_data["status"] == "draft"
    assert "version" in bid_response_data
    assert bid_response_data["version"] == 1
    assert "created_at" in bid_response_data


@pytest.mark.asyncio
async def test_create_bid_auto_generation(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test bid creation with auto-generation from requirements."""
    from src.models.procurement_document import ProcurementDocument
    from src.models.extracted_requirements import ExtractedRequirements
    from src.models.company_profile import CompanyProfile

    # Setup test data
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="auto_rfp.pdf",
        stored_filename="stored.pdf",
        file_size=1024000,
        file_hash="hash456",
        upload_user_id="test-user-id",
        title="Projet de transformation digitale",
        status="processed",
    )
    async_db.add(doc)

    # Add requirements
    req = ExtractedRequirements(
        document_id=document_id,
        technical_requirements=["Python", "FastAPI", "PostgreSQL"],
        functional_requirements=["API REST", "Dashboard", "Reporting"],
        evaluation_criteria={"technical": 40, "price": 35, "experience": 25},
        extraction_confidence=0.90,
    )
    async_db.add(req)

    # Add company profile
    profile = CompanyProfile(
        user_id="test-user-id",
        company_name="Digital Solutions",
        siret="12345678901234",
        capabilities=[
            {"name": "Backend", "keywords": ["Python", "FastAPI"]},
            {"name": "Database", "keywords": ["PostgreSQL", "MongoDB"]},
        ],
        team_size=40,
    )
    async_db.add(profile)
    await async_db.commit()

    response = await client.post(
        "/api/v1/bids",
        json={
            "document_id": document_id,
            "auto_generate": True,  # Request auto-generation
            "generation_options": {
                "tone": "professional",
                "emphasis": "technical_expertise",
            }
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()

    bid_data = data["data"]
    assert bid_data["document_id"] == document_id
    assert "executive_summary" in bid_data
    assert "technical_response" in bid_data
    assert bid_data["auto_generated"] is True


@pytest.mark.asyncio
async def test_create_bid_duplicate(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test creating duplicate bid for same document."""
    from src.models.procurement_document import ProcurementDocument
    from src.models.bid_response import BidResponse

    # Create document
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="test.pdf",
        stored_filename="stored.pdf",
        file_size=1024,
        file_hash="hash",
        upload_user_id="test-user-id",
        status="processed",
    )
    async_db.add(doc)

    # Create existing bid
    existing_bid = BidResponse(
        document_id=document_id,
        user_id="test-user-id",
        executive_summary="Existing bid",
        status="draft",
        version=1,
    )
    async_db.add(existing_bid)
    await async_db.commit()

    # Try to create another bid for same document
    response = await client.post(
        "/api/v1/bids",
        json={
            "document_id": document_id,
            "executive_summary": "New bid attempt",
        },
        headers=auth_headers,
    )

    assert response.status_code == 409  # Conflict
    data = response.json()
    assert "errors" in data
    assert "already exists" in data["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_create_bid_document_not_found(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test creating bid for non-existent document."""
    non_existent_id = str(uuid.uuid4())

    response = await client.post(
        "/api/v1/bids",
        json={
            "document_id": non_existent_id,
            "executive_summary": "Test summary",
        },
        headers=auth_headers,
    )

    assert response.status_code == 404
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_create_bid_with_attachments(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test creating bid with attachments."""
    from src.models.procurement_document import ProcurementDocument

    # Create document
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="rfp.pdf",
        stored_filename="stored.pdf",
        file_size=1024,
        file_hash="hash",
        upload_user_id="test-user-id",
        status="processed",
    )
    async_db.add(doc)
    await async_db.commit()

    bid_data = {
        "document_id": document_id,
        "executive_summary": "Proposition complète",
        "attachments": [
            {
                "name": "Annexe technique",
                "type": "technical_annex",
                "url": "https://storage.example.com/annex1.pdf",
            },
            {
                "name": "Références clients",
                "type": "references",
                "url": "https://storage.example.com/refs.pdf",
            },
        ],
    }

    response = await client.post(
        "/api/v1/bids",
        json=bid_data,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()

    bid_response_data = data["data"]
    assert len(bid_response_data["attachments"]) == 2
    assert bid_response_data["attachments"][0]["name"] == "Annexe technique"


@pytest.mark.asyncio
async def test_create_bid_no_auth(
    client: AsyncClient,
):
    """Test creating bid without authentication."""
    response = await client.post(
        "/api/v1/bids",
        json={
            "document_id": str(uuid.uuid4()),
            "executive_summary": "Test",
        },
    )

    assert response.status_code == 401
    data = response.json()
    assert "errors" in data