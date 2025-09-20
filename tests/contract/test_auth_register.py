"""Contract test for POST /auth/register endpoint."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient, sample_user_data):
    """Test successful user registration."""
    response = await client.post(
        "/api/v1/auth/register",
        json=sample_user_data,
    )

    assert response.status_code == 201
    data = response.json()

    # Verify response structure matches OpenAPI spec
    assert "data" in data
    assert "meta" in data

    user_data = data["data"]
    assert "id" in user_data
    assert user_data["email"] == sample_user_data["email"]
    assert user_data["full_name"] == sample_user_data["full_name"]
    assert user_data["role"] == sample_user_data["role"]
    assert "created_at" in user_data
    assert "password" not in user_data  # Password should never be returned


@pytest.mark.asyncio
async def test_register_user_duplicate_email(client: AsyncClient, sample_user_data):
    """Test registration with duplicate email."""
    # First registration
    await client.post("/api/v1/auth/register", json=sample_user_data)

    # Try to register with same email
    response = await client.post(
        "/api/v1/auth/register",
        json=sample_user_data,
    )

    assert response.status_code == 409
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_register_user_invalid_email(client: AsyncClient, sample_user_data):
    """Test registration with invalid email format."""
    sample_user_data["email"] = "invalid-email"

    response = await client.post(
        "/api/v1/auth/register",
        json=sample_user_data,
    )

    assert response.status_code == 400
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_register_user_weak_password(client: AsyncClient, sample_user_data):
    """Test registration with weak password."""
    sample_user_data["password"] = "weak"

    response = await client.post(
        "/api/v1/auth/register",
        json=sample_user_data,
    )

    assert response.status_code == 400
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_register_user_missing_fields(client: AsyncClient):
    """Test registration with missing required fields."""
    incomplete_data = {
        "email": "test@example.com",
        # Missing password and full_name
    }

    response = await client.post(
        "/api/v1/auth/register",
        json=incomplete_data,
    )

    assert response.status_code == 400
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_register_user_invalid_role(client: AsyncClient, sample_user_data):
    """Test registration with invalid role."""
    sample_user_data["role"] = "invalid_role"

    response = await client.post(
        "/api/v1/auth/register",
        json=sample_user_data,
    )

    assert response.status_code == 400
    data = response.json()
    assert "errors" in data