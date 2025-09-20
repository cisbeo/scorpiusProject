"""Contract test for GET /health endpoint."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_health_check_success(client: AsyncClient):
    """Test successful health check."""
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "status" in data
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_health_check_detailed(client: AsyncClient):
    """Test detailed health check with component status."""
    response = await client.get("/api/v1/health?detailed=true")

    assert response.status_code == 200
    data = response.json()

    # Verify detailed response
    assert "status" in data
    assert "version" in data
    assert "timestamp" in data
    assert "components" in data

    components = data["components"]
    assert "database" in components
    assert "redis" in components
    assert "storage" in components

    # Each component should have status
    for component, details in components.items():
        assert "status" in details
        assert details["status"] in ["healthy", "unhealthy", "degraded"]


@pytest.mark.asyncio
async def test_health_check_database_down(
    client: AsyncClient,
    monkeypatch,
):
    """Test health check when database is down."""
    # Mock database connection to fail
    def mock_db_check():
        raise Exception("Database connection failed")

    monkeypatch.setattr("src.api.v1.endpoints.health.check_database", mock_db_check)

    response = await client.get("/api/v1/health?detailed=true")

    # Should still return 200 but indicate unhealthy
    assert response.status_code == 503  # Service Unavailable
    data = response.json()

    assert data["status"] == "unhealthy"
    assert data["components"]["database"]["status"] == "unhealthy"
    assert "error" in data["components"]["database"]


@pytest.mark.asyncio
async def test_readiness_check(client: AsyncClient):
    """Test readiness endpoint for Kubernetes."""
    response = await client.get("/api/v1/ready")

    assert response.status_code == 200
    data = response.json()

    assert "ready" in data
    assert data["ready"] is True
    assert "checks" in data


@pytest.mark.asyncio
async def test_liveness_check(client: AsyncClient):
    """Test liveness endpoint for Kubernetes."""
    response = await client.get("/api/v1/live")

    assert response.status_code == 200
    data = response.json()

    assert "alive" in data
    assert data["alive"] is True