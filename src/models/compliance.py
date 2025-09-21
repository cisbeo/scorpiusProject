"""Compliance check model."""

from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import BaseModel

if TYPE_CHECKING:
    from src.models.bid import BidResponse


class ComplianceStatus(str, Enum):
    """Compliance check status enumeration."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"


class ComplianceSeverity(str, Enum):
    """Compliance issue severity enumeration."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class ComplianceCheck(BaseModel):
    """Model for compliance validation results."""

    __tablename__ = "compliance_checks"

    # Foreign key
    bid_response_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("bid_responses.id"),
        nullable=False,
        index=True,
    )

    # Check details
    rule_category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Category of compliance rule",
    )
    rule_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Name of compliance rule",
    )
    status: Mapped[ComplianceStatus] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Compliance check message",
    )
    severity: Mapped[ComplianceSeverity] = mapped_column(
        String(20),
        nullable=False,
        default=ComplianceSeverity.MINOR,
        index=True,
    )
    auto_fixable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether issue can be auto-fixed",
    )

    # Relationship
    bid_response: Mapped["BidResponse"] = relationship(
        "BidResponse",
        back_populates="compliance_checks",
        lazy="select",
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<ComplianceCheck(id={self.id}, rule={self.rule_name}, "
            f"status={self.status}, severity={self.severity})>"
        )

    @property
    def is_passed(self) -> bool:
        """Check if compliance check passed."""
        return self.status == ComplianceStatus.PASSED

    @property
    def is_failed(self) -> bool:
        """Check if compliance check failed."""
        return self.status == ComplianceStatus.FAILED

    @property
    def is_warning(self) -> bool:
        """Check if compliance check is a warning."""
        return self.status == ComplianceStatus.WARNING

    @property
    def is_critical(self) -> bool:
        """Check if issue is critical."""
        return self.severity == ComplianceSeverity.CRITICAL
