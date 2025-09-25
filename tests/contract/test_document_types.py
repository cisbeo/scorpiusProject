"""Contract test for GET /api/v1/document-types endpoint."""
import pytest
from fastapi.testclient import TestClient
from src.main import app

class TestDocumentTypesContract:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer mock-jwt-token"}

    def test_get_document_types_contract(self, client: TestClient, auth_headers: dict):
        """Expected to FAIL until implementation is complete."""
        response = client.get("/api/v1/document-types", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        if data:
            item = data[0]
            required_fields = {"code", "name", "category"}
            for field in required_fields:
                assert field in item

    def test_get_document_types_unauthorized_contract(self, client: TestClient):
        response = client.get("/api/v1/document-types")
        assert response.status_code == 401