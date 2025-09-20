"""Contract test for GET /company-profile endpoint."""

import pytest
from httpx import AsyncClient
import uuid

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_get_company_profile_success(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test successful retrieval of company profile."""
    from src.models.company_profile import CompanyProfile

    # Create test company profile
    profile = CompanyProfile(
        user_id="test-user-id",
        company_name="Test Company SARL",
        siret="12345678901234",
        description="Leading technology solutions provider",
        capabilities=[
            {"name": "Web Development", "keywords": ["Python", "React", "FastAPI"]},
            {"name": "Cloud Services", "keywords": ["AWS", "Docker", "Kubernetes"]},
        ],
        certifications=[
            {"name": "ISO 9001", "valid_until": "2025-12-31"},
            {"name": "ISO 27001", "valid_until": "2026-06-30"},
        ],
        team_size=50,
        annual_revenue=3000000.00,
    )
    async_db.add(profile)
    await async_db.commit()

    response = await client.get(
        "/api/v1/company-profile",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "data" in data
    assert "meta" in data

    profile_data = data["data"]
    assert profile_data["company_name"] == "Test Company SARL"
    assert profile_data["siret"] == "12345678901234"
    assert profile_data["team_size"] == 50
    assert len(profile_data["capabilities"]) == 2
    assert len(profile_data["certifications"]) == 2


@pytest.mark.asyncio
async def test_get_company_profile_not_found(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test getting company profile when none exists."""
    response = await client.get(
        "/api/v1/company-profile",
        headers=auth_headers,
    )

    assert response.status_code == 404
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_get_company_profile_no_auth(
    client: AsyncClient,
):
    """Test getting company profile without authentication."""
    response = await client.get("/api/v1/company-profile")

    assert response.status_code == 401
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_update_company_profile_success(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test successful company profile update."""
    from src.models.company_profile import CompanyProfile

    # Create initial profile
    profile = CompanyProfile(
        user_id="test-user-id",
        company_name="Old Company Name",
        siret="12345678901234",
        description="Old description",
        team_size=30,
        annual_revenue=1000000.00,
    )
    async_db.add(profile)
    await async_db.commit()

    # Update profile
    update_data = {
        "company_name": "New Company Name SARL",
        "description": "Updated description with new focus",
        "team_size": 75,
        "annual_revenue": 5000000.00,
        "capabilities_json": [
            {"name": "AI/ML", "keywords": ["TensorFlow", "PyTorch", "NLP"]},
        ],
    }

    response = await client.put(
        "/api/v1/company-profile",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    profile_data = data["data"]
    assert profile_data["company_name"] == "New Company Name SARL"
    assert profile_data["team_size"] == 75
    assert profile_data["annual_revenue"] == 5000000.00
    assert len(profile_data["capabilities"]) == 1


@pytest.mark.asyncio
async def test_update_company_profile_not_found(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test updating non-existent company profile."""
    update_data = {
        "company_name": "Updated Name",
        "team_size": 100,
    }

    response = await client.put(
        "/api/v1/company-profile",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 404
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_update_company_profile_partial(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test partial update of company profile."""
    from src.models.company_profile import CompanyProfile

    # Create initial profile
    profile = CompanyProfile(
        user_id="test-user-id",
        company_name="Test Company",
        siret="12345678901234",
        description="Original description",
        team_size=50,
        annual_revenue=2000000.00,
        capabilities=[{"name": "Web Dev", "keywords": ["Python"]}],
    )
    async_db.add(profile)
    await async_db.commit()

    # Partial update - only update team size
    update_data = {
        "team_size": 65,
    }

    response = await client.patch(
        "/api/v1/company-profile",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    profile_data = data["data"]
    assert profile_data["team_size"] == 65
    # Other fields should remain unchanged
    assert profile_data["company_name"] == "Test Company"
    assert profile_data["annual_revenue"] == 2000000.00


@pytest.mark.asyncio
async def test_delete_company_profile_success(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test successful company profile deletion (soft delete)."""
    from src.models.company_profile import CompanyProfile

    # Create profile
    profile = CompanyProfile(
        user_id="test-user-id",
        company_name="To Delete Company",
        siret="99999999999999",
        description="This will be deleted",
        team_size=10,
        annual_revenue=500000.00,
    )
    async_db.add(profile)
    await async_db.commit()

    response = await client.delete(
        "/api/v1/company-profile",
        headers=auth_headers,
    )

    assert response.status_code == 204  # No content

    # Verify profile is soft-deleted (GET should return 404)
    response = await client.get(
        "/api/v1/company-profile",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_company_profile_not_found(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test deleting non-existent company profile."""
    response = await client.delete(
        "/api/v1/company-profile",
        headers=auth_headers,
    )

    assert response.status_code == 404
    data = response.json()
    assert "errors" in data