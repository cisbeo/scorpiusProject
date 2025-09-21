"""Analysis and matching schemas for API requests/responses."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MatchAnalysisRequest(BaseModel):
    """Request schema for capability matching analysis."""

    document_id: UUID = Field(description="ID of the processed document")
    company_profile_id: UUID = Field(description="ID of the company profile")
    analysis_options: dict[str, Any] = Field(
        default={},
        description="Optional analysis configuration"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "document_id": "123e4567-e89b-12d3-a456-426614174000",
                "company_profile_id": "123e4567-e89b-12d3-a456-426614174001",
                "analysis_options": {
                    "min_score_threshold": 0.5,
                    "include_partial_matches": True,
                    "weight_technical": 0.6,
                    "weight_experience": 0.4
                }
            }
        }
    }


class MatchResult(BaseModel):
    """Schema for individual match result."""

    requirement_id: str = Field(description="Identifier of the requirement")
    requirement_text: str = Field(description="Text of the requirement")
    capability_match: bool = Field(description="Whether company has matching capability")
    match_score: float = Field(description="Match score (0.0 to 1.0)")
    gap_analysis: str = Field(description="Analysis of gaps if any")
    recommendations: list[str] = Field(description="Recommendations to improve match")

    model_config = {
        "json_schema_extra": {
            "example": {
                "requirement_id": "tech_req_001",
                "requirement_text": "Développement en Python avec FastAPI",
                "capability_match": True,
                "match_score": 0.95,
                "gap_analysis": "Excellente correspondance",
                "recommendations": ["Mettre en avant l'expérience FastAPI dans la réponse"]
            }
        }
    }


class MatchAnalysisResponse(BaseModel):
    """Response schema for capability matching analysis."""

    analysis_id: UUID = Field(description="Unique identifier for this analysis")
    document_id: UUID = Field(description="ID of the analyzed document")
    company_profile_id: UUID = Field(description="ID of the company profile")

    # Overall analysis
    overall_match_score: float = Field(description="Overall compatibility score (0.0 to 1.0)")
    recommendation: str = Field(description="Overall recommendation")
    confidence_level: str = Field(description="Confidence level (low/medium/high)")

    # Detailed results
    technical_matches: list[MatchResult] = Field(description="Technical requirement matches")
    functional_matches: list[MatchResult] = Field(description="Functional requirement matches")
    administrative_matches: list[MatchResult] = Field(description="Administrative requirement matches")

    # Summary statistics
    total_requirements: int = Field(description="Total number of requirements analyzed")
    matched_requirements: int = Field(description="Number of matched requirements")
    missing_capabilities: list[str] = Field(description="Key capabilities that are missing")
    strengths: list[str] = Field(description="Company strengths for this bid")

    # Analysis metadata
    analyzed_at: datetime = Field(description="Analysis timestamp")
    analysis_duration_ms: int = Field(description="Analysis duration in milliseconds")
    analyst_version: str = Field(description="Version of analysis engine used")

    model_config = {
        "json_schema_extra": {
            "example": {
                "analysis_id": "123e4567-e89b-12d3-a456-426614174002",
                "document_id": "123e4567-e89b-12d3-a456-426614174000",
                "company_profile_id": "123e4567-e89b-12d3-a456-426614174001",
                "overall_match_score": 0.78,
                "recommendation": "Bid recommandé avec quelques améliorations",
                "confidence_level": "high",
                "technical_matches": [
                    {
                        "requirement_id": "tech_req_001",
                        "requirement_text": "Développement en Python avec FastAPI",
                        "capability_match": True,
                        "match_score": 0.95,
                        "gap_analysis": "Excellente correspondance",
                        "recommendations": ["Mettre en avant l'expérience FastAPI"]
                    }
                ],
                "functional_matches": [],
                "administrative_matches": [],
                "total_requirements": 12,
                "matched_requirements": 9,
                "missing_capabilities": ["Certification RGPD", "Expérience secteur public"],
                "strengths": ["Expertise technique Python", "Équipe expérimentée", "Références solides"],
                "analyzed_at": "2024-01-15T10:30:00Z",
                "analysis_duration_ms": 2500,
                "analyst_version": "1.0.0"
            }
        }
    }
