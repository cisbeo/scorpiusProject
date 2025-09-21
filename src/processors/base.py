"""Base interface for document processors."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass
class ProcessingResult:
    """
    Result of document processing operation.

    Contains extracted content and metadata from document processing.
    """

    # Core extracted content
    raw_text: str
    structured_content: dict[str, Any]

    # Processing metadata
    success: bool
    processing_time_ms: int
    processor_name: str
    processor_version: str

    # Content analysis
    page_count: int
    word_count: int
    language: Optional[str] = None
    confidence_score: float = 1.0

    # Error information
    errors: list[str] = None
    warnings: list[str] = None

    # Additional metadata
    metadata: dict[str, Any] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.metadata is None:
            self.metadata = {}

    @property
    def has_errors(self) -> bool:
        """Check if processing had errors."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if processing had warnings."""
        return len(self.warnings) > 0

    @property
    def processing_time_seconds(self) -> float:
        """Get processing time in seconds."""
        return self.processing_time_ms / 1000.0

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)
        self.success = False

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "raw_text": self.raw_text,
            "structured_content": self.structured_content,
            "success": self.success,
            "processing_time_ms": self.processing_time_ms,
            "processor_name": self.processor_name,
            "processor_version": self.processor_version,
            "page_count": self.page_count,
            "word_count": self.word_count,
            "language": self.language,
            "confidence_score": self.confidence_score,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata
        }


