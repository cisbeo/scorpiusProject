"""
Database models for document embeddings and NLP results.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    # Fallback for development without pgvector
    from sqlalchemy import LargeBinary as Vector
    PGVECTOR_AVAILABLE = False

from src.db.base import Base


class DocumentEmbedding(Base):
    """
    Store document chunk embeddings for vector similarity search.
    
    Each row represents a chunk of a document with its embedding vector.
    """
    __tablename__ = "document_embeddings"
    
    # Primary key
    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Foreign keys
    document_id = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("procurement_documents.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Chunk information
    chunk_id = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    
    # Embedding vector (768 dimensions for CamemBERT)
    embedding = Column(Vector(768) if PGVECTOR_AVAILABLE else Vector, nullable=True)
    
    # Metadata
    chunk_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Multi-tenancy
    tenant_id = Column(PostgresUUID(as_uuid=True), nullable=True)
    
    # Relationships
    document = relationship("ProcurementDocument", back_populates="embeddings")
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('document_id', 'chunk_id', name='uq_document_chunk'),
        Index('idx_embeddings_document', 'document_id'),
        Index('idx_embeddings_tenant', 'tenant_id'),
    )
    
    def __repr__(self) -> str:
        return f"<DocumentEmbedding(document_id={self.document_id}, chunk_id={self.chunk_id})>"
    
    @property
    def content_preview(self) -> str:
        """Get a preview of the chunk content."""
        return self.content[:100] + "..." if len(self.content) > 100 else self.content
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'document_id': str(self.document_id),
            'chunk_id': self.chunk_id,
            'content_preview': self.content_preview,
            'has_embedding': self.embedding is not None,
            'metadata': self.chunk_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class RequirementSummary(Base):
    """
    Store extracted requirements from documents.
    
    Each row represents a requirement extracted from a document.
    """
    __tablename__ = "requirement_summaries"
    
    # Primary key
    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Foreign keys
    document_id = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("procurement_documents.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Requirement details
    requirement_type = Column(
        String(50),
        nullable=False
    )  # technical, functional, administrative
    
    requirement_text = Column(Text, nullable=False)
    
    priority = Column(
        String(20),
        nullable=False
    )  # mandatory, optional, nice-to-have
    
    # Extracted information
    extracted_entities = Column(ARRAY(String), nullable=True)
    keywords = Column(ARRAY(String), nullable=True)
    
    # Quality metrics
    confidence_score = Column(Float, nullable=True)
    
    # Additional metadata
    requirement_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Multi-tenancy
    tenant_id = Column(PostgresUUID(as_uuid=True), nullable=True)
    
    # Relationships
    document = relationship("ProcurementDocument", back_populates="requirement_summaries")
    
    # Indexes
    __table_args__ = (
        Index('idx_req_summary_document', 'document_id'),
        Index('idx_req_summary_type', 'requirement_type'),
        Index('idx_req_summary_priority', 'priority'),
    )
    
    def __repr__(self) -> str:
        return f"<RequirementSummary(type={self.requirement_type}, priority={self.priority})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'document_id': str(self.document_id),
            'requirement_type': self.requirement_type,
            'requirement_text': self.requirement_text,
            'priority': self.priority,
            'extracted_entities': self.extracted_entities,
            'keywords': self.keywords,
            'confidence_score': self.confidence_score,
            'metadata': self.requirement_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class SimilaritySearchResult:
    """
    Result from a vector similarity search.
    
    Not a database model, but a data class for search results.
    """
    
    def __init__(
        self,
        embedding: DocumentEmbedding,
        similarity_score: float,
        rank: int
    ):
        self.embedding = embedding
        self.similarity_score = similarity_score
        self.rank = rank
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'document_id': str(self.embedding.document_id),
            'chunk_id': self.embedding.chunk_id,
            'content_preview': self.embedding.content_preview,
            'similarity_score': self.similarity_score,
            'rank': self.rank,
            'metadata': self.embedding.chunk_metadata
        }