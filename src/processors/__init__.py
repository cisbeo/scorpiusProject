"""Document processors for extracting content from various file formats."""

from src.processors.base import (
    DocumentProcessor,
    ProcessingError,
    ProcessingResult,
    processor_factory,
)
from src.processors.pdf_processor import PDFProcessor

# Try to import Docling-enhanced processors (highest priority)
try:
    from src.processors.pdf_processor_nlp_docling import PDFProcessorNLPDocling
    DOCLING_NLP_AVAILABLE = True
except ImportError:
    PDFProcessorNLPDocling = None
    DOCLING_NLP_AVAILABLE = False

try:
    from src.processors.pdf_processor_docling import PDFProcessorDocling
    DOCLING_AVAILABLE = True
except ImportError:
    PDFProcessorDocling = None
    DOCLING_AVAILABLE = False

# Try to import NLP-enhanced processor (fallback)
try:
    from src.processors.pdf_processor_nlp import PDFProcessorNLP
    PDF_NLP_AVAILABLE = True
except ImportError:
    PDFProcessorNLP = None
    PDF_NLP_AVAILABLE = False

# Register processors in order of priority
# TODO: Fix Docling processors to implement supports_file method
# if DOCLING_NLP_AVAILABLE:
#     # Highest priority: Docling with NLP
#     processor_factory.register_processor(PDFProcessorNLPDocling())
# elif DOCLING_AVAILABLE:
#     # Second priority: Docling without NLP
#     processor_factory.register_processor(PDFProcessorDocling())
if PDF_NLP_AVAILABLE:
    # Third priority: Standard NLP processor
    processor_factory.register_processor(PDFProcessorNLP())
else:
    # Fallback: Basic PDF processor
    processor_factory.register_processor(PDFProcessor())

__all__ = [
    "DocumentProcessor",
    "ProcessingResult",
    "ProcessingError",
    "PDFProcessor",
    "processor_factory",
]

if DOCLING_NLP_AVAILABLE:
    __all__.append("PDFProcessorNLPDocling")

if DOCLING_AVAILABLE:
    __all__.append("PDFProcessorDocling")

if PDF_NLP_AVAILABLE:
    __all__.append("PDFProcessorNLP")
