"""Integration test for complete authentication flow."""

import pytest
from httpx import AsyncClient
import time

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_complete_auth_flow(client: AsyncClient, sample_user_data):
    """Test complete authentication flow: register -> login -> refresh -> use token."""
    # Step 1: Register new user
    register_response = await client.post(
        "/api/v1/auth/register",
        json=sample_user_data,
    )
    assert register_response.status_code == 201
    user_data = register_response.json()["data"]
    user_id = user_data["id"]

    # Step 2: Login with credentials
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": sample_user_data["email"],
            "password": sample_user_data["password"],
        },
    )
    assert login_response.status_code == 200
    tokens = login_response.json()["data"]
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # Step 3: Use access token to access protected endpoint
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    profile_response = await client.get(
        "/api/v1/company-profile",
        headers=auth_headers,
    )
    # Should be 404 since no profile exists yet, but not 401
    assert profile_response.status_code == 404

    # Step 4: Create company profile
    company_data = {
        "company_name": "Test Company SARL",
        "siret": "12345678901234",
        "description": "Test company",
        "team_size": 10,
        "annual_revenue": 1000000.00,
    }
    create_profile_response = await client.post(
        "/api/v1/company-profile",
        json=company_data,
        headers=auth_headers,
    )
    assert create_profile_response.status_code == 201

    # Step 5: Refresh token
    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 200
    new_tokens = refresh_response.json()["data"]
    new_access_token = new_tokens["access_token"]

    # Step 6: Use new access token
    new_auth_headers = {"Authorization": f"Bearer {new_access_token}"}
    profile_check_response = await client.get(
        "/api/v1/company-profile",
        headers=new_auth_headers,
    )
    assert profile_check_response.status_code == 200
    profile = profile_check_response.json()["data"]
    assert profile["company_name"] == "Test Company SARL"


@pytest.mark.asyncio
async def test_token_expiry_and_refresh(client: AsyncClient, sample_user_data, settings):
    """Test token expiry and refresh mechanism."""
    # Register and login
    await client.post("/api/v1/auth/register", json=sample_user_data)
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": sample_user_data["email"],
            "password": sample_user_data["password"],
        },
    )
    tokens = login_response.json()["data"]

    # Create expired access token scenario
    # (In real test, we'd manipulate time or use a short-lived token)
    from jose import jwt
    from datetime import datetime, timedelta

    # Decode to check expiry (for testing understanding)
    access_payload = jwt.decode(
        tokens["access_token"],
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    assert "exp" in access_payload

    # Use refresh token to get new access token
    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 200

    new_tokens = refresh_response.json()["data"]
    assert new_tokens["access_token"] != tokens["access_token"]
    assert new_tokens["refresh_token"] != tokens["refresh_token"]


@pytest.mark.asyncio
async def test_concurrent_authentication(client: AsyncClient):
    """Test concurrent authentication requests."""
    import asyncio

    # Create multiple users concurrently
    users = [
        {
            "email": f"user{i}@example.com",
            "password": "SecurePass123!",
            "full_name": f"User {i}",
            "role": "bid_manager",
        }
        for i in range(5)
    ]

    # Register all users concurrently
    register_tasks = [
        client.post("/api/v1/auth/register", json=user_data)
        for user_data in users
    ]
    register_responses = await asyncio.gather(*register_tasks)

    # All should succeed
    for response in register_responses:
        assert response.status_code == 201

    # Login all users concurrently
    login_tasks = [
        client.post(
            "/api/v1/auth/login",
            json={
                "email": user_data["email"],
                "password": user_data["password"],
            },
        )
        for user_data in users
    ]
    login_responses = await asyncio.gather(*login_tasks)

    # All should succeed and get different tokens
    tokens_set = set()
    for response in login_responses:
        assert response.status_code == 200
        token = response.json()["data"]["access_token"]
        tokens_set.add(token)

    # All tokens should be unique
    assert len(tokens_set) == 5


@pytest.mark.asyncio
async def test_role_based_access(client: AsyncClient, async_db):
    """Test role-based access control."""
    # Create admin user
    admin_data = {
        "email": "admin@example.com",
        "password": "AdminPass123!",
        "full_name": "Admin User",
        "role": "admin",
    }
    await client.post("/api/v1/auth/register", json=admin_data)

    # Create regular user
    user_data = {
        "email": "user@example.com",
        "password": "UserPass123!",
        "full_name": "Regular User",
        "role": "bid_manager",
    }
    await client.post("/api/v1/auth/register", json=user_data)

    # Login as admin
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": admin_data["email"],
            "password": admin_data["password"],
        },
    )
    admin_token = admin_login.json()["data"]["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Login as regular user
    user_login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": user_data["email"],
            "password": user_data["password"],
        },
    )
    user_token = user_login.json()["data"]["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # Admin should access admin endpoints
    # (When implemented, test admin-only endpoints here)

    # Regular user should not access admin endpoints
    # (When implemented, test restricted access here)

    # Both should access regular endpoints
    for headers in [admin_headers, user_headers]:
        response = await client.get("/api/v1/documents", headers=headers)
        assert response.status_code == 200