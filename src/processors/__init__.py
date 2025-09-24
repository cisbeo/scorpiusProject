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
    from src.processors.doc_processor_nlp_docling import DocProcessorNLPDocling
    DOCLING_NLP_AVAILABLE = True
except ImportError:
    # Fallback to v1 if v2 not available
    try:
        from src.processors.pdf_processor_nlp_docling import PDFProcessorNLPDocling as DocProcessorNLPDocling
        DOCLING_NLP_AVAILABLE = True
    except ImportError:
        DocProcessorNLPDocling = None
        DOCLING_NLP_AVAILABLE = False

try:
    from src.processors.doc_processor_docling import DocProcessorDocling
    DOCLING_AVAILABLE = True
except ImportError:
    # Fallback to v1 if v2 not available
    try:
        from src.processors.pdf_processor_docling import PDFProcessorDocling as DocProcessorDocling
        DOCLING_AVAILABLE = True
    except ImportError:
        DocProcessorDocling = None
        DOCLING_AVAILABLE = False

# Try to import NLP-enhanced processor (fallback)
try:
    from src.processors.pdf_processor_nlp import PDFProcessorNLP
    PDF_NLP_AVAILABLE = True
except ImportError:
    PDFProcessorNLP = None
    PDF_NLP_AVAILABLE = False

# Register processors in order of priority
if DOCLING_NLP_AVAILABLE:
    # Highest priority: Docling with NLP (async support, multi-format)
    processor_factory.register_processor(DocProcessorNLPDocling())
elif DOCLING_AVAILABLE:
    # Second priority: Docling without NLP (async support, multi-format)
    processor_factory.register_processor(DocProcessorDocling())
elif PDF_NLP_AVAILABLE:
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
    __all__.append("DocProcessorNLPDocling")

if DOCLING_AVAILABLE:
    __all__.append("DocProcessorDocling")

if PDF_NLP_AVAILABLE:
    __all__.append("PDFProcessorNLP")
