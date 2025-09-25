"""Pydantic schemas for tender endpoints."""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator

from src.models.procurement_tender import TenderStatus
from src.models.document_type import DocumentType


# Request schemas

class TenderCreateRequest(BaseModel):
    """Schema for creating a new tender."""

    reference: str = Field(..., min_length=1, max_length=100, description="Unique tender reference")
    title: str = Field(..., min_length=1, max_length=500, description="Tender title")
    organization: str = Field(..., min_length=1, max_length=255, description="Issuing organization")
    description: Optional[str] = Field(None, description="Detailed description")
    deadline_date: Optional[datetime] = Field(None, description="Submission deadline")
    publication_date: Optional[datetime] = Field(None, description="Publication date")
    budget_estimate: Optional[Decimal] = Field(None, gt=0, description="Budget estimate in euros")

    @field_validator('deadline_date')
    def validate_deadline(cls, v):
        if v:
            current_time = datetime.now(timezone.utc)
            # If v is naive, make it UTC aware
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            if v <= current_time:
                raise ValueError('Deadline must be in the future')
        return v

    model_config = ConfigDict(from_attributes=True)


class TenderUpdateRequest(BaseModel):
    """Schema for updating a tender."""

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    organization: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    deadline_date: Optional[datetime] = None
    publication_date: Optional[datetime] = None
    budget_estimate: Optional[Decimal] = Field(None, gt=0)

    model_config = ConfigDict(from_attributes=True)


class TenderStatusUpdateRequest(BaseModel):
    """Schema for updating tender status."""

    status: TenderStatus = Field(..., description="New status")
    reason: Optional[str] = Field(None, description="Reason for status change")

    model_config = ConfigDict(from_attributes=True)


class DocumentAssociationRequest(BaseModel):
    """Schema for associating a document with a tender."""

    document_id: UUID = Field(..., description="UUID of the document to associate")
    document_type: Optional[DocumentType] = Field(None, description="Type of the document")
    is_mandatory: Optional[bool] = Field(False, description="Whether the document is mandatory")

    model_config = ConfigDict(from_attributes=True)


class TenderAnalysisRequest(BaseModel):
    """Schema for requesting tender analysis."""

    force_reanalysis: bool = Field(False, description="Force re-analysis of already analyzed documents")
    include_recommendations: bool = Field(True, description="Include strategic recommendations")

    model_config = ConfigDict(from_attributes=True)


# Response schemas

class TenderDocumentResponse(BaseModel):
    """Schema for document information in tender response."""

    id: UUID
    original_filename: str
    document_type: Optional[str]
    is_mandatory: bool
    status: str
    file_size: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TenderResponse(BaseModel):
    """Schema for tender response."""

    id: UUID
    reference: str
    title: str
    organization: str
    description: Optional[str]
    deadline_date: Optional[datetime]
    publication_date: Optional[datetime]
    budget_estimate: Optional[Decimal]
    status: str
    matching_score: Optional[float]
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    days_until_deadline: Optional[int] = None
    document_count: int = 0
    documents: Optional[List[TenderDocumentResponse]] = None

    @classmethod
    def from_orm_with_computed(cls, tender):
        """Create response from ORM model with computed fields."""
        data = {
            'id': tender.id,
            'reference': tender.reference,
            'title': tender.title,
            'organization': tender.organization,
            'description': tender.description,
            'deadline_date': tender.deadline_date,
            'publication_date': tender.publication_date,
            'budget_estimate': tender.budget_estimate,
            'status': tender.status,
            'matching_score': tender.matching_score,
            'created_by': tender.created_by,
            'created_at': tender.created_at,
            'updated_at': tender.updated_at,
            'days_until_deadline': tender.days_until_deadline,
            'document_count': tender.document_count,
        }

        # Include documents if loaded
        if hasattr(tender, 'documents') and tender.documents is not None:
            data['documents'] = [
                TenderDocumentResponse.model_validate(doc)
                for doc in tender.documents
            ]

        return cls(**data)

    model_config = ConfigDict(from_attributes=True)


class TenderListResponse(BaseModel):
    """Schema for paginated tender list response."""

    items: List[TenderResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)


class TenderCompletenessResponse(BaseModel):
    """Schema for tender completeness analysis."""

    tender_id: UUID
    total_documents: int
    processed_documents: int
    completeness_score: float
    document_types: Dict[str, Dict[str, int]]
    missing_types: List[str]
    has_mandatory_documents: bool
    can_analyze: bool

    model_config = ConfigDict(from_attributes=True)


class TenderAnalysisResponse(BaseModel):
    """Schema for tender analysis results."""

    tender_id: UUID
    analysis_timestamp: datetime
    matching_score: float
    document_count: int
    completeness_score: float
    capability_matches: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    risk_assessment: Dict[str, Any]
    strategic_insights: Dict[str, Any]
    global_requirements: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class TenderAnalysisSummaryResponse(BaseModel):
    """Schema for tender analysis summary."""

    tender_id: UUID
    analysis_date: Optional[datetime]
    matching_score: float
    document_count: int
    completeness_score: float
    primary_recommendation: str
    risk_level: str
    total_requirements: int
    status: str

    model_config = ConfigDict(from_attributes=True)


# Search and filter schemas

class TenderSearchRequest(BaseModel):
    """Schema for searching tenders."""

    query: Optional[str] = Field(None, min_length=2, description="Search query")
    status: Optional[TenderStatus] = Field(None, description="Filter by status")
    organization: Optional[str] = Field(None, description="Filter by organization")
    min_budget: Optional[Decimal] = Field(None, gt=0, description="Minimum budget")
    max_budget: Optional[Decimal] = Field(None, gt=0, description="Maximum budget")
    deadline_before: Optional[datetime] = Field(None, description="Deadline before date")
    deadline_after: Optional[datetime] = Field(None, description="Deadline after date")

    model_config = ConfigDict(from_attributes=True)


class ExpiringTendersRequest(BaseModel):
    """Schema for getting expiring tenders."""

    days_ahead: int = Field(7, ge=1, le=90, description="Number of days to look ahead")
    include_documents: bool = Field(False, description="Include document details")

    model_config = ConfigDict(from_attributes=True)


# Bulk operations schemas

class BulkDocumentAssociationRequest(BaseModel):
    """Schema for associating multiple documents with a tender."""

    document_associations: List[DocumentAssociationRequest]

    model_config = ConfigDict(from_attributes=True)


class BulkStatusUpdateRequest(BaseModel):
    """Schema for updating status of multiple tenders."""

    tender_ids: List[UUID]
    status: TenderStatus
    reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# Error response schemas

class TenderErrorResponse(BaseModel):
    """Schema for tender-specific error responses."""

    error: str
    detail: str
    tender_id: Optional[UUID] = None
    field_errors: Optional[Dict[str, str]] = None

    model_config = ConfigDict(from_attributes=True)