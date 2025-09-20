"""Contract test for POST /auth/refresh endpoint."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_refresh_token_success(client: AsyncClient, sample_user_data):
    """Test successful token refresh."""
    # Register and login to get tokens
    await client.post("/api/v1/auth/register", json=sample_user_data)

    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": sample_user_data["email"],
            "password": sample_user_data["password"],
        },
    )

    tokens = login_response.json()["data"]
    refresh_token = tokens["refresh_token"]

    # Refresh the token
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "data" in data
    assert "meta" in data

    new_tokens = data["data"]
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens
    assert "token_type" in new_tokens
    assert new_tokens["token_type"] == "Bearer"
    assert "expires_in" in new_tokens

    # New access token should be different
    assert new_tokens["access_token"] != tokens["access_token"]


@pytest.mark.asyncio
async def test_refresh_token_invalid(client: AsyncClient):
    """Test refresh with invalid token."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid.refresh.token"},
    )

    assert response.status_code == 401
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_refresh_token_expired(client: AsyncClient, settings):
    """Test refresh with expired token."""
    from jose import jwt
    from datetime import datetime, timedelta

    # Create an expired refresh token
    expired_token_data = {
        "sub": "test-user-id",
        "type": "refresh",
        "exp": datetime.utcnow() - timedelta(days=1),  # Expired yesterday
    }

    expired_token = jwt.encode(
        expired_token_data,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": expired_token},
    )

    assert response.status_code == 401
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_refresh_token_missing(client: AsyncClient):
    """Test refresh with missing token."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={},
    )

    assert response.status_code == 400
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_refresh_token_wrong_type(client: AsyncClient, settings):
    """Test refresh with access token instead of refresh token."""
    from jose import jwt
    from datetime import datetime, timedelta

    # Create an access token (wrong type)
    access_token_data = {
        "sub": "test-user-id",
        "type": "access",  # Wrong type
        "exp": datetime.utcnow() + timedelta(minutes=30),
    }

    access_token = jwt.encode(
        access_token_data,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},
    )

    assert response.status_code == 401
    data = response.json()
    assert "errors" in data


@pytest.mark.asyncio
async def test_refresh_token_malformed(client: AsyncClient):
    """Test refresh with malformed token."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "not.a.valid.jwt"},
    )

    assert response.status_code == 401
    data = response.json()
    assert "errors" in data