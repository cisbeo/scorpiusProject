"""RAG (Retrieval-Augmented Generation) API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field

from src.db.session import get_db
from src.middleware.auth import get_current_user_optional
from src.models.user import User
from src.services.ai.engines.router_engine import RouterQueryEngine
from src.core.ai_config import ai_config

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class QueryRequest(BaseModel):
    """Request model for RAG queries."""
    query: str = Field(..., description="The question to ask")
    engine: Optional[str] = Field(None, description="Force specific engine: 'simple', 'subquestion', or 'router'")
    top_k: Optional[int] = Field(5, description="Number of similar chunks to retrieve")
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional filters for search")
    use_cache: Optional[bool] = Field(True, description="Whether to use cached results")
    include_sources: Optional[bool] = Field(True, description="Include source references in response")


class QueryResponse(BaseModel):
    """Response model for RAG queries."""
    query: str = Field(..., description="The original query")
    answer: str = Field(..., description="Generated answer")
    sources: Optional[List[Dict[str, Any]]] = Field(None, description="Source references")
    confidence: float = Field(..., description="Confidence score (0-1)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    feedback_id: Optional[str] = Field(None, description="ID for submitting feedback")


class FeedbackRequest(BaseModel):
    """Request model for query feedback."""
    feedback_id: str = Field(..., description="Feedback ID from query response")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Rating from 1-5")
    feedback_type: str = Field("general", description="Type: 'positive', 'negative', 'correction', 'general'")
    feedback_text: Optional[str] = Field(None, description="Detailed feedback text")


class SearchRequest(BaseModel):
    """Request model for semantic search."""
    query: str = Field(..., description="Search query")
    document_ids: Optional[List[UUID]] = Field(None, description="Limit search to specific documents")
    top_k: Optional[int] = Field(10, description="Number of results to return")
    similarity_threshold: Optional[float] = Field(0.7, ge=0, le=1, description="Minimum similarity score")


@router.post("/query", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Execute a RAG query on indexed documents.

    This endpoint:
    - Processes natural language questions
    - Searches through indexed document chunks
    - Generates contextual answers using LLM
    - Returns sources and confidence scores

    The engine parameter allows forcing a specific query strategy:
    - 'simple': Direct vector search and response
    - 'subquestion': Decomposes complex queries
    - 'router': Automatically selects best strategy (default)
    """
    if not ai_config.enable_rag:
        raise HTTPException(
            status_code=503,
            detail="RAG features are currently disabled"
        )

    try:
        logger.info(f"Processing RAG query: {request.query[:100]}...")

        # Initialize appropriate engine
        if request.engine == "router" or request.engine is None:
            engine = RouterQueryEngine(db)
            result = await engine.query(
                query_text=request.query,
                top_k=request.top_k,
                filters=request.filters
            )
        else:
            # Direct engine selection
            from src.services.ai.engines.simple_query_engine import SimpleQueryEngine
            from src.services.ai.engines.subquestion_engine import SubQuestionQueryEngine

            if request.engine == "simple":
                engine = SimpleQueryEngine(db)
            elif request.engine == "subquestion":
                engine = SubQuestionQueryEngine(db)
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown engine: {request.engine}"
                )

            result = await engine.query(
                query_text=request.query,
                top_k=request.top_k,
                filters=request.filters,
                use_cache=request.use_cache
            )

        # Generate feedback ID for tracking
        import hashlib
        from datetime import datetime
        feedback_id = hashlib.md5(
            f"{request.query}{datetime.utcnow().isoformat()}{current_user.id if current_user else 'anon'}".encode()
        ).hexdigest()

        # Store feedback reference
        result.metadata["feedback_id"] = feedback_id

        # Filter sources if requested
        sources = result.sources if request.include_sources else None

        response = QueryResponse(
            query=result.query,
            answer=result.answer,
            sources=sources,
            confidence=result.confidence,
            metadata=result.metadata,
            feedback_id=feedback_id
        )

        logger.info(f"Query completed with confidence: {result.confidence:.2f}")
        return response

    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {str(e)}"
        )


