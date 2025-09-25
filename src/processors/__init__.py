"""Document processors for extracting content from various file formats."""

from src.processors.base import (
    DocumentProcessor,
    ProcessingError,
    ProcessingResult,
    processor_factory,
)
from src.processors.pdf_processor import PDFProcessor
from src.processors.unstructured_processor import UnstructuredProcessor

# Register processors
# UnstructuredProcessor as primary (will fallback to PyPDF2 if unavailable)
processor_factory.register_processor(UnstructuredProcessor())
processor_factory.register_processor(PDFProcessor())

__all__ = [
    "DocumentProcessor",
    "ProcessingResult",
    "ProcessingError",
    "PDFProcessor",
    "UnstructuredProcessor",
    "processor_factory",
]
