"""Requirements repository for extracted requirements operations."""

from typing import Optional, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.extracted_requirement import ExtractedRequirement
from src.repositories.base import BaseRepository


class RequirementsRepository(BaseRepository[ExtractedRequirement]):
    """Repository for ExtractedRequirement model with requirements-specific operations."""

    def __init__(self, db_session: AsyncSession):
        """Initialize requirements repository."""
        super().__init__(ExtractedRequirement, db_session)

    async def create_requirement(
        self,
        document_id: UUID,
        category: str,
        description: str,
        importance: str = "medium",
        is_mandatory: bool = False,
        extracted_text: str = "",
        confidence_score: float = 0.8,
        tenant_id: Optional[UUID] = None
    ) -> ExtractedRequirement:
        """
        Create a new extracted requirement.

        Args:
            document_id: UUID of the source document
            category: Requirement category
            description: Requirement description
            importance: Importance level (low, medium, high, critical)
            is_mandatory: Whether requirement is mandatory
            extracted_text: Original extracted text
            confidence_score: AI confidence score (0-1)
            tenant_id: Tenant ID for multi-tenancy

        Returns:
            Created requirement instance
        """
        return await self.create(
            document_id=document_id,
            category=category,
            description=description,
            importance=importance,
            is_mandatory=is_mandatory,
            extracted_text=extracted_text,
            confidence_score=confidence_score,
            tenant_id=tenant_id
        )

    async def get_by_document(
        self,
        document_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> List[ExtractedRequirement]:
        """
        Get all requirements for a specific document.

        Args:
            document_id: UUID of the document
            tenant_id: Tenant ID for isolation

        Returns:
            List of requirements for the document
        """
        return await self.get_multi(
            document_id=document_id,
            tenant_id=tenant_id
        )

    async def get_by_category(
        self,
        category: str,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> List[ExtractedRequirement]:
        """
        Get requirements by category.

        Args:
            category: Requirement category
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of requirements in the category
        """
        return await self.get_multi(
            skip=skip,
            limit=limit,
            category=category,
            tenant_id=tenant_id
        )

    async def get_by_tender(
        self,
        tender_id: UUID,
        category: Optional[str] = None,
        is_mandatory: Optional[bool] = None,
        tenant_id: Optional[UUID] = None
    ) -> List[ExtractedRequirement]:
        """
        Get all requirements for a specific tender.

        Args:
            tender_id: UUID of the tender
            category: Optional category filter
            is_mandatory: Optional mandatory filter
            tenant_id: Tenant ID for isolation

        Returns:
            List of requirements for the tender
        """
        query = select(ExtractedRequirement).where(
            ExtractedRequirement.tender_id == tender_id
        )

        if tenant_id is not None:
            query = query.where(ExtractedRequirement.tenant_id == tenant_id)

        if category is not None:
            query = query.where(ExtractedRequirement.category == category)

        if is_mandatory is not None:
            query = query.where(ExtractedRequirement.is_mandatory == is_mandatory)

        # Filter out soft-deleted records
        query = query.where(ExtractedRequirement.deleted_at.is_(None))

        result = await self.db.execute(query)
        return result.scalars().all()