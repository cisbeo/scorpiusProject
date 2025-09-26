"""Advanced PDF processor using Unstructured.io for structured extraction."""

from datetime import datetime
from typing import Any, Optional, List, Dict
from pathlib import Path
import tempfile
import asyncio
import json

from src.processors.base import DocumentProcessor, ProcessingResult, ProcessingError


class UnstructuredProcessor(DocumentProcessor):
    """
    Advanced document processor using Unstructured.io.

    Provides high-quality extraction with:
    - Automatic section detection (CCTP, CCAP, annexes, etc.)
    - Table preservation with structure
    - Layout understanding
    - Metadata preservation (page, coordinates, style)
    """

    def __init__(self):
        """Initialize Unstructured processor."""
        super().__init__(name="UnstructuredProcessor", version="2.0.0")
        self.supported_mime_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain"
        ]
        self.supported_extensions = [".pdf", ".docx", ".txt"]
        self._unstructured_available = self._check_unstructured()

    def _check_unstructured(self) -> bool:
        """Check if Unstructured library is available."""
        # Temporarily disable Unstructured to force PyPDF2 fallback
        # TODO: Fix torch dependency issue with Unstructured
        return False

    async def process_document(
        self,
        file_content: bytes,
        filename: str,
        mime_type: Optional[str] = None,
        processing_options: Optional[dict[str, Any]] = None
    ) -> ProcessingResult:
        """
        Process document using Unstructured for structured extraction.

        Args:
            file_content: Binary content of the document
            filename: Original filename
            mime_type: MIME type of the document
            processing_options: Optional processing configuration
                - strategy: "hi_res" (best quality) or "fast" (speed)
                - extract_tables: Whether to extract tables (default: True)
                - extract_images: Whether to extract images (default: False)
                - languages: List of languages (default: ["fra"])

        Returns:
            ProcessingResult with structured content
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

        # Check if Unstructured is available
        if not self._unstructured_available:
            # Fallback to PyPDF2 processor
            from src.processors.pdf_processor import PDFProcessor
            fallback = PDFProcessor()
            result = await fallback.process_document(
                file_content, filename, mime_type, processing_options
            )
            result.add_warning("Unstructured not available, using basic extraction")
            return result

        # Parse options
        options = processing_options or {}
        strategy = options.get('strategy', 'fast')  # fast by default, hi_res for best quality
        extract_tables = options.get('extract_tables', True)
        extract_images = options.get('extract_images', False)
        languages = options.get('languages', ['fra'])

        try:
            # Process with Unstructured
            result = await self._process_with_unstructured(
                file_content,
                filename,
                strategy=strategy,
                extract_tables=extract_tables,
                extract_images=extract_images,
                languages=languages
            )

            result.processing_time_ms = self.measure_processing_time(start_time)
            return result

        except Exception as e:
            error_msg = f"Unstructured processing failed: {str(e)}"
            return self.create_result(
                success=False,
                errors=[error_msg],
                processing_time_ms=self.measure_processing_time(start_time)
            )

    async def _process_with_unstructured(
        self,
        file_content: bytes,
        filename: str,
        strategy: str,
        extract_tables: bool,
        extract_images: bool,
        languages: List[str]
    ) -> ProcessingResult:
        """
        Process document using Unstructured library.

        Args:
            file_content: Binary content
            filename: Original filename
            strategy: Extraction strategy
            extract_tables: Whether to extract tables
            extract_images: Whether to extract images
            languages: Document languages

        Returns:
            ProcessingResult with structured content
        """
        # Create temporary file for processing
        with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False) as tmp_file:
            tmp_file.write(file_content)
            tmp_path = tmp_file.name

        try:
            # Run extraction in executor to avoid blocking
            loop = asyncio.get_event_loop()
            elements = await loop.run_in_executor(
                None,
                self._extract_elements,
                tmp_path,
                strategy,
                extract_tables,
                extract_images,
                languages
            )

            # Process elements into structured content
            structured_content = self._process_elements(elements)

            # Extract raw text
            raw_text = self._extract_raw_text(elements)

            # Count pages
            page_count = self._count_pages(elements)

            # Detect language
            language = self.detect_language(raw_text) or languages[0]

            return self.create_result(
                raw_text=self.clean_text(raw_text),
                structured_content=structured_content,
                page_count=page_count,
                language=language,
                success=True,
                metadata={
                    "extraction_method": "unstructured",
                    "strategy": strategy,
                    "tables_extracted": extract_tables,
                    "images_extracted": extract_images,
                    "element_count": len(elements)
                }
            )

        finally:
            # Clean up temp file
            Path(tmp_path).unlink(missing_ok=True)

    def _extract_elements(
        self,
        file_path: str,
        strategy: str,
        extract_tables: bool,
        extract_images: bool,
        languages: List[str]
    ) -> List[Any]:
        """
        Extract elements from document using Unstructured.

        Args:
            file_path: Path to document
            strategy: Extraction strategy
            extract_tables: Whether to extract tables
            extract_images: Whether to extract images
            languages: Document languages

        Returns:
            List of extracted elements
        """
        try:
            # Try to use partition for PDF files
            if file_path.lower().endswith('.pdf'):
                # Use PDF-specific partition that doesn't need torch
                from unstructured.partition.pdf import partition_pdf
                elements = partition_pdf(
                    filename=file_path,
                    include_page_breaks=True,
                    include_metadata=True,
                    extract_images_in_pdf=False,  # Disable image extraction to avoid torch
                    strategy='fast'  # Use fast strategy to avoid OCR/torch
                )
            elif file_path.lower().endswith('.docx'):
                from unstructured.partition.docx import partition_docx
                elements = partition_docx(
                    filename=file_path,
                    include_page_breaks=True,
                    include_metadata=True
                )
            else:
                # Fallback to text partition
                from unstructured.partition.text import partition_text
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                elements = partition_text(
                    text=text,
                    include_metadata=True
                )

            return elements
        except Exception as e:
            # If Unstructured fails, return empty list to trigger fallback
            print(f"Unstructured extraction failed: {e}")
            raise

    def _process_elements(self, elements: List[Any]) -> Dict[str, Any]:
        """
        Process Unstructured elements into structured content.

        Args:
            elements: List of Unstructured elements

        Returns:
            Structured content dictionary
        """
        structured = {
            "sections": {},
            "tables": [],
            "lists": [],
            "titles": [],
            "pages": {},
            "procurement_sections": {
                "cahier_charges": [],
                "annexes": [],
                "bordereaux": [],
                "clauses": []
            },
            "metadata": {}
        }

        current_section = None
        current_page = 1

        for element in elements:
            element_type = element.__class__.__name__

            # Get metadata
            metadata = {}
            if hasattr(element, 'metadata'):
                metadata = {
                    'page': getattr(element.metadata, 'page_number', current_page),
                    'coordinates': getattr(element.metadata, 'coordinates', None),
                    'filename': getattr(element.metadata, 'filename', None),
                    'detection_class': getattr(element.metadata, 'detection_class_prob', None)
                }
                current_page = metadata['page']

            # Store by page
            if current_page not in structured["pages"]:
                structured["pages"][current_page] = {
                    "elements": [],
                    "text": "",
                    "tables": [],
                    "lists": []
                }

            element_data = {
                "type": element_type,
                "text": str(element),
                "metadata": metadata
            }

            structured["pages"][current_page]["elements"].append(element_data)
            structured["pages"][current_page]["text"] += str(element) + "\n"

            # Process by type
            if element_type == "Title":
                title_text = str(element).upper()
                structured["titles"].append({
                    "text": str(element),
                    "page": metadata['page'],
                    "level": self._detect_title_level(str(element))
                })

                # Detect procurement sections
                if "CCTP" in title_text or "CAHIER" in title_text and "TECHNIQUE" in title_text:
                    current_section = "cahier_charges"
                elif "CCAP" in title_text or "CAHIER" in title_text and "ADMINISTRATIF" in title_text:
                    current_section = "clauses"
                elif "ANNEXE" in title_text:
                    current_section = "annexes"
                elif "BORDEREAU" in title_text or "BPU" in title_text or "DQE" in title_text:
                    current_section = "bordereaux"

            elif element_type == "Table":
                table_data = self._extract_table_data(element)
                table_data["page"] = metadata['page']
                table_data["section"] = current_section
                structured["tables"].append(table_data)
                structured["pages"][current_page]["tables"].append(table_data)

            elif element_type in ["ListItem", "BulletedListItem", "NumberedListItem"]:
                list_item = {
                    "text": str(element),
                    "page": metadata['page'],
                    "type": element_type,
                    "section": current_section
                }
                structured["lists"].append(list_item)
                structured["pages"][current_page]["lists"].append(list_item)

            # Add to current procurement section
            if current_section and current_section in structured["procurement_sections"]:
                structured["procurement_sections"][current_section].append(element_data)

            # Store as regular section
            if element_type == "Title":
                section_key = self._normalize_section_key(str(element))
                structured["sections"][section_key] = {
                    "title": str(element),
                    "page": metadata['page'],
                    "content": []
                }
                current_section = section_key
            elif current_section in structured["sections"]:
                structured["sections"][current_section]["content"].append(element_data)

        return structured

    def _extract_table_data(self, table_element) -> Dict[str, Any]:
        """
        Extract table data from Unstructured table element.

        Args:
            table_element: Unstructured table element

        Returns:
            Dictionary with table data
        """
        table_data = {
            "type": "table",
            "text": str(table_element),
            "html": None,
            "data": []
        }

        # Try to get HTML representation if available
        if hasattr(table_element, 'metadata') and hasattr(table_element.metadata, 'text_as_html'):
            table_data["html"] = table_element.metadata.text_as_html

        # Try to parse table structure
        try:
            # Split by lines and cells
            lines = str(table_element).split('\n')
            for line in lines:
                if line.strip():
                    # Simple cell splitting - could be improved
                    cells = [cell.strip() for cell in line.split('\t')]
                    if not cells:
                        cells = [cell.strip() for cell in line.split('|')]
                    table_data["data"].append(cells)
        except:
            pass

        return table_data

    def _extract_raw_text(self, elements: List[Any]) -> str:
        """
        Extract raw text from all elements.

        Args:
            elements: List of Unstructured elements

        Returns:
            Combined text
        """
        texts = []
        for element in elements:
            if str(element).strip():
                texts.append(str(element))
        return "\n\n".join(texts)

    def _count_pages(self, elements: List[Any]) -> int:
        """
        Count number of pages from elements.

        Args:
            elements: List of Unstructured elements

        Returns:
            Number of pages
        """
        max_page = 0
        for element in elements:
            if hasattr(element, 'metadata') and hasattr(element.metadata, 'page_number'):
                max_page = max(max_page, element.metadata.page_number)
        return max_page if max_page > 0 else 1

    def _detect_title_level(self, title_text: str) -> int:
        """
        Detect title hierarchy level.

        Args:
            title_text: Title text

        Returns:
            Level (1-4)
        """
        # Simple heuristic based on patterns
        if title_text.isupper() and len(title_text) < 50:
            return 1  # Main title
        elif title_text.startswith(("CHAPITRE", "PARTIE", "SECTION")):
            return 1
        elif title_text.startswith(("Article", "ARTICLE")):
            return 2
        elif any(title_text.startswith(f"{i}.") for i in range(1, 20)):
            return 2
        elif any(title_text.startswith(f"{i}.{j}") for i in range(1, 20) for j in range(1, 20)):
            return 3
        else:
            return 2

    def _normalize_section_key(self, title: str) -> str:
        """
        Normalize section title for use as dictionary key.

        Args:
            title: Section title

        Returns:
            Normalized key
        """
        import re
        # Remove special characters and normalize
        key = re.sub(r'[^\w\s]', '', title)
        key = key.lower().strip().replace(' ', '_')
        return key[:50]  # Limit length

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

    async def extract_sections(self, structured_content: Dict) -> Dict[str, Any]:
        """
        Extract and categorize document sections.

        Args:
            structured_content: Structured content from processing

        Returns:
            Categorized sections
        """
        sections = structured_content.get("procurement_sections", {})

        # Enhance with additional detection
        all_text = ""
        for page_data in structured_content.get("pages", {}).values():
            all_text += page_data.get("text", "") + "\n"

        # Additional patterns for French procurement documents
        patterns = {
            "objet_marche": r"(?:Objet du marché|OBJET).*?(?:\n.*?){0,5}",
            "duree_marche": r"(?:Durée du marché|DUREE).*?(?:\n.*?){0,3}",
            "criteres_selection": r"(?:Critères de sélection|CRITERES).*?(?:\n.*?){0,10}",
            "modalites_paiement": r"(?:Modalités de paiement|PAIEMENT).*?(?:\n.*?){0,5}"
        }

        for section_type, pattern in patterns.items():
            import re
            matches = re.findall(pattern, all_text, re.IGNORECASE | re.MULTILINE)
            if matches:
                sections[section_type] = matches

        return sections