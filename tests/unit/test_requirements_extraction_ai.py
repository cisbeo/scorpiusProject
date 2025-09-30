"""Unit tests for AI-based requirements extraction."""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone
from uuid import UUID

from src.services.tender_analysis_service import TenderAnalysisService
from src.models.document_type import DocumentType
from src.schemas.requirements_extraction import (
    RequirementExtractionResponse,
    ExtractedRequirement
)


@pytest.mark.asyncio
class TestRequirementsExtractionAI:
    """Test suite for AI requirements extraction."""

    @pytest.fixture
    def mock_document(self):
        """Create mock document for testing."""
        doc = Mock()
        doc.id = UUID("12345678-1234-5678-1234-567812345678")
        doc.text_content = """
        Le soumissionnaire doit fournir au minimum 3 références clients.
        L'application devra être développée en mode responsive.
        Le paiement sera effectué dans un délai de 30 jours.
        """
        doc.document_type = DocumentType.RC
        return doc

    @pytest.fixture
    def mock_mistral_response(self):
        """Mock successful Mistral AI response."""
        return json.dumps({
            "requirements": [
                {
                    "category": "administrative",
                    "description": "Fournir au minimum 3 références clients",
                    "importance": "high",
                    "is_mandatory": True,
                    "confidence": 0.95,
                    "source_text": "Le soumissionnaire doit fournir au minimum 3 références clients.",
                    "keywords": ["références", "clients", "soumissionnaire"]
                },
                {
                    "category": "technical",
                    "description": "Application développée en mode responsive",
                    "importance": "high",
                    "is_mandatory": True,
                    "confidence": 0.92,
                    "source_text": "L'application devra être développée en mode responsive.",
                    "keywords": ["application", "responsive", "développement"]
                },
                {
                    "category": "financial",
                    "description": "Paiement dans un délai de 30 jours",
                    "importance": "medium",
                    "is_mandatory": True,
                    "confidence": 0.88,
                    "source_text": "Le paiement sera effectué dans un délai de 30 jours.",
                    "keywords": ["paiement", "délai", "30 jours"]
                }
            ],
            "metadata": {
                "total_requirements_found": 3,
                "sections_analyzed": ["main"],
                "extraction_notes": "Document RC standard"
            },
            "confidence_avg": 0.92,
            "document_type": "rc"
        })

    @pytest.mark.asyncio
    async def test_extract_requirements_with_ai_success(
        self,
        mock_document,
        mock_mistral_response
    ):
        """Test successful AI extraction."""
        with patch('src.services.tender_analysis_service.ai_config') as mock_config:
            mock_config.mistral_api_key = "test-key"
            mock_config.llm_model.value = "mistral-large-latest"

            with patch('src.services.tender_analysis_service.get_mistral_service') as mock_get_service:
                # Setup mock Mistral service
                mock_service = AsyncMock()
                mock_service.generate_completion.return_value = mock_mistral_response
                mock_get_service.return_value = mock_service

                # Mock cache and monitor
                with patch('src.services.tender_analysis_service.get_requirements_cache'):
                    with patch('src.services.tender_analysis_service.get_extraction_monitor') as mock_monitor:
                        mock_monitor.return_value.record = AsyncMock()

                        # Create service and test
                        service = TenderAnalysisService(Mock())
                        result = await service._extract_requirements_with_ai(
                            mock_document,
                            DocumentType.RC,
                            None
                        )

                        # Assertions
                        assert result is not None
                        assert len(result["requirements"]) == 3
                        assert result["metadata"]["extraction_method"] == "mistral-ai"
                        assert result["confidence_avg"] == 0.92

                        # Verify requirements
                        req1 = result["requirements"][0]
                        assert req1["category"] == "administrative"
                        assert req1["is_mandatory"] is True
                        assert req1["confidence"] == 0.95

                        # Verify API was called
                        mock_service.generate_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_requirements_cache_hit(self, mock_document):
        """Test extraction with cache hit."""
        cached_result = {
            "requirements": [
                {
                    "category": "administrative",
                    "description": "Cached requirement",
                    "importance": "high",
                    "is_mandatory": True,
                    "confidence": 0.9,
                    "source_text": "Cached text",
                    "keywords": ["cached"]
                }
            ],
            "metadata": {"cached": True, "confidence_avg": 0.9},
            "confidence_avg": 0.9
        }

        with patch('src.services.tender_analysis_service.ai_config') as mock_config:
            mock_config.mistral_api_key = "test-key"

            with patch('src.services.tender_analysis_service.get_requirements_cache') as mock_cache_factory:
                # Setup mock cache
                mock_cache = AsyncMock()
                mock_cache.get.return_value = cached_result
                mock_cache_factory.return_value = mock_cache

                with patch('src.services.tender_analysis_service.get_extraction_monitor') as mock_monitor:
                    mock_monitor.return_value.record = AsyncMock()

                    # Create service and test
                    service = TenderAnalysisService(Mock())
                    result = await service._extract_requirements_with_ai(
                        mock_document,
                        DocumentType.RC,
                        None
                    )

                    # Assertions
                    assert result == cached_result
                    assert result["metadata"]["cached"] is True

                    # Verify cache was checked
                    mock_cache.get.assert_called_once_with(mock_document.id)

    @pytest.mark.asyncio
    async def test_extract_requirements_fallback_on_error(self, mock_document):
        """Test fallback to rule-based extraction on AI error."""
        with patch('src.services.tender_analysis_service.ai_config') as mock_config:
            mock_config.mistral_api_key = "test-key"

            with patch('src.services.tender_analysis_service.get_mistral_service') as mock_get_service:
                # Setup mock to raise error
                mock_service = AsyncMock()
                mock_service.generate_completion.side_effect = Exception("API Error")
                mock_get_service.return_value = mock_service

                with patch('src.services.tender_analysis_service.get_requirements_cache'):
                    with patch('src.services.tender_analysis_service.get_extraction_monitor'):
                        # Create service and test
                        service = TenderAnalysisService(Mock())
                        result = await service._extract_requirements_with_ai(
                            mock_document,
                            DocumentType.RC,
                            None
                        )

                        # Should fallback to rule-based
                        assert result is not None
                        assert result["metadata"]["extraction_method"] in [
                            "rule-based-fallback",
                            "minimal-fallback"
                        ]

    @pytest.mark.asyncio
    async def test_extract_requirements_invalid_json(self, mock_document):
        """Test handling of invalid JSON response from AI."""
        with patch('src.services.tender_analysis_service.ai_config') as mock_config:
            mock_config.mistral_api_key = "test-key"

            with patch('src.services.tender_analysis_service.get_mistral_service') as mock_get_service:
                # Setup mock with invalid JSON
                mock_service = AsyncMock()
                mock_service.generate_completion.return_value = "Invalid JSON response"
                mock_get_service.return_value = mock_service

                with patch('src.services.tender_analysis_service.get_requirements_cache'):
                    with patch('src.services.tender_analysis_service.get_extraction_monitor'):
                        # Create service and test
                        service = TenderAnalysisService(Mock())
                        result = await service._extract_requirements_with_ai(
                            mock_document,
                            DocumentType.RC,
                            None
                        )

                        # Should fallback
                        assert result is not None
                        assert result["metadata"]["extraction_method"] in [
                            "rule-based-fallback",
                            "minimal-fallback"
                        ]

    @pytest.mark.asyncio
    async def test_extract_requirements_no_api_key(self, mock_document):
        """Test extraction without API key configured."""
        with patch('src.services.tender_analysis_service.ai_config') as mock_config:
            mock_config.mistral_api_key = None

            with patch('src.services.tender_analysis_service.get_extraction_monitor'):
                # Create service and test
                service = TenderAnalysisService(Mock())
                result = await service._extract_requirements_with_ai(
                    mock_document,
                    DocumentType.RC,
                    None
                )

                # Should use fallback
                assert result is not None
                assert result["metadata"]["extraction_method"] in [
                    "rule-based-fallback",
                    "minimal-fallback"
                ]

    @pytest.mark.asyncio
    async def test_extract_requirements_metrics_recording(
        self,
        mock_document,
        mock_mistral_response
    ):
        """Test that extraction metrics are properly recorded."""
        with patch('src.services.tender_analysis_service.ai_config') as mock_config:
            mock_config.mistral_api_key = "test-key"
            mock_config.llm_model.value = "mistral-large-latest"

            with patch('src.services.tender_analysis_service.get_mistral_service') as mock_get_service:
                mock_service = AsyncMock()
                mock_service.generate_completion.return_value = mock_mistral_response
                mock_get_service.return_value = mock_service

                with patch('src.services.tender_analysis_service.get_requirements_cache'):
                    with patch('src.services.tender_analysis_service.get_extraction_monitor') as mock_monitor:
                        mock_monitor_instance = Mock()
                        mock_monitor_instance.record = AsyncMock()
                        mock_monitor.return_value = mock_monitor_instance

                        # Create service and test
                        service = TenderAnalysisService(Mock())
                        await service._extract_requirements_with_ai(
                            mock_document,
                            DocumentType.RC,
                            None
                        )

                        # Verify metrics were recorded
                        mock_monitor_instance.record.assert_called_once()
                        recorded_metrics = mock_monitor_instance.record.call_args[0][0]

                        assert recorded_metrics.document_id == str(mock_document.id)
                        assert recorded_metrics.document_type == "rc"
                        assert recorded_metrics.extraction_method == "mistral-ai"
                        assert recorded_metrics.num_requirements == 3
                        assert recorded_metrics.confidence_avg == 0.92
                        assert recorded_metrics.api_calls == 1
                        assert recorded_metrics.cache_hit is False

    @pytest.mark.asyncio
    async def test_extract_requirements_different_doc_types(self):
        """Test extraction with different document types."""
        doc_types = [
            DocumentType.CCTP,
            DocumentType.CCAP,
            DocumentType.RC,
            DocumentType.BPU
        ]

        for doc_type in doc_types:
            mock_doc = Mock()
            mock_doc.id = UUID("12345678-1234-5678-1234-567812345678")
            mock_doc.text_content = "Document de test avec exigences"

            with patch('src.services.tender_analysis_service.ai_config') as mock_config:
                mock_config.mistral_api_key = None  # Force fallback

                with patch('src.services.tender_analysis_service.get_extraction_monitor'):
                    service = TenderAnalysisService(Mock())
                    result = await service._extract_requirements_with_ai(
                        mock_doc,
                        doc_type,
                        None
                    )

                    assert result is not None
                    assert result["metadata"]["document_type"] == doc_type.value