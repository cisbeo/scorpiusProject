"""Contract test for POST /api/v1/tenders/{id}/analyze endpoint."""
import pytest
from fastapi.testclient import TestClient
from src.main import app

class TestIntelligenceAnalyzeContract:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer mock-jwt-token"}

    @pytest.fixture
    def sample_tender_id(self):
        return "123e4567-e89b-12d3-a456-426614174000"

    def test_analyze_tender_contract(self, client: TestClient, auth_headers: dict, sample_tender_id: str):
        """Expected to FAIL until implementation is complete."""
        response = client.post(
            f"/api/v1/tenders/{sample_tender_id}/analyze",
            json={"analysis_types": ["coherence", "risks", "complexity", "summary"]},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "coherence" in data or "summary" in data

    def test_analyze_unauthorized_contract(self, client: TestClient, sample_tender_id: str):
        response = client.post(f"/api/v1/tenders/{sample_tender_id}/analyze", json={})
        assert response.status_code == 401