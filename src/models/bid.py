"""Bid response model."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import BaseModel

if TYPE_CHECKING:
    from src.models.company import CompanyProfile
    from src.models.compliance import ComplianceCheck
    from src.models.document import ProcurementDocument
    from src.models.match import CapabilityMatch
    from src.models.procurement_tender import ProcurementTender
    from src.models.user import User


class ResponseType(str, Enum):
    """Bid response type enumeration."""

    TECHNICAL = "technical"
    COMMERCIAL = "commercial"
    COMPLETE = "complete"


class ResponseStatus(str, Enum):
    """Bid response status enumeration."""

    DRAFT = "draft"
    REVIEWING = "reviewing"
    FINAL = "final"


class BidResponse(BaseModel):
    """Model for generated bid responses."""

    __tablename__ = "bid_responses"

    # Foreign keys
    procurement_document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("procurement_documents.id"),
        nullable=False,
        index=True,
    )
    tender_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("procurement_tenders.id"),
        nullable=True,
        index=True,
    )
    company_profile_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("company_profiles.id"),
        nullable=False,
        index=True,
    )
    capability_match_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("capability_matches.id"),
        nullable=False,
        unique=True,
    )
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    reviewed_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    # Response information
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    response_type: Mapped[ResponseType] = mapped_column(
        String(20),
        nullable=False,
        default=ResponseType.COMPLETE,
    )
    status: Mapped[ResponseStatus] = mapped_column(
        String(20),
        nullable=False,
        default=ResponseStatus.DRAFT,
        index=True,
    )

    # Content (JSON field)
    content_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Structured response content",
    )

    # File generation
    generated_file_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Path to generated response file",
    )

    # Compliance
    compliance_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Compliance score (0-100)",
    )
    compliance_issues_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Compliance issues found",
    )

    # Timestamps
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
    )

    # Versioning
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    # Relationships
    procurement_document: Mapped["ProcurementDocument"] = relationship(
        "ProcurementDocument",
        back_populates="bid_responses",
        lazy="select",
    )

    tender: Mapped[Optional["ProcurementTender"]] = relationship(
        "ProcurementTender",
        back_populates="bid_responses",
        lazy="select",
    )

    company_profile: Mapped["CompanyProfile"] = relationship(
        "CompanyProfile",
        back_populates="bid_responses",
        lazy="select",
    )

    capability_match: Mapped["CapabilityMatch"] = relationship(
        "CapabilityMatch",
        back_populates="bid_response",
        lazy="select",
    )

    creator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="bid_responses_created",
        lazy="select",
    )

    reviewer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[reviewed_by],
        back_populates="bid_responses_reviewed",
        lazy="select",
    )

    compliance_checks: Mapped[list["ComplianceCheck"]] = relationship(
        "ComplianceCheck",
        back_populates="bid_response",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<BidResponse(id={self.id}, title={self.title}, status={self.status})>"

    @property
    def is_draft(self) -> bool:
        """Check if response is in draft status."""
        return self.status == ResponseStatus.DRAFT

    @property
    def is_final(self) -> bool:
        """Check if response is in final status."""
        return self.status == ResponseStatus.FINAL

    @property
    def is_submitted(self) -> bool:
        """Check if response has been submitted."""
        return self.submitted_at is not None

    @property
    def has_compliance_issues(self) -> bool:
        """Check if response has compliance issues."""
        return bool(self.compliance_issues_json)
