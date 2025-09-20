"""Contract test for POST /auth/login endpoint."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, sample_user_data):
    """Test successful user login."""
    # First register a user
    await client.post("/api/v1/auth/register", json=sample_user_data)

    # Now login
    login_data = {
        "email": sample_user_data["email"],
        "password": sample_user_data["password"],
    }

    response = await client.post(
        "/api/v1/auth/login",
        json=login_data,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure matches OpenAPI spec
    assert "data" in data
    assert "meta" in data

    token_data = data["data"]
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert "token_type" in token_data
    assert token_data["token_type"] == "Bearer"
    assert "expires_in" in token_data


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient, sample_user_data):
    """Test login with invalid credentials."""
    # Register a user
    await client.post("/api/v1/auth/register", json=sample_user_data)

    # Try to login with wrong password
    login_data = {
        "email": sample_user_data["email"],
        "password": "WrongPassword123!",
    }

    response = await client.post(
        "/api/v1/auth/login",
        json=login_data,
    )

    assert response.status_code == 401
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Test login with non-existent user."""
    login_data = {
        "email": "nonexistent@example.com",
        "password": "SomePassword123!",
    }

    response = await client.post(
        "/api/v1/auth/login",
        json=login_data,
    )

    assert response.status_code == 401
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_login_missing_email(client: AsyncClient):
    """Test login with missing email."""
    login_data = {
        "password": "SomePassword123!",
    }

    response = await client.post(
        "/api/v1/auth/login",
        json=login_data,
    )

    assert response.status_code == 400
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_login_missing_password(client: AsyncClient):
    """Test login with missing password."""
    login_data = {
        "email": "test@example.com",
    }

    response = await client.post(
        "/api/v1/auth/login",
        json=login_data,
    )

    assert response.status_code == 400
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_login_invalid_email_format(client: AsyncClient):
    """Test login with invalid email format."""
    login_data = {
        "email": "not-an-email",
        "password": "SomePassword123!",
    }

    response = await client.post(
        "/api/v1/auth/login",
        json=login_data,
    )

    assert response.status_code == 400
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_login_deactivated_user(client: AsyncClient, sample_user_data, async_db):
    """Test login with deactivated user account."""
    # Register and deactivate a user
    await client.post("/api/v1/auth/register", json=sample_user_data)

    # Deactivate user in database
    from src.models.user import User
    from sqlalchemy import select

    result = await async_db.execute(
        select(User).where(User.email == sample_user_data["email"])
    )
    user = result.scalar_one()
    user.is_active = False
    await async_db.commit()

    # Try to login
    login_data = {
        "email": sample_user_data["email"],
        "password": sample_user_data["password"],
    }

    response = await client.post(
        "/api/v1/auth/login",
        json=login_data,
    )

    assert response.status_code == 401
    data = response.json()
    assert "errors" in data