"""Document processors for extracting content from various file formats."""

from src.processors.base import (
    DocumentProcessor,
    ProcessingError,
    ProcessingResult,
    processor_factory,
)
from src.processors.pdf_processor import PDFProcessor

# Register PDF processor
processor_factory.register_processor(PDFProcessor())

__all__ = [
    "DocumentProcessor",
    "ProcessingResult",
    "ProcessingError",
    "PDFProcessor",
    "processor_factory",
]
