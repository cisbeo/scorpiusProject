"""Match repository for capability matches operations."""

from typing import Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.match import CapabilityMatch, MatchRecommendation
from src.repositories.base import BaseRepository


class MatchRepository(BaseRepository[CapabilityMatch]):
    """Repository for CapabilityMatch model with matching-specific operations."""

    def __init__(self, db_session: AsyncSession):
        """Initialize match repository."""
        super().__init__(CapabilityMatch, db_session)

    async def create_match(
        self,
        tender_id: UUID,
        requirement_category: str,
        our_capability_score: float,
        market_competitiveness: str,
        risk_level: str,
        effort_estimate: int,
        confidence_score: float = 0.8,
        tenant_id: Optional[UUID] = None
    ) -> CapabilityMatch:
        """
        Create a new capability match.

        Args:
            tender_id: UUID of the tender
            requirement_category: Category of requirements being matched
            our_capability_score: Our capability score (0-100)
            market_competitiveness: Market competitiveness level
            risk_level: Risk level assessment
            effort_estimate: Estimated effort in hours/days
            confidence_score: Confidence in the assessment
            tenant_id: Tenant ID for multi-tenancy

        Returns:
            Created capability match instance
        """
        return await self.create(
            tender_id=tender_id,
            requirement_category=requirement_category,
            our_capability_score=our_capability_score,
            market_competitiveness=market_competitiveness,
            risk_level=risk_level,
            effort_estimate=effort_estimate,
            confidence_score=confidence_score,
            tenant_id=tenant_id
        )

    async def get_by_tender(
        self,
        tender_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> List[CapabilityMatch]:
        """
        Get all capability matches for a tender.

        Args:
            tender_id: UUID of the tender
            tenant_id: Tenant ID for isolation

        Returns:
            List of capability matches for the tender
        """
        return await self.get_multi(
            tender_id=tender_id,
            tenant_id=tenant_id
        )

    async def get_by_category(
        self,
        requirement_category: str,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> List[CapabilityMatch]:
        """
        Get matches by requirement category.

        Args:
            requirement_category: Category to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of matches in the category
        """
        return await self.get_multi(
            skip=skip,
            limit=limit,
            requirement_category=requirement_category,
            tenant_id=tenant_id
        )