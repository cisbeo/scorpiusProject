"""Document processing pipeline service."""

import logging
from typing import Optional, Any, Dict
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from src.processors import processor_factory
from src.processors.pdf_processor import PDFProcessor
from src.processors.unstructured_processor import UnstructuredProcessor

# Configure logging
logger = logging.getLogger(__name__)


class DocumentPipelineService:
    """Service for processing documents through the pipeline."""

    def __init__(self, db: AsyncSession):
        """Initialize the pipeline service."""
        self.db = db

    async def process_document(
        self,
        file_content: bytes,
        filename: str,
        document_id: UUID,
        processing_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a document through the pipeline.

        Args:
            file_content: Binary content of the document
            filename: Original filename
            document_id: Document ID in database
            processing_options: Processing options including processor selection

        Returns:
            Processing result dictionary
        """
        options = processing_options or {}

        # Get processor preference
        processor_name = options.get("processor", "auto")
        strategy = options.get("strategy", "fast")

        logger.info(f"Processing document {document_id} with processor={processor_name}, strategy={strategy}")
        logger.debug(f"Processing options: {options}")

        # Select processor
        if processor_name == "pypdf2" or strategy == "ultra_fast":
            # Force PyPDF2 for ultra fast processing
            processor = PDFProcessor()
        elif processor_name == "unstructured":
            # Force Unstructured
            processor = UnstructuredProcessor()
        else:
            # Auto selection - try Unstructured first, fallback to PyPDF2
            processor = UnstructuredProcessor()
            if not processor._unstructured_available:
                processor = PDFProcessor()

        # Process document
        logger.info(f"Starting extraction with {processor.__class__.__name__}")
        result = await processor.process_document(
            file_content=file_content,
            filename=filename,
            mime_type="application/pdf",
            processing_options=options
        )

        # Log extraction results
        logger.info(f"Extraction completed: success={result.success}, pages={result.page_count}, words={result.word_count}")
        logger.info(f"Processing time: {result.processing_time_ms}ms")

        # Log extracted text details
        if result.raw_text:
            text_preview = result.raw_text[:500] + "..." if len(result.raw_text) > 500 else result.raw_text
            logger.debug(f"Text preview: {text_preview}")
            logger.info(f"Total text length: {len(result.raw_text)} characters")

        # Log structured content
        if result.structured_content:
            logger.info(f"Structured content keys: {list(result.structured_content.keys())}")
            for key, value in result.structured_content.items():
                if isinstance(value, list):
                    logger.debug(f"  {key}: {len(value)} items")
                elif isinstance(value, dict):
                    logger.debug(f"  {key}: {list(value.keys())}")
                else:
                    logger.debug(f"  {key}: {value}")

        # Log metadata
        if result.metadata:
            logger.info(f"Metadata: {result.metadata}")

        # Log warnings and errors
        if result.warnings:
            for warning in result.warnings:
                logger.warning(f"Processing warning: {warning}")
        if result.errors:
            for error in result.errors:
                logger.error(f"Processing error: {error}")

        # Update document in database
        from src.repositories.document_repository import DocumentRepository
        from src.models.document import DocumentStatus

        doc_repo = DocumentRepository(self.db)
        document = await doc_repo.get_by_id(document_id)

        if document:
            update_data = {}
            if result.success:
                update_data["status"] = DocumentStatus.PROCESSED
                update_data["processing_duration_ms"] = result.processing_time_ms
                # Skip page_count for now as it's not in the model
                update_data["extraction_metadata"] = {
                    "processor": result.processor_name,
                    "strategy": strategy,
                    **result.metadata
                }
            else:
                update_data["status"] = DocumentStatus.FAILED
                update_data["error_message"] = " | ".join(result.errors)

            await doc_repo.update(document_id, update_data)
            await self.db.commit()

            logger.info(f"Document {document_id} updated in database with status={update_data.get('status')}")
            if update_data.get('extraction_metadata'):
                logger.debug(f"Extraction metadata saved: {update_data['extraction_metadata']}")

        return_data = {
            "success": result.success,
            "processor": result.processor_name,
            "processing_time_ms": result.processing_time_ms,
            "metadata": result.metadata
        }

        logger.info(f"Pipeline processing completed for document {document_id}")
        return return_data