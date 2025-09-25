"""Procurement document model."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import BaseModel
from src.models.document_type import DocumentType

if TYPE_CHECKING:
    from src.models.bid import BidResponse
    from src.models.events import ProcessingEvent
    from src.models.procurement_tender import ProcurementTender
    from src.models.requirements import ExtractedRequirements
    from src.models.user import User


class DocumentStatus(str, Enum):
    """Document processing status enumeration."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class ProcurementDocument(BaseModel):
    """Model for uploaded procurement PDF documents."""

    __tablename__ = "procurement_documents"

    # File information
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Encrypted file path on storage",
    )
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="File size in bytes",
    )
    file_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 hash of file",
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="application/pdf",
    )

    # Processing status
    status: Mapped[DocumentStatus] = mapped_column(
        String(20),
        nullable=False,
        default=DocumentStatus.UPLOADED,
        index=True,
    )
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
    )
    processing_completed_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
    )
    processing_duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Processing duration in milliseconds",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Versioning
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    # Document type and tender association
    tender_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("procurement_tenders.id"),
        nullable=True,
        index=True,
        comment="Associated tender ID",
    )

    document_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Type of document (RC, CCAP, CCTP, etc.)",
    )

    is_mandatory: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this document type is mandatory for the tender",
    )

    # Cross-references and metadata
    cross_references: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="References to other documents in the tender",
    )

    extraction_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Extracted metadata specific to document type",
    )

    # Foreign keys
    uploaded_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    # Relationships
    uploaded_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="procurement_documents",
        lazy="select",
    )

    tender: Mapped[Optional["ProcurementTender"]] = relationship(
        "ProcurementTender",
        back_populates="documents",
        lazy="select",
    )

    extracted_requirements: Mapped[Optional["ExtractedRequirements"]] = relationship(
        "ExtractedRequirements",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )

    bid_responses: Mapped[list["BidResponse"]] = relationship(
        "BidResponse",
        back_populates="procurement_document",
        cascade="all, delete-orphan",
        lazy="select",
    )

    processing_events: Mapped[list["ProcessingEvent"]] = relationship(
        "ProcessingEvent",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="ProcessingEvent.created_at",
    )

    def __repr__(self) -> str:
        """String representation."""
        tender_ref = f", tender={self.tender.reference}" if self.tender else ""
        return f"<ProcurementDocument(id={self.id}, filename={self.original_filename}, type={self.document_type}{tender_ref})>"

    @property
    def is_processed(self) -> bool:
        """Check if document is processed."""
        return self.status == DocumentStatus.PROCESSED

    @property
    def is_failed(self) -> bool:
        """Check if document processing failed."""
        return self.status == DocumentStatus.FAILED

    @property
    def processing_duration_seconds(self) -> Optional[float]:
        """Get processing duration in seconds."""
        if self.processing_duration_ms:
            return self.processing_duration_ms / 1000.0
        return None

    @property
    def document_type_enum(self) -> Optional[DocumentType]:
        """Get document type as enum."""
        if self.document_type:
            try:
                return DocumentType(self.document_type)
            except ValueError:
                return DocumentType.OTHER
        return None
