"""Document schemas for API requests/responses."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from src.models.document import DocumentStatus


class DocumentUploadResponse(BaseModel):
    """Response schema for document upload."""

    id: UUID = Field(description="Document unique identifier")
    original_filename: str = Field(description="Original filename")
    file_size: int = Field(description="File size in bytes")
    mime_type: str = Field(description="MIME type of the file")
    status: DocumentStatus = Field(description="Processing status")
    uploaded_by: UUID = Field(description="ID of user who uploaded the document")
    created_at: datetime = Field(description="Upload timestamp")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "original_filename": "cahier_des_charges.pdf",
                "file_size": 2048576,
                "mime_type": "application/pdf",
                "status": "uploaded",
                "uploaded_by": "123e4567-e89b-12d3-a456-426614174001",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
    }


class DocumentResponse(BaseModel):
    """Response schema for document information."""

    id: UUID = Field(description="Document unique identifier")
    original_filename: str = Field(description="Original filename")
    file_size: int = Field(description="File size in bytes")
    mime_type: str = Field(description="MIME type of the file")
    status: DocumentStatus = Field(description="Processing status")

    # Processing information
    processing_started_at: Optional[datetime] = Field(description="Processing start time")
    processing_completed_at: Optional[datetime] = Field(description="Processing completion time")
    processing_duration_ms: Optional[int] = Field(description="Processing duration in milliseconds")
    error_message: Optional[str] = Field(description="Error message if processing failed")

    # Metadata
    uploaded_by: UUID = Field(description="ID of user who uploaded the document")
    version: int = Field(description="Document version")
    tenant_id: Optional[UUID] = Field(description="Tenant ID for multi-tenancy")

    # Timestamps
    created_at: datetime = Field(description="Upload timestamp")
    updated_at: datetime = Field(description="Last update timestamp")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "original_filename": "cahier_des_charges.pdf",
                "file_size": 2048576,
                "mime_type": "application/pdf",
                "status": "processed",
                "processing_started_at": "2024-01-15T10:30:10Z",
                "processing_completed_at": "2024-01-15T10:30:45Z",
                "processing_duration_ms": 35000,
                "error_message": None,
                "uploaded_by": "123e4567-e89b-12d3-a456-426614174001",
                "version": 1,
                "tenant_id": None,
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:45Z"
            }
        }
    }


class DocumentListResponse(BaseModel):
    """Response schema for document list."""

    documents: list[DocumentResponse] = Field(description="List of documents")
    total: int = Field(description="Total number of documents")
    page: int = Field(description="Current page number")
    per_page: int = Field(description="Number of documents per page")
    pages: int = Field(description="Total number of pages")

    model_config = {
        "json_schema_extra": {
            "example": {
                "documents": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "original_filename": "cahier_des_charges.pdf",
                        "file_size": 2048576,
                        "mime_type": "application/pdf",
                        "status": "processed",
                        "processing_started_at": "2024-01-15T10:30:10Z",
                        "processing_completed_at": "2024-01-15T10:30:45Z",
                        "processing_duration_ms": 35000,
                        "error_message": None,
                        "uploaded_by": "123e4567-e89b-12d3-a456-426614174001",
                        "version": 1,
                        "tenant_id": None,
                        "created_at": "2024-01-15T10:30:00Z",
                        "updated_at": "2024-01-15T10:30:45Z"
                    }
                ],
                "total": 1,
                "page": 1,
                "per_page": 20,
                "pages": 1
            }
        }
    }


class ProcessingResultResponse(BaseModel):
    """Response schema for document processing result."""

    success: bool = Field(description="Whether processing was successful")
    processing_time_ms: int = Field(description="Processing time in milliseconds")
    processor_name: str = Field(description="Name of processor used")
    processor_version: str = Field(description="Version of processor used")

    # Content information
    page_count: int = Field(description="Number of pages processed")
    word_count: int = Field(description="Number of words extracted")
    language: Optional[str] = Field(description="Detected language")
    confidence_score: float = Field(description="Extraction confidence score")

    # Results
    raw_text: str = Field(description="Extracted raw text")
    structured_content: dict[str, Any] = Field(description="Structured content")

    # Quality information
    errors: list[str] = Field(description="Processing errors")
    warnings: list[str] = Field(description="Processing warnings")
    metadata: dict[str, Any] = Field(description="Processing metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "processing_time_ms": 35000,
                "processor_name": "PyPDF2Processor",
                "processor_version": "1.0.0",
                "page_count": 12,
                "word_count": 3456,
                "language": "fr",
                "confidence_score": 0.92,
                "raw_text": "CAHIER DES CHARGES\\n\\nObjet du marché: Développement d'une application...",
                "structured_content": {
                    "procurement_specific": {
                        "reference": ["REF-2024-001"],
                        "organism": ["Ministère de l'Éducation Nationale"]
                    },
                    "sections": {
                        "article_1": "Objet du marché..."
                    }
                },
                "errors": [],
                "warnings": ["Document contains images, image content cannot be extracted"],
                "metadata": {
                    "file_size": 2048576,
                    "processor": "PyPDF2Processor"
                }
            }
        }
    }


class DocumentProcessRequest(BaseModel):
    """Request schema for document processing."""

    processing_options: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional processing configuration"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "processing_options": {
                    "max_pages": 50,
                    "extract_images": False,
                    "language_hint": "fr"
                }
            }
        }
    }


class ExtractedRequirementsResponse(BaseModel):
    """Response schema for extracted requirements."""

    document_id: UUID = Field(description="Associated document ID")
    raw_content: dict[str, Any] = Field(description="Raw extracted content")
    technical_requirements: dict[str, Any] = Field(description="Technical requirements")
    functional_requirements: dict[str, Any] = Field(description="Functional requirements")
    administrative_requirements: dict[str, Any] = Field(description="Administrative requirements")
    evaluation_criteria: dict[str, Any] = Field(description="Evaluation criteria")

    # Metadata
    extracted_at: datetime = Field(description="Extraction timestamp")
    extraction_confidence: float = Field(description="Confidence score")
    language_detected: Optional[str] = Field(description="Detected language")
    version: int = Field(description="Requirements version")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "document_id": "123e4567-e89b-12d3-a456-426614174000",
                "raw_content": {
                    "raw_text": "CAHIER DES CHARGES...",
                    "structured_content": {}
                },
                "technical_requirements": {
                    "technology": "Python, FastAPI",
                    "performance": "< 200ms response time"
                },
                "functional_requirements": {
                    "features": ["User authentication", "Document upload"]
                },
                "administrative_requirements": {
                    "reference": ["REF-2024-001"],
                    "deadline": ["2024-03-15"]
                },
                "evaluation_criteria": {
                    "technical": 60,
                    "financial": 40
                },
                "extracted_at": "2024-01-15T10:30:45Z",
                "extraction_confidence": 0.92,
                "language_detected": "fr",
                "version": 1
            }
        }
    }
