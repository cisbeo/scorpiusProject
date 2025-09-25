"""Document repository for procurement document operations."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.document import DocumentStatus, ProcurementDocument
from src.models.document_type import DocumentType
from src.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[ProcurementDocument]):
    """
    Repository for ProcurementDocument model with document-specific operations.

    Extends BaseRepository with document-specific methods:
    - Status-based filtering
    - User document queries
    - Processing tracking
    - File operations support
    - Tender association and multi-document support
    - Document type classification
    - Cross-referencing between related documents
    - Metadata and extraction result management
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize document repository."""
        super().__init__(ProcurementDocument, db_session)

    async def create_document(
        self,
        original_filename: str,
        file_path: str,
        file_size: int,
        file_hash: str,
        uploaded_by: UUID,
        mime_type: str = "application/pdf",
        tender_id: Optional[UUID] = None,
        document_type: Optional[DocumentType] = None,
        is_mandatory: bool = False,
        tenant_id: Optional[UUID] = None
    ) -> ProcurementDocument:
        """
        Create a new procurement document.

        Args:
            original_filename: Original name of the uploaded file
            file_path: Path where file is stored
            file_size: Size of file in bytes
            file_hash: SHA-256 hash of the file
            uploaded_by: UUID of the user who uploaded the document
            mime_type: MIME type of the file
            tender_id: UUID of the associated tender (optional)
            document_type: Type of procurement document (RC, CCAP, etc.)
            is_mandatory: Whether this document is required for the tender
            tenant_id: Tenant ID for multi-tenancy

        Returns:
            Created document instance
        """
        return await self.create(
            original_filename=original_filename,
            file_path=file_path,
            file_size=file_size,
            file_hash=file_hash,
            uploaded_by=uploaded_by,
            mime_type=mime_type,
            tender_id=tender_id,
            document_type=document_type.value if document_type else None,
            is_mandatory=is_mandatory,
            status=DocumentStatus.UPLOADED,
            tenant_id=tenant_id
        )

    async def get_by_user(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
        status: Optional[DocumentStatus] = None,
        tenant_id: Optional[UUID] = None
    ) -> list[ProcurementDocument]:
        """
        Get documents uploaded by a specific user.

        Args:
            user_id: UUID of the user
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Optional status filter
            tenant_id: Tenant ID for isolation

        Returns:
            List of documents uploaded by the user
        """
        filters = {"uploaded_by": user_id}
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
        status: DocumentStatus,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[ProcurementDocument]:
        """
        Get documents by processing status.

        Args:
            status: Document status to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of documents with specified status
        """
        return await self.get_multi(
            skip=skip,
            limit=limit,
            tenant_id=tenant_id,
            status=status
        )

    async def get_by_hash(
        self,
        file_hash: str,
        tenant_id: Optional[UUID] = None
    ) -> Optional[ProcurementDocument]:
        """
        Get document by file hash (for duplicate detection).

        Args:
            file_hash: SHA-256 hash of the file
            tenant_id: Tenant ID for isolation

        Returns:
            Document instance if found, None otherwise
        """
        return await self.get_by_field(
            field_name="file_hash",
            field_value=file_hash,
            tenant_id=tenant_id
        )

    async def start_processing(
        self,
        document_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Mark document as processing started.

        Args:
            document_id: Document UUID
            tenant_id: Tenant ID for isolation

        Returns:
            True if status was updated, False if document not found
        """
        updated_doc = await self.update(
            id=document_id,
            update_data={
                "status": DocumentStatus.PROCESSING,
                "processing_started_at": datetime.utcnow(),
                "error_message": None
            },
            tenant_id=tenant_id
        )
        return updated_doc is not None

    async def complete_processing(
        self,
        document_id: UUID,
        processing_duration_ms: Optional[int] = None,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Mark document processing as completed.

        Args:
            document_id: Document UUID
            processing_duration_ms: Processing duration in milliseconds
            tenant_id: Tenant ID for isolation

        Returns:
            True if status was updated, False if document not found
        """
        update_data = {
            "status": DocumentStatus.PROCESSED,
            "processing_completed_at": datetime.utcnow(),
            "error_message": None
        }

        if processing_duration_ms is not None:
            update_data["processing_duration_ms"] = processing_duration_ms

        updated_doc = await self.update(
            id=document_id,
            update_data=update_data,
            tenant_id=tenant_id
        )
        return updated_doc is not None

    async def fail_processing(
        self,
        document_id: UUID,
        error_message: str,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Mark document processing as failed.

        Args:
            document_id: Document UUID
            error_message: Error message describing the failure
            tenant_id: Tenant ID for isolation

        Returns:
            True if status was updated, False if document not found
        """
        updated_doc = await self.update(
            id=document_id,
            update_data={
                "status": DocumentStatus.FAILED,
                "processing_completed_at": datetime.utcnow(),
                "error_message": error_message
            },
            tenant_id=tenant_id
        )
        return updated_doc is not None

    async def get_processed_documents(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[ProcurementDocument]:
        """
        Get all successfully processed documents.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of processed documents
        """
        return await self.get_by_status(
            status=DocumentStatus.PROCESSED,
            skip=skip,
            limit=limit,
            tenant_id=tenant_id
        )

    async def get_pending_documents(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[ProcurementDocument]:
        """
        Get documents pending processing (uploaded or processing).

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of pending documents
        """
        query = select(ProcurementDocument).where(
            ProcurementDocument.status.in_([
                DocumentStatus.UPLOADED,
                DocumentStatus.PROCESSING
            ])
        )

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(ProcurementDocument.tenant_id == tenant_id)

        # Filter out soft-deleted records
        query = query.where(ProcurementDocument.deleted_at.is_(None))

        # Apply pagination and ordering
        query = query.offset(skip).limit(limit).order_by(
            ProcurementDocument.created_at.desc()
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_failed_documents(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[ProcurementDocument]:
        """
        Get documents that failed processing.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of failed documents
        """
        return await self.get_by_status(
            status=DocumentStatus.FAILED,
            skip=skip,
            limit=limit,
            tenant_id=tenant_id
        )

    async def get_with_requirements(
        self,
        document_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> Optional[ProcurementDocument]:
        """
        Get document with its extracted requirements loaded.

        Args:
            document_id: Document UUID
            tenant_id: Tenant ID for isolation

        Returns:
            Document with requirements if found, None otherwise
        """
        query = select(ProcurementDocument).options(
            selectinload(ProcurementDocument.extracted_requirements)
        ).where(ProcurementDocument.id == document_id)

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(ProcurementDocument.tenant_id == tenant_id)

        # Filter out soft-deleted records
        query = query.where(ProcurementDocument.deleted_at.is_(None))

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def count_by_status(
        self,
        status: DocumentStatus,
        tenant_id: Optional[UUID] = None
    ) -> int:
        """
        Count documents by status.

        Args:
            status: Document status to count
            tenant_id: Tenant ID for isolation

        Returns:
            Number of documents with specified status
        """
        return await self.count(tenant_id=tenant_id, status=status)

    async def get_recent_documents(
        self,
        days: int = 7,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[ProcurementDocument]:
        """
        Get recently uploaded documents.

        Args:
            days: Number of days to look back
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of recent documents
        """
        cutoff_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date.replace(day=cutoff_date.day - days)

        query = select(ProcurementDocument).where(
            ProcurementDocument.created_at >= cutoff_date
        )

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(ProcurementDocument.tenant_id == tenant_id)

        # Filter out soft-deleted records
        query = query.where(ProcurementDocument.deleted_at.is_(None))

        # Apply pagination and ordering
        query = query.offset(skip).limit(limit).order_by(
            ProcurementDocument.created_at.desc()
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def increment_version(
        self,
        document_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Increment document version.

        Args:
            document_id: Document UUID
            tenant_id: Tenant ID for isolation

        Returns:
            True if version was incremented, False if document not found
        """
        document = await self.get_by_id(document_id, tenant_id=tenant_id)
        if document is None:
            return False

        updated_doc = await self.update(
            id=document_id,
            update_data={"version": document.version + 1},
            tenant_id=tenant_id
        )
        return updated_doc is not None

    # New tender-specific methods

    async def get_by_tender(
        self,
        tender_id: UUID,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[ProcurementDocument]:
        """
        Get all documents associated with a tender.

        Args:
            tender_id: UUID of the tender
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of documents for the tender
        """
        return await self.get_multi(
            skip=skip,
            limit=limit,
            tenant_id=tenant_id,
            tender_id=tender_id
        )

    async def get_by_tender_and_type(
        self,
        tender_id: UUID,
        document_type: DocumentType,
        tenant_id: Optional[UUID] = None
    ) -> list[ProcurementDocument]:
        """
        Get documents of specific type for a tender.

        Args:
            tender_id: UUID of the tender
            document_type: Type of documents to retrieve
            tenant_id: Tenant ID for isolation

        Returns:
            List of documents of specified type for the tender
        """
        return await self.get_multi(
            tender_id=tender_id,
            document_type=document_type.value,
            tenant_id=tenant_id
        )

    async def get_mandatory_documents(
        self,
        tender_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> list[ProcurementDocument]:
        """
        Get mandatory documents for a tender.

        Args:
            tender_id: UUID of the tender
            tenant_id: Tenant ID for isolation

        Returns:
            List of mandatory documents for the tender
        """
        return await self.get_multi(
            tender_id=tender_id,
            is_mandatory=True,
            tenant_id=tenant_id
        )

    async def get_orphaned_documents(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[ProcurementDocument]:
        """
        Get documents not associated with any tender.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of documents without tender association
        """
        query = select(ProcurementDocument).where(
            ProcurementDocument.tender_id.is_(None)
        )

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(ProcurementDocument.tenant_id == tenant_id)

        # Filter out soft-deleted records
        query = query.where(ProcurementDocument.deleted_at.is_(None))

        # Apply pagination and ordering
        query = query.offset(skip).limit(limit).order_by(
            ProcurementDocument.created_at.desc()
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def associate_with_tender(
        self,
        document_id: UUID,
        tender_id: UUID,
        document_type: Optional[DocumentType] = None,
        is_mandatory: Optional[bool] = None,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Associate a document with a tender.

        Args:
            document_id: UUID of the document
            tender_id: UUID of the tender
            document_type: Optional document type to set
            is_mandatory: Optional mandatory flag
            tenant_id: Tenant ID for isolation

        Returns:
            True if association was successful, False if document not found
        """
        update_data = {"tender_id": tender_id}

        if document_type is not None:
            update_data["document_type"] = document_type.value

        if is_mandatory is not None:
            update_data["is_mandatory"] = is_mandatory

        updated_doc = await self.update(
            id=document_id,
            update_data=update_data,
            tenant_id=tenant_id
        )
        return updated_doc is not None

    async def update_cross_references(
        self,
        document_id: UUID,
        cross_references: dict,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Update cross-references between tender documents.

        Args:
            document_id: UUID of the document
            cross_references: Dictionary of cross-references to other documents
            tenant_id: Tenant ID for isolation

        Returns:
            True if update was successful, False if document not found
        """
        updated_doc = await self.update(
            id=document_id,
            update_data={"cross_references": cross_references},
            tenant_id=tenant_id
        )
        return updated_doc is not None

    async def update_extraction_metadata(
        self,
        document_id: UUID,
        extraction_metadata: dict,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Update extraction metadata for a document.

        Args:
            document_id: UUID of the document
            extraction_metadata: Metadata from document extraction/processing
            tenant_id: Tenant ID for isolation

        Returns:
            True if update was successful, False if document not found
        """
        updated_doc = await self.update(
            id=document_id,
            update_data={"extraction_metadata": extraction_metadata},
            tenant_id=tenant_id
        )
        return updated_doc is not None

    async def count_by_tender(
        self,
        tender_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> int:
        """
        Count documents for a specific tender.

        Args:
            tender_id: UUID of the tender
            tenant_id: Tenant ID for isolation

        Returns:
            Number of documents associated with the tender
        """
        return await self.count(tender_id=tender_id, tenant_id=tenant_id)

    async def count_by_type(
        self,
        document_type: DocumentType,
        tender_id: Optional[UUID] = None,
        tenant_id: Optional[UUID] = None
    ) -> int:
        """
        Count documents by type, optionally filtered by tender.

        Args:
            document_type: Type of documents to count
            tender_id: Optional tender UUID to filter by
            tenant_id: Tenant ID for isolation

        Returns:
            Number of documents of specified type
        """
        filters = {"document_type": document_type.value}
        if tender_id is not None:
            filters["tender_id"] = tender_id

        return await self.count(tenant_id=tenant_id, **filters)

    async def get_documents_with_cross_references(
        self,
        tender_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> list[ProcurementDocument]:
        """
        Get tender documents that have cross-references to other documents.

        Args:
            tender_id: UUID of the tender
            tenant_id: Tenant ID for isolation

        Returns:
            List of documents with cross-references
        """
        query = select(ProcurementDocument).where(
            ProcurementDocument.tender_id == tender_id,
            ProcurementDocument.cross_references.is_not(None)
        )

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(ProcurementDocument.tenant_id == tenant_id)

        # Filter out soft-deleted records
        query = query.where(ProcurementDocument.deleted_at.is_(None))

        # Order by document type for consistency
        query = query.order_by(ProcurementDocument.document_type.asc())

        result = await self.db.execute(query)
        return result.scalars().all()
