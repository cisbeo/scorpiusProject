"""Contract test for POST /analysis/match endpoint."""

import pytest
from httpx import AsyncClient
import uuid

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_match_analysis_success(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test successful capability matching analysis."""
    from src.models.procurement_document import ProcurementDocument
    from src.models.extracted_requirements import ExtractedRequirements
    from src.models.company_profile import CompanyProfile

    # Create test document with requirements
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="rfp.pdf",
        stored_filename="stored.pdf",
        file_size=1024000,
        file_hash="hash123",
        upload_user_id="test-user-id",
        title="Développement d'une plateforme web",
        status="processed",
    )
    async_db.add(doc)

    # Add requirements
    req = ExtractedRequirements(
        document_id=document_id,
        technical_requirements=[
            "Python avec FastAPI",
            "PostgreSQL",
            "React ou Vue.js",
            "Docker et Kubernetes",
        ],
        functional_requirements=[
            "API REST",
            "Authentification OAuth2",
            "Dashboard temps réel",
        ],
        administrative_requirements=["ISO 27001 requis"],
        evaluation_criteria={"technical": 50, "price": 30, "experience": 20},
        extraction_confidence=0.90,
    )
    async_db.add(req)

    # Create company profile
    profile = CompanyProfile(
        user_id="test-user-id",
        company_name="Tech Solutions",
        siret="12345678901234",
        capabilities=[
            {"name": "Backend Python", "keywords": ["Python", "FastAPI", "Django"]},
            {"name": "Frontend", "keywords": ["React", "Vue.js", "TypeScript"]},
            {"name": "DevOps", "keywords": ["Docker", "Kubernetes", "CI/CD"]},
            {"name": "Database", "keywords": ["PostgreSQL", "MongoDB", "Redis"]},
        ],
        certifications=[
            {"name": "ISO 27001", "valid_until": "2025-12-31"},
        ],
        team_size=50,
    )
    async_db.add(profile)
    await async_db.commit()

    response = await client.post(
        "/api/v1/analysis/match",
        json={
            "document_id": document_id,
            "analysis_options": {
                "deep_analysis": True,
                "include_suggestions": True,
            }
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "data" in data
    assert "meta" in data

    match_data = data["data"]
    assert match_data["document_id"] == document_id
    assert "overall_match_score" in match_data
    assert match_data["overall_match_score"] >= 0.7  # Good match expected
    assert "capability_matches" in match_data
    assert "missing_capabilities" in match_data
    assert "recommendations" in match_data


@pytest.mark.asyncio
async def test_match_analysis_partial_match(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test capability matching with partial matches."""
    from src.models.procurement_document import ProcurementDocument
    from src.models.extracted_requirements import ExtractedRequirements
    from src.models.company_profile import CompanyProfile

    # Create document with specific requirements
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="specific_rfp.pdf",
        stored_filename="stored.pdf",
        file_size=1024000,
        file_hash="hash456",
        upload_user_id="test-user-id",
        status="processed",
    )
    async_db.add(doc)

    # Add requirements that partially match
    req = ExtractedRequirements(
        document_id=document_id,
        technical_requirements=[
            "Java Spring Boot",  # Company doesn't have
            "Angular",  # Company doesn't have
            "PostgreSQL",  # Company has
            "AWS",  # Company might have partial
        ],
        functional_requirements=["Microservices architecture"],
        extraction_confidence=0.85,
    )
    async_db.add(req)

    # Company with partial capabilities
    profile = CompanyProfile(
        user_id="test-user-id",
        company_name="Partial Tech",
        siret="98765432109876",
        capabilities=[
            {"name": "Backend", "keywords": ["Python", "Node.js"]},  # No Java
            {"name": "Frontend", "keywords": ["React", "Vue.js"]},  # No Angular
            {"name": "Database", "keywords": ["PostgreSQL", "MySQL"]},  # Has PostgreSQL
            {"name": "Cloud", "keywords": ["Azure", "GCP"]},  # No explicit AWS
        ],
        team_size=30,
    )
    async_db.add(profile)
    await async_db.commit()

    response = await client.post(
        "/api/v1/analysis/match",
        json={"document_id": document_id},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    match_data = data["data"]
    assert match_data["overall_match_score"] < 0.6  # Partial match
    assert len(match_data["missing_capabilities"]) > 0
    assert "Java" in str(match_data["missing_capabilities"])


@pytest.mark.asyncio
async def test_match_analysis_no_profile(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test matching when company profile doesn't exist."""
    from src.models.procurement_document import ProcurementDocument

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
    await async_db.commit()

    response = await client.post(
        "/api/v1/analysis/match",
        json={"document_id": document_id},
        headers=auth_headers,
    )

    assert response.status_code == 404
    data = response.json()
    assert "errors" in data
    assert "company profile" in data["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_match_analysis_document_not_processed(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test matching with unprocessed document."""
    from src.models.procurement_document import ProcurementDocument

    # Create unprocessed document
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="unprocessed.pdf",
        stored_filename="stored.pdf",
        file_size=1024,
        file_hash="hash",
        upload_user_id="test-user-id",
        status="uploaded",  # Not processed
    )
    async_db.add(doc)
    await async_db.commit()

    response = await client.post(
        "/api/v1/analysis/match",
        json={"document_id": document_id},
        headers=auth_headers,
    )

    assert response.status_code == 400
    data = response.json()
    assert "errors" in data
    assert "not processed" in data["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_match_analysis_save_results(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test saving capability match results."""
    from src.models.procurement_document import ProcurementDocument
    from src.models.extracted_requirements import ExtractedRequirements
    from src.models.company_profile import CompanyProfile

    # Setup test data
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="save_test.pdf",
        stored_filename="stored.pdf",
        file_size=1024,
        file_hash="hash",
        upload_user_id="test-user-id",
        status="processed",
    )
    async_db.add(doc)

    req = ExtractedRequirements(
        document_id=document_id,
        technical_requirements=["Python", "FastAPI"],
        extraction_confidence=0.90,
    )
    async_db.add(req)

    profile = CompanyProfile(
        user_id="test-user-id",
        company_name="Test Co",
        siret="11111111111111",
        capabilities=[{"name": "Python Dev", "keywords": ["Python", "FastAPI"]}],
        team_size=20,
    )
    async_db.add(profile)
    await async_db.commit()

    response = await client.post(
        "/api/v1/analysis/match",
        json={
            "document_id": document_id,
            "save_results": True,  # Save match results
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    match_data = data["data"]
    assert "match_id" in match_data  # Should return saved match ID

    # Verify match was saved in database
    from src.models.capability_match import CapabilityMatch
    from sqlalchemy import select

    result = await async_db.execute(
        select(CapabilityMatch).where(
            CapabilityMatch.document_id == document_id
        )
    )
    saved_match = result.scalar_one_or_none()
    assert saved_match is not None
    assert saved_match.overall_score > 0


@pytest.mark.asyncio
async def test_match_analysis_no_auth(
    client: AsyncClient,
):
    """Test capability matching without authentication."""
    response = await client.post(
        "/api/v1/analysis/match",
        json={"document_id": str(uuid.uuid4())},
    )

    assert response.status_code == 401
    data = response.json()
    assert "errors" in data