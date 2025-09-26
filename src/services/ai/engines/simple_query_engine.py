"""Simple query engine for basic RAG queries."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.ai.vector_store_service import VectorStoreService
from src.services.ai.mistral_service import get_mistral_service
from src.models.document_embedding import DocumentEmbedding
from src.core.ai_config import ai_config

logger = logging.getLogger(__name__)


class QueryResult:
    """Result from a query operation."""

    def __init__(
        self,
        query: str,
        answer: str,
        sources: List[Dict[str, Any]],
        metadata: Dict[str, Any] = None,
        confidence: float = 1.0
    ):
        self.query = query
        self.answer = answer
        self.sources = sources
        self.metadata = metadata or {}
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query": self.query,
            "answer": self.answer,
            "sources": self.sources,
            "metadata": self.metadata,
            "confidence": self.confidence
        }


class SimpleQueryEngine:
    """Simple query engine for basic vector search and response generation."""

    def __init__(self, db: AsyncSession):
        """
        Initialize simple query engine.

        Args:
            db: Database session
        """
        self.db = db
        self.vector_store = VectorStoreService(db)
        self.mistral_service = get_mistral_service()

    async def query(
        self,
        query_text: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        use_hybrid: bool = False
    ) -> QueryResult:
        """
        Execute a simple query.

        Args:
            query_text: Query text
            top_k: Number of similar chunks to retrieve
            filters: Additional filters for search
            use_cache: Whether to use cached results
            use_hybrid: Whether to use hybrid search

        Returns:
            QueryResult with answer and sources
        """
        start_time = datetime.utcnow()

        try:
            # Check cache if enabled
            if use_cache and ai_config.enable_query_cache:
                cached = await self.vector_store.get_cached_response(query_text)
                if cached:
                    logger.info(f"Returning cached response for query: {query_text[:50]}...")
                    return QueryResult(**cached)

            # Generate query embedding
            logger.info(f"Processing query: {query_text[:50]}...")
            query_embedding = await self.mistral_service.generate_embedding(query_text)

            # Perform search
            if use_hybrid and ai_config.enable_hybrid_search:
                logger.info("Using hybrid search")
                search_results = await self.vector_store.hybrid_search(
                    query_text=query_text,
                    query_embedding=query_embedding,
                    top_k=top_k
                )
            else:
                logger.info("Using vector similarity search")
                search_results = await self.vector_store.search_similar(
                    query_embedding=query_embedding,
                    top_k=top_k,
                    filters=filters
                )

            if not search_results:
                logger.warning("No similar documents found")
                return QueryResult(
                    query=query_text,
                    answer="Je n'ai pas trouvé d'informations pertinentes dans les documents pour répondre à cette question.",
                    sources=[],
                    confidence=0.0
                )

            # Prepare context from search results
            context = self._prepare_context(search_results)

            # Generate answer using LLM
            answer = await self._generate_answer(
                query_text,
                context,
                search_results
            )

            # Prepare sources
            sources = self._prepare_sources(search_results)

            # Calculate confidence
            confidence = self._calculate_confidence(search_results)

            # Create result
            result = QueryResult(
                query=query_text,
                answer=answer,
                sources=sources,
                metadata={
                    "top_k": len(search_results),
                    "search_type": "hybrid" if use_hybrid else "vector",
                    "processing_time_ms": int(
                        (datetime.utcnow() - start_time).total_seconds() * 1000
                    )
                },
                confidence=confidence
            )

            # Cache result if enabled
            if use_cache and ai_config.enable_query_cache:
                await self.vector_store.cache_query(
                    query_text=query_text,
                    query_embedding=query_embedding,
                    response=result.to_dict()
                )

            logger.info(f"Query completed with confidence: {confidence:.2f}")
            return result

        except Exception as e:
            logger.error(f"Query failed: {e}")
            return QueryResult(
                query=query_text,
                answer=f"Une erreur s'est produite lors du traitement de votre question: {str(e)}",
                sources=[],
                confidence=0.0
            )

    def _prepare_context(
        self,
        search_results: List[Tuple[DocumentEmbedding, float]]
    ) -> str:
        """
        Prepare context from search results.

        Args:
            search_results: List of (embedding, score) tuples

        Returns:
            Formatted context string
        """
        context_parts = []

        for i, (embedding, score) in enumerate(search_results, 1):
            # Add source reference and content
            context_part = f"[Source {i}] (Pertinence: {score:.2f})\n"

            # Add section info if available
            if embedding.section_type:
                context_part += f"Section: {embedding.section_type}\n"

            # Add the actual text content
            context_part += f"{embedding.chunk_text}\n"
            context_parts.append(context_part)

        return "\n---\n".join(context_parts)

    async def _generate_answer(
        self,
        query: str,
        context: str,
        search_results: List[Tuple[DocumentEmbedding, float]]
    ) -> str:
        """
        Generate answer using LLM.

        Args:
            query: User query
            context: Retrieved context
            search_results: Search results for additional info

        Returns:
            Generated answer
        """
        # Build system prompt
        system_prompt = """Tu es un assistant expert en marchés publics français.
        Tu réponds aux questions en te basant UNIQUEMENT sur le contexte fourni.

        Règles importantes:
        1. Cite toujours les sources pertinentes [Source N]
        2. Si l'information n'est pas dans le contexte, dis-le clairement
        3. Sois précis et factuel
        4. Utilise un français professionnel
        5. Structure ta réponse de manière claire
        """

        # Build user prompt
        user_prompt = f"""Question: {query}

