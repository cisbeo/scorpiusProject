"""Individual extracted requirement model."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import BaseModel


class ExtractedRequirement(BaseModel):
    """Model for individual requirements extracted from documents."""

    __tablename__ = "extracted_requirement"

    # Foreign keys
    tender_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("procurement_tenders.id"),
        nullable=False,
        index=True,
    )

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("procurement_documents.id"),
        nullable=False,
        index=True,
    )

    # Requirement content
    requirement_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The extracted requirement text",
    )

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="other",
        comment="Category: functional, technical, security, performance, compliance, financial, administrative, other",
    )

    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium",
        comment="Priority: critical, high, medium, low",
    )

    is_mandatory: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the requirement is mandatory",
    )

    # Source information
    source_document: Mapped[str] = mapped_column(
        String(100),
        nullable=True,
        comment="Document type this was extracted from",
    )

    page_number: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="Page number in the document",
    )

    # Confidence and metadata
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Extraction confidence score (0-1)",
    )

    extraction_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional extraction metadata",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<ExtractedRequirement(id={self.id}, category={self.category}, priority={self.priority})>"