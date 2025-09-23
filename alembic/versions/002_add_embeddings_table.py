"""Add embeddings table for vector search.

Revision ID: 002
Revises: 001
Create Date: 2025-01-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from pgvector.sqlalchemy import Vector

# revision identifiers
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create embeddings table and enable pgvector extension."""
    
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Create embeddings table
    op.create_table(
        'document_embeddings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_id', UUID(as_uuid=True), nullable=False),
        sa.Column('chunk_id', sa.Integer, nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('embedding', Vector(768), nullable=True),  # 768 dimensions for CamemBERT
        sa.Column('metadata', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=True),
        
        # Foreign key to procurement_documents
        sa.ForeignKeyConstraint(['document_id'], ['procurement_documents.id'], ondelete='CASCADE'),
        
        # Indexes
        sa.Index('idx_embeddings_document', 'document_id'),
        sa.Index('idx_embeddings_tenant', 'tenant_id'),
        sa.UniqueConstraint('document_id', 'chunk_id', name='uq_document_chunk')
    )
    
    # Create index for vector similarity search
    op.execute(
        'CREATE INDEX idx_embeddings_vector ON document_embeddings '
        'USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)'
    )
    
    # Add column to procurement_documents for NLP processing status
    op.add_column(
        'procurement_documents',
        sa.Column('nlp_processed', sa.Boolean, default=False, nullable=False, server_default='false')
    )
    
    op.add_column(
        'procurement_documents',
        sa.Column('nlp_metadata', sa.JSON, nullable=True)
    )
    
    # Create requirements summary table
    op.create_table(
        'requirement_summaries',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_id', UUID(as_uuid=True), nullable=False),
        sa.Column('requirement_type', sa.String(50), nullable=False),  # technical, functional, administrative
        sa.Column('requirement_text', sa.Text, nullable=False),
        sa.Column('priority', sa.String(20), nullable=False),  # mandatory, optional, nice-to-have
        sa.Column('extracted_entities', ARRAY(sa.String), nullable=True),
        sa.Column('keywords', ARRAY(sa.String), nullable=True),
        sa.Column('confidence_score', sa.Float, nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=True),
        
        sa.ForeignKeyConstraint(['document_id'], ['procurement_documents.id'], ondelete='CASCADE'),
        sa.Index('idx_req_summary_document', 'document_id'),
        sa.Index('idx_req_summary_type', 'requirement_type'),
        sa.Index('idx_req_summary_priority', 'priority')
    )


def downgrade() -> None:
    """Drop embeddings tables and pgvector extension."""
    
    # Drop tables
    op.drop_table('requirement_summaries')
    op.drop_table('document_embeddings')
    
    # Remove columns from procurement_documents
    op.drop_column('procurement_documents', 'nlp_metadata')
    op.drop_column('procurement_documents', 'nlp_processed')
    
    # Note: We don't drop the vector extension as other tables might use it