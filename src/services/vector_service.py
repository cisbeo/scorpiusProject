"""Service for managing vector embeddings with pgvector."""

import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.ai.mistral_service import get_mistral_service
from src.models.document_embedding import DocumentEmbedding

logger = logging.getLogger(__name__)


class VectorService:
    """Service pour gérer les embeddings vectoriels avec pgvector."""

    def __init__(self, db: AsyncSession):
        """
        Initialize vector service.

        Args:
            db: Async database session
        """
        self.db = db
        self.mistral = get_mistral_service()
        self.embedding_dimension = 1536  # Mistral embedding size

    async def create_requirement_embeddings(
        self,
        requirements: List[Dict[str, Any]],
        document_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> int:
        """
        Create and store embeddings for each requirement.

        Args:
            requirements: List of requirements to embed
            document_id: Document UUID
            tenant_id: Optional tenant ID

        Returns:
            Number of embeddings created
        """
        embeddings_created = 0

        try:
            for idx, req in enumerate(requirements):
                # Prepare text for embedding
                text = self._prepare_requirement_text(req)

                # Generate embedding via Mistral
                try:
                    embedding = await self.mistral.generate_embedding(text)

                    # Convert to numpy array for pgvector
                    embedding_vector = np.array(embedding, dtype=np.float32)

                    # Create embedding record
                    doc_embedding = DocumentEmbedding(
                        id=uuid4(),
                        document_id=document_id,
                        chunk_id=f"req_{idx}",
                        chunk_text=req.get("description", ""),
                        embedding=embedding_vector.tolist(),  # Store as list for now
                        metadata={
                            "category": req.get("category"),
                            "importance": req.get("importance"),
                            "is_mandatory": req.get("is_mandatory"),
                            "confidence": req.get("confidence", 0.8),
                            "keywords": req.get("keywords", [])
                        },
                        document_type=req.get("category", "general"),
                        section_type=req.get("section", "requirements"),
                        chunk_index=idx,
                        chunk_size=len(text),
                        confidence_score=req.get("confidence", 0.8),
                        tenant_id=tenant_id
                    )

                    self.db.add(doc_embedding)
                    embeddings_created += 1

                except Exception as e:
                    logger.error(f"Failed to create embedding for requirement {idx}: {e}")
                    continue

            # Commit all embeddings
            await self.db.commit()
            logger.info(f"Created {embeddings_created} embeddings for document {document_id}")

        except Exception as e:
            logger.error(f"Error creating requirement embeddings: {e}")
            await self.db.rollback()
            raise

        return embeddings_created

    async def search_similar_requirements(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.7,
        tenant_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar requirements using vector similarity.

        Args:
            query: Search query text
            limit: Maximum results to return
            threshold: Similarity threshold (0-1)
            tenant_id: Optional tenant filter

        Returns:
            List of similar requirements with metadata
        """
        try:
            # Generate embedding for query
            query_embedding = await self.mistral.generate_embedding(query)
            query_vector = np.array(query_embedding, dtype=np.float32)

            # Build SQL query for vector similarity search
            # Using cosine similarity: 1 - (embedding <=> query_vector)
            sql = text("""
                SELECT
                    de.id,
                    de.document_id,
                    de.chunk_text,
                    de.metadata,
                    de.confidence_score,
                    pd.original_filename,
                    pt.title as tender_title,
                    1 - (de.embedding::vector <=> :query_vector::vector) as similarity
                FROM document_embeddings de
                JOIN procurement_documents pd ON de.document_id = pd.id
                LEFT JOIN procurement_tenders pt ON pd.tender_id = pt.id
                WHERE de.deleted_at IS NULL
                    AND (:tenant_id::uuid IS NULL OR de.tenant_id = :tenant_id::uuid)
                    AND 1 - (de.embedding::vector <=> :query_vector::vector) > :threshold
                ORDER BY similarity DESC
                LIMIT :limit
            """)

            # Execute query
            result = await self.db.execute(
                sql,
                {
                    "query_vector": query_vector.tolist(),
                    "tenant_id": tenant_id,
                    "threshold": threshold,
                    "limit": limit
                }
            )

            # Format results
            similar_requirements = []
            for row in result:
                similar_requirements.append({
                    "id": str(row.id),
                    "document_id": str(row.document_id),
                    "requirement": row.chunk_text,
                    "metadata": row.metadata,
                    "confidence": row.confidence_score,
                    "document": row.original_filename,
                    "tender": row.tender_title,
                    "similarity": float(row.similarity)
                })

            logger.info(f"Found {len(similar_requirements)} similar requirements for query")
            return similar_requirements

        except Exception as e:
            logger.error(f"Error searching similar requirements: {e}")
            return []

    async def find_cross_document_duplicates(
        self,
        tender_id: UUID,
        similarity_threshold: float = 0.9,
        tenant_id: Optional[UUID] = None
    ) -> List[Tuple[Dict, Dict, float]]:
        """
        Find duplicate or near-duplicate requirements across documents in a tender.

        Args:
            tender_id: Tender UUID
            similarity_threshold: Threshold for considering duplicates
            tenant_id: Optional tenant filter

        Returns:
            List of duplicate pairs with similarity scores
        """
        try:
            # Get all embeddings for the tender
            sql = text("""
                SELECT
                    de.id,
                    de.document_id,
                    de.chunk_text,
                    de.metadata,
                    de.embedding,
                    pd.original_filename
                FROM document_embeddings de
                JOIN procurement_documents pd ON de.document_id = pd.id
                WHERE pd.tender_id = :tender_id
                    AND de.deleted_at IS NULL
                    AND (:tenant_id::uuid IS NULL OR de.tenant_id = :tenant_id::uuid)
                ORDER BY de.document_id, de.chunk_index
            """)

            result = await self.db.execute(
                sql,
                {"tender_id": tender_id, "tenant_id": tenant_id}
            )

            embeddings = list(result)
            duplicates = []

            # Compare all pairs
            for i in range(len(embeddings)):
                for j in range(i + 1, len(embeddings)):
                    # Skip if same document
                    if embeddings[i].document_id == embeddings[j].document_id:
                        continue

                    # Calculate similarity
                    vec1 = np.array(embeddings[i].embedding)
                    vec2 = np.array(embeddings[j].embedding)

                    # Cosine similarity
                    similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

                    if similarity >= similarity_threshold:
                        duplicates.append((
                            {
                                "id": str(embeddings[i].id),
                                "document": embeddings[i].original_filename,
                                "text": embeddings[i].chunk_text,
                                "metadata": embeddings[i].metadata
                            },
                            {
                                "id": str(embeddings[j].id),
                                "document": embeddings[j].original_filename,
                                "text": embeddings[j].chunk_text,
                                "metadata": embeddings[j].metadata
                            },
                            float(similarity)
                        ))

            logger.info(f"Found {len(duplicates)} duplicate requirements in tender {tender_id}")
            return duplicates

        except Exception as e:
            logger.error(f"Error finding cross-document duplicates: {e}")
            return []

    async def get_requirement_clusters(
        self,
        tender_id: UUID,
        num_clusters: int = 5,
        tenant_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """
        Group similar requirements into clusters for analysis.

        Args:
            tender_id: Tender UUID
            num_clusters: Number of clusters to create
            tenant_id: Optional tenant filter

        Returns:
            List of requirement clusters
        """
        # This would require sklearn KMeans or similar
        # For now, return a simplified version
        logger.warning("Clustering not fully implemented yet")
        return []

    def _prepare_requirement_text(self, requirement: Dict[str, Any]) -> str:
        """
        Prepare requirement text for embedding.

        Args:
            requirement: Requirement dictionary

        Returns:
            Formatted text for embedding
        """
        parts = []

        # Add category
        if category := requirement.get("category"):
            parts.append(f"[{category.upper()}]")

        # Add importance
        if importance := requirement.get("importance"):
            parts.append(f"Priority: {importance}")

        # Add description
        if description := requirement.get("description"):
            parts.append(description)

        # Add keywords
        if keywords := requirement.get("keywords"):
            parts.append(f"Keywords: {', '.join(keywords)}")

        return " ".join(parts)

    async def cleanup_old_embeddings(
        self,
        days_old: int = 30,
        tenant_id: Optional[UUID] = None
    ) -> int:
        """
        Clean up old embeddings to save space.

        Args:
            days_old: Delete embeddings older than this many days
            tenant_id: Optional tenant filter

        Returns:
            Number of embeddings deleted
        """
        try:
            cutoff_date = datetime.now(timezone.utc).replace(days=-days_old)

            sql = text("""
                UPDATE document_embeddings
                SET deleted_at = NOW()
                WHERE created_at < :cutoff_date
                    AND deleted_at IS NULL
                    AND (:tenant_id::uuid IS NULL OR tenant_id = :tenant_id::uuid)
            """)

            result = await self.db.execute(
                sql,
                {"cutoff_date": cutoff_date, "tenant_id": tenant_id}
            )

            deleted_count = result.rowcount
            await self.db.commit()

            logger.info(f"Cleaned up {deleted_count} old embeddings")
            return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning up embeddings: {e}")
            await self.db.rollback()
            return 0