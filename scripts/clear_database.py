#!/usr/bin/env python
"""Script pour nettoyer complètement la base de données."""

import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import async_engine, get_async_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def clear_all_tables():
    """Vider toutes les tables de la base de données en respectant les contraintes."""

    async with async_engine.begin() as conn:
        try:
            logger.info("🧹 Début du nettoyage de la base de données...")

            # Désactiver temporairement les contraintes de clé étrangère
            await conn.execute(text("SET CONSTRAINTS ALL DEFERRED"))

            # Liste des tables à vider dans l'ordre correct (pour respecter les dépendances)
            tables_to_clear = [
                # D'abord les tables avec des références externes
                "processing_events",
                "extracted_requirements",
                "compliance_checks",
                "capability_matches",
                "bid_responses",
                "procurement_documents",
                "company_profiles",
                "tenders",
                "audit_logs",
                "users",  # En dernier car référencé par beaucoup d'autres
            ]

            # Vider chaque table
            for table in tables_to_clear:
                try:
                    # Utiliser TRUNCATE avec CASCADE pour gérer les dépendances
                    await conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                    logger.info(f"  ✅ Table '{table}' vidée")
                except Exception as e:
                    logger.warning(f"  ⚠️  Impossible de vider '{table}': {str(e)}")
                    # Essayer avec DELETE si TRUNCATE échoue
                    try:
                        await conn.execute(text(f"DELETE FROM {table}"))
                        logger.info(f"  ✅ Table '{table}' vidée avec DELETE")
                    except Exception as e2:
                        logger.error(f"  ❌ Échec pour '{table}': {str(e2)}")

            # Réinitialiser les séquences (pour les IDs auto-incrémentés)
            sequences_to_reset = [
                "audit_logs_id_seq",
                "processing_events_id_seq",
            ]

            for sequence in sequences_to_reset:
                try:
                    await conn.execute(text(f"ALTER SEQUENCE {sequence} RESTART WITH 1"))
                    logger.info(f"  ✅ Séquence '{sequence}' réinitialisée")
                except Exception as e:
                    logger.debug(f"  ℹ️  Séquence '{sequence}' non trouvée ou non applicable: {str(e)}")

            await conn.commit()
            logger.info("✅ Base de données nettoyée avec succès!")

        except Exception as e:
            logger.error(f"❌ Erreur lors du nettoyage: {str(e)}")
            await conn.rollback()
            raise


async def verify_tables_empty():
    """Vérifier que toutes les tables sont vides."""

    async with async_engine.begin() as conn:
        logger.info("\n📊 Vérification des tables:")

        tables_to_check = [
            "users",
            "tenders",
            "procurement_documents",
            "company_profiles",
            "bid_responses",
            "capability_matches",
            "compliance_checks",
            "extracted_requirements",
            "processing_events",
            "audit_logs"
        ]

        all_empty = True
        for table in tables_to_check:
            try:
                result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()

                if count == 0:
                    logger.info(f"  ✅ {table}: 0 enregistrements")
                else:
                    logger.warning(f"  ⚠️  {table}: {count} enregistrements restants")
                    all_empty = False

            except Exception as e:
                logger.error(f"  ❌ Erreur pour {table}: {str(e)}")

        if all_empty:
            logger.info("\n✅ Toutes les tables sont vides!")
        else:
            logger.warning("\n⚠️  Certaines tables contiennent encore des données")

        return all_empty


async def main():
    """Fonction principale."""

    print("\n" + "="*60)
    print("🗑️  NETTOYAGE COMPLET DE LA BASE DE DONNÉES")
    print("="*60)
    print("\n⚠️  ATTENTION: Cette opération va supprimer TOUTES les données!")

    # Demander confirmation
    response = input("\nÊtes-vous sûr de vouloir continuer? (tapez 'OUI' pour confirmer): ")

    if response != "OUI":
        print("❌ Opération annulée")
        return

    try:
        # Nettoyer les tables
        await clear_all_tables()

        # Vérifier que tout est vide
        await verify_tables_empty()

        print("\n✅ Nettoyage terminé avec succès!")
        print("Vous pouvez maintenant relancer vos tests avec une base de données propre.")

    except Exception as e:
        logger.error(f"❌ Erreur fatale: {str(e)}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)