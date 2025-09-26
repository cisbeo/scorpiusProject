"""add_vector_embeddings_table

Revision ID: 71a8fecf90f8
Revises:
Create Date: 2025-09-26 09:27:17.684516

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '71a8fecf90f8'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')

    # Create document_embeddings table
    op.create_table('document_embeddings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chunk_id', sa.String(length=100), nullable=False),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True),  # Will be converted to vector
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('document_type', sa.String(length=50), nullable=True),
        sa.Column('section_type', sa.String(length=100), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('chunk_size', sa.Integer(), nullable=False),
        sa.Column('overlap_size', sa.Integer(), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['procurement_documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chunk_id')
    )

    # Convert embedding column to vector type (1024 dimensions for Mistral)
    op.execute('ALTER TABLE document_embeddings ALTER COLUMN embedding TYPE vector(1024) USING embedding::vector(1024)')

    # Create indexes for performance
    op.create_index('idx_embedding_document_id', 'document_embeddings', ['document_id'])
    op.create_index('idx_embedding_document_type', 'document_embeddings', ['document_type'])
    op.create_index('idx_embedding_section_type', 'document_embeddings', ['section_type'])
    op.create_index('idx_embedding_chunk_text_trgm', 'document_embeddings', ['chunk_text'], postgresql_using='gin', postgresql_ops={'chunk_text': 'gin_trgm_ops'})

    # Create HNSW index for vector similarity search
    op.execute("""
        CREATE INDEX idx_embedding_vector_hnsw
        ON document_embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # Create query_cache table for caching frequent queries
    op.create_table('query_cache',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('query_hash', sa.String(length=64), nullable=False),
        sa.Column('query_text', sa.Text(), nullable=False),
        sa.Column('query_embedding', postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column('response', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('hit_count', sa.Integer(), default=1, nullable=False),
        sa.Column('ttl_seconds', sa.Integer(), default=3600, nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_accessed_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('query_hash')
    )

    # Convert query_embedding to vector
    op.execute('ALTER TABLE query_cache ALTER COLUMN query_embedding TYPE vector(1024) USING query_embedding::vector(1024)')

    # Create indexes for query cache
    op.create_index('idx_query_cache_hash', 'query_cache', ['query_hash'])
    op.create_index('idx_query_cache_expires', 'query_cache', ['expires_at'])

    # Create rag_feedback table for improving responses
    op.create_table('rag_feedback',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('query_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('query_text', sa.Text(), nullable=False),
        sa.Column('response_text', sa.Text(), nullable=False),
        sa.Column('feedback_type', sa.String(length=20), nullable=False),  # 'positive', 'negative', 'correction'
        sa.Column('feedback_text', sa.Text(), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['query_id'], ['query_cache.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index('idx_feedback_query_id', 'rag_feedback', ['query_id'])
    op.create_index('idx_feedback_type', 'rag_feedback', ['feedback_type'])
    op.create_index('idx_feedback_rating', 'rag_feedback', ['rating'])


def downgrade() -> None:
    # Drop tables
    op.drop_table('rag_feedback')
    op.drop_table('query_cache')
    op.drop_table('document_embeddings')

    # Drop extensions (be careful in production)
    op.execute('DROP EXTENSION IF EXISTS vector')
    op.execute('DROP EXTENSION IF EXISTS pg_trgm')