class DocumentProcessor(ABC):
    """
    Abstract base class for document processors.

    Defines the interface that all document processors must implement
    for extracting content from various file formats.
    """

    def __init__(self, name: str, version: str = "1.0.0"):
        """
        Initialize document processor.

        Args:
            name: Name of the processor
            version: Version of the processor
        """
        self.name = name
        self.version = version
        self.supported_mime_types: list[str] = []
        self.supported_extensions: list[str] = []

    @abstractmethod
    async def process_document(
        self,
        file_content: bytes,
        filename: str,
        mime_type: Optional[str] = None,
        processing_options: Optional[dict[str, Any]] = None
    ) -> ProcessingResult:
        """
        Process a document and extract content.

        Args:
            file_content: Binary content of the document
            filename: Original filename
            mime_type: MIME type of the document
            processing_options: Optional processing configuration

        Returns:
            ProcessingResult with extracted content and metadata

        Raises:
            ProcessingError: If document processing fails critically
        """
        pass

    @abstractmethod
    def supports_file(self, filename: str, mime_type: Optional[str] = None) -> bool:
        """
        Check if processor supports the given file.

        Args:
            filename: Original filename
            mime_type: MIME type of the file

        Returns:
            True if processor can handle this file type
        """
        pass

    def get_supported_types(self) -> dict[str, list[str]]:
        """
        Get supported file types.

        Returns:
            Dictionary with mime_types and extensions lists
        """
        return {
            "mime_types": self.supported_mime_types.copy(),
            "extensions": self.supported_extensions.copy()
        }

    def validate_input(
        self,
        file_content: bytes,
        filename: str,
        mime_type: Optional[str] = None
    ) -> tuple[bool, list[str]]:
        """
        Validate input before processing.

        Args:
            file_content: Binary content of the document
            filename: Original filename
            mime_type: MIME type of the document

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check if file is supported
        if not self.supports_file(filename, mime_type):
            errors.append(f"File type not supported by {self.name}")

        # Check if content is not empty
        if not file_content:
            errors.append("File content is empty")

        # Check minimum file size
        if len(file_content) < 10:
            errors.append("File is too small to be valid")

        return len(errors) == 0, errors

    def create_result(
        self,
        raw_text: str = "",
        structured_content: Optional[dict[str, Any]] = None,
        success: bool = True,
        processing_time_ms: int = 0,
        page_count: int = 0,
        **kwargs
    ) -> ProcessingResult:
        """
        Create a ProcessingResult with default values.

        Args:
            raw_text: Extracted raw text
            structured_content: Structured content dictionary
            success: Whether processing was successful
            processing_time_ms: Processing time in milliseconds
            page_count: Number of pages processed
            **kwargs: Additional arguments for ProcessingResult

        Returns:
            ProcessingResult instance
        """
        if structured_content is None:
            structured_content = {}

        # Calculate word count
        word_count = len(raw_text.split()) if raw_text else 0

        return ProcessingResult(
            raw_text=raw_text,
            structured_content=structured_content,
            success=success,
            processing_time_ms=processing_time_ms,
            processor_name=self.name,
            processor_version=self.version,
            page_count=page_count,
            word_count=word_count,
            **kwargs
        )

    def measure_processing_time(self, start_time: datetime) -> int:
        """
        Calculate processing time from start time.

        Args:
            start_time: Processing start time

        Returns:
            Processing time in milliseconds
        """
        end_time = datetime.utcnow()
        duration = end_time - start_time
        return int(duration.total_seconds() * 1000)

    def extract_metadata(
        self,
        file_content: bytes,
        filename: str
    ) -> dict[str, Any]:
        """
        Extract basic metadata from file.

        Args:
            file_content: Binary content of the document
            filename: Original filename

        Returns:
            Dictionary with file metadata
        """
        from pathlib import Path

        return {
            "file_size": len(file_content),
            "filename": filename,
            "file_extension": Path(filename).suffix.lower(),
            "processor": self.name,
            "processor_version": self.version,
            "processed_at": datetime.utcnow().isoformat()
        }

    def clean_text(self, text: str) -> str:
        """
        Clean and normalize extracted text.

        Args:
            text: Raw extracted text

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove excessive whitespace
        text = " ".join(text.split())

        # Remove control characters except newlines and tabs
        cleaned_chars = []
        for char in text:
            if char.isprintable() or char in ['\n', '\t']:
                cleaned_chars.append(char)
            else:
                cleaned_chars.append(' ')

        text = ''.join(cleaned_chars)

        # Normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        return text.strip()

    def detect_language(self, text: str) -> Optional[str]:
        """
        Detect language of the extracted text.

        Args:
            text: Text to analyze

        Returns:
            Language code (e.g., 'fr', 'en') or None if detection fails

        Note:
            This is a placeholder implementation. In production,
            you might want to use a more sophisticated language detection library.
        """
        if not text or len(text) < 50:
            return None

        # Simple French detection based on common words
        french_indicators = [
            'le ', 'la ', 'les ', 'de ', 'du ', 'des ', 'et ', 'à ', 'pour ',
            'dans ', 'avec ', 'sur ', 'par ', 'que ', 'qui ', 'une ', 'un ',
            'est ', 'sont ', 'avoir ', 'être ', 'faire ', 'aller'
        ]

        text_lower = text.lower()
        french_count = sum(1 for indicator in french_indicators if indicator in text_lower)

        if french_count >= 3:
            return 'fr'

        # Default to French for French procurement documents
        return 'fr'

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on the processor.

        Returns:
            Dictionary with health status information
        """
        return {
            "processor": self.name,
            "version": self.version,
            "status": "healthy",
            "supported_types": self.get_supported_types(),
            "timestamp": datetime.utcnow().isoformat()
        }


class ProcessingError(Exception):
    """Exception raised when document processing fails."""

    def __init__(self, message: str, processor_name: str, cause: Optional[Exception] = None):
        """
        Initialize processing error.

        Args:
            message: Error message
            processor_name: Name of the processor that failed
            cause: Optional underlying exception
        """
        super().__init__(message)
        self.processor_name = processor_name
        self.cause = cause

    def __str__(self) -> str:
        """String representation of the error."""
        base_msg = f"[{self.processor_name}] {super().__str__()}"
        if self.cause:
            base_msg += f" (caused by: {str(self.cause)})"
        return base_msg


class ProcessorFactory:
    """
    Factory for creating and managing document processors.

    Provides a registry of available processors and methods for
    selecting the appropriate processor for a given file type.
    """

    def __init__(self):
        """Initialize processor factory."""
        self._processors: dict[str, DocumentProcessor] = {}

    def register_processor(self, processor: DocumentProcessor) -> None:
        """
        Register a document processor.

        Args:
            processor: DocumentProcessor instance to register
        """
        self._processors[processor.name] = processor

    def get_processor(self, name: str) -> Optional[DocumentProcessor]:
        """
        Get processor by name.

        Args:
            name: Name of the processor

        Returns:
            DocumentProcessor instance or None if not found
        """
        return self._processors.get(name)

    def get_processor_for_file(
        self,
        filename: str,
        mime_type: Optional[str] = None
    ) -> Optional[DocumentProcessor]:
        """
        Get the best processor for a given file.

        Args:
            filename: Original filename
            mime_type: MIME type of the file

        Returns:
            DocumentProcessor instance that can handle the file, or None
        """
        for processor in self._processors.values():
            if processor.supports_file(filename, mime_type):
                return processor
        return None

    def list_processors(self) -> list[str]:
        """
        List all registered processor names.

        Returns:
            List of processor names
        """
        return list(self._processors.keys())

    def get_supported_types(self) -> dict[str, dict[str, list[str]]]:
        """
        Get supported file types for all processors.

        Returns:
            Dictionary mapping processor names to their supported types
        """
        return {
            name: processor.get_supported_types()
            for name, processor in self._processors.items()
        }


# Global processor factory instance
processor_factory = ProcessorFactory()
