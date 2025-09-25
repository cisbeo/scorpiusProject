"""
Contract test for POST /api/v1/tenders/{id}/extract endpoint.
"""
import pytest
from fastapi.testclient import TestClient

from src.main import app


class TestIntelligenceExtractContract:
    """Contract tests for POST /api/v1/tenders/{id}/extract endpoint."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer mock-jwt-token"}

    @pytest.fixture
    def sample_tender_id(self):
        return "123e4567-e89b-12d3-a456-426614174000"

    def test_extract_information_contract(
        self, client: TestClient, auth_headers: dict, sample_tender_id: str
    ):
        """
        Test structured information extraction.
        Expected to FAIL until implementation is complete.
        """
        extract_data = {
            "fields": ["reference", "organization", "budget", "deadline"]
        }

        response = client.post(
            f"/api/v1/tenders/{sample_tender_id}/extract",
            json=extract_data,
            headers=auth_headers
        )

        assert response.status_code == 200

        response_data = response.json()
        for field in extract_data["fields"]:
            assert field in response_data

        # Validate budget structure if present
        if "budget" in response_data and response_data["budget"]:
            budget = response_data["budget"]
            assert "confidence" in budget
            assert isinstance(budget["confidence"], (int, float))

    def test_extract_unauthorized_contract(
        self, client: TestClient, sample_tender_id: str
    ):
        """Test extraction without authentication."""
        response = client.post(f"/api/v1/tenders/{sample_tender_id}/extract", json={})
        assert response.status_code == 401