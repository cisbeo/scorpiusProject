"""Schemas for semantic search endpoints."""

from typing import List, Dict, Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SemanticSearchRequest(BaseModel):
    """Request for semantic search."""

    query: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Search query text"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results"
    )
    similarity_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score (0-1)"
    )
    filter_category: Optional[str] = Field(
        None,
        description="Filter by requirement category"
    )
    filter_tender_id: Optional[UUID] = Field(
        None,
        description="Limit search to specific tender"
    )


class SimilarRequirement(BaseModel):
    """A requirement similar to the search query."""

    id: str = Field(..., description="Requirement ID")
    document_id: str = Field(..., description="Source document ID")
    requirement_text: str = Field(..., description="Full requirement text")
    document_name: str = Field(..., description="Source document name")
    tender_title: str = Field(..., description="Tender title")
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Similarity to query (0-1)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional requirement metadata"
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Extraction confidence"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "document_id": "456e7890-e89b-12d3-a456-426614174000",
                "requirement_text": "La solution doit être compatible avec PostgreSQL 15",
                "document_name": "CCTP_2024.pdf",
                "tender_title": "Système de gestion documentaire",
                "similarity_score": 0.92,
                "metadata": {
                    "category": "technical",
                    "importance": "high",
                    "is_mandatory": True
                },
                "confidence": 0.95
            }
        }


class SemanticSearchResponse(BaseModel):
    """Response from semantic search."""

    query: str = Field(..., description="Original search query")
    results: List[SimilarRequirement] = Field(
        ...,
        description="List of similar requirements"
    )
    total_results: int = Field(..., description="Total number of results")
    search_type: str = Field(
        default="semantic",
        description="Type of search performed"
    )
    processing_time_ms: int = Field(
        default=0,
        description="Processing time in milliseconds"
    )


class DuplicateRequirementPair(BaseModel):
    """A pair of duplicate requirements."""

    requirement_1: Dict[str, Any] = Field(
        ...,
        description="First requirement"
    )
    requirement_2: Dict[str, Any] = Field(
        ...,
        description="Second requirement"
    )
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Similarity between requirements"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "requirement_1": {
                    "id": "req_1",
                    "text": "Certification ISO 27001 obligatoire",
                    "document": "RC_2024.pdf",
                    "metadata": {"category": "legal"}
                },
                "requirement_2": {
                    "id": "req_2",
                    "text": "ISO 27001 certification is mandatory",
                    "document": "CCAP_2024.pdf",
                    "metadata": {"category": "legal"}
                },
                "similarity_score": 0.95
            }
        }


class RequirementCluster(BaseModel):
    """A cluster of similar requirements."""

    cluster_id: str = Field(..., description="Cluster identifier")
    cluster_name: str = Field(..., description="Descriptive name")
    requirements: List[Dict[str, Any]] = Field(
        ...,
        description="Requirements in this cluster"
    )
    centroid_text: str = Field(
        ...,
        description="Representative text for the cluster"
    )
    avg_similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Average intra-cluster similarity"
    )