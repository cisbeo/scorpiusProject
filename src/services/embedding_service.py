"""Service for managing document embeddings."""

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.services.ai.mistral_service import get_mistral_service
from src.services.ai.chunking_service import ChunkingService
from src.services.ai.vector_store_service import VectorStoreService
from src.repositories.document_repository import DocumentRepository
from src.models.document import ProcurementDocument, DocumentStatus
from src.processors.base import ProcessingResult

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating and managing embeddings."""

    def __init__(self, db: AsyncSession):
        """
        Initialize embedding service.

        Args:
            db: Database session
        """
        self.db = db
        self.mistral_service = get_mistral_service()
        self.chunking_service = ChunkingService()
        self.vector_store = VectorStoreService(db)
        self.doc_repo = DocumentRepository(db)

    async def generate_tender_embeddings(
        self,
        tender_id: UUID,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Generate embeddings for all documents in a tender.

        Args:
            tender_id: Tender UUID
            force_regenerate: Force regeneration of existing embeddings

        Returns:
            Result dictionary with statistics
        """
        try:
            logger.info(f"Starting embedding generation for tender {tender_id}, force={force_regenerate}")

            # Get all documents for the tender
            documents = await self.doc_repo.get_by_tender(
                tender_id=tender_id
            )

            logger.info(f"Found {len(documents) if documents else 0} documents for tender {tender_id}")

            if not documents:
                logger.warning(f"No documents found for tender {tender_id}")
                return {
                    "documents_processed": 0,
                    "total_embeddings": 0,
                    "errors": []
                }

            total_embeddings = 0
            documents_processed = 0
            errors = []

            for doc in documents:
                try:
                    logger.info(f"Processing document {doc.id}: status={doc.status}, has_content={bool(doc.processed_content)}")

                    # Check if document is processed
                    if doc.status != DocumentStatus.PROCESSED:
                        logger.warning(f"Document {doc.id} is not processed yet (status: {doc.status})")
                        errors.append(f"Document {doc.id} not processed")
                        continue

                    # Check if embeddings already exist
                    if not force_regenerate:
                        existing = await self.vector_store.get_embeddings_by_document(doc.id)
                        if existing:
                            logger.info(f"Document {doc.id} already has {len(existing)} embeddings")
                            total_embeddings += len(existing)
                            documents_processed += 1
                            continue

                    # Generate embeddings for document
                    embeddings_count = await self._generate_document_embeddings(doc)
                    total_embeddings += embeddings_count
                    documents_processed += 1

                    logger.info(f"Generated {embeddings_count} embeddings for document {doc.id}")

                except Exception as e:
                    logger.error(f"Failed to process document {doc.id}: {e}")
                    errors.append(f"Document {doc.id}: {str(e)}")

            return {
                "documents_processed": documents_processed,
                "total_embeddings": total_embeddings,
                "errors": errors
            }

        except Exception as e:
            logger.error(f"Failed to generate tender embeddings: {e}")
            raise

    async def _generate_document_embeddings(
        self,
        document: ProcurementDocument
    ) -> int:
        """
        Generate embeddings for a single document.

        Args:
            document: Document to process

        Returns:
            Number of embeddings created
        """
        try:
            # Get document content
            if not document.processed_content:
                logger.warning(f"Document {document.id} has no processed content")
                return 0

            # Create ProcessingResult for chunking
            processing_result = ProcessingResult(
                raw_text=document.processed_content,
                structured_content={},
                success=True,
                processing_time_ms=0,
                processor_name="manual",
                processor_version="1.0.0",
                page_count=1,
                word_count=len(document.processed_content.split()),
                language="fr",
                metadata={}
            )

            # Chunk the document
            chunks = await self.chunking_service.chunk_document(
                processing_result,
                str(document.id)
            )

            if not chunks:
                logger.warning(f"No chunks created for document {document.id}")
                return 0

            # Generate embeddings for chunks
            embeddings_data = []
            chunk_texts = [chunk.chunk_text for chunk in chunks]

            # Generate embeddings in batches
            embeddings = await self.mistral_service.generate_embeddings_batch(
                texts=chunk_texts,
                batch_size=5,
                show_progress=True,
                delay_between_batches=2.0
            )

            # Prepare embedding data for storage
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                embeddings_data.append({
                    "chunk_id": chunk.chunk_id,
                    "chunk_text": chunk.chunk_text,
                    "chunk_index": i,
                    "embedding": embedding,
                    "metadata": chunk.metadata,
                    "document_type": document.document_type,
                    "page_number": chunk.metadata.get("page_numbers", [1])[0] if chunk.metadata.get("page_numbers") else None,
                    "overlap_size": chunk.overlap_size,
                    "confidence_score": 1.0
                })

            # Store embeddings
            num_stored = await self.vector_store.add_embeddings(
                embeddings_data,
                document.id
            )

            # Update document metadata
            await self._update_document_metadata(document.id, num_stored)

            return num_stored

        except Exception as e:
            logger.error(f"Failed to generate embeddings for document {document.id}: {e}")
            raise

    async def _update_document_metadata(
        self,
        document_id: UUID,
        num_embeddings: int
    ):
        """
        Update document metadata with embedding information.

        Args:
            document_id: Document UUID
            num_embeddings: Number of embeddings created
        """
        try:
            # Update document with embedding count
            metadata = {
                "embeddings_count": num_embeddings,
                "embeddings_generated_at": datetime.utcnow().isoformat(),
                "embedding_model": "mistral-embed"
            }

            await self.doc_repo.update(
                document_id,
                {"metadata": metadata}
            )
            await self.db.commit()

        except Exception as e:
            logger.error(f"Failed to update document metadata: {e}")

    async def search_similar_chunks(
        self,
        query: str,
        tender_id: Optional[UUID] = None,
        document_type: Optional[str] = None,
        top_k: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks using embeddings.

        Args:
            query: Search query
            tender_id: Optional tender ID to filter
            document_type: Optional document type filter
            top_k: Number of results
            threshold: Similarity threshold

        Returns:
            List of similar chunks with scores
        """
        try:
            # Generate query embedding
            query_embedding = await self.mistral_service.generate_embedding(query)

            # Build filters
            filters = {}
            if tender_id:
                filters["tender_id"] = tender_id
            if document_type:
                filters["document_type"] = document_type

            # Search in vector store
            results = await self.vector_store.search_similar(
                query_embedding=query_embedding,
                top_k=top_k,
                threshold=threshold,
                filters=filters
            )

            # Format results
            formatted_results = []
            for embedding, score in results:
                formatted_results.append({
                    "document_id": str(embedding.document_id),
                    "chunk_id": embedding.chunk_id,
                    "text": embedding.chunk_text,
                    "similarity_score": score,
                    "metadata": embedding.chunk_metadata,
                    "page_number": embedding.page_number,
                    "document_type": embedding.document_type
                })

            return formatted_results

        except Exception as e:
            logger.error(f"Failed to search similar chunks: {e}")
            raise