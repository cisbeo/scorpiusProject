"""Add tender support and document types

Revision ID: 001
Revises:
Create Date: 2025-09-25 12:40:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create procurement_tenders table
    op.create_table(
        'procurement_tenders',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reference', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('organization', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('deadline_date', sa.DateTime(), nullable=True),
        sa.Column('publication_date', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('budget_estimate', sa.DECIMAL(precision=15, scale=2), nullable=True),
        sa.Column('global_analysis', sa.JSON(), nullable=True),
        sa.Column('matching_score', sa.Float(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reference')
    )
    op.create_index(op.f('ix_procurement_tenders_deadline_date'), 'procurement_tenders', ['deadline_date'], unique=False)
    op.create_index(op.f('ix_procurement_tenders_reference'), 'procurement_tenders', ['reference'], unique=False)
    op.create_index(op.f('ix_procurement_tenders_status'), 'procurement_tenders', ['status'], unique=False)

    # Add new columns to procurement_documents
    op.add_column('procurement_documents', sa.Column('tender_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('procurement_documents', sa.Column('document_type', sa.String(length=50), nullable=True))
    op.add_column('procurement_documents', sa.Column('is_mandatory', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('procurement_documents', sa.Column('cross_references', sa.JSON(), nullable=True))
    op.add_column('procurement_documents', sa.Column('extraction_metadata', sa.JSON(), nullable=True))

    # Create foreign key and index for tender_id
    op.create_foreign_key('fk_procurement_documents_tender_id', 'procurement_documents', 'procurement_tenders', ['tender_id'], ['id'])
    op.create_index(op.f('ix_procurement_documents_tender_id'), 'procurement_documents', ['tender_id'], unique=False)
    op.create_index(op.f('ix_procurement_documents_document_type'), 'procurement_documents', ['document_type'], unique=False)

    # Add tender_id to bid_responses
    op.add_column('bid_responses', sa.Column('tender_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_bid_responses_tender_id', 'bid_responses', 'procurement_tenders', ['tender_id'], ['id'])
    op.create_index(op.f('ix_bid_responses_tender_id'), 'bid_responses', ['tender_id'], unique=False)


def downgrade() -> None:
    # Remove tender_id from bid_responses
    op.drop_index(op.f('ix_bid_responses_tender_id'), table_name='bid_responses')
    op.drop_constraint('fk_bid_responses_tender_id', 'bid_responses', type_='foreignkey')
    op.drop_column('bid_responses', 'tender_id')

    # Remove new columns from procurement_documents
    op.drop_index(op.f('ix_procurement_documents_document_type'), table_name='procurement_documents')
    op.drop_index(op.f('ix_procurement_documents_tender_id'), table_name='procurement_documents')
    op.drop_constraint('fk_procurement_documents_tender_id', 'procurement_documents', type_='foreignkey')
    op.drop_column('procurement_documents', 'extraction_metadata')
    op.drop_column('procurement_documents', 'cross_references')
    op.drop_column('procurement_documents', 'is_mandatory')
    op.drop_column('procurement_documents', 'document_type')
    op.drop_column('procurement_documents', 'tender_id')

    # Drop procurement_tenders table
    op.drop_index(op.f('ix_procurement_tenders_status'), table_name='procurement_tenders')
    op.drop_index(op.f('ix_procurement_tenders_reference'), table_name='procurement_tenders')
    op.drop_index(op.f('ix_procurement_tenders_deadline_date'), table_name='procurement_tenders')
    op.drop_table('procurement_tenders')