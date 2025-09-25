"""Docling-based document processor for advanced PDF extraction."""

from datetime import datetime
from typing import Any, Optional
import asyncio
import tempfile
import os
from pathlib import Path

from src.processors.base import DocumentProcessor, ProcessingResult, ProcessingError


class DoclingProcessor(DocumentProcessor):
    """
    Advanced document processor using Docling for high-quality extraction.

    Docling provides advanced PDF analysis capabilities including:
    - Layout understanding (headers, paragraphs, lists, tables)
    - Table extraction with structure preservation
    - Multi-column layout handling
    - Image and figure extraction
    - Metadata extraction
    """

    def __init__(self):
        """Initialize Docling processor."""
        super().__init__(name="DoclingProcessor", version="1.0.0")
        self.supported_mime_types = [
            "application/pdf",
            "application/x-pdf"
        ]
        self.supported_extensions = [".pdf"]
        self.docling_converter = None
        self._initialize_docling()

    def _initialize_docling(self):
        """Initialize Docling components lazily."""
        try:
            from docling.document_converter import DocumentConverter
            from docling.datamodel.pipeline_options import PipelineOptions
            from docling.datamodel.base_models import InputFormat

            # Configure pipeline options for French documents
            pipeline_options = PipelineOptions(
                do_table_structure=True,  # Extract table structure
                do_ocr=False,  # Disable OCR by default (can be enabled per document)
            )

            self.docling_converter = DocumentConverter(
                pipeline_options=pipeline_options
            )
            self.docling_available = True
        except ImportError:
            self.docling_available = False
            self.docling_converter = None

    async def process_document(
        self,
        file_content: bytes,
        filename: str,
        mime_type: Optional[str] = None,
        processing_options: Optional[dict[str, Any]] = None
    ) -> ProcessingResult:
        """
        Process document using Docling for advanced extraction.

        Args:
            file_content: Binary content of the document
            filename: Original filename
            mime_type: MIME type of the document
            processing_options: Optional processing configuration
                - language_hint: Language of the document (default: 'fr')
                - extract_tables: Whether to extract tables (default: True)
                - extract_images: Whether to extract images (default: False)
                - enable_ocr: Whether to enable OCR (default: False)

        Returns:
            ProcessingResult with extracted content and structure
        """
        start_time = datetime.utcnow()

        # Validate input
        is_valid, errors = self.validate_input(file_content, filename, mime_type)
        if not is_valid:
            return self.create_result(
                success=False,
                errors=errors,
                processing_time_ms=self.measure_processing_time(start_time)
            )

        # Check if Docling is available
        if not self.docling_available:
            # Fallback to basic PDF processor
            return await self._fallback_process(file_content, filename, start_time)

        # Parse processing options
        options = processing_options or {}
        language_hint = options.get('language_hint', 'fr')
        extract_tables = options.get('extract_tables', True)
        extract_images = options.get('extract_images', False)
        enable_ocr = options.get('enable_ocr', False)

        try:
            # Process with Docling
            result = await self._process_with_docling(
                file_content,
                filename,
                extract_tables=extract_tables,
                extract_images=extract_images,
                enable_ocr=enable_ocr
            )

            # Add language detection
            if result.raw_text:
                result.language = self.detect_language(result.raw_text) or language_hint

            result.processing_time_ms = self.measure_processing_time(start_time)
            return result

        except Exception as e:
            error_msg = f"Docling processing failed: {str(e)}"
            return self.create_result(
                success=False,
                errors=[error_msg],
                processing_time_ms=self.measure_processing_time(start_time)
            )

    async def _process_with_docling(
        self,
        file_content: bytes,
        filename: str,
        extract_tables: bool = True,
        extract_images: bool = False,
        enable_ocr: bool = False
    ) -> ProcessingResult:
        """
        Process document using Docling library.

        Args:
            file_content: Binary content of the document
            filename: Original filename
            extract_tables: Whether to extract tables
            extract_images: Whether to extract images
            enable_ocr: Whether to enable OCR

        Returns:
            ProcessingResult with structured content
        """
        # Create temporary file for Docling processing
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file.write(file_content)
            tmp_path = tmp_file.name

        try:
            # Run Docling in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._docling_extract,
                tmp_path,
                extract_tables,
                extract_images,
                enable_ocr
            )

            return result

        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _docling_extract(
        self,
        file_path: str,
        extract_tables: bool,
        extract_images: bool,
        enable_ocr: bool
    ) -> ProcessingResult:
        """
        Synchronous Docling extraction.

        Args:
            file_path: Path to PDF file
            extract_tables: Whether to extract tables
            extract_images: Whether to extract images
            enable_ocr: Whether to enable OCR

        Returns:
            ProcessingResult with extracted content
        """
        from docling.datamodel.base_models import DocumentStream
        from docling.datamodel.pipeline_options import PipelineOptions

        # Update pipeline options if needed
        if enable_ocr or not extract_tables:
            pipeline_options = PipelineOptions(
                do_table_structure=extract_tables,
                do_ocr=enable_ocr
            )
            self.docling_converter.pipeline_options = pipeline_options

        # Convert document
        result = self.docling_converter.convert(file_path)

        # Extract structured content
        structured_content = self._extract_structured_content(result)

        # Extract raw text
        raw_text = result.document.export_to_markdown() if hasattr(result.document, 'export_to_markdown') else str(result.document)

        # Count pages
        page_count = len(result.document.pages) if hasattr(result.document, 'pages') else 1

        return self.create_result(
            raw_text=self.clean_text(raw_text),
            structured_content=structured_content,
            page_count=page_count,
            success=True,
            metadata={
                "extraction_method": "docling",
                "ocr_enabled": enable_ocr,
                "tables_extracted": extract_tables
            }
        )

    def _extract_structured_content(self, docling_result) -> dict[str, Any]:
        """
        Extract structured content from Docling result.

        Args:
            docling_result: Docling conversion result

        Returns:
            Dictionary with structured content
        """
        structured = {
            "sections": [],
            "tables": [],
            "lists": [],
            "metadata": {}
        }

        # Extract document structure
        if hasattr(docling_result.document, 'body'):
            for element in docling_result.document.body:
                element_type = element.__class__.__name__.lower()

                if 'heading' in element_type:
                    structured["sections"].append({
                        "type": "heading",
                        "level": getattr(element, 'level', 1),
                        "text": str(element)
                    })
                elif 'table' in element_type:
                    structured["tables"].append(self._extract_table(element))
                elif 'list' in element_type:
                    structured["lists"].append({
                        "type": "list",
                        "items": [str(item) for item in element.items]
                    })

        # Extract metadata
        if hasattr(docling_result.document, 'metadata'):
            meta = docling_result.document.metadata
            structured["metadata"] = {
                "title": getattr(meta, 'title', None),
                "author": getattr(meta, 'author', None),
                "subject": getattr(meta, 'subject', None),
                "keywords": getattr(meta, 'keywords', None),
                "creation_date": str(getattr(meta, 'creation_date', None))
            }

        return structured

    def _extract_table(self, table_element) -> dict[str, Any]:
        """
        Extract table structure from Docling table element.

        Args:
            table_element: Docling table element

        Returns:
            Dictionary with table data
        """
        table_data = {
            "type": "table",
            "headers": [],
            "rows": []
        }

        if hasattr(table_element, 'data'):
            # Extract headers if available
            if hasattr(table_element.data, 'headers'):
                table_data["headers"] = [str(h) for h in table_element.data.headers]

            # Extract rows
            if hasattr(table_element.data, 'rows'):
                for row in table_element.data.rows:
                    table_data["rows"].append([str(cell) for cell in row])

        return table_data

    async def _fallback_process(
        self,
        file_content: bytes,
        filename: str,
        start_time: datetime
    ) -> ProcessingResult:
        """
        Fallback to basic PDF processing when Docling is not available.

        Args:
            file_content: Binary content of the document
            filename: Original filename
            start_time: Processing start time

        Returns:
            ProcessingResult from basic processor
        """
        # Import basic PDF processor
        from src.processors.pdf_processor import PDFProcessor

        # Use basic processor as fallback
        basic_processor = PDFProcessor()
        result = await basic_processor.process_document(
            file_content=file_content,
            filename=filename,
            mime_type="application/pdf"
        )

        # Update processor info
        result.processor_name = self.name
        result.processor_version = self.version
        result.metadata["fallback_processor"] = "PDFProcessor"
        result.add_warning("Docling not available, using basic PDF extraction")

        return result

    def supports_file(self, filename: str, mime_type: Optional[str] = None) -> bool:
        """
        Check if processor supports the given file.

        Args:
            filename: Original filename
            mime_type: MIME type of the file

        Returns:
            True if processor can handle this file type
        """
        # Check extension
        ext = Path(filename).suffix.lower()
        if ext in self.supported_extensions:
            return True

        # Check MIME type
        if mime_type and mime_type in self.supported_mime_types:
            return True

        return False

    async def extract_requirements(self, content: str) -> list[dict[str, Any]]:
        """
        Extract requirements from document content.

        Args:
            content: Document text content

        Returns:
            List of extracted requirements
        """
        requirements = []

        # Pattern matching for requirements
        requirement_patterns = [
            r"(?:doit|devra|devront)\s+(?:être|avoir|fournir|respecter)",
            r"(?:obligation|obligatoire|exigence|requis|nécessaire)",
            r"(?:il est|il sera)\s+(?:obligatoire|nécessaire|requis)",
        ]

        import re

        # Split content into sentences
        sentences = re.split(r'[.!?]\s+', content)

        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue

            # Check if sentence contains requirement pattern
            for pattern in requirement_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    requirements.append({
                        "text": sentence,
                        "position": i,
                        "type": "requirement",
                        "confidence": 0.8
                    })
                    break

        return requirements

    async def extract_evaluation_criteria(self, structured_content: dict) -> list[dict[str, Any]]:
        """
        Extract evaluation criteria from structured content.

        Args:
            structured_content: Structured document content

        Returns:
            List of evaluation criteria
        """
        criteria = []

        # Look for evaluation criteria in sections
        for section in structured_content.get("sections", []):
            if "critère" in section.get("text", "").lower() or \
               "évaluation" in section.get("text", "").lower():
                criteria.append({
                    "section": section.get("text"),
                    "type": "evaluation_criteria"
                })

        # Look for criteria in tables
        for table in structured_content.get("tables", []):
            headers = [h.lower() for h in table.get("headers", [])]
            if any(term in " ".join(headers) for term in ["critère", "pondération", "note", "coefficient"]):
                criteria.append({
                    "type": "criteria_table",
                    "data": table
                })

        return criteria