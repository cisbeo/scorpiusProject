"""Vector store service for pgvector operations."""

import logging
import hashlib
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from uuid import UUID
import json
import asyncio
import numpy as np

from sqlalchemy import text, select, delete, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from src.models.document_embedding import DocumentEmbedding, QueryCache, RAGFeedback
from src.services.ai.mistral_service import get_mistral_service
from src.core.ai_config import ai_config

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Service for managing vector embeddings in pgvector."""

    def __init__(self, db: AsyncSession):
        """
        Initialize vector store service.

        Args:
            db: Database session
        """
        self.db = db
        self.mistral_service = get_mistral_service()
        self.vector_dimension = ai_config.vector_dimension
        self.similarity_threshold = ai_config.similarity_threshold
        self.similarity_top_k = ai_config.similarity_top_k

    async def add_embeddings(
        self,
        embeddings: List[Dict[str, Any]],
        document_id: UUID,
        batch_size: int = 100
    ) -> int:
        """
        Add embeddings to the vector store.

        Args:
            embeddings: List of embedding data with text and vectors
            document_id: Document UUID
            batch_size: Batch size for insertion

        Returns:
            Number of embeddings added
        """
        try:
            added_count = 0

            for i in range(0, len(embeddings), batch_size):
                batch = embeddings[i:i + batch_size]

                for emb_data in batch:
                    # Use raw SQL to properly insert vector data
                    embedding_str = '[' + ','.join(map(str, emb_data["embedding"])) + ']'

                    # Use CAST function instead of :: operator to avoid parameter binding issues
                    query = text("""
                        INSERT INTO document_embeddings
                        (id, document_id, chunk_id, chunk_text, embedding, metadata,
                         document_type, section_type, page_number, chunk_index,
                         chunk_size, overlap_size, language, confidence_score, created_at, updated_at)
                        VALUES
                        (:id, :document_id, :chunk_id, :chunk_text, CAST(:embedding AS vector),
                         CAST(:metadata AS jsonb), :document_type, :section_type, :page_number,
                         :chunk_index, :chunk_size, :overlap_size, :language, :confidence_score, NOW(), NOW())
                    """)

                    await self.db.execute(query, {
                        "id": str(uuid.uuid4()),
                        "document_id": str(document_id),
                        "chunk_id": emb_data["chunk_id"],
                        "chunk_text": emb_data["chunk_text"],
                        "embedding": embedding_str,
                        "metadata": json.dumps(emb_data.get("metadata", {})),
                        "document_type": emb_data.get("document_type"),
                        "section_type": emb_data.get("section_type"),
                        "page_number": emb_data.get("page_number"),
                        "chunk_index": emb_data["chunk_index"],
                        "chunk_size": len(emb_data["chunk_text"]),
                        "overlap_size": emb_data.get("overlap_size", 0),
                        "language": emb_data.get("language", "fr"),
                        "confidence_score": emb_data.get("confidence_score", 1.0)
                    })

                # Commit batch
                await self.db.commit()
                added_count += len(batch)

                logger.info(f"Added batch {i//batch_size + 1}: {len(batch)} embeddings")

            logger.info(f"Successfully added {added_count} embeddings for document {document_id}")
            return added_count

        except Exception as e:
            logger.error(f"Failed to add embeddings: {e}")
            await self.db.rollback()
            raise

    async def search_similar(
        self,
        query_embedding: List[float],
        top_k: Optional[int] = None,
        threshold: Optional[float] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[DocumentEmbedding, float]]:
        """
        Search for similar embeddings using vector similarity.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            threshold: Minimum similarity threshold
            filters: Additional filters (document_type, section_type, etc.)

        Returns:
            List of (embedding, similarity_score) tuples
        """
        try:
            top_k = top_k or self.similarity_top_k
            threshold = threshold or self.similarity_threshold

            # Build base query with cosine similarity
            # Note: In actual implementation, we'll use pgvector's <=> operator
            query = text("""
                SELECT
                    id,
                    document_id,
                    chunk_id,
                    chunk_text,
                    metadata,
                    document_type,
                    section_type,
                    page_number,
                    chunk_index,
                    1 - (embedding <=> CAST(:query_vector AS vector)) as similarity
                FROM document_embeddings
                WHERE 1=1
            """)

            # Add filters
            filter_conditions = []
            # Convert embedding list to PostgreSQL vector format
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
            params = {"query_vector": embedding_str}

            if filters:
                if "document_type" in filters:
                    filter_conditions.append("document_type = :document_type")
                    params["document_type"] = filters["document_type"]

                if "section_type" in filters:
                    filter_conditions.append("section_type = :section_type")
                    params["section_type"] = filters["section_type"]

                if "document_id" in filters:
                    filter_conditions.append("document_id = :document_id")
                    params["document_id"] = filters["document_id"]

            # Combine query with filters
            if filter_conditions:
                filter_clause = " AND " + " AND ".join(filter_conditions)
                query = text(str(query) + filter_clause)

            # Add similarity threshold and ordering
            query = text(str(query) + f"""
                AND 1 - (embedding <=> CAST(:query_vector AS vector)) > :threshold
                ORDER BY embedding <=> CAST(:query_vector AS vector)
                LIMIT :limit
            """)
            params["threshold"] = threshold
            params["limit"] = top_k

            # Execute query
            result = await self.db.execute(query, params)
            rows = result.fetchall()

            # Convert to DocumentEmbedding objects with scores
            results = []
            for row in rows:
                # Create embedding object from row data
                embedding = DocumentEmbedding(
                    id=row[0],
                    document_id=row[1],
                    chunk_id=row[2],
                    chunk_text=row[3],
                    metadata=row[4],
                    document_type=row[5],
                    section_type=row[6],
                    page_number=row[7],
                    chunk_index=row[8]
                )
                similarity_score = row[9]
                results.append((embedding, similarity_score))

            logger.info(f"Found {len(results)} similar embeddings")
            return results

        except Exception as e:
            logger.error(f"Failed to search similar embeddings: {e}")
            raise

    async def hybrid_search(
        self,
        query_text: str,
        query_embedding: Optional[List[float]] = None,
        top_k: Optional[int] = None,
        alpha: float = 0.5
    ) -> List[Tuple[DocumentEmbedding, float]]:
        """
        Perform hybrid search combining vector and keyword search.

        Args:
            query_text: Query text for keyword search
            query_embedding: Query vector (will be generated if not provided)
            top_k: Number of results
            alpha: Weight for vector search (1-alpha for keyword search)

        Returns:
            List of (embedding, combined_score) tuples
        """
        try:
            # Generate embedding if not provided
            if query_embedding is None:
                query_embedding = await self.mistral_service.generate_embedding(query_text)

            top_k = top_k or self.similarity_top_k

            # Vector search
            vector_results = await self.search_similar(
                query_embedding,
                top_k=top_k * 2  # Get more for reranking
            )

            # Keyword search using pg_trgm
            keyword_query = text("""
                SELECT
                    id,
                    document_id,
                    chunk_id,
                    chunk_text,
                    metadata,
                    document_type,
                    section_type,
                    page_number,
                    chunk_index,
                    similarity(chunk_text, :query_text) as text_similarity
                FROM document_embeddings
                WHERE chunk_text % :query_text  -- Trigram similarity
                ORDER BY similarity(chunk_text, :query_text) DESC
                LIMIT :limit
            """)

            keyword_result = await self.db.execute(
                keyword_query,
                {"query_text": query_text, "limit": top_k * 2}
            )
            keyword_rows = keyword_result.fetchall()

            # Combine results
            combined_scores = {}

            # Add vector search results
            for embedding, vector_score in vector_results:
                combined_scores[embedding.chunk_id] = {
                    "embedding": embedding,
                    "vector_score": vector_score,
                    "keyword_score": 0,
                    "combined_score": vector_score * alpha
                }

            # Add keyword search results
            for row in keyword_rows:
                chunk_id = row[2]
                keyword_score = row[9]

                if chunk_id in combined_scores:
                    combined_scores[chunk_id]["keyword_score"] = keyword_score
                    combined_scores[chunk_id]["combined_score"] += keyword_score * (1 - alpha)
                else:
                    embedding = DocumentEmbedding(
                        id=row[0],
                        document_id=row[1],
                        chunk_id=row[2],
                        chunk_text=row[3],
                        metadata=row[4],
                        document_type=row[5],
                        section_type=row[6],
                        page_number=row[7],
                        chunk_index=row[8]
                    )
                    combined_scores[chunk_id] = {
                        "embedding": embedding,
                        "vector_score": 0,
                        "keyword_score": keyword_score,
                        "combined_score": keyword_score * (1 - alpha)
                    }

            # Sort by combined score and return top k
            sorted_results = sorted(
                combined_scores.values(),
                key=lambda x: x["combined_score"],
                reverse=True
            )[:top_k]

            results = [
                (item["embedding"], item["combined_score"])
                for item in sorted_results
            ]

            logger.info(f"Hybrid search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Failed to perform hybrid search: {e}")
            raise

    async def get_embeddings_by_document(
        self,
        document_id: UUID,
        section_type: Optional[str] = None
    ) -> List[DocumentEmbedding]:
        """
        Get all embeddings for a document.

        Args:
            document_id: Document UUID
            section_type: Optional section type filter

        Returns:
            List of embeddings
        """
        try:
            query = select(DocumentEmbedding).where(
                DocumentEmbedding.document_id == document_id
            )

            if section_type:
                query = query.where(DocumentEmbedding.section_type == section_type)

            query = query.order_by(DocumentEmbedding.chunk_index)

            result = await self.db.execute(query)
            embeddings = result.scalars().all()

            logger.info(f"Retrieved {len(embeddings)} embeddings for document {document_id}")
            return embeddings

        except Exception as e:
            logger.error(f"Failed to get embeddings: {e}")
            raise

    async def delete_embeddings(
        self,
        document_id: UUID
    ) -> int:
        """
        Delete all embeddings for a document.

        Args:
            document_id: Document UUID

        Returns:
            Number of embeddings deleted
        """
        try:
            # Count before deletion
            count_query = select(func.count(DocumentEmbedding.id)).where(
                DocumentEmbedding.document_id == document_id
            )
            count_result = await self.db.execute(count_query)
            count = count_result.scalar()

            # Delete embeddings
            delete_query = delete(DocumentEmbedding).where(
                DocumentEmbedding.document_id == document_id
            )
            await self.db.execute(delete_query)
            await self.db.commit()

            logger.info(f"Deleted {count} embeddings for document {document_id}")
            return count

        except Exception as e:
            logger.error(f"Failed to delete embeddings: {e}")
            await self.db.rollback()
            raise

    async def cache_query(
        self,
        query_text: str,
        query_embedding: List[float],
        response: Dict[str, Any],
        ttl_seconds: Optional[int] = None
    ) -> QueryCache:
        """
        Cache a query and its response.

        Args:
            query_text: Query text
            query_embedding: Query embedding vector
            response: Response data
            ttl_seconds: Time to live in seconds

        Returns:
            Created cache entry
        """
        try:
            ttl = ttl_seconds or ai_config.cache_ttl_seconds
            query_hash = hashlib.sha256(query_text.encode()).hexdigest()
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)

            # Check if entry exists
            existing = await self.db.execute(
                select(QueryCache).where(QueryCache.query_hash == query_hash)
            )
            cache_entry = existing.scalar_one_or_none()

            if cache_entry:
                # Update existing entry
                cache_entry.hit_count += 1
                cache_entry.last_accessed_at = datetime.utcnow()
                cache_entry.expires_at = expires_at
                cache_entry.response = response
            else:
                # Create new entry
                cache_entry = QueryCache(
                    query_hash=query_hash,
                    query_text=query_text,
                    query_embedding=query_embedding,
                    response=response,
                    ttl_seconds=ttl,
                    expires_at=expires_at
                )
                self.db.add(cache_entry)

            await self.db.commit()
            logger.info(f"Cached query: {query_hash[:8]}")
            return cache_entry

        except Exception as e:
            logger.error(f"Failed to cache query: {e}")
            await self.db.rollback()
            raise

    async def get_cached_response(
        self,
        query_text: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached response for a query.

        Args:
            query_text: Query text

        Returns:
            Cached response or None
        """
        try:
            query_hash = hashlib.sha256(query_text.encode()).hexdigest()

            result = await self.db.execute(
                select(QueryCache).where(
                    and_(
                        QueryCache.query_hash == query_hash,
                        QueryCache.expires_at > datetime.utcnow()
                    )
                )
            )
            cache_entry = result.scalar_one_or_none()

            if cache_entry:
                # Update access time and hit count
                cache_entry.last_accessed_at = datetime.utcnow()
                cache_entry.hit_count += 1
                await self.db.commit()

                logger.info(f"Cache hit for query: {query_hash[:8]}")
                return cache_entry.response

            return None

        except Exception as e:
            logger.error(f"Failed to get cached response: {e}")
            return None

    async def add_feedback(
        self,
        query_text: str,
        response_text: str,
        feedback_type: str,
        feedback_text: Optional[str] = None,
        rating: Optional[int] = None,
        user_id: Optional[UUID] = None
    ) -> RAGFeedback:
        """
        Add user feedback for a RAG response.

        Args:
            query_text: Original query
            response_text: Generated response
            feedback_type: Type of feedback (positive, negative, correction)
            feedback_text: Detailed feedback
            rating: Rating (1-5)
            user_id: User who provided feedback

        Returns:
            Created feedback entry
        """
        try:
            feedback = RAGFeedback(
                query_text=query_text,
                response_text=response_text,
                feedback_type=feedback_type,
                feedback_text=feedback_text,
                rating=rating,
                user_id=user_id
            )
            self.db.add(feedback)
            await self.db.commit()

            logger.info(f"Added {feedback_type} feedback for query")
            return feedback

        except Exception as e:
            logger.error(f"Failed to add feedback: {e}")
            await self.db.rollback()
            raise

    async def clean_expired_cache(self) -> int:
        """
        Clean expired cache entries.

        Returns:
            Number of entries cleaned
        """
        try:
            # Count expired entries
            count_query = select(func.count(QueryCache.id)).where(
                QueryCache.expires_at <= datetime.utcnow()
            )
            count_result = await self.db.execute(count_query)
            count = count_result.scalar()

            # Delete expired entries
            delete_query = delete(QueryCache).where(
                QueryCache.expires_at <= datetime.utcnow()
            )
            await self.db.execute(delete_query)
            await self.db.commit()

            logger.info(f"Cleaned {count} expired cache entries")
            return count

        except Exception as e:
            logger.error(f"Failed to clean cache: {e}")
            await self.db.rollback()
            raise

    async def get_index_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector index.

        Returns:
            Index statistics
        """
        try:
            # Count total embeddings
            total_query = select(func.count(DocumentEmbedding.id))
            total_result = await self.db.execute(total_query)
            total_embeddings = total_result.scalar()

            # Count by document type
            type_query = select(
                DocumentEmbedding.document_type,
                func.count(DocumentEmbedding.id)
            ).group_by(DocumentEmbedding.document_type)
            type_result = await self.db.execute(type_query)
            by_type = dict(type_result.fetchall())

            # Count unique documents
            doc_query = select(func.count(func.distinct(DocumentEmbedding.document_id)))
            doc_result = await self.db.execute(doc_query)
            unique_documents = doc_result.scalar()

            # Cache stats
            cache_query = select(func.count(QueryCache.id))
            cache_result = await self.db.execute(cache_query)
            cache_entries = cache_result.scalar()

            # Feedback stats
            feedback_query = select(
                RAGFeedback.feedback_type,
                func.count(RAGFeedback.id)
            ).group_by(RAGFeedback.feedback_type)
            feedback_result = await self.db.execute(feedback_query)
            feedback_stats = dict(feedback_result.fetchall())

            return {
                "total_embeddings": total_embeddings,
                "unique_documents": unique_documents,
                "embeddings_by_type": by_type,
                "cache_entries": cache_entries,
                "feedback_stats": feedback_stats,
                "vector_dimension": self.vector_dimension,
                "similarity_threshold": self.similarity_threshold
            }

        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            raise