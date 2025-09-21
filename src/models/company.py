"""Company profile model."""

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import BaseModel

if TYPE_CHECKING:
    from src.models.bid import BidResponse
    from src.models.match import CapabilityMatch


class CompanyProfile(BaseModel):
    """Model for company information and capabilities."""

    __tablename__ = "company_profiles"

    # Company information
    company_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    siret: Mapped[str] = mapped_column(
        String(14),
        unique=True,
        nullable=False,
        index=True,
        comment="French company registration number",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
    )

    # Structured data (JSON fields)
    capabilities_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="List of capabilities with keywords",
    )
    certifications_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="List of certifications with validity dates",
    )
    references_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="List of project references",
    )

    # Company metrics
    team_size: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
    )
    annual_revenue: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )
    founding_year: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
    )

    # Contact information
    contact_email: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )
    contact_phone: Mapped[str] = mapped_column(
        String(20),
        nullable=True,
    )
    address: Mapped[str] = mapped_column(
        Text,
        nullable=True,
    )

    # Versioning
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    # Relationships
    capability_matches: Mapped[list["CapabilityMatch"]] = relationship(
        "CapabilityMatch",
        back_populates="company_profile",
        cascade="all, delete-orphan",
        lazy="select",
    )

    bid_responses: Mapped[list["BidResponse"]] = relationship(
        "BidResponse",
        back_populates="company_profile",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<CompanyProfile(id={self.id}, name={self.company_name}, siret={self.siret})>"

    @property
    def has_certifications(self) -> bool:
        """Check if company has certifications."""
        return bool(self.certifications_json)

    @property
    def capability_count(self) -> int:
        """Get number of capabilities."""
        return len(self.capabilities_json)

    @property
    def years_in_business(self) -> int:
        """Calculate years in business."""
        if self.founding_year:
            from datetime import datetime
            return datetime.now().year - self.founding_year
        return 0
