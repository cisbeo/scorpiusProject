"""Document endpoints for upload, processing, and retrieval."""

import math
from typing import Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.documents import (
    DocumentListResponse,
    DocumentProcessRequest,
    DocumentResponse,
    DocumentUploadResponse,
    ExtractedRequirementsResponse,
    ProcessingResultResponse,
)
from src.db.session import get_async_db
from src.middleware.auth import get_current_user
from src.models.user import User
from src.services.document import (
    DocumentPipelineService,
    PipelineError,
    ValidationError,
)

# Create router for document endpoints
router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
    description="Upload a procurement document for processing",
    responses={
        201: {
            "description": "Document successfully uploaded",
            "model": DocumentUploadResponse
        },
        400: {
            "description": "File validation failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "File validation failed: File size exceeds maximum allowed size"
                    }
                }
            }
        },
        401: {
            "description": "Authentication required"
        },
        413: {
            "description": "File too large"
        },
        422: {
            "description": "Validation error"
        }
    }
)
async def upload_document(
    request: Request,
    file: UploadFile = File(..., description="PDF document to upload"),
    processing_options: Optional[str] = Form(None, description="Optional JSON processing options"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> DocumentUploadResponse:
    """
    Upload a procurement document for processing.

    This endpoint accepts PDF files and immediately starts the processing pipeline:
    1. Validates the uploaded file
    2. Stores it securely
    3. Begins content extraction
    4. Returns document information

    **File Requirements:**
    - Format: PDF only
    - Size: Maximum 50MB
    - Content: Must be a valid, non-corrupted PDF

    **Processing Options (JSON string):**
    ```json
    {
        "max_pages": 50,
        "language_hint": "fr",
        "extract_images": false
    }
    ```

    The document will be processed asynchronously. Use the returned document ID
    to check processing status and retrieve results.
    """
    try:
        # Validate file upload
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required"
            )

        # Read file content
        file_content = await file.read()
        if not file_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content is empty"
            )

        # Parse processing options if provided
        options = None
        if processing_options:
            try:
                import json
                options = json.loads(processing_options)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON in processing_options"
                )

        # Initialize pipeline service
        pipeline_service = DocumentPipelineService(db)

        # Process document through pipeline
        document, processing_result = await pipeline_service.process_uploaded_document(
            file_content=file_content,
            filename=file.filename,
            user_id=current_user.id,
            content_type=file.content_type,
            tenant_id=current_user.tenant_id,
            processing_options=options
        )

        # Return document information
        return DocumentUploadResponse.model_validate(document)

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PipelineError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document upload failed due to internal error"
        )


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents",
    description="Retrieve list of uploaded documents with pagination",
    responses={
        200: {
            "description": "List of documents",
            "model": DocumentListResponse
        },
        401: {
            "description": "Authentication required"
        },
        422: {
            "description": "Validation error"
        }
    }
)
async def list_documents(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    per_page: int = Query(20, ge=1, le=100, description="Number of documents per page"),
    status_filter: Optional[str] = Query(None, description="Filter by document status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> DocumentListResponse:
    """
    Retrieve a paginated list of documents uploaded by the current user.

    **Query Parameters:**
    - **page**: Page number (starts from 1)
    - **per_page**: Number of documents per page (1-100)
    - **status_filter**: Filter by status ('uploaded', 'processing', 'processed', 'failed')

    **Response includes:**
    - List of documents with metadata
    - Pagination information (total, pages, current page)
    - Processing status and timestamps
    """
    try:
        from src.repositories.document_repository import DocumentRepository

        document_repo = DocumentRepository(db)

        # Calculate offset
        skip = (page - 1) * per_page

        # Apply status filter if provided
        filter_status = None
        if status_filter:
            from src.models.document import DocumentStatus
            try:
                filter_status = DocumentStatus(status_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status filter: {status_filter}"
                )

        # Get documents for user
        documents = await document_repo.get_by_user(
            user_id=current_user.id,
            skip=skip,
            limit=per_page,
            status=filter_status,
            tenant_id=current_user.tenant_id
        )

        # Get total count for pagination
        total = await document_repo.count(
            tenant_id=current_user.tenant_id,
            uploaded_by=current_user.id,
            **({"status": filter_status} if filter_status else {})
        )

        # Calculate pagination info
        pages = math.ceil(total / per_page) if total > 0 else 1

        # Convert to response models
        document_responses = [
            DocumentResponse.model_validate(doc) for doc in documents
        ]

        return DocumentListResponse(
            documents=document_responses,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents"
        )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document details",
    description="Retrieve detailed information about a specific document",
    responses={
        200: {
            "description": "Document details",
            "model": DocumentResponse
        },
        401: {
            "description": "Authentication required"
        },
        404: {
            "description": "Document not found"
        }
    }
)
async def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> DocumentResponse:
    """
    Retrieve detailed information about a specific document.

    **Path Parameters:**
    - **document_id**: UUID of the document to retrieve

    **Response includes:**
    - Complete document metadata
    - Processing status and timing
    - Version information
    - Error messages (if any)

    Only returns documents uploaded by the current user.
    """
    try:
        from src.repositories.document_repository import DocumentRepository

        document_repo = DocumentRepository(db)

        # Get document
        document = await document_repo.get_by_id(
            document_id,
            tenant_id=current_user.tenant_id
        )

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # Check if user owns the document
        if document.uploaded_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        return DocumentResponse.model_validate(document)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document"
        )


