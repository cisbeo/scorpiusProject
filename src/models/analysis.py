"""Analysis history model for tracking AI analysis operations."""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy import JSON, String, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import BaseModel


class AnalysisStatus(str, Enum):
    """Analysis status enumeration."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalysisHistory(BaseModel):
    """Model for tracking AI analysis operations."""

    __tablename__ = "analysis_history"

    # Analysis identification
    tender_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("procurement_tenders.id"),
        nullable=False,
        index=True,
        comment="Associated tender ID"
    )

    analysis_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Type of analysis (requirements_extraction, duplicate_detection, etc.)"
    )

    status: Mapped[AnalysisStatus] = mapped_column(
        String(20),
        nullable=False,
        default=AnalysisStatus.PENDING,
        index=True,
        comment="Current status of the analysis"
    )

    # Timing information
    started_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="When the analysis started"
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="When the analysis completed"
    )

    # Analysis metadata and results
    analysis_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Analysis metadata and configuration"
    )

    results: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Analysis results summary"
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if analysis failed"
    )

    # Performance metrics
    processing_time_ms: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="Total processing time in milliseconds"
    )

    tokens_used: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="Number of AI tokens consumed"
    )

    # User tracking
    triggered_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
        comment="User who triggered the analysis"
    )