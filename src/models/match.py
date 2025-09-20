"""Capability matching model."""

from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Float, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import BaseModel

if TYPE_CHECKING:
    from src.models.bid import BidResponse
    from src.models.company import CompanyProfile
    from src.models.requirements import ExtractedRequirements


class MatchRecommendation(str, Enum):
    """Match recommendation enumeration."""

    GO = "go"
    NO_GO = "no_go"
    REVIEW_NEEDED = "review_needed"


class CapabilityMatch(BaseModel):
    """Model for capability matching analysis results."""

    __tablename__ = "capability_matches"

    # Foreign keys
    extracted_requirements_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("extracted_requirements.id"),
        nullable=False,
        index=True,
    )
    company_profile_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("company_profiles.id"),
        nullable=False,
        index=True,
    )

    # Scoring
    overall_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        index=True,
        comment="Overall match score (0-100)",
    )
    technical_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Technical match score (0-100)",
    )
    functional_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Functional match score (0-100)",
    )

    # Analysis results (JSON fields)
    gaps_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Identified capability gaps",
    )
    strengths_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Matching strengths",
    )
    match_details_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Detailed matching analysis",
    )

    # Recommendation
    recommendation: Mapped[MatchRecommendation] = mapped_column(
        String(20),
        nullable=False,
        default=MatchRecommendation.REVIEW_NEEDED,
        index=True,
    )
    confidence_level: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5,
        comment="Confidence level of recommendation (0-1)",
    )

    # Relationships
    extracted_requirements: Mapped["ExtractedRequirements"] = relationship(
        "ExtractedRequirements",
        back_populates="capability_matches",
        lazy="select",
    )

    company_profile: Mapped["CompanyProfile"] = relationship(
        "CompanyProfile",
        back_populates="capability_matches",
        lazy="select",
    )

    bid_response: Mapped[Optional["BidResponse"]] = relationship(
        "BidResponse",
        back_populates="capability_match",
        uselist=False,
        lazy="select",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<CapabilityMatch(id={self.id}, score={self.overall_score}, recommendation={self.recommendation})>"

    @property
    def is_recommended(self) -> bool:
        """Check if match is recommended."""
        return self.recommendation == MatchRecommendation.GO

    @property
    def needs_review(self) -> bool:
        """Check if match needs review."""
        return self.recommendation == MatchRecommendation.REVIEW_NEEDED

    @property
    def has_critical_gaps(self) -> bool:
        """Check if there are critical capability gaps."""
        if self.gaps_json:
            return any(gap.get("severity") == "critical"
                      for gap in self.gaps_json.get("items", []))
        return False