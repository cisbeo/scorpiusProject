"""Tender service for business logic and orchestration."""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document_type import DocumentType, detect_document_type_from_filename
from src.models.procurement_tender import ProcurementTender, TenderStatus
from src.models.document import ProcurementDocument, DocumentStatus
from src.repositories.tender_repository import TenderRepository
from src.repositories.document_repository import DocumentRepository
from src.core.exceptions import NotFoundError, ValidationError, BusinessLogicError


class TenderService:
    """
    Service for tender business logic and orchestration.

    Handles tender lifecycle management, document association,
    validation, and multi-document analysis coordination.
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize tender service with repositories."""
        self.db = db_session
        self.tender_repo = TenderRepository(db_session)
        self.document_repo = DocumentRepository(db_session)

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
        Create a new procurement tender with validation.

        Args:
            reference: Unique tender reference (e.g., VSGP-2024-001)
            title: Tender title
            organization: Issuing organization
            created_by: UUID of the user creating the tender
            description: Optional detailed description
            deadline_date: Submission deadline
            publication_date: Publication date
            budget_estimate: Estimated budget in euros
            tenant_id: Tenant ID for multi-tenancy

        Returns:
            Created tender instance

        Raises:
            ValidationError: If reference already exists or validation fails
        """
        # Check if reference already exists
        existing_tender = await self.tender_repo.get_by_reference(
            reference=reference,
            tenant_id=tenant_id
        )
        if existing_tender:
            raise ValidationError(f"Tender reference '{reference}' already exists")

        # Validate deadline is in the future
        if deadline_date:
            # Ensure both datetimes are timezone-aware for comparison
            current_time = datetime.now(timezone.utc)
            # If deadline_date is naive, make it UTC aware
            if deadline_date.tzinfo is None:
                deadline_date = deadline_date.replace(tzinfo=timezone.utc)
            if deadline_date <= current_time:
                raise ValidationError("Deadline must be in the future")

        # Validate budget is positive
        if budget_estimate is not None and budget_estimate <= 0:
            raise ValidationError("Budget estimate must be positive")

        # Create the tender
        return await self.tender_repo.create_tender(
            reference=reference,
            title=title,
            organization=organization,
            created_by=created_by,
            description=description,
            deadline_date=deadline_date,
            publication_date=publication_date,
            budget_estimate=budget_estimate,
            tenant_id=tenant_id
        )

    async def get_tender_with_documents(
        self,
        tender_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> ProcurementTender:
        """
        Get tender with all associated documents.

        Args:
            tender_id: Tender UUID
            tenant_id: Tenant ID for isolation

        Returns:
            Tender with loaded documents

        Raises:
            NotFoundError: If tender not found
        """
        tender = await self.tender_repo.get_with_documents(
            tender_id=tender_id,
            tenant_id=tenant_id
        )
        if not tender:
            raise NotFoundError(f"Tender {tender_id} not found")

        return tender

    async def add_document_to_tender(
        self,
        tender_id: UUID,
        document_id: UUID,
        document_type: Optional[DocumentType] = None,
        is_mandatory: Optional[bool] = None,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Associate an existing document with a tender.

        Args:
            tender_id: UUID of the tender
            document_id: UUID of the document
            document_type: Optional document type classification
            is_mandatory: Whether document is mandatory for tender
            tenant_id: Tenant ID for isolation

        Returns:
            True if association successful

        Raises:
            NotFoundError: If tender or document not found
            BusinessLogicError: If document already associated with another tender
        """
        # Verify tender exists
        tender = await self.tender_repo.get_by_id(tender_id, tenant_id)
        if not tender:
            raise NotFoundError(f"Tender {tender_id} not found")

        # Verify document exists
        document = await self.document_repo.get_by_id(document_id, tenant_id)
        if not document:
            raise NotFoundError(f"Document {document_id} not found")

        # Check if document is already associated with another tender
        if document.tender_id and document.tender_id != tender_id:
            raise BusinessLogicError(
                f"Document {document_id} is already associated with tender {document.tender_id}"
            )

        # Auto-detect document type if not provided
        if document_type is None:
            document_type = detect_document_type_from_filename(document.original_filename)

        # Associate document with tender
        return await self.document_repo.associate_with_tender(
            document_id=document_id,
            tender_id=tender_id,
            document_type=document_type,
            is_mandatory=is_mandatory,
            tenant_id=tenant_id
        )

    async def remove_document_from_tender(
        self,
        tender_id: UUID,
        document_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Remove document association from tender (make it orphaned).

        Args:
            tender_id: UUID of the tender
            document_id: UUID of the document
            tenant_id: Tenant ID for isolation

        Returns:
            True if dissociation successful

        Raises:
            NotFoundError: If document not found or not associated with tender
        """
        document = await self.document_repo.get_by_id(document_id, tenant_id)
        if not document:
            raise NotFoundError(f"Document {document_id} not found")

        if document.tender_id != tender_id:
            raise NotFoundError(f"Document {document_id} is not associated with tender {tender_id}")

        # Remove tender association
        return await self.document_repo.associate_with_tender(
            document_id=document_id,
            tender_id=None,
            document_type=None,
            is_mandatory=False,
            tenant_id=tenant_id
        )

    async def get_tender_documents_by_type(
        self,
        tender_id: UUID,
        document_type: DocumentType,
        tenant_id: Optional[UUID] = None
    ) -> List[ProcurementDocument]:
        """
        Get tender documents of a specific type.

        Args:
            tender_id: UUID of the tender
            document_type: Type of documents to retrieve
            tenant_id: Tenant ID for isolation

        Returns:
            List of documents of specified type
        """
        return await self.document_repo.get_by_tender_and_type(
            tender_id=tender_id,
            document_type=document_type,
            tenant_id=tenant_id
        )

    async def get_tender_completeness(
        self,
        tender_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Analyze tender completeness based on document requirements.

        Args:
            tender_id: UUID of the tender
            tenant_id: Tenant ID for isolation

        Returns:
            Dictionary with completeness analysis

        Raises:
            NotFoundError: If tender not found
        """
        tender = await self.tender_repo.get_by_id(tender_id, tenant_id)
        if not tender:
            raise NotFoundError(f"Tender {tender_id} not found")

        # Get all documents for this tender
        documents = await self.document_repo.get_by_tender(
            tender_id=tender_id,
            tenant_id=tenant_id
        )

        # Analyze by document type
        document_types = {}
        for doc in documents:
            doc_type = doc.document_type or "unknown"
            if doc_type not in document_types:
                document_types[doc_type] = {
                    "count": 0,
                    "mandatory_count": 0,
                    "processed_count": 0,
                    "failed_count": 0
                }

            document_types[doc_type]["count"] += 1
            if doc.is_mandatory:
                document_types[doc_type]["mandatory_count"] += 1
            if doc.status == DocumentStatus.PROCESSED:
                document_types[doc_type]["processed_count"] += 1
            elif doc.status == DocumentStatus.FAILED:
                document_types[doc_type]["failed_count"] += 1

        # Expected document types for French tenders
        expected_types = [dt.value for dt in DocumentType]
        missing_types = [
            dt for dt in expected_types
            if dt not in document_types
        ]

        # Calculate completeness score
        total_documents = len(documents)
        processed_documents = sum(
            dt_info["processed_count"]
            for dt_info in document_types.values()
        )

        completeness_score = (
            (processed_documents / total_documents * 100)
            if total_documents > 0 else 0
        )

        return {
            "tender_id": tender_id,
            "total_documents": total_documents,
            "processed_documents": processed_documents,
            "completeness_score": round(completeness_score, 2),
            "document_types": document_types,
            "missing_types": missing_types,
            "has_mandatory_documents": any(
                dt_info["mandatory_count"] > 0
                for dt_info in document_types.values()
            ),
            "can_analyze": (
                completeness_score >= 80 and
                processed_documents >= 2  # Need at least 2 processed documents
            )
        }

    async def update_tender_status(
        self,
        tender_id: UUID,
        new_status: TenderStatus,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Update tender status with business logic validation.

        Args:
            tender_id: Tender UUID
            new_status: New status to set
            tenant_id: Tenant ID for isolation

        Returns:
            True if status was updated

        Raises:
            NotFoundError: If tender not found
            BusinessLogicError: If status transition is invalid
        """
        tender = await self.tender_repo.get_by_id(tender_id, tenant_id)
        if not tender:
            raise NotFoundError(f"Tender {tender_id} not found")

        # Validate status transitions
        current_status = TenderStatus(tender.status)

        # Define valid transitions
        valid_transitions = {
            TenderStatus.DRAFT: [TenderStatus.ANALYZING, TenderStatus.ARCHIVED, TenderStatus.CANCELLED],
            TenderStatus.ANALYZING: [TenderStatus.READY, TenderStatus.DRAFT, TenderStatus.ARCHIVED, TenderStatus.CANCELLED],
            TenderStatus.READY: [TenderStatus.SUBMITTED, TenderStatus.ANALYZING, TenderStatus.ARCHIVED, TenderStatus.CANCELLED],
            TenderStatus.SUBMITTED: [TenderStatus.AWARDED, TenderStatus.REJECTED, TenderStatus.ARCHIVED, TenderStatus.CANCELLED],
            TenderStatus.AWARDED: [TenderStatus.ARCHIVED],
            TenderStatus.REJECTED: [TenderStatus.ARCHIVED],
            TenderStatus.CANCELLED: [TenderStatus.ARCHIVED],
            TenderStatus.ARCHIVED: []  # No transitions from archived
        }

        if new_status not in valid_transitions.get(current_status, []):
            raise BusinessLogicError(
                f"Invalid status transition from {current_status.value} to {new_status.value}"
            )

        # Special validation for READY status
        if new_status == TenderStatus.READY:
            completeness = await self.get_tender_completeness(tender_id, tenant_id)
            if not completeness["can_analyze"]:
                raise BusinessLogicError(
                    f"Tender {tender_id} is not complete enough to be marked as ready "
                    f"(completeness: {completeness['completeness_score']}%)"
                )

        return await self.tender_repo.update_status(
            tender_id=tender_id,
            new_status=new_status,
            tenant_id=tenant_id
        )

    async def get_tenders_ready_for_analysis(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> List[ProcurementTender]:
        """
        Get tenders that have sufficient documents for analysis.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of tenders ready for analysis
        """
        return await self.tender_repo.get_ready_for_analysis(
            skip=skip,
            limit=limit,
            tenant_id=tenant_id
        )

    async def get_expiring_tenders(
        self,
        days_ahead: int = 7,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> List[ProcurementTender]:
        """
        Get tenders expiring within specified days.

        Args:
            days_ahead: Number of days to look ahead
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of tenders expiring soon
        """
        return await self.tender_repo.get_expiring_soon(
            days_ahead=days_ahead,
            skip=skip,
            limit=limit,
            tenant_id=tenant_id
        )

    async def search_tenders(
        self,
        query: str,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> List[ProcurementTender]:
        """
        Search tenders by title, reference, or organization.

        Args:
            query: Search query
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of matching tenders
        """
        return await self.tender_repo.search_tenders(
            search_term=query,
            skip=skip,
            limit=limit,
            tenant_id=tenant_id
        )

    async def delete_tender(
        self,
        tender_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Soft delete a tender and handle associated documents.

        Args:
            tender_id: UUID of the tender to delete
            tenant_id: Tenant ID for isolation

        Returns:
            True if deletion successful

        Raises:
            NotFoundError: If tender not found
            BusinessLogicError: If tender cannot be deleted
        """
        tender = await self.tender_repo.get_by_id(tender_id, tenant_id)
        if not tender:
            raise NotFoundError(f"Tender {tender_id} not found")

        # Check if tender can be deleted (business rules)
        if tender.status in [TenderStatus.SUBMITTED, TenderStatus.AWARDED]:
            raise BusinessLogicError(
                f"Cannot delete tender in {tender.status} status"
            )

        # Get associated documents
        documents = await self.document_repo.get_by_tender(
            tender_id=tender_id,
            tenant_id=tenant_id
        )

        # Remove tender association from documents (make them orphaned)
        for doc in documents:
            await self.document_repo.associate_with_tender(
                document_id=doc.id,
                tender_id=None,
                tenant_id=tenant_id
            )

        # Soft delete the tender
        return await self.tender_repo.delete(tender_id, tenant_id=tenant_id)