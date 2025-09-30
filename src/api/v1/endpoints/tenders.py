"""API endpoints for tender management."""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, status, Path, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.db.session import get_db
from src.models.user import User
from src.models.procurement_tender import TenderStatus
from src.middleware.auth import get_current_user
from src.models.user import UserRole
from src.services.tender_service import TenderService
from src.services.tender_analysis_service import TenderAnalysisService
from src.core.exceptions import NotFoundError, ValidationError, BusinessLogicError
from src.repositories.document_repository import DocumentRepository
from src.repositories.tender_repository import TenderRepository
from src.api.v1.schemas.tender import (
    TenderCreateRequest,
    TenderUpdateRequest,
    TenderStatusUpdateRequest,
    TenderResponse,
    TenderListResponse,
    DocumentAssociationRequest,
    BulkDocumentAssociationRequest,
    TenderCompletenessResponse,
    TenderAnalysisRequest,
    TenderAnalysisResponse,
    TenderAnalysisSummaryResponse,
    TenderSearchRequest,
    ExpiringTendersRequest,
    TenderErrorResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenders", tags=["tenders"])


# CRUD Endpoints

@router.post("/", response_model=TenderResponse, status_code=status.HTTP_201_CREATED)
async def create_tender(
    request: TenderCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new procurement tender.

    Requires authenticated user.
    """
    service = TenderService(db)

    try:
        tender = await service.create_tender(
            reference=request.reference,
            title=request.title,
            organization=request.organization,
            created_by=current_user.id,
            description=request.description,
            deadline_date=request.deadline_date,
            publication_date=request.publication_date,
            budget_estimate=request.budget_estimate,
            tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
        )
        await db.commit()
        return TenderResponse.from_orm_with_computed(tender)

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating tender: {str(e)}",
        )



@router.put("/{tender_id}", response_model=TenderResponse)
async def update_tender(
    tender_id: UUID,
    request: TenderUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a tender.

    Only the creator or admin can update.
    """
    from src.repositories.tender_repository import TenderRepository
    repo = TenderRepository(db)

    # Get tender to check permissions
    tender = await repo.get_by_id(
        tender_id,
        tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
    )
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender {tender_id} not found",
        )

    # Check permissions
    if tender.created_by != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this tender",
        )

    try:
        # Update tender
        update_data = request.model_dump(exclude_unset=True)
        updated_tender = await repo.update(
            id=tender_id,
            update_data=update_data,
            tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
        )
        await db.commit()

        return TenderResponse.from_orm_with_computed(updated_tender)

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating tender: {str(e)}",
        )


@router.delete("/{tender_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tender(
    tender_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a tender.

    Only the creator or admin can delete. Documents become orphaned.
    """
    service = TenderService(db)

    try:
        # Get tender to check permissions
        from src.repositories.tender_repository import TenderRepository
        repo = TenderRepository(db)
        tender = await repo.get_by_id(
            tender_id,
            tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
        )
        if not tender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tender {tender_id} not found",
            )

        # Check permissions
        if tender.created_by != current_user.id and current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this tender",
            )

        # Delete tender
        success = await service.delete_tender(
            tender_id=tender_id,
            tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete tender",
            )

        await db.commit()

    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        await db.rollback()
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting tender: {str(e)}",
        )


# List and Search Endpoints

@router.get("/", response_model=TenderListResponse)
async def list_tenders(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[TenderStatus] = Query(None, description="Filter by status"),
    organization: Optional[str] = Query(None, description="Filter by organization"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List tenders with pagination and filters.
    """
    from src.repositories.tender_repository import TenderRepository
    repo = TenderRepository(db)

    skip = (page - 1) * page_size
    tenant_id = current_user.tenant_id if hasattr(current_user, 'tenant_id') else None

    # Get filtered tenders
    if status:
        tenders = await repo.get_by_status(
            status=status,
            skip=skip,
            limit=page_size,
            tenant_id=tenant_id,
        )
    elif organization:
        tenders = await repo.get_by_organization(
            organization=organization,
            skip=skip,
            limit=page_size,
            tenant_id=tenant_id,
        )
    else:
        tenders = await repo.get_multi(
            skip=skip,
            limit=page_size,
            tenant_id=tenant_id,
        )

    # Get total count
    if status:
        total = await repo.count_by_status(status=status, tenant_id=tenant_id)
    else:
        total = await repo.count(tenant_id=tenant_id)

    total_pages = (total + page_size - 1) // page_size

    return TenderListResponse(
        items=[TenderResponse.from_orm_with_computed(t) for t in tenders],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/my/tenders", response_model=TenderListResponse)
async def get_my_tenders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[TenderStatus] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get tenders created by the current user.
    """
    from src.repositories.tender_repository import TenderRepository
    repo = TenderRepository(db)

    skip = (page - 1) * page_size
    tenders = await repo.get_by_user(
        user_id=current_user.id,
        skip=skip,
        limit=page_size,
        status=status,
        tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
    )

    # Count user's tenders
    all_user_tenders = await repo.get_by_user(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
    )
    total = len(all_user_tenders)
    total_pages = (total + page_size - 1) // page_size

    return TenderListResponse(
        items=[TenderResponse.from_orm_with_computed(t) for t in tenders],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/search", response_model=TenderListResponse)
async def search_tenders(
    request: TenderSearchRequest,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Search tenders with advanced filters.
    """
    service = TenderService(db)
    skip = (page - 1) * page_size

    # Perform search
    if request.query:
        tenders = await service.search_tenders(
            query=request.query,
            skip=skip,
            limit=page_size,
            tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
        )
    else:
        # Use filters
        from src.repositories.tender_repository import TenderRepository
        repo = TenderRepository(db)
        tenders = await repo.get_multi(
            skip=skip,
            limit=page_size,
            tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
        )

    # Apply additional filters
    if request.min_budget or request.max_budget:
        tenders = [
            t for t in tenders
            if (not request.min_budget or (t.budget_estimate and t.budget_estimate >= request.min_budget))
            and (not request.max_budget or (t.budget_estimate and t.budget_estimate <= request.max_budget))
        ]

    if request.deadline_before or request.deadline_after:
        tenders = [
            t for t in tenders
            if (not request.deadline_before or (t.deadline_date and t.deadline_date <= request.deadline_before))
            and (not request.deadline_after or (t.deadline_date and t.deadline_date >= request.deadline_after))
        ]

    total = len(tenders)
    total_pages = (total + page_size - 1) // page_size

    return TenderListResponse(
        items=[TenderResponse.from_orm_with_computed(t) for t in tenders],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/expiring", response_model=List[TenderResponse])
async def get_expiring_tenders(
    days_ahead: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get tenders expiring within specified days.
    """
    service = TenderService(db)
    tenders = await service.get_expiring_tenders(
        days_ahead=days_ahead,
        tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
    )

    return [TenderResponse.from_orm_with_computed(t) for t in tenders]


# Status Management Endpoints

@router.put("/{tender_id}/status", response_model=TenderResponse)
async def update_tender_status(
    tender_id: UUID,
    request: TenderStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update tender status with validation.
    """
    service = TenderService(db)

    try:
        success = await service.update_tender_status(
            tender_id=tender_id,
            new_status=request.status,
            tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update tender status",
            )

        await db.commit()

        # Get updated tender
        from src.repositories.tender_repository import TenderRepository
        repo = TenderRepository(db)
        tender = await repo.get_by_id(
            tender_id,
            tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
        )

        return TenderResponse.from_orm_with_computed(tender)

    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating status: {str(e)}",
        )


# Document Association Endpoints

@router.post("/{tender_id}/documents", response_model=TenderResponse)
async def associate_document(
    tender_id: UUID,
    request: DocumentAssociationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Associate a document with a tender.
    """
    service = TenderService(db)

    try:
        success = await service.add_document_to_tender(
            tender_id=tender_id,
            document_id=request.document_id,
            document_type=request.document_type,
            is_mandatory=request.is_mandatory,
            tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to associate document",
            )

        await db.commit()

        # Get updated tender with documents
        tender = await service.get_tender_with_documents(
            tender_id=tender_id,
            tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
        )

        return TenderResponse.from_orm_with_computed(tender)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error associating document: {str(e)}",
        )


@router.post("/{tender_id}/documents/bulk", response_model=TenderResponse)
async def associate_documents_bulk(
    tender_id: UUID,
    request: BulkDocumentAssociationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Associate multiple documents with a tender.
    """
    service = TenderService(db)
    success_count = 0

    try:
        for association in request.document_associations:
            success = await service.add_document_to_tender(
                tender_id=tender_id,
                document_id=association.document_id,
                document_type=association.document_type,
                is_mandatory=association.is_mandatory,
                tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
            )
            if success:
                success_count += 1

        await db.commit()

        # Get updated tender with documents
        tender = await service.get_tender_with_documents(
            tender_id=tender_id,
            tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
        )

        return TenderResponse.from_orm_with_computed(tender)

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error associating documents (associated {success_count}/{len(request.document_associations)}): {str(e)}",
        )


@router.get("/{tender_id}/documents", response_model=List[dict])
async def get_tender_documents(
    tender_id: UUID = Path(..., description="Tender UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all documents associated with a tender.

    Returns a list of documents with their metadata.
    """
    from src.repositories.tender_repository import TenderRepository
    from src.repositories.document_repository import DocumentRepository

    tender_repo = TenderRepository(db)
    doc_repo = DocumentRepository(db)

    # Check if tender exists
    tender = await tender_repo.get_by_id(
        tender_id,
        tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None
    )

    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender {tender_id} not found"
        )

    # Get documents associated with the tender using the repository
    tender_docs = await doc_repo.get_by_tender(
        tender_id=tender_id,
        tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None
    )

    # Format documents for response
    documents = []
    for doc in tender_docs:
        doc_dict = {
            "id": str(doc.id),
            "original_filename": doc.original_filename,
            "document_type": doc.document_type if hasattr(doc, 'document_type') else "Unknown",
            "title": doc.title if hasattr(doc, 'title') else doc.original_filename,
            "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
            "file_size": doc.file_size,
            "uploaded_at": doc.created_at.isoformat() if doc.created_at else None,
            "processing_status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status)
        }
        documents.append(doc_dict)

    return documents


@router.delete("/{tender_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_document_from_tender(
    tender_id: UUID,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Remove a document association from a tender.
    """
    service = TenderService(db)

    try:
        success = await service.remove_document_from_tender(
            tender_id=tender_id,
            document_id=document_id,
            tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to remove document",
            )

        await db.commit()

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error removing document: {str(e)}",
        )


# Analysis Endpoints

@router.get("/{tender_id}/completeness", response_model=TenderCompletenessResponse)
async def get_tender_completeness(
    tender_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get tender completeness analysis.
    """
    service = TenderService(db)

    try:
        completeness = await service.get_tender_completeness(
            tender_id=tender_id,
            tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
        )

        return TenderCompletenessResponse(**completeness)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing completeness: {str(e)}",
        )


@router.post("/{tender_id}/analyze", response_model=TenderAnalysisResponse)
async def analyze_tender(
    tender_id: UUID,
    request: TenderAnalysisRequest = TenderAnalysisRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Perform comprehensive AI-powered analysis of a tender.

    This endpoint analyzes all tender documents, extracts requirements,
    performs capability matching, and generates strategic recommendations.
    """
    analysis_service = TenderAnalysisService(db)

    try:
        analysis_result = await analysis_service.analyze_tender_documents(
            tender_id=tender_id,
            force_reanalysis=request.force_reanalysis,
            tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
        )

        await db.commit()

        # Filter response based on request
        if not request.include_recommendations:
            analysis_result.pop('recommendations', None)
            analysis_result.pop('strategic_insights', None)

        return TenderAnalysisResponse(**analysis_result)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except BusinessLogicError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing tender: {str(e)}",
        )


@router.get("/{tender_id}/analysis/summary", response_model=Optional[TenderAnalysisSummaryResponse])
async def get_analysis_summary(
    tender_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get summary of existing analysis for a tender.
    """
    analysis_service = TenderAnalysisService(db)

    summary = await analysis_service.get_tender_analysis_summary(
        tender_id=tender_id,
        tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
    )

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis available for this tender",
        )

    return TenderAnalysisSummaryResponse(**summary)


# Ready for Analysis Endpoint

@router.get("/ready-for-analysis", response_model=List[TenderResponse])
async def get_tenders_ready_for_analysis(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get tenders that have sufficient documents for analysis.
    """
    service = TenderService(db)
    skip = (page - 1) * page_size

    tenders = await service.get_tenders_ready_for_analysis(
        skip=skip,
        limit=page_size,
        tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
    )

    return [TenderResponse.from_orm_with_computed(t) for t in tenders]


# Individual Tender Operations (must be after static paths like /expiring and /ready-for-analysis)

@router.get("/{tender_id}", response_model=TenderResponse)
async def get_tender(
    tender_id: UUID = Path(..., description="Tender UUID"),
    include_documents: bool = Query(False, description="Include document details"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific tender by ID.

    Optionally includes document details.
    """
    service = TenderService(db)

    try:
        if include_documents:
            tender = await service.get_tender_with_documents(
                tender_id=tender_id,
                tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
            )
        else:
            from src.repositories.tender_repository import TenderRepository
            repo = TenderRepository(db)
            tender = await repo.get_by_id(
                tender_id,
                tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else None,
            )
            if not tender:
                raise NotFoundError(f"Tender {tender_id} not found")

        return TenderResponse.from_orm_with_computed(tender)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving tender: {str(e)}",
        )


# Store analysis jobs in memory (in production, use Redis or database)
analysis_jobs: Dict[str, Dict[str, Any]] = {}


@router.post("/{tender_id}/analyze")
async def trigger_tender_analysis(
    tender_id: UUID,
    background_tasks: BackgroundTasks,
    analysis_type: str = "comprehensive",
    extract_requirements: bool = True,
    generate_embeddings: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger AI analysis for all documents in a tender.

    Returns immediately with an analysis ID while processing happens in background.
    """
    try:
        # Verify tender exists
        tender_repo = TenderRepository(db)
        tender = await tender_repo.get_by_id(tender_id)
        if not tender:
            raise HTTPException(status_code=404, detail="Tender not found")

        # Get all documents for this tender
        doc_repo = DocumentRepository(db)
        documents = await doc_repo.get_by_tender(tender_id)

        if not documents:
            raise HTTPException(
                status_code=400,
                detail="No documents found for this tender"
            )

        # Create analysis job
        analysis_id = str(uuid4())
        analysis_jobs[analysis_id] = {
            "id": analysis_id,
            "tender_id": str(tender_id),
            "status": "pending",
            "document_count": len(documents),
            "documents_processed": 0,
            "analysis_type": analysis_type,
            "extract_requirements": extract_requirements,
            "generate_embeddings": generate_embeddings,
            "created_by": str(current_user.id)
        }

        # Process in background
        async def process_analysis():
            from src.db.session import get_db
            from src.services.ai_service import AIService

            async for bg_db in get_db():
                try:
                    analysis_jobs[analysis_id]["status"] = "processing"

                    ai_service = AIService()
                    bg_doc_repo = DocumentRepository(bg_db)

                    for doc in documents:
                        # Get document content
                        document = await bg_doc_repo.get_by_id(doc.id)
                        if document and document.processed_content:
                            # Extract requirements if requested
                            if extract_requirements:
                                try:
                                    requirements = await ai_service.extract_requirements(
                                        document.processed_content[:5000]  # Limit content
                                    )
                                    logger.info(f"Extracted {len(requirements)} requirements from {doc.id}")
                                except Exception as e:
                                    logger.error(f"Failed to extract requirements: {e}")

                            # Generate embeddings if requested
                            if generate_embeddings:
                                try:
                                    # This would normally call an embedding service
                                    logger.info(f"Would generate embeddings for {doc.id}")
                                except Exception as e:
                                    logger.error(f"Failed to generate embeddings: {e}")

                        analysis_jobs[analysis_id]["documents_processed"] += 1

                    analysis_jobs[analysis_id]["status"] = "completed"

                except Exception as e:
                    logger.error(f"Analysis failed: {e}")
                    analysis_jobs[analysis_id]["status"] = "failed"
                    analysis_jobs[analysis_id]["error"] = str(e)
                finally:
                    await bg_db.close()

        background_tasks.add_task(process_analysis)

        return {
            "analysis_id": analysis_id,
            "status": "pending",
            "document_count": len(documents)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))