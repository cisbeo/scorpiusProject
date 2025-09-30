"""Schemas for AI extraction endpoints."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field


class ExtractionType(str, Enum):
    """Types of extraction available."""

    REQUIREMENTS = "requirements"
    KEY_DATES = "key_dates"
    EVALUATION_CRITERIA = "evaluation_criteria"
    FINANCIAL_INFO = "financial_info"
    FULL_ANALYSIS = "full_analysis"


class RequirementPriority(str, Enum):
    """Priority levels for requirements."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RequirementCategory(str, Enum):
    """Categories for requirements."""

    FUNCTIONAL = "functional"
    TECHNICAL = "technical"
    SECURITY = "security"
    PERFORMANCE = "performance"
    COMPLIANCE = "compliance"
    FINANCIAL = "financial"
    ADMINISTRATIVE = "administrative"
    OTHER = "other"


class ExtractedRequirement(BaseModel):
    """Schema for an extracted requirement."""

    requirement_text: str = Field(..., description="The extracted requirement text")
    category: RequirementCategory = Field(..., description="Category of the requirement")
    priority: RequirementPriority = Field(RequirementPriority.MEDIUM, description="Priority level")
    is_mandatory: bool = Field(False, description="Whether the requirement is mandatory")
    source_document: str = Field(..., description="Source document type (CCTP, RC, etc)")
    page_number: Optional[int] = Field(None, description="Page number in source document")
    confidence_score: float = Field(1.0, description="Confidence score of extraction")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ExtractionRequest(BaseModel):
    """Request schema for triggering extraction."""

    tender_id: UUID = Field(..., description="Tender ID to extract from")
    extraction_type: ExtractionType = Field(
        ExtractionType.REQUIREMENTS,
        description="Type of extraction to perform"
    )
    document_types: Optional[List[str]] = Field(
        None,
        description="Specific document types to analyze (None = all)"
    )
    force_reprocess: bool = Field(
        False,
        description="Force reprocessing even if extraction exists"
    )


class ExtractionResponse(BaseModel):
    """Response schema for extraction request."""

    analysis_id: UUID = Field(..., description="Analysis ID for tracking")
    tender_id: UUID = Field(..., description="Tender ID")
    status: str = Field(..., description="Status of extraction")
    message: str = Field(..., description="Status message")
    documents_processed: int = Field(0, description="Number of documents processed")
    requirements_extracted: int = Field(0, description="Number of requirements extracted")


class ExtractionStatusResponse(BaseModel):
    """Response schema for extraction status check."""

    analysis_id: UUID
    tender_id: UUID
    status: str
    progress_percentage: int
    documents_processed: int
    total_documents: int
    requirements_extracted: int
    started_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]


class RequirementsListResponse(BaseModel):
    """Response schema for listing extracted requirements."""

    tender_id: UUID
    total_requirements: int
    requirements: List[ExtractedRequirement]
    extraction_date: Optional[datetime] = None
    analysis_id: Optional[UUID] = None


class RequirementAnalysis(BaseModel):
    """Detailed analysis of a single requirement."""

    requirement_id: UUID
    requirement_text: str
    category: RequirementCategory
    priority: RequirementPriority
    is_mandatory: bool
    implementation_effort: Optional[str] = Field(None, description="Estimated effort")
    technical_complexity: Optional[str] = Field(None, description="Technical complexity level")
    dependencies: Optional[List[str]] = Field(default_factory=list, description="Related requirements")
    risks: Optional[List[str]] = Field(default_factory=list, description="Identified risks")
    compliance_notes: Optional[str] = Field(None, description="Compliance considerations")