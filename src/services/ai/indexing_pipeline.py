"""Document indexing pipeline for RAG system."""

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.ai.chunking_service import ChunkingService, DocumentChunk
from src.services.ai.vector_store_service import VectorStoreService
from src.services.ai.mistral_service import get_mistral_service
from src.processors.base import ProcessingResult
from src.repositories.document_repository import DocumentRepository
from src.models.document import DocumentStatus
from src.core.ai_config import ai_config

logger = logging.getLogger(__name__)


class IndexingResult:
    """Result of document indexing operation."""

    def __init__(
        self,
        success: bool,
        document_id: UUID,
        num_chunks: int = 0,
        num_embeddings: int = 0,
        processing_time_ms: int = 0,
        errors: List[str] = None
    ):
        self.success = success
        self.document_id = document_id
        self.num_chunks = num_chunks
        self.num_embeddings = num_embeddings
        self.processing_time_ms = processing_time_ms
        self.errors = errors or []


class DocumentIndexingPipeline:
    """Pipeline for indexing documents into the RAG system."""

    def __init__(self, db: AsyncSession):
        """
        Initialize indexing pipeline.

        Args:
            db: Database session
        """
        self.db = db
        self.chunking_service = ChunkingService()
        self.vector_store = VectorStoreService(db)
        self.mistral_service = get_mistral_service()
        self.doc_repo = DocumentRepository(db)

    async def index_document(
        self,
        document_id: UUID,
        processing_result: ProcessingResult,
        force_reindex: bool = False
    ) -> IndexingResult:
        """
        Index a document for RAG.

        Args:
            document_id: Document UUID
            processing_result: Processing result from document processor
            force_reindex: Force reindexing even if already indexed

        Returns:
            IndexingResult with status and statistics
        """
        start_time = datetime.utcnow()

        try:
            # Check if document already indexed
            if not force_reindex:
                existing = await self.vector_store.get_embeddings_by_document(document_id)
                if existing:
                    logger.info(f"Document {document_id} already indexed with {len(existing)} embeddings")
                    return IndexingResult(
                        success=True,
                        document_id=document_id,
                        num_chunks=len(existing),
                        num_embeddings=len(existing),
                        processing_time_ms=0
                    )

            # Delete existing embeddings if reindexing
            if force_reindex:
                deleted_count = await self.vector_store.delete_embeddings(document_id)
                logger.info(f"Deleted {deleted_count} existing embeddings for reindexing")

            # Step 1: Chunk the document
            logger.info(f"Starting chunking for document {document_id}")
            chunks = await self.chunking_service.chunk_document(
                processing_result,
                str(document_id)
            )
            logger.info(f"Created {len(chunks)} chunks")

            if not chunks:
                return IndexingResult(
                    success=False,
                    document_id=document_id,
                    errors=["No chunks created from document"]
                )

            # Step 2: Generate embeddings for chunks
            logger.info(f"Generating embeddings for {len(chunks)} chunks")
            embeddings_data = await self._generate_embeddings_for_chunks(chunks)

            # Step 3: Store embeddings in vector database
            logger.info(f"Storing {len(embeddings_data)} embeddings in vector store")
            num_stored = await self.vector_store.add_embeddings(
                embeddings_data,
                document_id
            )

            # Step 4: Update document status
            await self._update_document_status(
                document_id,
                num_chunks=len(chunks),
                num_embeddings=num_stored
            )

            # Calculate processing time
            processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            logger.info(
                f"Successfully indexed document {document_id}: "
                f"{num_stored} embeddings in {processing_time}ms"
            )

            return IndexingResult(
                success=True,
                document_id=document_id,
                num_chunks=len(chunks),
                num_embeddings=num_stored,
                processing_time_ms=processing_time
            )

        except Exception as e:
            logger.error(f"Failed to index document {document_id}: {e}")

            # Update document status to failed
            try:
                await self.doc_repo.update(
                    document_id,
                    {
                        "status": DocumentStatus.FAILED,
                        "error_message": f"Indexing failed: {str(e)}"
                    }
                )
                await self.db.commit()
            except:
                pass

            processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            return IndexingResult(
                success=False,
                document_id=document_id,
                processing_time_ms=processing_time,
                errors=[str(e)]
            )

    async def _generate_embeddings_for_chunks(
        self,
        chunks: List[DocumentChunk]
    ) -> List[Dict[str, Any]]:
        """
        Generate embeddings for document chunks.

        Args:
            chunks: List of document chunks

        Returns:
            List of embedding data dictionaries
        """
        # Extract texts for batch processing
        texts = [chunk.chunk_text for chunk in chunks]

        # Generate embeddings in batches
        embeddings = await self.mistral_service.generate_embeddings_batch(
            texts,
            show_progress=True
        )

        # Combine chunks with embeddings
        embeddings_data = []
        for chunk, embedding in zip(chunks, embeddings):
            embeddings_data.append({
                "chunk_id": chunk.chunk_id,
                "chunk_text": chunk.chunk_text,
                "embedding": embedding,
                "metadata": chunk.metadata,
                "document_type": chunk.document_type,
                "section_type": chunk.section_type,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "overlap_size": chunk.overlap_size,
                "language": chunk.metadata.get("language", "fr"),
                "confidence_score": chunk.confidence_score
            })

        return embeddings_data

    async def _update_document_status(
        self,
        document_id: UUID,
        num_chunks: int,
        num_embeddings: int
    ):
        """
        Update document with indexing metadata.

        Args:
            document_id: Document UUID
            num_chunks: Number of chunks created
            num_embeddings: Number of embeddings stored
        """
        try:
            document = await self.doc_repo.get_by_id(document_id)
            if document:
                # Update extraction metadata with indexing info
                metadata = document.extraction_metadata or {}
                metadata["indexing"] = {
                    "num_chunks": num_chunks,
                    "num_embeddings": num_embeddings,
                    "indexed_at": datetime.utcnow().isoformat(),
                    "vector_dimension": ai_config.vector_dimension,
                    "chunking_strategy": ai_config.chunking_strategy.value
                }

                await self.doc_repo.update(
                    document_id,
                    {"extraction_metadata": metadata}
                )
                await self.db.commit()

        except Exception as e:
            logger.error(f"Failed to update document status: {e}")

    async def index_multiple_documents(
        self,
        document_ids: List[UUID],
        force_reindex: bool = False
    ) -> Dict[UUID, IndexingResult]:
        """
        Index multiple documents concurrently.

        Args:
            document_ids: List of document UUIDs
            force_reindex: Force reindexing

        Returns:
            Dictionary mapping document ID to indexing result
        """
        results = {}

        # Process documents in parallel with limited concurrency
        semaphore = asyncio.Semaphore(ai_config.max_concurrent_requests)

        async def index_with_semaphore(doc_id: UUID) -> Tuple[UUID, IndexingResult]:
            async with semaphore:
                document = await self.doc_repo.get_by_id(doc_id)
                if not document:
                    return doc_id, IndexingResult(
                        success=False,
                        document_id=doc_id,
                        errors=["Document not found"]
                    )

                # Get processing result (assumed to be stored in extraction_metadata)
                if not document.extraction_metadata:
                    return doc_id, IndexingResult(
                        success=False,
                        document_id=doc_id,
                        errors=["No processing result available"]
                    )

                # Reconstruct processing result from metadata
                processing_result = self._reconstruct_processing_result(
                    document.extraction_metadata
                )

                result = await self.index_document(
                    doc_id,
                    processing_result,
                    force_reindex
                )
                return doc_id, result

        # Run indexing tasks concurrently
        tasks = [index_with_semaphore(doc_id) for doc_id in document_ids]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for item in completed:
            if isinstance(item, Exception):
                logger.error(f"Indexing task failed: {item}")
            else:
                doc_id, result = item
                results[doc_id] = result

        return results

    def _reconstruct_processing_result(
        self,
        metadata: Dict[str, Any]
    ) -> ProcessingResult:
        """
        Reconstruct ProcessingResult from stored metadata.

        Args:
            metadata: Stored extraction metadata

        Returns:
            ProcessingResult object
        """
        from src.processors.base import ProcessingResult

        # This is a simplified reconstruction
        # In practice, you'd store the full processing result
        return ProcessingResult(
            raw_text=metadata.get("raw_text", ""),
            structured_content=metadata.get("structured_content", {}),
            success=True,
            processing_time_ms=metadata.get("processing_time_ms", 0),
            processor_name=metadata.get("processor", "unknown"),
            processor_version="1.0.0",
            page_count=metadata.get("page_count", 1),
            word_count=metadata.get("word_count", 0),
            language=metadata.get("language", "fr"),
            confidence_score=metadata.get("confidence_score", 1.0),
            metadata=metadata
        )

    async def get_indexing_status(
        self,
        document_id: UUID
    ) -> Dict[str, Any]:
        """
        Get indexing status for a document.

        Args:
            document_id: Document UUID

        Returns:
            Status dictionary
        """
        try:
            # Get document
            document = await self.doc_repo.get_by_id(document_id)
            if not document:
                return {"status": "not_found", "document_id": str(document_id)}

            # Get embeddings
            embeddings = await self.vector_store.get_embeddings_by_document(document_id)

            # Extract indexing metadata
            indexing_metadata = (
                document.extraction_metadata.get("indexing", {})
                if document.extraction_metadata
                else {}
            )

            return {
                "document_id": str(document_id),
                "status": "indexed" if embeddings else "not_indexed",
                "num_embeddings": len(embeddings),
                "num_chunks": indexing_metadata.get("num_chunks", 0),
                "indexed_at": indexing_metadata.get("indexed_at"),
                "chunking_strategy": indexing_metadata.get("chunking_strategy"),
                "vector_dimension": indexing_metadata.get("vector_dimension"),
                "document_status": document.status.value if document.status else "unknown"
            }

        except Exception as e:
            logger.error(f"Failed to get indexing status: {e}")
            return {
                "status": "error",
                "document_id": str(document_id),
                "error": str(e)
            }

    async def reindex_all_documents(
        self,
        batch_size: int = 10
    ) -> Dict[str, Any]:
        """
        Reindex all documents in the system.

        Args:
            batch_size: Number of documents to process in parallel

        Returns:
            Summary of reindexing operation
        """
        try:
            # Get all processed documents
            documents = await self.doc_repo.get_all_processed()
            total_documents = len(documents)

            logger.info(f"Starting reindexing of {total_documents} documents")

            successful = 0
            failed = 0
            errors = []

            # Process in batches
            for i in range(0, total_documents, batch_size):
                batch = documents[i:i + batch_size]
                batch_ids = [doc.id for doc in batch]

                results = await self.index_multiple_documents(
                    batch_ids,
                    force_reindex=True
                )

                # Count successes and failures
                for doc_id, result in results.items():
                    if result.success:
                        successful += 1
                    else:
                        failed += 1
                        errors.extend(result.errors)

                logger.info(
                    f"Batch {i//batch_size + 1}/{(total_documents-1)//batch_size + 1} completed: "
                    f"{successful} successful, {failed} failed"
                )

            return {
                "total_documents": total_documents,
                "successful": successful,
                "failed": failed,
                "errors": errors[:10]  # Limit error list
            }

        except Exception as e:
            logger.error(f"Reindexing failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }