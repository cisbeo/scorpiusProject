"""PDF document processor using PyPDF2."""

import io
import re
from datetime import datetime
from typing import Any, Optional

import PyPDF2
from PyPDF2.errors import PdfReadError

from src.processors.base import DocumentProcessor, ProcessingError, ProcessingResult


class PDFProcessor(DocumentProcessor):
    """
    PDF document processor using PyPDF2.

    Extracts text content and metadata from PDF documents,
    with special handling for French procurement documents.
    """

    def __init__(self):
        """Initialize PDF processor."""
        super().__init__(name="PyPDF2Processor", version="1.0.0")
        self.supported_mime_types = ["application/pdf"]
        self.supported_extensions = [".pdf"]

    async def process_document(
        self,
        file_content: bytes,
        filename: str,
        mime_type: Optional[str] = None,
        processing_options: Optional[dict[str, Any]] = None
    ) -> ProcessingResult:
        """
        Process PDF document and extract content.

        Args:
            file_content: Binary content of the PDF
            filename: Original filename
            mime_type: MIME type (should be application/pdf)
            processing_options: Processing configuration options

        Returns:
            ProcessingResult with extracted content and metadata

        Raises:
            ProcessingError: If PDF processing fails critically
        """
        start_time = datetime.utcnow()
        processing_options = processing_options or {}

        # Validate input
        is_valid, errors = self.validate_input(file_content, filename, mime_type)
        if not is_valid:
            result = self.create_result(
                success=False,
                processing_time_ms=self.measure_processing_time(start_time)
            )
            for error in errors:
                result.add_error(error)
            return result

        try:
            # Create PDF reader from bytes
            pdf_stream = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_stream)

            # Extract basic metadata
            pdf_metadata = self._extract_pdf_metadata(pdf_reader)
            page_count = len(pdf_reader.pages)

            # Extract text from all pages
            raw_text, page_texts = self._extract_text_from_pages(
                pdf_reader, processing_options
            )

            # Clean and normalize text
            cleaned_text = self.clean_text(raw_text)

            # Detect language
            language = self.detect_language(cleaned_text)

            # Extract structured content for procurement documents
            structured_content = self._extract_structured_content(
                cleaned_text, page_texts, processing_options
            )

            # Calculate confidence score based on text quality
            confidence_score = self._calculate_confidence_score(
                cleaned_text, page_count, pdf_metadata
            )

            # Build result metadata
            metadata = self.extract_metadata(file_content, filename)
            metadata.update(pdf_metadata)
            metadata.update({
                "pages_processed": page_count,
                "extraction_method": "PyPDF2",
                "has_images": self._detect_images(pdf_reader),
                "has_forms": self._detect_forms(pdf_reader),
                "is_encrypted": pdf_reader.is_encrypted,
                "pdf_version": getattr(pdf_reader, 'pdf_header', 'unknown')
            })

            # Create successful result
            result = self.create_result(
                raw_text=cleaned_text,
                structured_content=structured_content,
                success=True,
                processing_time_ms=self.measure_processing_time(start_time),
                page_count=page_count,
                language=language,
                confidence_score=confidence_score,
                metadata=metadata
            )

            # Add warnings for quality issues
            self._add_quality_warnings(result, cleaned_text, pdf_metadata)

            return result

        except PdfReadError as e:
            raise ProcessingError(
                f"PDF file is corrupted or invalid: {str(e)}",
                self.name,
                e
            )
        except Exception as e:
            raise ProcessingError(
                f"Unexpected error processing PDF: {str(e)}",
                self.name,
                e
            )

    def supports_file(self, filename: str, mime_type: Optional[str] = None) -> bool:
        """
        Check if processor supports the given file.

        Args:
            filename: Original filename
            mime_type: MIME type of the file

        Returns:
            True if file is a PDF
        """
        from pathlib import Path

        # Check file extension
        extension = Path(filename).suffix.lower()
        if extension in self.supported_extensions:
            return True

        # Check MIME type
        if mime_type in self.supported_mime_types:
            return True

        return False

    def _extract_pdf_metadata(self, pdf_reader: PyPDF2.PdfReader) -> dict[str, Any]:
        """
        Extract metadata from PDF.

        Args:
            pdf_reader: PyPDF2 PdfReader instance

        Returns:
            Dictionary with PDF metadata
        """
        metadata = {}

        try:
            if pdf_reader.metadata:
                # Standard PDF metadata
                pdf_meta = pdf_reader.metadata
                metadata.update({
                    "title": str(pdf_meta.get("/Title", "")) if pdf_meta.get("/Title") else None,
                    "author": str(pdf_meta.get("/Author", "")) if pdf_meta.get("/Author") else None,
                    "subject": str(pdf_meta.get("/Subject", "")) if pdf_meta.get("/Subject") else None,
                    "creator": str(pdf_meta.get("/Creator", "")) if pdf_meta.get("/Creator") else None,
                    "producer": str(pdf_meta.get("/Producer", "")) if pdf_meta.get("/Producer") else None,
                    "creation_date": pdf_meta.get("/CreationDate"),
                    "modification_date": pdf_meta.get("/ModDate"),
                })

                # Clean up empty strings
                metadata = {k: v for k, v in metadata.items() if v}

        except Exception:
            # If metadata extraction fails, continue without it
            pass

        return metadata

    def _extract_text_from_pages(
        self,
        pdf_reader: PyPDF2.PdfReader,
        processing_options: dict[str, Any]
    ) -> tuple[str, list[str]]:
        """
        Extract text from all PDF pages.

        Args:
            pdf_reader: PyPDF2 PdfReader instance
            processing_options: Processing configuration

        Returns:
            Tuple of (combined_text, list_of_page_texts)
        """
        page_texts = []
        max_pages = processing_options.get("max_pages", None)

        for page_num, page in enumerate(pdf_reader.pages):
            if max_pages and page_num >= max_pages:
                break

            try:
                page_text = page.extract_text()
                page_texts.append(page_text)
            except Exception:
                # If page extraction fails, add empty text and continue
                page_texts.append("")
                # Note: We could add this as a warning to the result

        # Combine all page texts
        combined_text = "\n\n".join(page_texts)
        return combined_text, page_texts

    def _extract_structured_content(
        self,
        text: str,
        page_texts: list[str],
        processing_options: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Extract structured content from PDF text for procurement documents.

        Args:
            text: Combined text from all pages
            page_texts: Text from individual pages
            processing_options: Processing configuration

        Returns:
            Dictionary with structured content
        """
        structured = {
            "pages": [],
            "sections": {},
            "extracted_fields": {},
            "procurement_specific": {}
        }

        # Store individual page content
        for i, page_text in enumerate(page_texts):
            structured["pages"].append({
                "page_number": i + 1,
                "text": self.clean_text(page_text),
                "word_count": len(page_text.split()) if page_text else 0
            })

        # Extract procurement-specific information
        procurement_info = self._extract_procurement_fields(text)
        structured["procurement_specific"] = procurement_info

        # Extract document sections
        sections = self._identify_document_sections(text)
        structured["sections"] = sections

        # Extract key-value pairs
        fields = self._extract_key_value_pairs(text)
        structured["extracted_fields"] = fields

        return structured

    def _extract_procurement_fields(self, text: str) -> dict[str, Any]:
        """
        Extract procurement-specific fields from text.

        Args:
            text: Document text

        Returns:
            Dictionary with procurement information
        """
        procurement = {}

        # Common French procurement patterns
        patterns = {
            "reference": [
                r"(?:référence|réf\.?|n°)\s*:?\s*([A-Z0-9\-\/]+)",
                r"marché\s+n°\s*:?\s*([A-Z0-9\-\/]+)"
            ],
            "cpv_code": [
                r"(?:CPV|code CPV)\s*:?\s*(\d{8}(?:-\d)?)",
                r"classification\s+CPV\s*:?\s*(\d{8}(?:-\d)?)"
            ],
            "budget": [
                r"(?:montant|budget|estimation)\s*:?\s*([\d\s]+(?:,\d+)?\s*€)",
                r"prix\s+maximum\s*:?\s*([\d\s]+(?:,\d+)?\s*€)"
            ],
            "deadline": [
                r"(?:date limite|échéance|limite de réception)\s*:?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})",
                r"avant\s+le\s+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})"
            ],
            "organism": [
                r"pouvoir adjudicateur\s*:?\s*([^\n\r]+)",
                r"organisme acheteur\s*:?\s*([^\n\r]+)",
                r"collectivité\s*:?\s*([^\n\r]+)"
            ],
            "object": [
                r"objet du marché\s*:?\s*([^\n\r]+)",
                r"objet\s*:?\s*([^\n\r]+)"
            ]
        }

        for field, field_patterns in patterns.items():
            for pattern in field_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    value = match.group(1).strip()
                    if value and len(value) > 2:  # Avoid very short matches
                        if field not in procurement:
                            procurement[field] = []
                        procurement[field].append(value)

        # Clean up and deduplicate
        for field, values in procurement.items():
            if values:
                # Remove duplicates while preserving order
                seen = set()
                unique_values = []
                for value in values:
                    if value.lower() not in seen:
                        seen.add(value.lower())
                        unique_values.append(value)
                procurement[field] = unique_values

        return procurement

    def _identify_document_sections(self, text: str) -> dict[str, str]:
        """
        Identify and extract document sections.

        Args:
            text: Document text

        Returns:
            Dictionary mapping section names to content
        """
        sections = {}

        # Common section headers in French procurement documents
        section_patterns = {
            "article_1": r"article\s+1[:\.]?\s*([^\n]*(?:\n(?!article)[^\n]*)*)",
            "article_2": r"article\s+2[:\.]?\s*([^\n]*(?:\n(?!article)[^\n]*)*)",
            "conditions": r"conditions?\s+(?:d'exécution|générales?)[:\.]?\s*([^\n]*(?:\n(?!(?:article|conditions?))[^\n]*)*)",
            "criteres": r"critères?\s+(?:d'attribution|de sélection)[:\.]?\s*([^\n]*(?:\n(?!(?:article|critères?))[^\n]*)*)",
            "specifications": r"spécifications?\s+techniques?[:\.]?\s*([^\n]*(?:\n(?!(?:article|spécifications?))[^\n]*)*)",
            "delai": r"délais?\s+(?:d'exécution|de livraison)[:\.]?\s*([^\n]*(?:\n(?!(?:article|délais?))[^\n]*)*)"
        }

        for section_name, pattern in section_patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            for match in matches:
                content = match.group(1).strip()
                if content and len(content) > 10:
                    sections[section_name] = content[:1000]  # Limit section length
                    break  # Take first match only

        return sections

    def _extract_key_value_pairs(self, text: str) -> dict[str, str]:
        """
        Extract key-value pairs from text.

        Args:
            text: Document text

        Returns:
            Dictionary with extracted key-value pairs
        """
        fields = {}

        # Pattern for key: value pairs
        kv_pattern = r"([a-záéèêëîïôöùûüÿç\s]+)\s*:\s*([^\n\r]+)"
        matches = re.finditer(kv_pattern, text, re.IGNORECASE)

        for match in matches:
            key = match.group(1).strip()
            value = match.group(2).strip()

            # Filter out very short keys/values and common false positives
            if (len(key) > 3 and len(value) > 2 and
                len(key) < 50 and len(value) < 200 and
                not key.lower().startswith(('http', 'www', 'page'))):

                # Clean up key
                key = re.sub(r'\s+', ' ', key).strip()

                # Only keep if key looks like a real field name
                if any(word in key.lower() for word in [
                    'référence', 'code', 'date', 'délai', 'montant', 'prix',
                    'durée', 'lieu', 'contact', 'téléphone', 'email', 'adresse'
                ]):
                    fields[key] = value

        return fields

    def _calculate_confidence_score(
        self,
        text: str,
        page_count: int,
        metadata: dict[str, Any]
    ) -> float:
        """
        Calculate confidence score for extraction quality.

        Args:
            text: Extracted text
            page_count: Number of pages
            metadata: PDF metadata

        Returns:
            Confidence score between 0.0 and 1.0
        """
        score = 1.0

        # Penalize for very short text
        if len(text) < 100:
            score -= 0.3
        elif len(text) < 500:
            score -= 0.1

        # Penalize for too many garbled characters
        garbled_ratio = len(re.findall(r'[^\w\s\n\r\t.,;:!?()[\]{}"\'@#$%^&*+=<>/\\|`~-]', text)) / max(len(text), 1)
        if garbled_ratio > 0.1:
            score -= 0.2

        # Penalize for excessive whitespace or formatting issues
        if len(text.split()) / max(len(text), 1) < 0.1:  # Very low word density
            score -= 0.2

        # Bonus for having French words
        french_words = ['le', 'la', 'les', 'de', 'du', 'des', 'et', 'à', 'pour', 'dans', 'avec']
        french_count = sum(1 for word in french_words if word in text.lower())
        if french_count >= 5:
            score += 0.1

        # Bonus for having procurement-specific terms
        procurement_terms = ['marché', 'appel', 'offre', 'cahier', 'charges', 'soumission']
        procurement_count = sum(1 for term in procurement_terms if term in text.lower())
        if procurement_count >= 3:
            score += 0.1

        return max(0.0, min(1.0, score))

    def _add_quality_warnings(
        self,
        result: ProcessingResult,
        text: str,
        metadata: dict[str, Any]
    ) -> None:
        """
        Add warnings about text extraction quality.

        Args:
            result: ProcessingResult to add warnings to
            text: Extracted text
            metadata: PDF metadata
        """
        # Check for empty or very short text
        if len(text.strip()) < 50:
            result.add_warning("Extracted text is very short, document may be image-based or corrupted")

        # Check for potential OCR issues
        if len(re.findall(r'[^\w\s\n\r\t.,;:!?()[\]{}"\'@#$%^&*+=<>/\\|`~-]', text)) > len(text) * 0.05:
            result.add_warning("Document contains many non-standard characters, text extraction may be incomplete")

        # Check for password protection
        if metadata.get("is_encrypted"):
            result.add_warning("Document was encrypted, some content may not be accessible")

        # Check for form fields
        if metadata.get("has_forms"):
            result.add_warning("Document contains form fields, form data may not be extracted")

        # Check for images
        if metadata.get("has_images"):
            result.add_warning("Document contains images, image content cannot be extracted with text-only processing")

        # Check word density
        words = text.split()
        if len(words) < result.page_count * 50:  # Less than 50 words per page on average
            result.add_warning("Low word density detected, document may contain mostly images or tables")

    def _detect_images(self, pdf_reader: PyPDF2.PdfReader) -> bool:
        """
        Detect if PDF contains images.

        Args:
            pdf_reader: PyPDF2 PdfReader instance

        Returns:
            True if images are detected
        """
        try:
            for page in pdf_reader.pages:
                if "/XObject" in page and "/Resources" in page:
                    xobjects = page["/Resources"].get("/XObject", {})
                    for obj in xobjects.values():
                        if hasattr(obj, "get") and obj.get("/Subtype") == "/Image":
                            return True
        except Exception:
            pass
        return False

    def _detect_forms(self, pdf_reader: PyPDF2.PdfReader) -> bool:
        """
        Detect if PDF contains form fields.

        Args:
            pdf_reader: PyPDF2 PdfReader instance

        Returns:
            True if form fields are detected
        """
        try:
            if hasattr(pdf_reader, "get_form_text_fields"):
                fields = pdf_reader.get_form_text_fields()
                return bool(fields)
        except Exception:
            pass
        return False
