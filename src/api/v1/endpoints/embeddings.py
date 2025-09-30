"""API endpoints for embeddings management."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Dict, Any, Optional
from uuid import UUID
import logging

from src.db.session import get_async_db
from src.middleware.auth import get_current_user
from src.models.user import User
from src.services.embedding_service import EmbeddingService
from src.services.ai.mistral_service import get_mistral_service
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/embeddings", tags=["Embeddings"])


class GenerateEmbeddingRequest(BaseModel):
    """Request model for generating embeddings."""
    text: str
    metadata: Optional[Dict[str, Any]] = None


class GenerateEmbeddingResponse(BaseModel):
    """Response model for generated embeddings."""
    embedding: List[float]
    dimension: int
    model: str = "mistral-embed"


class EmbeddingStatusResponse(BaseModel):
    """Response model for embedding status."""
    tender_id: str
    total_embeddings: int
    total_documents: int
    avg_dimension: float
    storage_size: int
    status: str


class SearchRequest(BaseModel):
    """Request model for semantic search."""
    query: str
    tender_id: Optional[UUID] = None
    document_type: Optional[str] = None
    top_k: int = 10
    threshold: float = 0.7


class SearchResult(BaseModel):
    """Search result item."""
    document_id: str
    chunk_id: str
    text: str
    similarity_score: float
    metadata: Dict[str, Any]


@router.post("/generate", response_model=GenerateEmbeddingResponse)
async def generate_embedding(
    request: GenerateEmbeddingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Generate an embedding for a text.

    This endpoint generates a vector embedding for the provided text using
    the Mistral embedding model.
    """
    try:
        mistral_service = get_mistral_service()

        # Generate embedding
        embedding = await mistral_service.generate_embedding(
            text=request.text,
            metadata=request.metadata
        )

        return GenerateEmbeddingResponse(
            embedding=embedding,
            dimension=len(embedding),
            model="mistral-embed"
        )

    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate embedding: {str(e)}"
        )


@router.get("/status/{tender_id}", response_model=EmbeddingStatusResponse)
async def get_embeddings_status(
    tender_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get embedding status for a tender.

    Returns statistics about embeddings for all documents in a tender.
    """
    try:
        # Query embedding statistics
        query = text("""
            SELECT
                COUNT(DISTINCT de.id) as total_embeddings,
                COUNT(DISTINCT de.document_id) as total_documents,
                AVG(array_length(de.embedding::float[], 1)) as avg_dimension,
                SUM(pg_column_size(de.embedding)) as storage_size
            FROM document_embeddings de
            JOIN procurement_documents pd ON de.document_id = pd.id
            WHERE pd.tender_id = :tender_id
        """)

        result = await db.execute(query, {"tender_id": str(tender_id)})
        row = result.fetchone()

        if row and row.total_embeddings > 0:
            return EmbeddingStatusResponse(
                tender_id=str(tender_id),
                total_embeddings=row.total_embeddings or 0,
                total_documents=row.total_documents or 0,
                avg_dimension=row.avg_dimension or 0,
                storage_size=row.storage_size or 0,
                status="indexed"
            )
        else:
            return EmbeddingStatusResponse(
                tender_id=str(tender_id),
                total_embeddings=0,
                total_documents=0,
                avg_dimension=0,
                storage_size=0,
                status="not_indexed"
            )

    except Exception as e:
        logger.error(f"Failed to get embedding status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get embedding status: {str(e)}"
        )


@router.post("/tender/{tender_id}/generate")
async def generate_tender_embeddings(
    tender_id: UUID,
    force_regenerate: bool = Query(False, description="Force regeneration of existing embeddings"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Generate embeddings for all documents in a tender.

    This endpoint processes all documents in a tender and generates embeddings
    for their content.
    """
    try:
        embedding_service = EmbeddingService(db)

        # Process all documents in the tender
        result = await embedding_service.generate_tender_embeddings(
            tender_id=tender_id,
            force_regenerate=force_regenerate
        )

        return {
            "tender_id": str(tender_id),
            "documents_processed": result["documents_processed"],
            "total_embeddings": result["total_embeddings"],
            "status": "completed"
        }

    except Exception as e:
        logger.error(f"Failed to generate tender embeddings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate tender embeddings: {str(e)}"
        )


@router.post("/search", response_model=List[SearchResult])
async def search_embeddings(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Search for similar content using embeddings.

    Performs semantic search across document embeddings using vector similarity.
    """
    try:
        # Generate embedding for query
        mistral_service = get_mistral_service()
        query_embedding = await mistral_service.generate_embedding(request.query)

        # Build search query with filters
        filters = []
        params = {"query_embedding": str(query_embedding)}

        if request.tender_id:
            filters.append("pd.tender_id = :tender_id")
            params["tender_id"] = str(request.tender_id)

        if request.document_type:
            filters.append("de.document_type = :document_type")
            params["document_type"] = request.document_type

        where_clause = " AND " + " AND ".join(filters) if filters else ""

        # Search using pgvector
        query = text(f"""
            SELECT
                de.document_id,
                de.chunk_id,
                de.chunk_text,
                de.metadata,
                1 - (de.embedding <=> CAST(:query_embedding AS vector)) as similarity
            FROM document_embeddings de
            JOIN procurement_documents pd ON de.document_id = pd.id
            WHERE 1=1 {where_clause}
              AND 1 - (de.embedding <=> CAST(:query_embedding AS vector)) > :threshold
            ORDER BY similarity DESC
            LIMIT :limit
        """)

        params["threshold"] = request.threshold
        params["limit"] = request.top_k

        result = await db.execute(query, params)
        rows = result.fetchall()

        # Format results
        results = []
        for row in rows:
            results.append(SearchResult(
                document_id=str(row.document_id),
                chunk_id=row.chunk_id,
                text=row.chunk_text,
                similarity_score=row.similarity,
                metadata=row.metadata or {}
            ))

        return results

    except Exception as e:
        logger.error(f"Failed to search embeddings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search: {str(e)}"
        )


@router.delete("/tender/{tender_id}")
async def delete_tender_embeddings(
    tender_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Delete all embeddings for a tender.

    Removes all vector embeddings associated with documents in a tender.
    """
    try:
        query = text("""
            DELETE FROM document_embeddings
            WHERE document_id IN (
                SELECT id FROM procurement_documents
                WHERE tender_id = :tender_id
            )
        """)

        result = await db.execute(query, {"tender_id": str(tender_id)})
        await db.commit()

        return {
            "tender_id": str(tender_id),
            "deleted_count": result.rowcount,
            "status": "deleted"
        }

    except Exception as e:
        logger.error(f"Failed to delete embeddings: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete embeddings: {str(e)}"
        )