"""Semantic search endpoints using vector embeddings."""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.search import (
    SemanticSearchRequest,
    SemanticSearchResponse,
    SimilarRequirement,
    DuplicateRequirementPair,
    RequirementCluster
)
from src.db.session import get_db
from src.middleware.auth import get_current_user
from src.models.user import User
from src.services.vector_service import VectorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["semantic-search"])


@router.post(
    "/requirements",
    response_model=SemanticSearchResponse,
    summary="Search requirements by semantic similarity",
    description="Find similar requirements using vector embeddings and AI"
)
async def search_requirements(
    request: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> SemanticSearchResponse:
    """
    Search for similar requirements using semantic similarity.

    This endpoint uses vector embeddings to find requirements that are
    semantically similar to the query, even if they don't share exact keywords.

    Args:
        request: Search parameters
        db: Database session
        current_user: Authenticated user

    Returns:
        List of similar requirements with similarity scores
    """
    try:
        vector_service = VectorService(db)

        # Perform semantic search
        results = await vector_service.search_similar_requirements(
            query=request.query,
            limit=request.limit,
            threshold=request.similarity_threshold,
            tenant_id=current_user.tenant_id if current_user.tenant_id else None
        )

        # Format response
        similar_requirements = []
        for result in results:
            similar_requirements.append(SimilarRequirement(
                id=result["id"],
                document_id=result["document_id"],
                requirement_text=result["requirement"],
                document_name=result.get("document", "Unknown"),
                tender_title=result.get("tender", "Unknown"),
                similarity_score=result["similarity"],
                metadata=result.get("metadata", {}),
                confidence=result.get("confidence", 0.8)
            ))

        return SemanticSearchResponse(
            query=request.query,
            results=similar_requirements,
            total_results=len(similar_requirements),
            search_type="semantic",
            processing_time_ms=0  # Could track actual time
        )

    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.get(
    "/requirements/duplicates/{tender_id}",
    response_model=List[DuplicateRequirementPair],
    summary="Find duplicate requirements in a tender",
    description="Detect duplicate or near-duplicate requirements across documents"
)
async def find_duplicate_requirements(
    tender_id: UUID,
    similarity_threshold: float = Query(
        0.9,
        ge=0.5,
        le=1.0,
        description="Minimum similarity to consider duplicates"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[DuplicateRequirementPair]:
    """
    Find duplicate requirements across documents in a tender.

    This helps identify redundant requirements that appear in multiple
    documents with slightly different wording.

    Args:
        tender_id: Tender to analyze
        similarity_threshold: Minimum similarity score (0.5-1.0)
        db: Database session
        current_user: Authenticated user

    Returns:
        List of duplicate requirement pairs
    """
    try:
        vector_service = VectorService(db)

        # Find duplicates
        duplicates = await vector_service.find_cross_document_duplicates(
            tender_id=tender_id,
            similarity_threshold=similarity_threshold,
            tenant_id=current_user.tenant_id if current_user.tenant_id else None
        )

        # Format response
        duplicate_pairs = []
        for req1, req2, similarity in duplicates:
            duplicate_pairs.append(DuplicateRequirementPair(
                requirement_1={
                    "id": req1["id"],
                    "text": req1["text"],
                    "document": req1["document"],
                    "metadata": req1.get("metadata", {})
                },
                requirement_2={
                    "id": req2["id"],
                    "text": req2["text"],
                    "document": req2["document"],
                    "metadata": req2.get("metadata", {})
                },
                similarity_score=similarity
            ))

        return duplicate_pairs

    except Exception as e:
        logger.error(f"Duplicate detection failed for tender {tender_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Duplicate detection failed: {str(e)}"
        )


@router.post(
    "/requirements/similar-tenders",
    response_model=List[dict],
    summary="Find tenders with similar requirements",
    description="Find other tenders that have similar requirements patterns"
)
async def find_similar_tenders(
    query: str = Query(..., description="Requirement pattern to search for"),
    limit: int = Query(5, ge=1, le=20, description="Maximum tenders to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[dict]:
    """
    Find tenders with similar requirement patterns.

    Useful for identifying similar market opportunities or reusable bid content.

    Args:
        query: Requirement pattern to match
        limit: Maximum results
        db: Database session
        current_user: Authenticated user

    Returns:
        List of similar tenders with matching requirements
    """
    try:
        vector_service = VectorService(db)

        # Search for similar requirements
        similar_reqs = await vector_service.search_similar_requirements(
            query=query,
            limit=limit * 3,  # Get more to group by tender
            threshold=0.7,
            tenant_id=current_user.tenant_id if current_user.tenant_id else None
        )

        # Group by tender
        tenders_map = {}
        for req in similar_reqs:
            tender_title = req.get("tender", "Unknown")
            if tender_title not in tenders_map:
                tenders_map[tender_title] = {
                    "tender_title": tender_title,
                    "matching_requirements": [],
                    "avg_similarity": 0.0,
                    "total_matches": 0
                }

            tenders_map[tender_title]["matching_requirements"].append({
                "requirement": req["requirement"][:100] + "...",
                "similarity": req["similarity"]
            })
            tenders_map[tender_title]["total_matches"] += 1

        # Calculate average similarity per tender
        for tender_data in tenders_map.values():
            similarities = [r["similarity"] for r in tender_data["matching_requirements"]]
            tender_data["avg_similarity"] = sum(similarities) / len(similarities)

        # Sort by average similarity and limit
        similar_tenders = sorted(
            tenders_map.values(),
            key=lambda x: x["avg_similarity"],
            reverse=True
        )[:limit]

        return similar_tenders

    except Exception as e:
        logger.error(f"Similar tender search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )