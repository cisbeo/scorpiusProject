"""Tender repository for procurement tender operations."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models.procurement_tender import ProcurementTender, TenderStatus
from src.repositories.base import BaseRepository


class TenderRepository(BaseRepository[ProcurementTender]):
    """
    Repository for ProcurementTender model with tender-specific operations.

    Extends BaseRepository with tender-specific methods:
    - Status-based filtering
    - User tender queries
    - Document relationship management
    - Deadline tracking
    - Analysis results management
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize tender repository."""
        super().__init__(ProcurementTender, db_session)

    async def create_tender(
        self,
        reference: str,
        title: str,
        organization: str,
        created_by: UUID,
        description: Optional[str] = None,
        deadline_date: Optional[datetime] = None,
        publication_date: Optional[datetime] = None,
        budget_estimate: Optional[float] = None,
        tenant_id: Optional[UUID] = None
    ) -> ProcurementTender:
        """
        Create a new procurement tender.

        Args:
            reference: Unique tender reference (e.g., VSGP-2024-001)
            title: Tender title
            organization: Issuing organization
            created_by: UUID of the user who created the tender
            description: Optional detailed description
            deadline_date: Submission deadline
            publication_date: Publication date
            budget_estimate: Estimated budget in euros
            tenant_id: Tenant ID for multi-tenancy

        Returns:
            Created tender instance
        """
        return await self.create(
            reference=reference,
            title=title,
            organization=organization,
            created_by=created_by,
            description=description,
            deadline_date=deadline_date,
            publication_date=publication_date,
            budget_estimate=budget_estimate,
            status=TenderStatus.DRAFT,
            tenant_id=tenant_id
        )

    async def get_by_reference(
        self,
        reference: str,
        tenant_id: Optional[UUID] = None
    ) -> Optional[ProcurementTender]:
        """
        Get tender by reference number.

        Args:
            reference: Tender reference (e.g., VSGP-2024-001)
            tenant_id: Tenant ID for isolation

        Returns:
            Tender instance if found, None otherwise
        """
        return await self.get_by_field(
            field_name="reference",
            field_value=reference,
            tenant_id=tenant_id
        )

    async def get_by_user(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
        status: Optional[TenderStatus] = None,
        tenant_id: Optional[UUID] = None
    ) -> list[ProcurementTender]:
        """
        Get tenders created by a specific user.

        Args:
            user_id: UUID of the user
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Optional status filter
            tenant_id: Tenant ID for isolation

        Returns:
            List of tenders created by the user
        """
        filters = {"created_by": user_id}
        if status:
            filters["status"] = status

        return await self.get_multi(
            skip=skip,
            limit=limit,
            tenant_id=tenant_id,
            **filters
        )

    async def get_by_status(
        self,
        status: TenderStatus,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[ProcurementTender]:
        """
        Get tenders by status.

        Args:
            status: Tender status to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of tenders with specified status
        """
        return await self.get_multi(
            skip=skip,
            limit=limit,
            tenant_id=tenant_id,
            status=status
        )

    async def get_with_documents(
        self,
        tender_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> Optional[ProcurementTender]:
        """
        Get tender with all its documents loaded.

        Args:
            tender_id: Tender UUID
            tenant_id: Tenant ID for isolation

        Returns:
            Tender with documents if found, None otherwise
        """
        # Import here to avoid circular imports
        from src.models.document import ProcurementDocument

        query = select(ProcurementTender).options(
            joinedload(ProcurementTender.documents).joinedload(
                ProcurementDocument.extracted_requirements
            )
        ).where(ProcurementTender.id == tender_id)

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(ProcurementTender.tenant_id == tenant_id)

        # Filter out soft-deleted records
        query = query.where(ProcurementTender.deleted_at.is_(None))

        result = await self.db.execute(query)
        return result.unique().scalar_one_or_none()

    async def get_expiring_soon(
        self,
        days_ahead: int = 7,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[ProcurementTender]:
        """
        Get tenders expiring within specified days.

        Args:
            days_ahead: Number of days to look ahead for deadlines
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of tenders expiring soon
        """
        current_time = datetime.now(timezone.utc)
        cutoff_date = current_time + timedelta(days=days_ahead)

        query = select(ProcurementTender).where(
            ProcurementTender.deadline_date.is_not(None),
            ProcurementTender.deadline_date <= cutoff_date,
            ProcurementTender.deadline_date > current_time,
            ProcurementTender.status.in_([TenderStatus.DRAFT, TenderStatus.ANALYZING, TenderStatus.READY])
        )

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(ProcurementTender.tenant_id == tenant_id)

        # Filter out soft-deleted records
        query = query.where(ProcurementTender.deleted_at.is_(None))

        # Apply pagination and ordering by deadline
        query = query.offset(skip).limit(limit).order_by(
            ProcurementTender.deadline_date.asc()
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_by_organization(
        self,
        organization: str,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[ProcurementTender]:
        """
        Get tenders by issuing organization.

        Args:
            organization: Organization name
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of tenders from specified organization
        """
        return await self.get_multi(
            skip=skip,
            limit=limit,
            tenant_id=tenant_id,
            organization=organization
        )

    async def update_status(
        self,
        tender_id: UUID,
        new_status: TenderStatus,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Update tender status.

        Args:
            tender_id: Tender UUID
            new_status: New status to set
            tenant_id: Tenant ID for isolation

        Returns:
            True if status was updated, False if tender not found
        """
        updated_tender = await self.update(
            id=tender_id,
            update_data={"status": new_status},
            tenant_id=tenant_id
        )
        return updated_tender is not None

    async def update_analysis(
        self,
        tender_id: UUID,
        global_analysis: dict,
        matching_score: Optional[float] = None,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Update tender analysis results.

        Args:
            tender_id: Tender UUID
            global_analysis: Consolidated analysis results
            matching_score: Overall matching score (0-100)
            tenant_id: Tenant ID for isolation

        Returns:
            True if analysis was updated, False if tender not found
        """
        update_data = {"global_analysis": global_analysis}
        if matching_score is not None:
            update_data["matching_score"] = matching_score

        updated_tender = await self.update(
            id=tender_id,
            update_data=update_data,
            tenant_id=tenant_id
        )
        return updated_tender is not None

    async def get_ready_for_analysis(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[ProcurementTender]:
        """
        Get tenders that have documents but no analysis yet.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of tenders ready for analysis
        """
        # Select tenders with documents but no global analysis
        query = select(ProcurementTender).join(
            ProcurementTender.documents
        ).where(
            ProcurementTender.global_analysis.is_(None),
            ProcurementTender.status.in_([TenderStatus.DRAFT, TenderStatus.ANALYZING])
        )

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(ProcurementTender.tenant_id == tenant_id)

        # Filter out soft-deleted records
        query = query.where(ProcurementTender.deleted_at.is_(None))

        # Apply pagination and ordering
        query = query.offset(skip).limit(limit).order_by(
            ProcurementTender.created_at.desc()
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def count_by_status(
        self,
        status: TenderStatus,
        tenant_id: Optional[UUID] = None
    ) -> int:
        """
        Count tenders by status.

        Args:
            status: Tender status to count
            tenant_id: Tenant ID for isolation

        Returns:
            Number of tenders with specified status
        """
        return await self.count(tenant_id=tenant_id, status=status)

    async def get_with_complete_data(
        self,
        tender_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> Optional[ProcurementTender]:
        """
        Get tender with all related data (documents, bid responses).

        Args:
            tender_id: Tender UUID
            tenant_id: Tenant ID for isolation

        Returns:
            Tender with all relationships loaded if found, None otherwise
        """
        # Import here to avoid circular imports
        from src.models.document import ProcurementDocument

        query = select(ProcurementTender).options(
            joinedload(ProcurementTender.documents).joinedload(
                ProcurementDocument.extracted_requirements
            ),
            joinedload(ProcurementTender.documents).joinedload(
                ProcurementDocument.processing_events
            )
        ).where(ProcurementTender.id == tender_id)

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(ProcurementTender.tenant_id == tenant_id)

        # Filter out soft-deleted records
        query = query.where(ProcurementTender.deleted_at.is_(None))

        result = await self.db.execute(query)
        return result.unique().scalar_one_or_none()

    async def search_tenders(
        self,
        search_term: str,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[ProcurementTender]:
        """
        Search tenders by title, reference, or organization.

        Args:
            search_term: Term to search for
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of matching tenders
        """
        search_pattern = f"%{search_term.lower()}%"

        query = select(ProcurementTender).where(
            ProcurementTender.title.ilike(search_pattern) |
            ProcurementTender.reference.ilike(search_pattern) |
            ProcurementTender.organization.ilike(search_pattern) |
            ProcurementTender.description.ilike(search_pattern)
        )

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(ProcurementTender.tenant_id == tenant_id)

        # Filter out soft-deleted records
        query = query.where(ProcurementTender.deleted_at.is_(None))

        # Apply pagination and ordering by relevance (could be enhanced)
        query = query.offset(skip).limit(limit).order_by(
            ProcurementTender.updated_at.desc()
        )

        result = await self.db.execute(query)
        return result.scalars().all()