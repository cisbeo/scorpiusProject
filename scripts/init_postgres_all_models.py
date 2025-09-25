#!/usr/bin/env python3
"""
Script d'initialisation de la base de données PostgreSQL avec tous les modèles.
Ce script est appelé par init_docker_env.sh et garantit que tous les modèles
sont correctement créés, y compris les nouveaux modèles de tender.
"""

import asyncio
import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Forcer l'utilisation de PostgreSQL (pas SQLite)
os.environ["APP_ENV"] = "development"

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Récupérer DATABASE_URL depuis .env
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL non trouvée dans .env")
    sys.exit(1)

# S'assurer que c'est bien PostgreSQL
if "sqlite" in DATABASE_URL.lower():
    print("❌ DATABASE_URL pointe vers SQLite, PostgreSQL requis")
    print(f"   URL actuelle: {DATABASE_URL}")
    sys.exit(1)

print(f"🔌 Connexion à: {DATABASE_URL}")

# Import de la base après avoir configuré l'environnement
from src.db.base import Base

# Import explicite de TOUS les modèles pour s'assurer qu'ils sont enregistrés
from src.models.user import User, UserRole
from src.models.audit import AuditLog
from src.models.company import CompanyProfile

# Nouveaux modèles pour le support multi-documents
from src.models.procurement_tender import ProcurementTender, TenderStatus
from src.models.document_type import DocumentType, DocumentTypeInfo
from src.models.document import ProcurementDocument, DocumentStatus

# Modèles d'analyse et de traitement
from src.models.requirements import ExtractedRequirements
from src.models.match import CapabilityMatch, MatchRecommendation
from src.models.bid import BidResponse, ResponseType, ResponseStatus
from src.models.compliance import ComplianceCheck, ComplianceStatus, ComplianceSeverity
from src.models.events import ProcessingEvent, ProcessingStage, EventStatus


async def drop_all_tables(engine):
    """Supprime toutes les tables existantes."""
    print("🗑️  Suppression des tables existantes...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("✅ Tables supprimées")


async def create_all_tables(engine):
    """Crée toutes les tables."""
    print("🔨 Création des tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables créées")


async def verify_tables(engine):
    """Vérifie et liste toutes les tables créées."""
    print("\n📊 Vérification des tables créées:")

    async with engine.connect() as conn:
        # Liste des tables attendues
        expected_tables = [
            'users',
            'audit_logs',
            'company_profiles',
            'procurement_tenders',  # Nouvelle table
            'procurement_documents',
            'extracted_requirements',
            'capability_matches',
            'bid_responses',
            'compliance_checks',
            'processing_events'
        ]

        # Récupérer les tables existantes
        result = await conn.execute(
            text("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename;
            """)
        )
        tables = result.fetchall()
        existing_tables = [row[0] for row in tables]

        # Afficher les tables
        print("\n  Tables existantes:")
        for table in existing_tables:
            emoji = "✅" if table in expected_tables else "⚠️"
            print(f"    {emoji} {table}")

        # Vérifier les tables manquantes
        missing_tables = set(expected_tables) - set(existing_tables)
        if missing_tables:
            print("\n  ⚠️ Tables manquantes:")
            for table in missing_tables:
                print(f"    - {table}")

        # Vérifier les colonnes clés des nouvelles tables
        print("\n  📋 Vérification des nouvelles colonnes:")

        # Vérifier procurement_tenders
        if 'procurement_tenders' in existing_tables:
            result = await conn.execute(
                text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'procurement_tenders'
                AND column_name IN ('reference', 'title', 'organization', 'deadline_date', 'global_analysis')
                ORDER BY column_name;
                """)
            )
            columns = result.fetchall()
            print("    Table: procurement_tenders")
            for col_name, col_type in columns:
                print(f"      ✅ {col_name}: {col_type}")

        # Vérifier les nouvelles colonnes dans procurement_documents
        if 'procurement_documents' in existing_tables:
            result = await conn.execute(
                text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'procurement_documents'
                AND column_name IN ('tender_id', 'document_type', 'is_mandatory', 'cross_references', 'extraction_metadata')
                ORDER BY column_name;
                """)
            )
            columns = result.fetchall()
            print("    Table: procurement_documents (nouvelles colonnes)")
            for col_name, col_type in columns:
                print(f"      ✅ {col_name}: {col_type}")

        # Vérifier les foreign keys
        print("\n  🔗 Vérification des relations:")
        result = await conn.execute(
            text("""
            SELECT
                tc.table_name,
                tc.constraint_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = 'public'
            AND (
                (tc.table_name = 'procurement_documents' AND kcu.column_name = 'tender_id')
                OR (tc.table_name = 'bid_responses' AND kcu.column_name = 'tender_id')
            );
            """)
        )
        relations = result.fetchall()
        for table, constraint, column, foreign_table, foreign_column in relations:
            print(f"      ✅ {table}.{column} → {foreign_table}.{foreign_column}")

        # Statistiques finales
        print(f"\n📈 Résumé:")
        print(f"    - Tables créées: {len(existing_tables)}")
        print(f"    - Tables attendues: {len(expected_tables)}")
        print(f"    - Tables manquantes: {len(missing_tables)}")

        return len(missing_tables) == 0


async def create_test_data(engine):
    """Crée des données de test minimales."""
    print("\n🧪 Création de données de test...")

    async with engine.connect() as conn:
        try:
            # Créer un utilisateur de test
            await conn.execute(
                text("""
                INSERT INTO users (id, email, full_name, password_hash, is_active, role, created_at, updated_at)
                VALUES (
                    gen_random_uuid(),
                    'admin@scorpius.fr',
                    'Administrateur',
                    '$2b$12$wr6ZugWBgbfN43JtrMN0Q.R4ai/SRDPOucTNF40XqgV983ZoSrXra',  -- password: Admin123!
                    true,
                    'ADMIN',
                    NOW(),
                    NOW()
                )
                ON CONFLICT (email) DO NOTHING;
                """)
            )
            await conn.commit()
            print("    ✅ Utilisateur admin créé")

        except Exception as e:
            print(f"    ⚠️ Données de test: {str(e)}")


async def init_db():
    """Fonction principale d'initialisation."""
    print("🚀 Initialisation de la base de données PostgreSQL")
    print("=" * 50)

    # Créer l'engine
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,  # Mettre à True pour voir les requêtes SQL
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10
    )

    try:
        # Test de connexion
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version();"))
            version = result.scalar()
            print(f"✅ Connecté à PostgreSQL")
            print(f"   Version: {version.split(',')[0]}")

        # Suppression et création des tables
        await drop_all_tables(engine)
        await create_all_tables(engine)

        # Vérification
        success = await verify_tables(engine)

        # Données de test
        await create_test_data(engine)

        if success:
            print("\n✨ Initialisation réussie!")
            return 0
        else:
            print("\n⚠️ Initialisation terminée avec des avertissements")
            return 1

    except Exception as e:
        print(f"\n❌ Erreur lors de l'initialisation: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        await engine.dispose()


if __name__ == "__main__":
    exit_code = asyncio.run(init_db())
    sys.exit(exit_code)