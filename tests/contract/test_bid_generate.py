"""Contract test for POST /bids/{id}/generate endpoint."""

import pytest
from httpx import AsyncClient
import uuid

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_generate_bid_section_success(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test successful bid section generation."""
    from src.models.bid_response import BidResponse
    from src.models.procurement_document import ProcurementDocument
    from src.models.extracted_requirements import ExtractedRequirements

    # Create document with requirements
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="rfp.pdf",
        stored_filename="stored.pdf",
        file_size=1024000,
        file_hash="hash123",
        upload_user_id="test-user-id",
        title="Système de gestion documentaire",
        status="processed",
    )
    async_db.add(doc)

    req = ExtractedRequirements(
        document_id=document_id,
        technical_requirements=[
            "Architecture cloud-native",
            "API REST sécurisée",
            "Stockage distribué",
        ],
        functional_requirements=[
            "Gestion des versions",
            "Recherche full-text",
            "Workflow d'approbation",
        ],
        extraction_confidence=0.90,
    )
    async_db.add(req)

    # Create draft bid
    bid_id = str(uuid.uuid4())
    bid = BidResponse(
        id=bid_id,
        document_id=document_id,
        user_id="test-user-id",
        executive_summary="",  # Empty - to be generated
        status="draft",
        version=1,
    )
    async_db.add(bid)
    await async_db.commit()

    response = await client.post(
        f"/api/v1/bids/{bid_id}/generate",
        json={
            "section": "executive_summary",
            "generation_options": {
                "tone": "professional",
                "length": "medium",
                "emphasize": ["innovation", "experience"],
            }
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response
    assert "data" in data
    generated = data["data"]
    assert "section" in generated
    assert generated["section"] == "executive_summary"
    assert "content" in generated
    assert len(generated["content"]) > 100  # Should generate substantial content
    assert "generation_metadata" in generated


@pytest.mark.asyncio
async def test_generate_technical_response(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test generating technical response section."""
    from src.models.bid_response import BidResponse
    from src.models.procurement_document import ProcurementDocument
    from src.models.extracted_requirements import ExtractedRequirements
    from src.models.company_profile import CompanyProfile

    # Setup complete test data
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="tech_rfp.pdf",
        stored_filename="stored.pdf",
        file_size=1024000,
        file_hash="hash456",
        upload_user_id="test-user-id",
        status="processed",
    )
    async_db.add(doc)

    req = ExtractedRequirements(
        document_id=document_id,
        technical_requirements=[
            "Python/FastAPI backend",
            "React frontend",
            "PostgreSQL database",
            "Redis cache",
        ],
        extraction_confidence=0.85,
    )
    async_db.add(req)

    # Add company profile for context
    profile = CompanyProfile(
        user_id="test-user-id",
        company_name="Tech Experts",
        siret="12345678901234",
        capabilities=[
            {"name": "Backend", "keywords": ["Python", "FastAPI", "Django"]},
            {"name": "Frontend", "keywords": ["React", "Vue", "TypeScript"]},
            {"name": "Database", "keywords": ["PostgreSQL", "MongoDB", "Redis"]},
        ],
        team_size=30,
    )
    async_db.add(profile)

    # Create bid
    bid_id = str(uuid.uuid4())
    bid = BidResponse(
        id=bid_id,
        document_id=document_id,
        user_id="test-user-id",
        status="draft",
        version=1,
    )
    async_db.add(bid)
    await async_db.commit()

    response = await client.post(
        f"/api/v1/bids/{bid_id}/generate",
        json={
            "section": "technical_response",
            "generation_options": {
                "include_architecture_diagram": True,
                "detail_level": "comprehensive",
            }
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    generated = data["data"]
    assert generated["section"] == "technical_response"
    assert "content" in generated
    # Should reference the requirements
    assert any(tech in str(generated["content"])
              for tech in ["Python", "FastAPI", "React", "PostgreSQL"])


@pytest.mark.asyncio
async def test_generate_multiple_sections(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test generating multiple bid sections at once."""
    from src.models.bid_response import BidResponse
    from src.models.procurement_document import ProcurementDocument

    # Create document and bid
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="multi_rfp.pdf",
        stored_filename="stored.pdf",
        file_size=1024000,
        file_hash="hash789",
        upload_user_id="test-user-id",
        status="processed",
    )
    async_db.add(doc)

    bid_id = str(uuid.uuid4())
    bid = BidResponse(
        id=bid_id,
        document_id=document_id,
        user_id="test-user-id",
        status="draft",
        version=1,
    )
    async_db.add(bid)
    await async_db.commit()

    response = await client.post(
        f"/api/v1/bids/{bid_id}/generate",
        json={
            "sections": [
                "executive_summary",
                "technical_response",
                "commercial_proposal",
            ],
            "generation_options": {
                "tone": "confident",
                "consistency": "high",
            }
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    generated = data["data"]
    assert "sections" in generated
    assert len(generated["sections"]) == 3
    assert all(s in ["executive_summary", "technical_response", "commercial_proposal"]
              for s in generated["sections"].keys())


@pytest.mark.asyncio
async def test_regenerate_section_with_feedback(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test regenerating a section with user feedback."""
    from src.models.bid_response import BidResponse

    # Create bid with existing content
    bid_id = str(uuid.uuid4())
    bid = BidResponse(
        id=bid_id,
        document_id=str(uuid.uuid4()),
        user_id="test-user-id",
        executive_summary="Initial generated summary that needs improvement",
        status="draft",
        version=1,
    )
    async_db.add(bid)
    await async_db.commit()

    response = await client.post(
        f"/api/v1/bids/{bid_id}/generate",
        json={
            "section": "executive_summary",
            "regenerate": True,
            "feedback": "Make it more concise and emphasize our competitive advantages",
            "generation_options": {
                "tone": "confident",
                "length": "short",
            }
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    generated = data["data"]
    assert generated["section"] == "executive_summary"
    assert generated["content"] != "Initial generated summary that needs improvement"
    assert "regenerated" in generated["generation_metadata"]


@pytest.mark.asyncio
async def test_generate_from_template(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test generating bid content from a template."""
    from src.models.bid_response import BidResponse

    # Create bid
    bid_id = str(uuid.uuid4())
    bid = BidResponse(
        id=bid_id,
        document_id=str(uuid.uuid4()),
        user_id="test-user-id",
        status="draft",
        version=1,
    )
    async_db.add(bid)
    await async_db.commit()

    response = await client.post(
        f"/api/v1/bids/{bid_id}/generate",
        json={
            "section": "commercial_proposal",
            "template_id": "standard_commercial_template",
            "template_variables": {
                "discount_percentage": 10,
                "payment_terms": "30 jours",
                "warranty_period": "12 mois",
            }
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    generated = data["data"]
    assert "template_id" in generated["generation_metadata"]
    assert "30 jours" in str(generated["content"])


@pytest.mark.asyncio
async def test_generate_bid_not_found(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test generating content for non-existent bid."""
    non_existent_id = str(uuid.uuid4())

    response = await client.post(
        f"/api/v1/bids/{non_existent_id}/generate",
        json={"section": "executive_summary"},
        headers=auth_headers,
    )

    assert response.status_code == 404
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_generate_submitted_bid_error(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test that submitted bids cannot be regenerated."""
    from src.models.bid_response import BidResponse

    # Create submitted bid
    bid_id = str(uuid.uuid4())
    bid = BidResponse(
        id=bid_id,
        document_id=str(uuid.uuid4()),
        user_id="test-user-id",
        executive_summary="Final content",
        status="submitted",  # Already submitted
        version=1,
    )
    async_db.add(bid)
    await async_db.commit()

    response = await client.post(
        f"/api/v1/bids/{bid_id}/generate",
        json={"section": "executive_summary"},
        headers=auth_headers,
    )

    assert response.status_code == 409
    data = response.json()
    assert "errors" in data
    assert "cannot modify submitted bid" in data["errors"][0]["message"].lower()