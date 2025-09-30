#!/bin/bash

echo "🚀 Installation des dépendances pour le plan RAG"
echo "================================================"

# 1. Mettre à jour requirements.txt avec les dépendances manquantes
echo "📦 Ajout des dépendances Python manquantes..."
cat >> requirements.txt << EOF

# RAG Dependencies (added for implementation plan)
asyncpg-pgvector==0.2.0  # Async pgvector support
prometheus-client==0.19.0  # Metrics export
pandas>=2.0.0  # Data analysis for dashboard
EOF

# 2. Rebuild Docker image
echo "🐳 Reconstruction de l'image Docker..."
docker-compose build app

# 3. Exécuter les migrations SQL
echo "🗄️ Application des migrations SQL..."
docker-compose exec -T db psql -U scorpius -d scorpius_mvp < scripts/002_prepare_for_rag.sql

# 4. Créer la migration Alembic pour analysis_history
echo "📝 Création de la migration Alembic..."
docker-compose exec app alembic revision -m "Add analysis history and fix embeddings" << 'EOF'
"""Add analysis history and fix embeddings

Revision ID: ${revision}
Revises: ${down_revision}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

# revision identifiers
revision = '${revision}'
down_revision = '${down_revision}'
branch_labels = ${branch_labels}
depends_on = ${depends_on}

def upgrade():
    # Create analysis_history table
    op.create_table('analysis_history',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('tender_id', UUID(as_uuid=True), nullable=False),
        sa.Column('analysis_type', sa.String(50), nullable=False),
        sa.Column('analysis_version', sa.String(20), default='1.0'),
        sa.Column('matching_score', sa.Float()),
        sa.Column('completeness_score', sa.Float()),
        sa.Column('risk_level', sa.String(20)),
        sa.Column('recommendation', sa.String(50)),
        sa.Column('total_requirements', sa.Integer()),
        sa.Column('matched_requirements', sa.Integer()),
        sa.Column('critical_gaps', sa.Integer()),
        sa.Column('processing_time_ms', sa.Integer()),
        sa.Column('full_analysis', JSONB()),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('analyzed_by', UUID(as_uuid=True)),
        sa.Column('tenant_id', UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tender_id'], ['procurement_tenders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['analyzed_by'], ['users.id'])
    )

    # Create indexes
    op.create_index('idx_analysis_history_tender', 'analysis_history', ['tender_id'])
    op.create_index('idx_analysis_history_date', 'analysis_history', ['analyzed_at'])
    op.create_index('idx_analysis_history_score', 'analysis_history', ['matching_score'])

    # Fix document_embeddings table
    op.drop_column('document_embeddings', 'embedding')
    op.add_column('document_embeddings', sa.Column('embedding', Vector(1536)))

def downgrade():
    op.drop_index('idx_analysis_history_score')
    op.drop_index('idx_analysis_history_date')
    op.drop_index('idx_analysis_history_tender')
    op.drop_table('analysis_history')

    op.drop_column('document_embeddings', 'embedding')
    op.add_column('document_embeddings', sa.Column('embedding', JSONB()))
EOF

# 5. Appliquer les migrations
echo "⚙️ Application des migrations Alembic..."
docker-compose exec app alembic upgrade head

# 6. Vérifier l'installation
echo "✅ Vérification de l'installation..."
docker-compose exec -T db psql -U scorpius -d scorpius_mvp -c "
SELECT
    'pgvector' as component,
    extversion as version,
    'installed' as status
FROM pg_extension
WHERE extname = 'vector'
UNION ALL
SELECT
    'analysis_history' as component,
    'table' as version,
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'analysis_history')
         THEN 'created'
         ELSE 'missing'
    END as status;"

echo "✅ Installation terminée!"
echo "📋 Prochaines étapes:"
echo "   1. Implémenter les services Python (VectorService, etc.)"
echo "   2. Migrer les données existantes"
echo "   3. Créer les endpoints analytics"