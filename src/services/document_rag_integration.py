"""Integration service connecting document upload to RAG pipeline."""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.document_pipeline import DocumentPipelineService
from src.services.ai.indexing_pipeline import DocumentIndexingPipeline
from src.processors.base import ProcessingResult

logger = logging.getLogger(__name__)


class DocumentRAGIntegration:
    """Service to integrate document processing with RAG indexing."""

    def __init__(self, db: AsyncSession):
        """Initialize integration service."""
        self.db = db
        self.document_pipeline = DocumentPipelineService(db)
        self.indexing_pipeline = DocumentIndexingPipeline(db)

    async def process_and_index_document(
        self,
        file_content: bytes,
        filename: str,
        document_id: UUID,
        processing_options: Optional[dict] = None
    ) -> dict:
        """
        Process a document and index it for RAG.

        Args:
            file_content: Document binary content
            filename: Document filename
            document_id: Document UUID
            processing_options: Processing options

        Returns:
            Result dictionary with processing and indexing status
        """
        try:
            # Step 1: Process document (extract text and structure)
            logger.info(f"Processing document {document_id}")
            processing_result = await self.document_pipeline.process_document(
                file_content=file_content,
                filename=filename,
                document_id=document_id,
                processing_options=processing_options
            )

            if not processing_result.get("success"):
                logger.error(f"Document processing failed for {document_id}")
                return {
                    "success": False,
                    "stage": "processing",
                    "error": "Document processing failed"
                }

            # Convert to ProcessingResult object for indexing
            proc_result = ProcessingResult(
                raw_text=processing_result.get("raw_text", ""),
                structured_content=processing_result.get("structured_content", {}),
                success=True,
                processing_time_ms=processing_result.get("processing_time_ms", 0),
                processor_name=processing_result.get("processor", "unknown"),
                processor_version="1.0.0",
                page_count=processing_result.get("metadata", {}).get("page_count", 1),
                word_count=processing_result.get("metadata", {}).get("word_count", 0),
                language=processing_result.get("metadata", {}).get("language", "fr"),
                metadata=processing_result.get("metadata", {})
            )

            # Step 2: Index document for RAG
            logger.info(f"Indexing document {document_id} for RAG")
            indexing_result = await self.indexing_pipeline.index_document(
                document_id=document_id,
                processing_result=proc_result
            )

            if not indexing_result.success:
                logger.error(f"Document indexing failed for {document_id}")
                return {
                    "success": False,
                    "stage": "indexing",
                    "error": f"Indexing failed: {', '.join(indexing_result.errors)}"
                }

            # Step 3: Return combined result
            return {
                "success": True,
                "document_id": str(document_id),
                "processing": {
                    "success": True,
                    "processor": processing_result.get("processor"),
                    "processing_time_ms": processing_result.get("processing_time_ms")
                },
                "indexing": {
                    "success": True,
                    "num_chunks": indexing_result.num_chunks,
                    "num_embeddings": indexing_result.num_embeddings,
                    "indexing_time_ms": indexing_result.processing_time_ms
                },
                "total_time_ms": (
                    processing_result.get("processing_time_ms", 0) +
                    indexing_result.processing_time_ms
                )
            }

        except Exception as e:
            logger.error(f"Integration failed for document {document_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }