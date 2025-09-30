"""AI extraction endpoints."""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.middleware.auth import get_current_user
from src.db.session import get_db
from src.api.v1.schemas.extraction import (
    ExtractionRequest,
    ExtractionResponse,
    ExtractionStatusResponse,
    RequirementsListResponse,
    ExtractedRequirement,
    ExtractionType
)
from src.models.user import User
from src.repositories.requirements_repository import RequirementsRepository
from src.services.ai.extraction_service import ExtractionService
from src.services.ai.mistral_service import MistralAIService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/analysis",
    tags=["extraction", "ai"],
    responses={404: {"description": "Not found"}},
)


@router.post("/{tender_id}/extract", response_model=ExtractionResponse)
async def trigger_extraction(
    tender_id: UUID,
    request: Optional[ExtractionRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger AI extraction for a tender's documents.

    This endpoint initiates the extraction process for requirements
    from all documents associated with the specified tender.
    """
    try:
        # Use request body if provided, otherwise create default
        if not request:
            request = ExtractionRequest(
                tender_id=tender_id,
                extraction_type=ExtractionType.REQUIREMENTS,
                force_reprocess=False
            )

        # Initialize services
        mistral_service = MistralAIService()
        extraction_service = ExtractionService(db, mistral_service)

        # Trigger extraction
        result = await extraction_service.extract_requirements_from_tender(
            tender_id=tender_id,
            document_types=request.document_types,
            force_reprocess=request.force_reprocess
        )

        return ExtractionResponse(
            analysis_id=result["analysis_id"],
            tender_id=tender_id,
            status=result["status"],
            message=result["message"],
            documents_processed=result["documents_processed"],
            requirements_extracted=result["requirements_extracted"]
        )

    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}"
        )


@router.get("/{analysis_id}/status", response_model=ExtractionStatusResponse)
async def get_extraction_status(
    analysis_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the status of an ongoing extraction."""
    try:
        extraction_service = ExtractionService(db)
        status_data = await extraction_service.get_analysis_status(analysis_id)

        if not status_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found"
            )

        return ExtractionStatusResponse(**status_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get extraction status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/tender/{tender_id}/requirements", response_model=RequirementsListResponse)
async def get_extracted_requirements(
    tender_id: UUID,
    category: Optional[str] = Query(None, description="Filter by category"),
    is_mandatory: Optional[bool] = Query(None, description="Filter by mandatory status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all extracted requirements for a tender.

    Returns a list of all requirements that have been extracted
    from the tender's documents, with optional filtering.
    """
    try:
        req_repo = RequirementsRepository(db)

        # Get requirements
        requirements = await req_repo.get_by_tender(
            tender_id=tender_id,
            category=category,
            is_mandatory=is_mandatory
        )

        if not requirements:
            # Return empty response instead of 404
            return RequirementsListResponse(
                tender_id=tender_id,
                total_requirements=0,
                requirements=[],
                extraction_date=None,
                analysis_id=None
            )

        # Convert to response schema
        req_list = []
        for req in requirements:
            req_schema = ExtractedRequirement(
                requirement_text=req.requirement_text,
                category=req.category,
                priority=req.priority,
                is_mandatory=req.is_mandatory,
                source_document=req.source_document,
                page_number=req.page_number,
                confidence_score=req.confidence_score,
                metadata=req.extraction_metadata or {}
            )
            req_list.append(req_schema)

        # Get the latest analysis for this tender
        from src.models.analysis import AnalysisHistory
        from sqlalchemy import select, desc

        result = await db.execute(
            select(AnalysisHistory)
            .where(AnalysisHistory.tender_id == tender_id)
            .order_by(desc(AnalysisHistory.created_at))
            .limit(1)
        )
        latest_analysis = result.scalar_one_or_none()

        return RequirementsListResponse(
            tender_id=tender_id,
            total_requirements=len(req_list),
            requirements=req_list,
            extraction_date=requirements[0].created_at if requirements else None,
            analysis_id=latest_analysis.id if latest_analysis else None
        )

    except Exception as e:
        logger.error(f"Failed to get requirements: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{tender_id}/extract-simple", response_model=ExtractionResponse)
async def simple_extraction(
    tender_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Perform a simple extraction without AI (rule-based).

    This is a fallback endpoint for testing when Mistral is unavailable.
    """
    try:
        extraction_service = ExtractionService(db, mistral_service=None)

        # Use simple extraction
        result = await extraction_service.extract_requirements_from_tender(
            tender_id=tender_id,
            force_reprocess=True
        )

        return ExtractionResponse(
            analysis_id=result["analysis_id"],
            tender_id=tender_id,
            status=result["status"],
            message=result["message"] + " (simple extraction)",
            documents_processed=result["documents_processed"],
            requirements_extracted=result["requirements_extracted"]
        )

    except Exception as e:
        logger.error(f"Simple extraction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}"
        )