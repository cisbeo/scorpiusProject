"""Contract test for POST /api/v1/tenders/compare endpoint."""
import pytest
from fastapi.testclient import TestClient
from src.main import app

class TestIntelligenceCompareContract:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer mock-jwt-token"}

    def test_compare_tenders_contract(self, client: TestClient, auth_headers: dict):
        """Expected to FAIL until implementation is complete."""
        compare_data = {
            "tender_ids": [
                "123e4567-e89b-12d3-a456-426614174000",
                "223e4567-e89b-12d3-a456-426614174001"
            ],
            "comparison_aspects": ["budget", "duration", "requirements"]
        }

        response = client.post("/api/v1/tenders/compare", json=compare_data, headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "comparison" in data
        assert "tenders" in data

    def test_compare_unauthorized_contract(self, client: TestClient):
        response = client.post("/api/v1/tenders/compare", json={})
        assert response.status_code == 401