@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Submit feedback for a query result.

    Helps improve the RAG system by collecting user feedback on:
    - Answer quality and relevance
    - Missing information
    - Incorrect information
    - General suggestions
    """
    try:
        from src.services.ai.vector_store_service import VectorStoreService

        vector_store = VectorStoreService(db)

        # Submit feedback
        await vector_store.add_feedback(
            query_text="",  # Would need to store/retrieve from feedback_id
            response_text="",  # Would need to store/retrieve from feedback_id
            feedback_type=request.feedback_type,
            feedback_text=request.feedback_text,
            rating=request.rating,
            user_id=current_user.id if current_user else None
        )

        logger.info(f"Feedback submitted: {request.feedback_id}")
        return {"message": "Feedback received successfully", "feedback_id": request.feedback_id}

    except Exception as e:
        logger.error(f"Feedback submission failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit feedback: {str(e)}"
        )


@router.post("/search", response_model=Dict[str, Any])
async def semantic_search(
    request: SearchRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Perform semantic search on indexed documents.

    Unlike /query, this endpoint:
    - Returns raw search results without LLM processing
    - Provides direct access to document chunks
    - Useful for debugging and advanced users
    """
    if not ai_config.enable_semantic_search:
        raise HTTPException(
            status_code=503,
            detail="Semantic search is currently disabled"
        )

    try:
        from src.services.ai.vector_store_service import VectorStoreService
        from src.services.ai.mistral_service import get_mistral_service

        vector_store = VectorStoreService(db)
        mistral_service = get_mistral_service()

        # Generate query embedding
        logger.info(f"Performing semantic search: {request.query[:100]}...")
        query_embedding = await mistral_service.generate_embedding(request.query)

        # Build filters
        filters = {}
        if request.document_ids:
            filters["document_ids"] = request.document_ids

        # Perform search
        if ai_config.enable_hybrid_search:
            search_results = await vector_store.hybrid_search(
                query_text=request.query,
                query_embedding=query_embedding,
                top_k=request.top_k
            )
        else:
            search_results = await vector_store.search_similar(
                query_embedding=query_embedding,
                top_k=request.top_k,
                filters=filters
            )

        # Filter by similarity threshold
        filtered_results = [
            (emb, score) for emb, score in search_results
            if score >= request.similarity_threshold
        ]

        # Format results
        results = []
        for embedding, score in filtered_results:
            results.append({
                "chunk_id": embedding.chunk_id,
                "document_id": str(embedding.document_id),
                "text": embedding.chunk_text,
                "score": round(score, 3),
                "metadata": {
                    "document_type": embedding.document_type,
                    "section_type": embedding.section_type,
                    "page_number": embedding.page_number,
                    "chunk_index": embedding.chunk_index
                }
            })

        logger.info(f"Search returned {len(results)} results")
        return {
            "query": request.query,
            "results": results,
            "total_results": len(results),
            "search_type": "hybrid" if ai_config.enable_hybrid_search else "vector"
        }

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/stats")
async def get_rag_statistics(
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Get RAG system statistics.

    Returns information about:
    - Number of indexed documents
    - Total chunks in vector store
    - Cache hit rate
    - Average query time
    - System configuration
    """
    try:
        from sqlalchemy import select, func
        from src.models.document_embedding import DocumentEmbedding
        from src.models.document import ProcurementDocument

        # Get embedding statistics
        embedding_count = await db.scalar(
            select(func.count(DocumentEmbedding.id))
        )

        unique_docs = await db.scalar(
            select(func.count(func.distinct(DocumentEmbedding.document_id)))
        )

        # Get document statistics
        total_docs = await db.scalar(
            select(func.count(ProcurementDocument.id))
        )

        indexed_docs = await db.scalar(
            select(func.count(ProcurementDocument.id)).where(
                ProcurementDocument.id.in_(
                    select(func.distinct(DocumentEmbedding.document_id))
                )
            )
        )

        # Calculate coverage
        indexing_coverage = (indexed_docs / total_docs * 100) if total_docs > 0 else 0

        stats = {
            "vector_store": {
                "total_embeddings": embedding_count,
                "unique_documents": unique_docs,
                "vector_dimension": ai_config.vector_dimension
            },
            "documents": {
                "total_documents": total_docs,
                "indexed_documents": indexed_docs,
                "indexing_coverage_percentage": round(indexing_coverage, 1)
            },
            "configuration": {
                "embedding_model": ai_config.embedding_model.value,
                "llm_model": ai_config.llm_model.value,
                "chunking_strategy": ai_config.chunking_strategy.value,
                "chunk_size": ai_config.chunk_size,
                "similarity_threshold": ai_config.similarity_threshold,
                "rag_enabled": ai_config.enable_rag,
                "hybrid_search_enabled": ai_config.enable_hybrid_search
            },
            "performance": {
                "cache_enabled": ai_config.enable_query_cache,
                "batch_size": ai_config.batch_size,
                "max_concurrent_requests": ai_config.max_concurrent_requests
            }
        }

        return stats

    except Exception as e:
        logger.error(f"Failed to get RAG statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )


@router.post("/reindex/{document_id}")
async def reindex_document(
    document_id: UUID,
    force: bool = Query(False, description="Force reindex even if already indexed"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Reindex a specific document.

    Useful when:
    - Document processing has improved
    - Chunking strategy has changed
    - Fixing indexing issues
    """
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required for reindexing"
        )

    try:
        from src.services.document_rag_integration import DocumentRAGIntegration
        from src.repositories.document_repository import DocumentRepository

        # Get document
        doc_repo = DocumentRepository(db)
        document = await doc_repo.get_by_id(document_id)

        if not document:
            raise HTTPException(
                status_code=404,
                detail="Document not found"
            )

        # Check ownership or admin rights
        # TODO: Add proper authorization check

        logger.info(f"Reindexing document {document_id}")

        # TODO: Implement actual reindexing logic
        # This would involve:
        # 1. Deleting existing embeddings
        # 2. Re-processing the document
        # 3. Creating new embeddings

        return {
            "message": "Document reindexing initiated",
            "document_id": str(document_id),
            "status": "processing"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reindexing failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Reindexing failed: {str(e)}"
        )