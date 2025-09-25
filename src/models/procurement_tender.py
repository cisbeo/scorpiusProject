"""Procurement tender (appel d'offres) model."""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import DECIMAL, ForeignKey, JSON, String, Text, Float
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import BaseModel

if TYPE_CHECKING:
    from src.models.bid import BidResponse
    from src.models.document import ProcurementDocument
    from src.models.user import User


class TenderStatus(str, Enum):
    """Tender status enumeration."""

    DRAFT = "draft"                # En cours de constitution
    ANALYZING = "analyzing"         # En cours d'analyse
    READY = "ready"                # Prêt pour réponse
    SUBMITTED = "submitted"        # Réponse soumise
    AWARDED = "awarded"            # Marché attribué (nous)
    REJECTED = "rejected"          # Marché rejeté (pas nous)
    CANCELLED = "cancelled"        # Annulé par l'acheteur
    ARCHIVED = "archived"          # Archivé


class ProcurementTender(BaseModel):
    """
    Model for procurement tenders (appels d'offres).

    Represents a complete tender with all its associated documents.
    Each tender groups multiple documents (CCTP, CCAP, RC, etc.)
    that need to be analyzed together.
    """

    __tablename__ = "procurement_tenders"

    # Basic information
    reference: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        comment="Tender reference number (e.g., VSGP-2024-001)",
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Tender title",
    )

    organization: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Issuing organization",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed description of the tender",
    )

    # Timeline
    deadline_date: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Submission deadline",
        index=True,
    )

    publication_date: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Publication date of the tender",
    )

    # Status and budget
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=TenderStatus.DRAFT.value,
        comment="Current status of the tender",
        index=True,
    )

    budget_estimate: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(15, 2),
        nullable=True,
        comment="Estimated budget in euros",
    )

    # Analysis results (will be populated by analysis service)
    global_analysis: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Consolidated analysis of all documents",
    )

    matching_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Overall matching score (0-100)",
    )

    # User relationship
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        comment="User who created the tender",
    )

    # Relationships
    creator: Mapped["User"] = relationship(
        "User",
        back_populates="tenders",
        lazy="joined",
    )

    documents: Mapped[list["ProcurementDocument"]] = relationship(
        "ProcurementDocument",
        back_populates="tender",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    bid_responses: Mapped[list["BidResponse"]] = relationship(
        "BidResponse",
        back_populates="tender",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation of the tender."""
        return f"<ProcurementTender(reference={self.reference}, title={self.title})>"

    @property
    def is_complete(self) -> bool:
        """Check if all mandatory documents are present."""
        from src.models.document_type import MANDATORY_DOCUMENT_TYPES

        if not self.documents:
            return False

        present_types = {doc.document_type for doc in self.documents if doc.document_type}
        return MANDATORY_DOCUMENT_TYPES.issubset(present_types)

    @property
    def days_until_deadline(self) -> Optional[int]:
        """Calculate days remaining until deadline."""
        if not self.deadline_date:
            return None

        current_time = datetime.now(timezone.utc)
        # Ensure deadline_date is timezone-aware
        deadline = self.deadline_date
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)

        delta = deadline - current_time
        return delta.days if delta.days > 0 else 0

    @property
    def document_count(self) -> int:
        """Get the number of associated documents."""
        return len(self.documents) if self.documents else 0