@router.post(
    "/{document_id}/process",
    response_model=ProcessingResultResponse,
    summary="Reprocess document",
    description="Reprocess an existing document with optional new settings",
    responses={
        200: {
            "description": "Document processing result",
            "model": ProcessingResultResponse
        },
        401: {
            "description": "Authentication required"
        },
        404: {
            "description": "Document not found"
        },
        409: {
            "description": "Document is currently being processed"
        }
    }
)
async def process_document(
    document_id: UUID,
    process_request: DocumentProcessRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> ProcessingResultResponse:
    """
    Reprocess an existing document with optional new processing settings.

    **Path Parameters:**
    - **document_id**: UUID of the document to reprocess

    **Request Body:**
    - **processing_options**: Optional processing configuration

    **Processing Options:**
    ```json
    {
        "max_pages": 50,
        "language_hint": "fr",
        "extract_images": false
    }
    ```

    This endpoint will:
    1. Validate document ownership
    2. Check if document is not currently processing
    3. Reprocess the document with new settings
    4. Return detailed processing results
    """
    try:
        from src.repositories.document_repository import DocumentRepository

        document_repo = DocumentRepository(db)

        # Get document
        document = await document_repo.get_by_id(
            document_id,
            tenant_id=current_user.tenant_id
        )

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # Check if user owns the document
        if document.uploaded_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # Check if document is currently processing
        from src.models.document import DocumentStatus
        if document.status == DocumentStatus.PROCESSING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document is currently being processed"
            )

        # Initialize pipeline service
        pipeline_service = DocumentPipelineService(db)

        # Reprocess document
        processing_result = await pipeline_service.reprocess_document(
            document_id=document_id,
            processing_options=process_request.processing_options,
            tenant_id=current_user.tenant_id
        )

        return ProcessingResultResponse.model_validate(processing_result.to_dict())

    except HTTPException:
        raise
    except PipelineError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document reprocessing failed"
        )


@router.get(
    "/{document_id}/requirements",
    response_model=ExtractedRequirementsResponse,
    summary="Get extracted requirements",
    description="Retrieve extracted requirements from a processed document",
    responses={
        200: {
            "description": "Extracted requirements",
            "model": ExtractedRequirementsResponse
        },
        401: {
            "description": "Authentication required"
        },
        404: {
            "description": "Document or requirements not found"
        },
        409: {
            "description": "Document not yet processed"
        }
    }
)
async def get_document_requirements(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> ExtractedRequirementsResponse:
    """
    Retrieve extracted requirements from a processed document.

    **Path Parameters:**
    - **document_id**: UUID of the document

    **Response includes:**
    - Technical requirements
    - Functional requirements
    - Administrative requirements
    - Evaluation criteria
    - Extraction metadata

    The document must be successfully processed before requirements are available.
    """
    try:
        from src.repositories.document_repository import DocumentRepository

        document_repo = DocumentRepository(db)

        # Get document with requirements
        document = await document_repo.get_with_requirements(
            document_id,
            tenant_id=current_user.tenant_id
        )

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # Check if user owns the document
        if document.uploaded_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # Check if document is processed
        from src.models.document import DocumentStatus
        if document.status != DocumentStatus.PROCESSED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document is not yet processed"
            )

        # Check if requirements exist
        if not document.extracted_requirements:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Requirements not found for this document"
            )

        requirements = document.extracted_requirements

        return ExtractedRequirementsResponse.model_validate(requirements)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve requirements"
        )
