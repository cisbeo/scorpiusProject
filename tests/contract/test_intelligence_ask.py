"""
Contract test for POST /api/v1/tenders/{id}/ask endpoint.
This test validates the API contract for intelligent querying of tender documents.
"""
import pytest
from fastapi.testclient import TestClient

from src.main import app


class TestIntelligenceAskContract:
    """Contract tests for POST /api/v1/tenders/{id}/ask endpoint."""

    @pytest.fixture
    def client(self):
        """Test client fixture."""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """Mock authentication headers."""
        return {"Authorization": "Bearer mock-jwt-token"}

    @pytest.fixture
    def sample_tender_id(self):
        """Mock tender ID for testing."""
        return "123e4567-e89b-12d3-a456-426614174000"

    @pytest.fixture
    def valid_query_data(self):
        """Valid question data."""
        return {
            "question": "Quel est le budget maximum pour ce projet?",
            "include_confidence": True
        }

    def test_ask_question_success_contract(
        self, client: TestClient, auth_headers: dict,
        sample_tender_id: str, valid_query_data: dict
    ):
        """
        Test successful question asking - validates response schema.
        Expected to FAIL until implementation is complete.
        """
        response = client.post(
            f"/api/v1/tenders/{sample_tender_id}/ask",
            json=valid_query_data,
            headers=auth_headers
        )

        # Contract validation: HTTP status
        assert response.status_code == 200

        # Contract validation: Response schema
        response_data = response.json()
        required_fields = {"answer", "sources", "confidence_score", "processing_time_ms"}

        for field in required_fields:
            assert field in response_data, f"Required field '{field}' missing from response"

        # Contract validation: Field types and values
        assert isinstance(response_data["answer"], str)
        assert isinstance(response_data["sources"], list)
        assert isinstance(response_data["confidence_score"], (int, float))
        assert 0.0 <= response_data["confidence_score"] <= 1.0
        assert isinstance(response_data["processing_time_ms"], int)
        assert response_data["processing_time_ms"] > 0

        # Validate sources structure if present
        if response_data["sources"]:
            source = response_data["sources"][0]
            assert "document_id" in source
            assert "document_type" in source
            assert "confidence" in source

    def test_ask_question_invalid_tender_contract(
        self, client: TestClient, auth_headers: dict, valid_query_data: dict
    ):
        """
        Test question to non-existent tender.
        Expected to FAIL until implementation is complete.
        """
        invalid_tender_id = "00000000-0000-0000-0000-000000000000"
        response = client.post(
            f"/api/v1/tenders/{invalid_tender_id}/ask",
            json=valid_query_data,
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_ask_question_short_question_contract(
        self, client: TestClient, auth_headers: dict, sample_tender_id: str
    ):
        """
        Test question that's too short.
        Expected to FAIL until implementation is complete.
        """
        short_question = {"question": "Hi"}  # Less than 10 characters

        response = client.post(
            f"/api/v1/tenders/{sample_tender_id}/ask",
            json=short_question,
            headers=auth_headers
        )

        assert response.status_code == 400

    def test_ask_question_unauthorized_contract(
        self, client: TestClient, sample_tender_id: str, valid_query_data: dict
    ):
        """
        Test question without authentication.
        Expected to FAIL until implementation is complete.
        """
        response = client.post(
            f"/api/v1/tenders/{sample_tender_id}/ask",
            json=valid_query_data
            # No authorization headers
        )

        assert response.status_code == 401