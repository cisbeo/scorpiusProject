"""Processing event model."""

from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import BaseModel

if TYPE_CHECKING:
    from src.models.document import ProcurementDocument


class ProcessingStage(str, Enum):
    """Processing stage enumeration."""

    UPLOAD = "upload"
    VALIDATION = "validation"
    EXTRACTION = "extraction"
    ANALYSIS = "analysis"
    GENERATION = "generation"


class EventStatus(str, Enum):
    """Event status enumeration."""

    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingEvent(BaseModel):
    """Model for document processing pipeline audit trail."""

    __tablename__ = "processing_events"

    # Foreign key
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("procurement_documents.id"),
        nullable=False,
        index=True,
    )

    # Event information
    stage: Mapped[ProcessingStage] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    status: Mapped[EventStatus] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Event duration in milliseconds",
    )

    # Metadata (JSON field)
    metadata_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Event metadata and context",
    )

    # Error information
    error_details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error details if event failed",
    )

    # Relationship
    document: Mapped["ProcurementDocument"] = relationship(
        "ProcurementDocument",
        back_populates="processing_events",
        lazy="select",
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<ProcessingEvent(id={self.id}, document_id={self.document_id}, "
            f"stage={self.stage}, status={self.status})>"
        )

    @property
    def is_started(self) -> bool:
        """Check if event is started."""
        return self.status == EventStatus.STARTED

    @property
    def is_completed(self) -> bool:
        """Check if event is completed."""
        return self.status == EventStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if event failed."""
        return self.status == EventStatus.FAILED

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get duration in seconds."""
        if self.duration_ms:
            return self.duration_ms / 1000.0
        return None