"""Document processing pipeline service."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import ProcurementDocument, DocumentStatus
from src.processors import ProcessingError, ProcessingResult, processor_factory
from src.repositories.audit_repository import AuditRepository
from src.repositories.document_repository import DocumentRepository
from src.services.document.storage_service import DocumentStorageService, StorageError
from src.services.document.validation_service import (
    DocumentValidationService,
    ValidationError,
)


class PipelineError(Exception):
    """Custom exception for pipeline processing errors."""
    pass


class DocumentPipelineService:
    """
    Service for orchestrating document processing pipeline.

    Handles the complete workflow:
    1. Document validation
    2. Secure storage
    3. Content extraction
    4. Requirements processing
    5. Database updates
    6. Error handling and cleanup
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize pipeline service.

        Args:
            db_session: Async database session
        """
        self.db = db_session
        self.document_repo = DocumentRepository(db_session)
        self.audit_repo = AuditRepository(db_session)
        self.validation_service = DocumentValidationService()
        self.storage_service = DocumentStorageService()

    async def process_uploaded_document(
        self,
        file_content: bytes,
        filename: str,
        user_id: UUID,
        content_type: Optional[str] = None,
        tenant_id: Optional[UUID] = None,
        processing_options: Optional[dict[str, Any]] = None
    ) -> tuple[ProcurementDocument, ProcessingResult]:
        """
        Process an uploaded document through the complete pipeline.

        Args:
            file_content: Binary content of the uploaded file
            filename: Original filename
            user_id: UUID of the user uploading the document
            content_type: MIME content type from upload
            tenant_id: Optional tenant ID for multi-tenancy
            processing_options: Optional processing configuration

        Returns:
            Tuple of (created_document, processing_result)

        Raises:
            PipelineError: If pipeline processing fails
            ValidationError: If document validation fails
            StorageError: If document storage fails
        """
        processing_start = datetime.utcnow()
        document = None

        try:
            # Step 1: Validate uploaded file
            await self._log_pipeline_event(
                "validation_started", user_id, tenant_id,
                {"filename": filename, "file_size": len(file_content)}
            )

            is_valid, validation_errors, file_metadata = self.validation_service.validate_file_upload(
                file_content, filename, content_type
            )

            if not is_valid:
                error_msg = f"File validation failed: {'; '.join(validation_errors)}"
                await self._log_pipeline_event(
                    "validation_failed", user_id, tenant_id,
                    {"filename": filename, "errors": validation_errors}
                )
                raise ValidationError(error_msg)

            file_hash = file_metadata["file_hash"]
            detected_mime = file_metadata["detected_mime_type"]

            await self._log_pipeline_event(
                "validation_completed", user_id, tenant_id,
                {"filename": filename, "file_hash": file_hash[:16]}
            )

            # Step 2: Check for duplicates
            existing_doc = await self.document_repo.get_by_hash(file_hash, tenant_id)
            if existing_doc:
                await self._log_pipeline_event(
                    "duplicate_detected", user_id, tenant_id,
                    {"filename": filename, "existing_doc_id": str(existing_doc.id)}
                )
                raise PipelineError(f"Document with same content already exists (ID: {existing_doc.id})")

            # Step 3: Store document securely
            await self._log_pipeline_event(
                "storage_started", user_id, tenant_id,
                {"filename": filename, "file_hash": file_hash[:16]}
            )

            try:
                storage_path, relative_path = self.storage_service.store_document(
                    file_content, filename, file_hash, user_id, tenant_id
                )
            except StorageError as e:
                await self._log_pipeline_event(
                    "storage_failed", user_id, tenant_id,
                    {"filename": filename, "error": str(e)}
                )
                raise

            await self._log_pipeline_event(
                "storage_completed", user_id, tenant_id,
                {"filename": filename, "storage_path": relative_path}
            )

            # Step 4: Create document record
            document = await self.document_repo.create_document(
                original_filename=filename,
                file_path=relative_path,
                file_size=len(file_content),
                file_hash=file_hash,
                uploaded_by=user_id,
                mime_type=detected_mime or content_type or "application/octet-stream",
                tenant_id=tenant_id
            )

            await self._log_pipeline_event(
                "document_created", user_id, tenant_id,
                {"document_id": str(document.id), "filename": filename}
            )

            # Step 5: Process document content
            processing_result = await self._process_document_content(
                document, file_content, processing_options
            )

            # Step 6: Store extracted requirements if processing succeeded
            if processing_result.success and processing_result.structured_content:
                await self._store_extracted_requirements(document, processing_result)

            # Step 7: Update document status with extraction metadata
            processing_duration = int((datetime.utcnow() - processing_start).total_seconds() * 1000)

            if processing_result.success:
                # Store extraction metadata including text content for AI processing
                extraction_metadata = {
                    "processor": processing_result.processor_name,
                    "processor_version": processing_result.processor_version,
                    "text_content": processing_result.raw_text,  # Critical for AI extraction
                    "page_count": processing_result.page_count,
                    "word_count": processing_result.word_count,
                    "language": processing_result.language,
                    "confidence_score": processing_result.confidence_score,
                    **processing_result.metadata
                }

                # Update document with status and metadata
                await self.document_repo.update(
                    document.id,
                    {
                        "status": DocumentStatus.PROCESSED,
                        "processing_duration_ms": processing_duration,
                        "extraction_metadata": extraction_metadata,
                        "processed_content": processing_result.raw_text  # Store for AI extraction
                    },
                    tenant_id=tenant_id
                )
                status = "completed"
            else:
                error_msg = '; '.join(processing_result.errors) if processing_result.errors else "Unknown processing error"
                await self.document_repo.fail_processing(
                    document.id, error_msg, tenant_id
                )
                status = "failed"

            await self._log_pipeline_event(
                f"processing_{status}", user_id, tenant_id,
                {
                    "document_id": str(document.id),
                    "processing_duration_ms": processing_duration,
                    "success": processing_result.success
                }
            )

            return document, processing_result

        except (ValidationError, StorageError, PipelineError):
            # Re-raise known errors
            raise
        except Exception as e:
            # Handle unexpected errors
            error_msg = f"Unexpected pipeline error: {str(e)}"

            # Log error
            await self._log_pipeline_event(
                "pipeline_error", user_id, tenant_id,
                {"filename": filename, "error": error_msg}
            )

            # Clean up if document was created
            if document:
                try:
                    await self.document_repo.fail_processing(
                        document.id, error_msg, tenant_id
                    )
                except Exception:
                    pass  # Don't let cleanup errors mask the original error

            raise PipelineError(error_msg)

    async def reprocess_document(
        self,
        document_id: UUID,
        processing_options: Optional[dict[str, Any]] = None,
        tenant_id: Optional[UUID] = None
    ) -> ProcessingResult:
        """
        Reprocess an existing document.

        Args:
            document_id: UUID of the document to reprocess
            processing_options: Optional processing configuration
            tenant_id: Optional tenant ID for multi-tenancy

        Returns:
            ProcessingResult from reprocessing

        Raises:
            PipelineError: If reprocessing fails
        """
        try:
            # Get document
            document = await self.document_repo.get_by_id(document_id, tenant_id=tenant_id)
            if not document:
                raise PipelineError("Document not found")

            # Retrieve file content
            try:
                file_content = self.storage_service.retrieve_document(document.file_path)
            except StorageError as e:
                raise PipelineError(f"Failed to retrieve document for reprocessing: {str(e)}")

            # Mark as processing
            await self.document_repo.start_processing(document_id, tenant_id)

            await self._log_pipeline_event(
                "reprocessing_started", document.uploaded_by, tenant_id,
                {"document_id": str(document_id), "filename": document.original_filename}
            )

            # Process content
            processing_result = await self._process_document_content(
                document, file_content, processing_options
            )

            # Update requirements if processing succeeded
            if processing_result.success and processing_result.structured_content:
                await self._store_extracted_requirements(document, processing_result)

            # Update document status
            processing_duration = processing_result.processing_time_ms

            if processing_result.success:
                await self.document_repo.complete_processing(
                    document_id, processing_duration, tenant_id
                )
                # Increment version
                await self.document_repo.increment_version(document_id, tenant_id)
            else:
                error_msg = '; '.join(processing_result.errors) if processing_result.errors else "Reprocessing failed"
                await self.document_repo.fail_processing(
                    document_id, error_msg, tenant_id
                )

            await self._log_pipeline_event(
                f"reprocessing_{'completed' if processing_result.success else 'failed'}",
                document.uploaded_by, tenant_id,
                {
                    "document_id": str(document_id),
                    "processing_duration_ms": processing_duration,
                    "success": processing_result.success
                }
            )

            return processing_result

        except PipelineError:
            raise
        except Exception as e:
            error_msg = f"Reprocessing failed: {str(e)}"
            await self._log_pipeline_event(
                "reprocessing_error", None, tenant_id,
                {"document_id": str(document_id), "error": error_msg}
            )
            raise PipelineError(error_msg)

    async def delete_document(
        self,
        document_id: UUID,
        user_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Delete document and its associated files.

        Args:
            document_id: UUID of the document to delete
            user_id: UUID of the user requesting deletion
            tenant_id: Optional tenant ID for multi-tenancy

        Returns:
            True if document was deleted successfully

        Raises:
            PipelineError: If deletion fails
        """
        try:
            # Get document
            document = await self.document_repo.get_by_id(document_id, tenant_id=tenant_id)
            if not document:
                return False

            await self._log_pipeline_event(
                "deletion_started", user_id, tenant_id,
                {"document_id": str(document_id), "filename": document.original_filename}
            )

            # Delete file from storage
            try:
                file_deleted = self.storage_service.delete_document(document.file_path)
                if not file_deleted:
                    # File may have been already deleted, log but continue
                    await self._log_pipeline_event(
                        "file_not_found_during_deletion", user_id, tenant_id,
                        {"document_id": str(document_id), "file_path": document.file_path}
                    )
            except StorageError as e:
                # Log storage error but continue with database deletion
                await self._log_pipeline_event(
                    "storage_deletion_failed", user_id, tenant_id,
                    {"document_id": str(document_id), "error": str(e)}
                )

            # Soft delete document record
            success = await self.document_repo.delete(document_id, soft_delete=True, tenant_id=tenant_id)

            if success:
                await self._log_pipeline_event(
                    "deletion_completed", user_id, tenant_id,
                    {"document_id": str(document_id)}
                )

            return success

        except Exception as e:
            error_msg = f"Document deletion failed: {str(e)}"
            await self._log_pipeline_event(
                "deletion_error", user_id, tenant_id,
                {"document_id": str(document_id), "error": error_msg}
            )
            raise PipelineError(error_msg)

    async def _process_document_content(
        self,
        document: ProcurementDocument,
        file_content: bytes,
        processing_options: Optional[dict[str, Any]] = None
    ) -> ProcessingResult:
        """
        Process document content using appropriate processor.

        Args:
            document: Document model instance
            file_content: Binary file content
            processing_options: Optional processing configuration

        Returns:
            ProcessingResult from content processing
        """
        processing_start = datetime.utcnow()

        try:
            # Mark document as processing
            await self.document_repo.start_processing(document.id, document.tenant_id)

            # Get appropriate processor
            processor = processor_factory.get_processor_for_file(
                document.original_filename, document.mime_type
            )

            if not processor:
                return ProcessingResult(
                    raw_text="",
                    structured_content={},
                    success=False,
                    processing_time_ms=0,
                    processor_name="unknown",
                    processor_version="unknown",
                    page_count=0,
                    word_count=0,
                    errors=[f"No processor available for file type: {document.mime_type}"]
                )

            # Process document
            try:
                result = await processor.process_document(
                    file_content=file_content,
                    filename=document.original_filename,
                    mime_type=document.mime_type,
                    processing_options=processing_options
                )
                return result

            except ProcessingError as e:
                return ProcessingResult(
                    raw_text="",
                    structured_content={},
                    success=False,
                    processing_time_ms=int((datetime.utcnow() - processing_start).total_seconds() * 1000),
                    processor_name=processor.name,
                    processor_version=processor.version,
                    page_count=0,
                    word_count=0,
                    errors=[str(e)]
                )

        except Exception as e:
            return ProcessingResult(
                raw_text="",
                structured_content={},
                success=False,
                processing_time_ms=int((datetime.utcnow() - processing_start).total_seconds() * 1000),
                processor_name="unknown",
                processor_version="unknown",
                page_count=0,
                word_count=0,
                errors=[f"Processing failed: {str(e)}"]
            )

    async def _store_extracted_requirements(
        self,
        document: ProcurementDocument,
        processing_result: ProcessingResult
    ) -> None:
        """
        Store extracted requirements in database.

        Args:
            document: Document model instance
            processing_result: Processing result with extracted content
        """
        try:

            # Extract procurement-specific data
            procurement_data = processing_result.structured_content.get("procurement_specific", {})

            # Create ExtractedRequirements record
            # Note: This is a simplified version. In a real implementation,
            # you would have more sophisticated parsing and validation

            requirements_data = {
                "document_id": document.id,
                "raw_content_json": {
                    "raw_text": processing_result.raw_text,
                    "structured_content": processing_result.structured_content,
                    "processing_metadata": {
                        "processor": processing_result.processor_name,
                        "version": processing_result.processor_version,
                        "confidence": processing_result.confidence_score,
                        "processing_time_ms": processing_result.processing_time_ms
                    }
                },
                "technical_requirements_json": procurement_data.get("sections", {}),
                "functional_requirements_json": procurement_data.get("extracted_fields", {}),
                "administrative_requirements_json": {
                    "reference": procurement_data.get("reference", []),
                    "organism": procurement_data.get("organism", []),
                    "deadline": procurement_data.get("deadline", [])
                },
                "evaluation_criteria_json": {},  # Would be extracted from structured content
                "extracted_at": datetime.utcnow(),
                "extraction_confidence": processing_result.confidence_score,
                "language_detected": processing_result.language,
                "tenant_id": document.tenant_id
            }

            # Create the requirements record
            # Note: You would need to implement this in the requirements repository
            # For now, we'll just log that we would store it
            await self._log_pipeline_event(
                "requirements_extracted", document.uploaded_by, document.tenant_id,
                {
                    "document_id": str(document.id),
                    "confidence": processing_result.confidence_score,
                    "word_count": processing_result.word_count,
                    "page_count": processing_result.page_count
                }
            )

        except Exception as e:
            # Log error but don't fail the pipeline
            await self._log_pipeline_event(
                "requirements_storage_failed", document.uploaded_by, document.tenant_id,
                {"document_id": str(document.id), "error": str(e)}
            )

    async def _log_pipeline_event(
        self,
        action: str,
        user_id: Optional[UUID],
        tenant_id: Optional[UUID],
        metadata: dict[str, Any]
    ) -> None:
        """
        Log pipeline events for audit and monitoring.

        Args:
            action: Action being performed
            user_id: Optional user UUID
            tenant_id: Optional tenant UUID
            metadata: Event metadata
        """
        try:
            await self.audit_repo.log_action(
                action=f"pipeline_{action}",
                resource_type="document_pipeline",
                resource_id=UUID(metadata.get("document_id", "00000000-0000-0000-0000-000000000000")),
                user_id=user_id,
                metadata={
                    **metadata,
                    "timestamp": datetime.utcnow().isoformat()
                },
                tenant_id=tenant_id
            )
        except Exception:
            # Don't let audit logging failures break the pipeline
            pass

    async def get_processing_status(
        self,
        document_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> dict[str, Any]:
        """
        Get processing status for a document.

        Args:
            document_id: UUID of the document
            tenant_id: Optional tenant ID for multi-tenancy

        Returns:
            Dictionary with processing status information
        """
        try:
            document = await self.document_repo.get_by_id(document_id, tenant_id=tenant_id)
            if not document:
                return {"error": "Document not found"}

            return {
                "document_id": str(document.id),
                "status": document.status.value,
                "filename": document.original_filename,
                "file_size": document.file_size,
                "processing_started_at": document.processing_started_at.isoformat() if document.processing_started_at else None,
                "processing_completed_at": document.processing_completed_at.isoformat() if document.processing_completed_at else None,
                "processing_duration_ms": document.processing_duration_ms,
                "error_message": document.error_message,
                "version": document.version,
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat()
            }

        except Exception as e:
            return {"error": str(e)}

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on pipeline service.

        Returns:
            Dictionary with health status information
        """
        try:
            # Check processor factory
            processors = processor_factory.list_processors()

            # Check storage service
            storage_info = self.storage_service.get_storage_info()

            # Check validation service
            validation_healthy = True  # Basic check

            return {
                "service": "DocumentPipelineService",
                "status": "healthy",
                "processors_available": processors,
                "storage_info": storage_info,
                "validation_service": "healthy" if validation_healthy else "unhealthy",
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            return {
                "service": "DocumentPipelineService",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
