#!/usr/bin/env python3
"""
Script d'initialisation complète de la base de données.
Crée la base, les extensions et toutes les tables nécessaires.
"""

import asyncio
import sys
import os

# Add src to path
sys.path.append('/app/src')
sys.path.append('/app')

async def init_database_complete():
    """Initialisation complète de la base de données."""

    try:
        # Import après ajout du path
        from src.db.session import async_engine
        from src.db.base import Base

        # Import explicite de tous les modèles pour s'assurer qu'ils sont enregistrés
        from src.models.user import User
        from src.models.audit import AuditLog
        from src.models.company import CompanyProfile
        from src.models.document import ProcurementDocument
        from src.models.bid import BidResponse
        from src.models.match import CapabilityMatch
        from src.models.compliance import ComplianceCheck
        from src.models.requirements import ExtractedRequirements
        from src.models.events import ProcessingEvent
        from src.models.procurement_tender import ProcurementTender
        from src.models.document_embedding import DocumentEmbedding

        print("📋 Imported all models successfully")

        # Créer toutes les tables
        async with async_engine.begin() as conn:
            # Activer l'extension pgvector si nécessaire
            try:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                print("✅ pgvector extension enabled")
            except Exception as e:
                print(f"⚠️ pgvector extension warning: {e}")

            # Créer toutes les tables
            await conn.run_sync(Base.metadata.create_all)
            print("✅ All database tables created successfully")

            # Vérifier les tables créées
            result = await conn.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)

            tables = [row[0] for row in result.fetchall()]
            print(f"📊 Created {len(tables)} tables:")
            for table in tables:
                print(f"  - {table}")

        print("🎉 Database initialization completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(init_database_complete())
    sys.exit(0 if success else 1)