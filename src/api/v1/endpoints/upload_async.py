"""Async upload endpoint with deferred processing."""

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import asyncio
import logging
from typing import Optional

from src.db.session import get_db
from src.middleware.auth import get_current_user_optional
from src.models.user import User
from src.models.document import ProcurementDocument, DocumentStatus
from src.services.document_pipeline import DocumentPipelineService
from src.repositories.document_repository import DocumentRepository

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/upload-async")
async def upload_document_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    processing_strategy: Optional[str] = "fast",
    processor: Optional[str] = "auto",
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a document with asynchronous processing.

    Returns immediately with document ID while processing happens in background.

    Processing strategies:
    - fast: Quick extraction (default)
    - hi_res: High quality extraction (slower)
    - ultra_fast: Use PyPDF2 only (fastest)

    Processors:
    - auto: Choose automatically based on file size (default)
    - unstructured: Force Unstructured.io
    - pypdf2: Force PyPDF2
    """
    # Validate file
    if not file.filename.endswith(('.pdf', '.docx', '.txt')):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    logger.info(f"Received upload request: file={file.filename}, strategy={processing_strategy}, processor={processor}")

    # Initialize services
    pipeline_service = DocumentPipelineService(db)
    doc_repo = DocumentRepository(db)

    # Save file and create document record
    file_content = await file.read()
    logger.info(f"File read successfully: size={len(file_content)} bytes ({len(file_content) / 1024:.1f} KB)")

    # Generate file path for storage
    import hashlib
    from datetime import datetime

    # Generate unique file path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_hash = hashlib.md5(file_content).hexdigest()[:8]
    file_path = f"uploads/{timestamp}_{file_hash}_{file.filename}"

    # Create document with UPLOADED status
    document = await doc_repo.create(
        original_filename=file.filename,
        file_path=file_path,
        file_size=len(file_content),
        file_hash=hashlib.sha256(file_content).hexdigest(),
        mime_type=file.content_type,
        status=DocumentStatus.UPLOADED,
        uploaded_by=current_user.id if current_user else None
    )
    await db.commit()
    logger.info(f"Document created in database: id={document.id}, path={file_path}")

    # Process in background - using a separate DB session
    async def process_document_background():
        """Background processing task."""
        from src.db.session import get_db

        # Create a new DB session for background task
        async for bg_db in get_db():
            try:
                # Create new service instances with the background session
                bg_pipeline_service = DocumentPipelineService(bg_db)
                bg_doc_repo = DocumentRepository(bg_db)

                # Determine processor to use
                file_size_mb = len(file_content) / (1024 * 1024)

                # Auto selection logic
                if processor == "auto":
                    if processing_strategy == "ultra_fast" or file_size_mb > 5:
                        use_processor = "pypdf2"
                        logger.info(f"Auto-selected PyPDF2 (ultra_fast or large file: {file_size_mb:.1f}MB)")
                    else:
                        use_processor = "unstructured"
                        logger.info(f"Auto-selected Unstructured (file size: {file_size_mb:.1f}MB)")
                else:
                    use_processor = processor
                    logger.info(f"Using explicitly requested processor: {use_processor}")

                # Process with specified strategy
                processing_options = {
                    "strategy": processing_strategy,
                    "extract_tables": True,
                    "languages": ["fra"],
                    "processor": use_processor
                }

                # Use the pipeline service to process
                logger.info(f"Starting background processing for document {document.id}")
                result = await bg_pipeline_service.process_document(
                    file_content=file_content,
                    filename=file.filename,
                    document_id=document.id,
                    processing_options=processing_options
                )
                logger.info(f"Background processing completed: success={result.get('success')}")
            except Exception as e:
                logger.error(f"Error processing document {document.id}: {str(e)}", exc_info=True)
                # Update document with error
                await bg_doc_repo.update(
                    document.id,
                    {
                        "status": DocumentStatus.FAILED,
                        "error_message": str(e)
                    }
                )
                await bg_db.commit()
            finally:
                await bg_db.close()

    # Add to background tasks - this will run after response is sent
    background_tasks.add_task(process_document_background)
    logger.info(f"Background task scheduled for document {document.id}")

    response = {
        "id": str(document.id),
        "status": "processing",
        "message": "Document uploaded successfully. Processing in background.",
        "processing_strategy": processing_strategy,
        "check_status_url": f"/api/v1/documents/{document.id}/status"
    }
    logger.info(f"Returning upload response: {response}")
    return response

@router.get("/documents/{document_id}/status")
async def get_document_status(
    document_id: UUID,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """Check the processing status of a document."""
    doc_repo = DocumentRepository(db)
    document = await doc_repo.get_by_id(document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    response = {
        "id": str(document.id),
        "filename": document.original_filename,
        "status": document.status.value,
        "created_at": document.created_at.isoformat(),
    }

    if document.status == DocumentStatus.PROCESSED:
        response["processing_duration_ms"] = document.processing_duration_ms
        response["page_count"] = document.page_count if hasattr(document, 'page_count') else None
        response["extraction_metadata"] = document.extraction_metadata
    elif document.status == DocumentStatus.FAILED:
        response["error_message"] = document.error_message

    return response