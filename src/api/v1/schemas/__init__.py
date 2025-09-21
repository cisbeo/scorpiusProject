"""Pydantic schemas for API v1."""

from src.api.v1.schemas.analysis import MatchAnalysisRequest, MatchAnalysisResponse
from src.api.v1.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    UserResponse,
)
from src.api.v1.schemas.company import (
    CompanyProfileCreateRequest,
    CompanyProfileResponse,
    CompanyProfileUpdateRequest,
)
from src.api.v1.schemas.documents import (
    DocumentListResponse,
    DocumentProcessRequest,
    DocumentResponse,
    DocumentUploadResponse,
    ExtractedRequirementsResponse,
    ProcessingResultResponse,
)

__all__ = [
    # Auth schemas
    "LoginRequest",
    "LoginResponse",
    "RefreshRequest",
    "RefreshResponse",
    "RegisterRequest",
    "UserResponse",
    # Document schemas
    "DocumentUploadResponse",
    "DocumentResponse",
    "DocumentListResponse",
    "DocumentProcessRequest",
    "ProcessingResultResponse",
    "ExtractedRequirementsResponse",
    # Company schemas
    "CompanyProfileResponse",
    "CompanyProfileCreateRequest",
    "CompanyProfileUpdateRequest",
    # Analysis schemas
    "MatchAnalysisRequest",
    "MatchAnalysisResponse",
]
