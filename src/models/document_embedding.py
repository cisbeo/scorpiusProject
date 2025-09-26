"""Document embedding model for vector storage."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, JSON, String, Text, Float
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import BaseModel

if TYPE_CHECKING:
    from src.models.document import ProcurementDocument
    from src.models.user import User


class DocumentEmbedding(BaseModel):
    """Model for storing document embeddings in vector database."""

    __tablename__ = "document_embeddings"

    # Primary identifiers
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("procurement_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    chunk_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        comment="Unique identifier for this chunk"
    )

    # Content and embedding
    chunk_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Text content of the chunk"
    )

    # Note: embedding column is handled specially by pgvector
    # It will be a vector(1024) column but we declare it as JSON here
    # for SQLAlchemy compatibility
    embedding: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        comment="Vector embedding (1024 dimensions for Mistral)"
    )

    # Metadata for filtering and context
    chunk_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        default={},
        comment="Additional metadata for the chunk"
    )

    document_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Type of document (CCTP, CCAP, RC, etc.)"
    )

    section_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Section type within document (article, clause, annexe, etc.)"
    )

    page_number: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Page number in original document"
    )

    # Chunking metadata
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Sequential index of chunk in document"
    )

    chunk_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Size of chunk in characters"
    )

    overlap_size: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of overlapping characters with adjacent chunks"
    )

    # Quality and processing metadata
    language: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        default="fr",
        comment="Language of the chunk"
    )

    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Confidence score of embedding quality (0.0-1.0)"
    )

    # Relationships
    document: Mapped["ProcurementDocument"] = relationship(
        "ProcurementDocument",
        back_populates="embeddings",
        lazy="select"
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<DocumentEmbedding(chunk_id={self.chunk_id}, doc={self.document_id}, type={self.section_type})>"

    @property
    def text_preview(self) -> str:
        """Get preview of chunk text."""
        if self.chunk_text:
            return self.chunk_text[:100] + "..." if len(self.chunk_text) > 100 else self.chunk_text
        return ""


class QueryCache(BaseModel):
    """Model for caching frequent queries and responses."""

    __tablename__ = "query_cache"

    # Primary identifiers
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )

    query_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="SHA-256 hash of query text for deduplication"
    )

    # Query and response
    query_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Original query text"
    )

    query_embedding: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        comment="Query vector embedding"
    )

    response: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="Cached response data"
    )

    # Cache metadata
    cache_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        default={},
        comment="Additional metadata"
    )

    hit_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Number of cache hits"
    )

    ttl_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3600,
        comment="Time to live in seconds"
    )

    last_accessed_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        comment="Last time this cache entry was accessed"
    )

    expires_at: Mapped[datetime] = mapped_column(
        nullable=False,
        comment="When this cache entry expires"
    )

    def __repr__(self) -> str:
        """String representation."""
        query_preview = self.query_text[:50] + "..." if len(self.query_text) > 50 else self.query_text
        return f"<QueryCache(hash={self.query_hash[:8]}, query='{query_preview}', hits={self.hit_count})>"

    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return datetime.utcnow() > self.expires_at


class RAGFeedback(BaseModel):
    """Model for storing user feedback on RAG responses."""

    __tablename__ = "rag_feedback"

    # Primary identifiers
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )

    query_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("query_cache.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Content
    query_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Query that generated the response"
    )

    response_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Response that was provided"
    )

    # Feedback
    feedback_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Type: 'positive', 'negative', 'correction'"
    )

    feedback_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed feedback text"
    )

    rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Rating 1-5"
    )

    # User tracking
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Metadata
    feedback_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        default={},
        comment="Additional context"
    )

    # Relationships
    query: Mapped[Optional["QueryCache"]] = relationship(
        "QueryCache",
        lazy="select"
    )

    user: Mapped[Optional["User"]] = relationship(
        "User",
        lazy="select"
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<RAGFeedback(type={self.feedback_type}, rating={self.rating})>"