"""Search endpoints for vector similarity search."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from src.db.session import get_db
from src.middleware.auth import get_current_user_optional
from src.models.user import User
# from src.services.llamaindex_service import LlamaIndexService  # Temporarily disabled - import issue
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class SearchRequest(BaseModel):
    """Request model for document search."""
    query: str
    top_k: int = 5
    filters: Optional[Dict[str, Any]] = None


class SearchResult(BaseModel):
    """Search result model."""
    score: float
    text: str
    document_id: str
    filename: str
    metadata: Dict[str, Any]


class SearchResponse(BaseModel):
    """Response model for search endpoint."""
    query: str
    results: List[SearchResult]
    total_results: int


class QueryRequest(BaseModel):
    """Request model for question answering."""
    question: str
    top_k: int = 3


class QueryResponse(BaseModel):
    """Response model for question answering."""
    question: str
    answer: str
    sources: List[SearchResult]
    metadata: Dict[str, Any]


# Initialize LlamaIndex service (singleton)
llamaindex_service = None
# try:
#     llamaindex_service = LlamaIndexService()
#     logger.info("LlamaIndex service initialized for search endpoints")
# except Exception as e:
#     logger.error(f"Failed to initialize LlamaIndex service: {e}")


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Search indexed documents using vector similarity.

    Args:
        request: Search request with query and parameters
        current_user: Optional authenticated user
        db: Database session

    Returns:
        SearchResponse with matching documents
    """
    if not llamaindex_service:
        raise HTTPException(
            status_code=503,
            detail="Search service is unavailable"
        )

    try:
        logger.info(f"Searching for: '{request.query}' with top_k={request.top_k}")

        # Perform search
        results = llamaindex_service.search(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters
        )

        # Format response
        search_results = [
            SearchResult(
                score=r["score"],
                text=r["text"],
                document_id=r["document_id"],
                filename=r["filename"],
                metadata=r["metadata"]
            )
            for r in results
        ]

        response = SearchResponse(
            query=request.query,
            results=search_results,
            total_results=len(search_results)
        )

        logger.info(f"Search completed: {len(search_results)} results found")
        return response

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.post("/query", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Query indexed documents with a question (RAG).

    Args:
        request: Query request with question
        current_user: Optional authenticated user
        db: Database session

    Returns:
        QueryResponse with answer and sources
    """
    if not llamaindex_service:
        raise HTTPException(
            status_code=503,
            detail="Query service is unavailable"
        )

    try:
        logger.info(f"Processing query: '{request.question}'")

        # Execute query
        result = llamaindex_service.query(
            question=request.question,
            top_k=request.top_k
        )

        # Format sources
        sources = [
            SearchResult(
                score=s.get("score", 0.0),
                text=s.get("text", ""),
                document_id=s.get("document_id", ""),
                filename=s.get("filename", ""),
                metadata=s.get("metadata", {})
            )
            for s in result.get("sources", [])
        ]

        response = QueryResponse(
            question=result["question"],
            answer=result["answer"],
            sources=sources,
            metadata=result.get("metadata", {})
        )

        logger.info(f"Query completed with {len(sources)} sources")
        return response

    except Exception as e:
        logger.error(f"Query error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Query failed: {str(e)}"
        )


@router.get("/search/stats")
async def get_search_stats(
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Get statistics about the search index.

    Returns:
        Index statistics including document count and configuration
    """
    if not llamaindex_service:
        raise HTTPException(
            status_code=503,
            detail="Search service is unavailable"
        )

    try:
        stats = llamaindex_service.get_index_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting search stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get search stats: {str(e)}"
        )


@router.delete("/search/document/{document_id}")
async def delete_from_index(
    document_id: str,
    current_user: User = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a document from the search index.

    Args:
        document_id: Document ID to delete
        current_user: Authenticated user (required)
        db: Database session

    Returns:
        Success status
    """
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )

    if not llamaindex_service:
        raise HTTPException(
            status_code=503,
            detail="Search service is unavailable"
        )

    try:
        success = llamaindex_service.delete_document(document_id)
        if success:
            return {"message": f"Document {document_id} deleted from index"}
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Document {document_id} not found in index"
            )
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )


@router.post("/search/reindex")
async def reindex_all_documents(
    current_user: User = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Reindex all documents in the database.

    Args:
        current_user: Authenticated user (required)
        db: Database session

    Returns:
        Reindexing status
    """
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )

    if not llamaindex_service:
        raise HTTPException(
            status_code=503,
            detail="Search service is unavailable"
        )

    # This would typically trigger a background task to reindex all documents
    # For now, we'll just clear the index
    try:
        success = llamaindex_service.clear_index()
        if success:
            return {
                "message": "Index cleared. Documents need to be re-uploaded for indexing.",
                "status": "success"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to clear index"
            )
    except Exception as e:
        logger.error(f"Error reindexing: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Reindexing failed: {str(e)}"
        )