"""Bid repository for bid response operations."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models.bid import BidResponse, ResponseStatus, ResponseType
from src.repositories.base import BaseRepository


class BidRepository(BaseRepository[BidResponse]):
    """
    Repository for BidResponse model with bid-specific operations.

    Extends BaseRepository with bid-specific methods:
    - Status-based filtering
    - User and company queries
    - Compliance tracking
    - Submission handling
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize bid repository."""
        super().__init__(BidResponse, db_session)

    async def create_bid_response(
        self,
        procurement_document_id: UUID,
        company_profile_id: UUID,
        capability_match_id: UUID,
        created_by: UUID,
        title: str,
        response_type: ResponseType = ResponseType.COMPLETE,
        content: Optional[dict] = None,
        tenant_id: Optional[UUID] = None
    ) -> BidResponse:
        """
        Create a new bid response.

        Args:
            procurement_document_id: UUID of the procurement document
            company_profile_id: UUID of the company profile
            capability_match_id: UUID of the capability match
            created_by: UUID of the user creating the response
            title: Title of the bid response
            response_type: Type of response (technical, commercial, complete)
            content: Initial content for the response
            tenant_id: Tenant ID for multi-tenancy

        Returns:
            Created bid response instance
        """
        return await self.create(
            procurement_document_id=procurement_document_id,
            company_profile_id=company_profile_id,
            capability_match_id=capability_match_id,
            created_by=created_by,
            title=title,
            response_type=response_type,
            status=ResponseStatus.DRAFT,
            content_json=content or {},
            compliance_score=0.0,
            compliance_issues_json={},
            tenant_id=tenant_id
        )

    async def get_by_user(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
        status: Optional[ResponseStatus] = None,
        tenant_id: Optional[UUID] = None
    ) -> list[BidResponse]:
        """
        Get bid responses created by a specific user.

        Args:
            user_id: UUID of the user
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Optional status filter
            tenant_id: Tenant ID for isolation

        Returns:
            List of bid responses created by the user
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

    async def get_by_company(
        self,
        company_profile_id: UUID,
        skip: int = 0,
        limit: int = 100,
        status: Optional[ResponseStatus] = None,
        tenant_id: Optional[UUID] = None
    ) -> list[BidResponse]:
        """
        Get bid responses for a specific company.

        Args:
            company_profile_id: UUID of the company profile
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Optional status filter
            tenant_id: Tenant ID for isolation

        Returns:
            List of bid responses for the company
        """
        filters = {"company_profile_id": company_profile_id}
        if status:
            filters["status"] = status

        return await self.get_multi(
            skip=skip,
            limit=limit,
            tenant_id=tenant_id,
            **filters
        )

    async def get_by_document(
        self,
        procurement_document_id: UUID,
        skip: int = 0,
        limit: int = 100,
        status: Optional[ResponseStatus] = None,
        tenant_id: Optional[UUID] = None
    ) -> list[BidResponse]:
        """
        Get bid responses for a specific procurement document.

        Args:
            procurement_document_id: UUID of the procurement document
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Optional status filter
            tenant_id: Tenant ID for isolation

        Returns:
            List of bid responses for the document
        """
        filters = {"procurement_document_id": procurement_document_id}
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
        status: ResponseStatus,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[BidResponse]:
        """
        Get bid responses by status.

        Args:
            status: Response status to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of bid responses with specified status
        """
        return await self.get_multi(
            skip=skip,
            limit=limit,
            tenant_id=tenant_id,
            status=status
        )

    async def update_status(
        self,
        bid_response_id: UUID,
        status: ResponseStatus,
        reviewed_by: Optional[UUID] = None,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Update bid response status.

        Args:
            bid_response_id: Bid response UUID
            status: New status
            reviewed_by: UUID of reviewing user (if applicable)
            tenant_id: Tenant ID for isolation

        Returns:
            True if status was updated, False if bid response not found
        """
        update_data = {"status": status}
        if reviewed_by is not None:
            update_data["reviewed_by"] = reviewed_by

        updated_bid = await self.update(
            id=bid_response_id,
            update_data=update_data,
            tenant_id=tenant_id
        )
        return updated_bid is not None

    async def update_content(
        self,
        bid_response_id: UUID,
        content: dict[str, Any],
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Update bid response content.

        Args:
            bid_response_id: Bid response UUID
            content: New content dictionary
            tenant_id: Tenant ID for isolation

        Returns:
            True if content was updated, False if bid response not found
        """
        updated_bid = await self.update(
            id=bid_response_id,
            update_data={"content_json": content},
            tenant_id=tenant_id
        )
        return updated_bid is not None

    async def update_compliance(
        self,
        bid_response_id: UUID,
        compliance_score: float,
        compliance_issues: dict[str, Any],
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Update bid response compliance information.

        Args:
            bid_response_id: Bid response UUID
            compliance_score: Compliance score (0-100)
            compliance_issues: Dictionary of compliance issues
            tenant_id: Tenant ID for isolation

        Returns:
            True if compliance was updated, False if bid response not found
        """
        updated_bid = await self.update(
            id=bid_response_id,
            update_data={
                "compliance_score": compliance_score,
                "compliance_issues_json": compliance_issues
            },
            tenant_id=tenant_id
        )
        return updated_bid is not None

    async def set_generated_file(
        self,
        bid_response_id: UUID,
        file_path: str,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Set the generated file path for a bid response.

        Args:
            bid_response_id: Bid response UUID
            file_path: Path to the generated file
            tenant_id: Tenant ID for isolation

        Returns:
            True if file path was set, False if bid response not found
        """
        updated_bid = await self.update(
            id=bid_response_id,
            update_data={"generated_file_path": file_path},
            tenant_id=tenant_id
        )
        return updated_bid is not None

    async def submit_response(
        self,
        bid_response_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Mark bid response as submitted.

        Args:
            bid_response_id: Bid response UUID
            tenant_id: Tenant ID for isolation

        Returns:
            True if response was submitted, False if bid response not found
        """
        updated_bid = await self.update(
            id=bid_response_id,
            update_data={
                "submitted_at": datetime.utcnow(),
                "status": ResponseStatus.FINAL
            },
            tenant_id=tenant_id
        )
        return updated_bid is not None

    async def get_draft_responses(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[BidResponse]:
        """
        Get all draft bid responses.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of draft bid responses
        """
        return await self.get_by_status(
            status=ResponseStatus.DRAFT,
            skip=skip,
            limit=limit,
            tenant_id=tenant_id
        )

    async def get_final_responses(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[BidResponse]:
        """
        Get all final bid responses.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of final bid responses
        """
        return await self.get_by_status(
            status=ResponseStatus.FINAL,
            skip=skip,
            limit=limit,
            tenant_id=tenant_id
        )

    async def get_submitted_responses(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[BidResponse]:
        """
        Get all submitted bid responses.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of submitted bid responses
        """
        query = select(BidResponse).where(
            BidResponse.submitted_at.is_not(None)
        )

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(BidResponse.tenant_id == tenant_id)

        # Filter out soft-deleted records
        query = query.where(BidResponse.deleted_at.is_(None))

        # Apply pagination and ordering
        query = query.offset(skip).limit(limit).order_by(
            BidResponse.submitted_at.desc()
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_by_compliance_score(
        self,
        min_score: float,
        max_score: float = 100.0,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[BidResponse]:
        """
        Get bid responses by compliance score range.

        Args:
            min_score: Minimum compliance score
            max_score: Maximum compliance score
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of bid responses within score range
        """
        query = select(BidResponse).where(
            BidResponse.compliance_score >= min_score,
            BidResponse.compliance_score <= max_score
        )

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(BidResponse.tenant_id == tenant_id)

        # Filter out soft-deleted records
        query = query.where(BidResponse.deleted_at.is_(None))

        # Apply pagination and ordering
        query = query.offset(skip).limit(limit).order_by(
            BidResponse.compliance_score.desc()
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_with_relationships(
        self,
        bid_response_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> Optional[BidResponse]:
        """
        Get bid response with all relationships loaded.

        Args:
            bid_response_id: Bid response UUID
            tenant_id: Tenant ID for isolation

        Returns:
            Bid response with relationships if found, None otherwise
        """
        query = select(BidResponse).options(
            joinedload(BidResponse.procurement_document),
            joinedload(BidResponse.company_profile),
            joinedload(BidResponse.capability_match),
            joinedload(BidResponse.creator),
            joinedload(BidResponse.reviewer),
            joinedload(BidResponse.compliance_checks)
        ).where(BidResponse.id == bid_response_id)

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(BidResponse.tenant_id == tenant_id)

        # Filter out soft-deleted records
        query = query.where(BidResponse.deleted_at.is_(None))

        result = await self.db.execute(query)
        return result.unique().scalar_one_or_none()

    async def count_by_status(
        self,
        status: ResponseStatus,
        tenant_id: Optional[UUID] = None
    ) -> int:
        """
        Count bid responses by status.

        Args:
            status: Response status to count
            tenant_id: Tenant ID for isolation

        Returns:
            Number of bid responses with specified status
        """
        return await self.count(tenant_id=tenant_id, status=status)

    async def increment_version(
        self,
        bid_response_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Increment bid response version.

        Args:
            bid_response_id: Bid response UUID
            tenant_id: Tenant ID for isolation

        Returns:
            True if version was incremented, False if bid response not found
        """
        bid_response = await self.get_by_id(bid_response_id, tenant_id=tenant_id)
        if bid_response is None:
            return False

        updated_bid = await self.update(
            id=bid_response_id,
            update_data={"version": bid_response.version + 1},
            tenant_id=tenant_id
        )
        return updated_bid is not None
