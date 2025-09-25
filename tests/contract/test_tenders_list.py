"""
Contract test for GET /api/v1/tenders endpoint.
This test validates the API contract for listing tender dossiers.
"""
import pytest
from fastapi.testclient import TestClient

from src.main import app


class TestTendersListContract:
    """Contract tests for GET /api/v1/tenders endpoint."""

    @pytest.fixture
    def client(self):
        """Test client fixture."""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """Mock authentication headers."""
        return {"Authorization": "Bearer mock-jwt-token"}

    def test_list_tenders_success_contract(self, client: TestClient, auth_headers: dict):
        """
        Test successful tender listing - validates response schema.
        Expected to FAIL until implementation is complete.
        """
        response = client.get("/api/v1/tenders", headers=auth_headers)

        # Contract validation: HTTP status
        assert response.status_code == 200

        # Contract validation: Response schema
        response_data = response.json()
        required_fields = {"items", "total", "limit", "offset"}

        for field in required_fields:
            assert field in response_data, f"Required field '{field}' missing from response"

        # Contract validation: Field types
        assert isinstance(response_data["items"], list), "Items must be a list"
        assert isinstance(response_data["total"], int), "Total must be an integer"
        assert isinstance(response_data["limit"], int), "Limit must be an integer"
        assert isinstance(response_data["offset"], int), "Offset must be an integer"

    def test_list_tenders_pagination_contract(self, client: TestClient, auth_headers: dict):
        """
        Test pagination parameters.
        Expected to FAIL until implementation is complete.
        """
        # Test with pagination parameters
        response = client.get(
            "/api/v1/tenders?limit=10&offset=20",
            headers=auth_headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Contract validation: Pagination values reflected in response
        assert response_data["limit"] == 10
        assert response_data["offset"] == 20

    def test_list_tenders_status_filter_contract(self, client: TestClient, auth_headers: dict):
        """
        Test status filter parameter.
        Expected to FAIL until implementation is complete.
        """
        # Test with status filter
        response = client.get(
            "/api/v1/tenders?status=ready",
            headers=auth_headers
        )

        assert response.status_code == 200

        # Validate items have correct status if any returned
        response_data = response.json()
        for item in response_data["items"]:
            assert item["status"] == "ready"

    def test_list_tenders_item_schema_contract(self, client: TestClient, auth_headers: dict):
        """
        Test individual tender item schema in list.
        Expected to FAIL until implementation is complete.
        """
        response = client.get("/api/v1/tenders", headers=auth_headers)

        assert response.status_code == 200
        response_data = response.json()

        # If items exist, validate their schema
        if response_data["items"]:
            item = response_data["items"][0]
            required_item_fields = {
                "id", "reference_number", "title", "status",
                "documents_count", "created_at", "updated_at"
            }

            for field in required_item_fields:
                assert field in item, f"Required field '{field}' missing from tender item"

            # Validate field types
            assert isinstance(item["id"], str)
            assert isinstance(item["reference_number"], str)
            assert isinstance(item["title"], str)
            assert item["status"] in ["draft", "indexing", "ready", "error"]
            assert isinstance(item["documents_count"], int)
            assert isinstance(item["created_at"], str)  # ISO datetime string
            assert isinstance(item["updated_at"], str)  # ISO datetime string

    def test_list_tenders_unauthorized_contract(self, client: TestClient):
        """
        Test listing without authentication.
        Expected to FAIL until implementation is complete.
        """
        response = client.get("/api/v1/tenders")

        # Contract validation: Should return 401 for unauthorized request
        assert response.status_code == 401

    def test_list_tenders_invalid_pagination_contract(self, client: TestClient, auth_headers: dict):
        """
        Test invalid pagination parameters.
        Expected to FAIL until implementation is complete.
        """
        # Test negative offset
        response = client.get(
            "/api/v1/tenders?offset=-1",
            headers=auth_headers
        )

        assert response.status_code == 400

        # Test limit exceeding maximum
        response = client.get(
            "/api/v1/tenders?limit=101",
            headers=auth_headers
        )

        assert response.status_code == 400

    def test_list_tenders_invalid_status_filter_contract(self, client: TestClient, auth_headers: dict):
        """
        Test invalid status filter values.
        Expected to FAIL until implementation is complete.
        """
        response = client.get(
            "/api/v1/tenders?status=invalid_status",
            headers=auth_headers
        )

        # Should return 400 for invalid enum value
        assert response.status_code == 400

    def test_list_tenders_empty_list_contract(self, client: TestClient, auth_headers: dict):
        """
        Test response when no tenders exist.
        Expected to FAIL until implementation is complete.
        """
        response = client.get("/api/v1/tenders", headers=auth_headers)

        assert response.status_code == 200
        response_data = response.json()

        # Contract validation: Empty list is valid
        assert response_data["items"] == []
        assert response_data["total"] == 0
        assert "limit" in response_data
        assert "offset" in response_data

    def test_list_tenders_response_headers_contract(self, client: TestClient, auth_headers: dict):
        """
        Test response headers conform to API contract.
        Expected to FAIL until implementation is complete.
        """
        response = client.get("/api/v1/tenders", headers=auth_headers)

        # Contract validation: Content-Type header
        assert response.headers.get("content-type") == "application/json"