"""Database models package."""

from src.models.audit import AuditLog
from src.models.bid import BidResponse, ResponseStatus, ResponseType
from src.models.company import CompanyProfile
from src.models.compliance import (
    ComplianceCheck,
    ComplianceSeverity,
    ComplianceStatus,
)
from src.models.document import DocumentStatus, ProcurementDocument
from src.models.events import EventStatus, ProcessingEvent, ProcessingStage
from src.models.match import CapabilityMatch, MatchRecommendation
from src.models.requirements import ExtractedRequirements
from src.models.user import User, UserRole

# Optional NLP models (only available with ML dependencies)
try:
    from src.models.embeddings import DocumentEmbedding, RequirementSummary
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False

__all__ = [
    # User
    "User",
    "UserRole",
    # Document
    "ProcurementDocument",
    "DocumentStatus",
    # Requirements
    "ExtractedRequirements",
    # Company
    "CompanyProfile",
    # Match
    "CapabilityMatch",
    "MatchRecommendation",
    # Bid
    "BidResponse",
    "ResponseType",
    "ResponseStatus",
    # Compliance
    "ComplianceCheck",
    "ComplianceStatus",
    "ComplianceSeverity",
    # Events
    "ProcessingEvent",
    "ProcessingStage",
    "EventStatus",
    # Audit
    "AuditLog",
]

# Add NLP models to exports if available
if EMBEDDINGS_AVAILABLE:
    __all__.extend([
        "DocumentEmbedding",
        "RequirementSummary",
    ])
