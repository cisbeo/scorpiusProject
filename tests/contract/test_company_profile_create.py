"""Contract test for POST /company-profile endpoint."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_create_company_profile_success(
    client: AsyncClient,
    auth_headers: dict,
    sample_company_data,
):
    """Test successful company profile creation."""
    response = await client.post(
        "/api/v1/company-profile",
        json=sample_company_data,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()

    # Verify response structure
    assert "data" in data
    assert "meta" in data

    profile_data = data["data"]
    assert "id" in profile_data
    assert profile_data["company_name"] == sample_company_data["company_name"]
    assert profile_data["siret"] == sample_company_data["siret"]
    assert profile_data["description"] == sample_company_data["description"]
    assert profile_data["team_size"] == sample_company_data["team_size"]
    assert profile_data["annual_revenue"] == sample_company_data["annual_revenue"]
    assert "capabilities" in profile_data
    assert "certifications" in profile_data
    assert "created_at" in profile_data
    assert "updated_at" in profile_data


@pytest.mark.asyncio
async def test_create_company_profile_duplicate(
    client: AsyncClient,
    auth_headers: dict,
    sample_company_data,
    async_db,
):
    """Test creating duplicate company profile for same user."""
    # Create first profile
    response = await client.post(
        "/api/v1/company-profile",
        json=sample_company_data,
        headers=auth_headers,
    )
    assert response.status_code == 201

    # Try to create another profile for same user
    modified_data = sample_company_data.copy()
    modified_data["company_name"] = "Different Company"

    response = await client.post(
        "/api/v1/company-profile",
        json=modified_data,
        headers=auth_headers,
    )

    assert response.status_code == 409  # Conflict
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_create_company_profile_invalid_siret(
    client: AsyncClient,
    auth_headers: dict,
    sample_company_data,
):
    """Test creating company profile with invalid SIRET."""
    sample_company_data["siret"] = "123"  # Too short

    response = await client.post(
        "/api/v1/company-profile",
        json=sample_company_data,
        headers=auth_headers,
    )

    assert response.status_code == 400
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_create_company_profile_missing_fields(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test creating company profile with missing required fields."""
    incomplete_data = {
        "company_name": "Test Company",
        # Missing siret and other required fields
    }

    response = await client.post(
        "/api/v1/company-profile",
        json=incomplete_data,
        headers=auth_headers,
    )

    assert response.status_code == 400
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_create_company_profile_with_capabilities(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test creating company profile with detailed capabilities."""
    company_data = {
        "company_name": "Tech Solutions SARL",
        "siret": "98765432109876",
        "description": "Expertise en solutions digitales",
        "capabilities_json": [
            {
                "name": "Développement Web Full-Stack",
                "keywords": ["React", "Vue.js", "Node.js", "Python", "Django", "FastAPI"],
                "experience_years": 8,
                "team_size": 15,
            },
            {
                "name": "Intelligence Artificielle",
                "keywords": ["Machine Learning", "NLP", "Computer Vision", "TensorFlow"],
                "experience_years": 5,
                "team_size": 8,
            },
            {
                "name": "Cloud & DevOps",
                "keywords": ["AWS", "Azure", "Docker", "Kubernetes", "CI/CD"],
                "experience_years": 6,
                "team_size": 10,
            },
        ],
        "team_size": 50,
        "annual_revenue": 3500000.00,
    }

    response = await client.post(
        "/api/v1/company-profile",
        json=company_data,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()

    profile_data = data["data"]
    assert len(profile_data["capabilities"]) == 3
    assert profile_data["capabilities"][0]["name"] == "Développement Web Full-Stack"
    assert "React" in profile_data["capabilities"][0]["keywords"]


@pytest.mark.asyncio
async def test_create_company_profile_with_certifications(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test creating company profile with certifications."""
    company_data = {
        "company_name": "Certified Tech SARL",
        "siret": "11223344556677",
        "description": "Entreprise certifiée",
        "certifications_json": [
            {
                "name": "ISO 9001:2015",
                "issuer": "AFNOR Certification",
                "valid_until": "2025-12-31",
                "reference": "CERT-9001-2023-001",
            },
            {
                "name": "ISO 27001:2022",
                "issuer": "Bureau Veritas",
                "valid_until": "2026-06-30",
                "reference": "BV-27001-2023",
            },
            {
                "name": "Qualiopi",
                "issuer": "AFNOR",
                "valid_until": "2025-03-15",
                "reference": "QUAL-2023-789",
            },
        ],
        "team_size": 75,
        "annual_revenue": 5000000.00,
    }

    response = await client.post(
        "/api/v1/company-profile",
        json=company_data,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()

    profile_data = data["data"]
    assert len(profile_data["certifications"]) == 3
    assert profile_data["certifications"][0]["name"] == "ISO 9001:2015"
    assert profile_data["certifications"][0]["issuer"] == "AFNOR Certification"


@pytest.mark.asyncio
async def test_create_company_profile_negative_revenue(
    client: AsyncClient,
    auth_headers: dict,
    sample_company_data,
):
    """Test creating company profile with negative revenue."""
    sample_company_data["annual_revenue"] = -1000000

    response = await client.post(
        "/api/v1/company-profile",
        json=sample_company_data,
        headers=auth_headers,
    )

    assert response.status_code == 400
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_create_company_profile_no_auth(
    client: AsyncClient,
    sample_company_data,
):
    """Test creating company profile without authentication."""
    response = await client.post(
        "/api/v1/company-profile",
        json=sample_company_data,
    )

    assert response.status_code == 401
    data = response.json()
    assert "errors" in data