Contexte disponible:
{context}

Réponds à la question en te basant uniquement sur le contexte fourni.
Cite les sources entre crochets [Source N] pour chaque information importante."""

        # Generate response
        answer = await self.mistral_service.generate_completion(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.1  # Low temperature for factual responses
        )

        return answer

    def _prepare_sources(
        self,
        search_results: List[Tuple[DocumentEmbedding, float]]
    ) -> List[Dict[str, Any]]:
        """
        Prepare source information.

        Args:
            search_results: Search results

        Returns:
            List of source dictionaries
        """
        sources = []

        for embedding, score in search_results:
            source = {
                "chunk_id": embedding.chunk_id,
                "document_id": str(embedding.document_id),
                "text": embedding.chunk_text[:200] + "..." if len(embedding.chunk_text) > 200 else embedding.chunk_text,
                "score": round(score, 3),
                "metadata": {
                    "document_type": embedding.document_type,
                    "section_type": embedding.section_type,
                    "page_number": embedding.page_number,
                    "chunk_index": embedding.chunk_index
                }
            }
            sources.append(source)

        return sources

    def _calculate_confidence(
        self,
        search_results: List[Tuple[DocumentEmbedding, float]]
    ) -> float:
        """
        Calculate confidence score for the answer.

        Args:
            search_results: Search results

        Returns:
            Confidence score (0.0 to 1.0)
        """
        if not search_results:
            return 0.0

        # Calculate based on top result score and number of relevant results
        top_score = search_results[0][1]

        # Count high-quality results (score > threshold)
        high_quality = sum(1 for _, score in search_results if score > ai_config.similarity_threshold)

        # Weighted confidence
        confidence = (top_score * 0.6) + (min(high_quality / 3, 1.0) * 0.4)

        return min(max(confidence, 0.0), 1.0)

    async def query_with_feedback(
        self,
        query_text: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[QueryResult, str]:
        """
        Query with feedback collection setup.

        Args:
            query_text: Query text
            top_k: Number of results
            filters: Search filters

        Returns:
            Tuple of (QueryResult, feedback_id)
        """
        # Execute query
        result = await self.query(
            query_text=query_text,
            top_k=top_k,
            filters=filters
        )

        # Generate feedback ID for tracking
        import hashlib
        feedback_id = hashlib.md5(
            f"{query_text}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()

        # Store in metadata for feedback reference
        result.metadata["feedback_id"] = feedback_id

        return result, feedback_id

    async def submit_feedback(
        self,
        feedback_id: str,
        query_text: str,
        answer: str,
        feedback_type: str,
        feedback_text: Optional[str] = None,
        rating: Optional[int] = None,
        user_id: Optional[UUID] = None
    ):
        """
        Submit feedback for a query result.

        Args:
            feedback_id: Feedback ID from query
            query_text: Original query
            answer: Generated answer
            feedback_type: Type of feedback
            feedback_text: Detailed feedback
            rating: Rating (1-5)
            user_id: User ID
        """
        try:
            await self.vector_store.add_feedback(
                query_text=query_text,
                response_text=answer,
                feedback_type=feedback_type,
                feedback_text=feedback_text,
                rating=rating,
                user_id=user_id
            )
            logger.info(f"Feedback submitted for query: {feedback_id}")
        except Exception as e:
            logger.error(f"Failed to submit feedback: {e}")