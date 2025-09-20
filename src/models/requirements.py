"""Extracted requirements model."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Float, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import BaseModel

if TYPE_CHECKING:
    from src.models.document import ProcurementDocument
    from src.models.match import CapabilityMatch


class ExtractedRequirements(BaseModel):
    """Model for structured data extracted from procurement documents."""

    __tablename__ = "extracted_requirements"

    # Foreign keys
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("procurement_documents.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Basic information
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    reference_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    buyer_organization: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    submission_deadline: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
    )

    # Budget information
    budget_min: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )
    budget_max: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    # Structured data (JSON fields)
    requirements_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Structured requirements: technical, functional, administrative",
    )
    evaluation_criteria_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Evaluation criteria with weights",
    )
    mandatory_documents: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="List of required documents",
    )

    # Extracted content
    extracted_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full extracted text from document",
    )

    # Extraction metadata
    extraction_confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Extraction confidence score (0-1)",
    )
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="fr",
    )

    # Relationships
    document: Mapped["ProcurementDocument"] = relationship(
        "ProcurementDocument",
        back_populates="extracted_requirements",
        lazy="select",
    )

    capability_matches: Mapped[List["CapabilityMatch"]] = relationship(
        "CapabilityMatch",
        back_populates="extracted_requirements",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<ExtractedRequirements(id={self.id}, title={self.title}, deadline={self.submission_deadline})>"

    @property
    def is_expired(self) -> bool:
        """Check if submission deadline has passed."""
        return datetime.utcnow() > self.submission_deadline

    @property
    def days_until_deadline(self) -> int:
        """Calculate days until submission deadline."""
        delta = self.submission_deadline - datetime.utcnow()
        return delta.days if delta.days > 0 else 0

    @property
    def has_budget(self) -> bool:
        """Check if budget information is available."""
        return self.budget_min is not None or self.budget_max is not None