#!/usr/bin/env python3
"""
Démo d'utilisation des processeurs Docling v2.

Ce script montre comment utiliser les nouveaux processeurs Docling v2
avec l'interface async et les fonctionnalités avancées.

Usage:
    python scripts/demo_docling_v2.py [--file PDF_PATH]
"""

import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Optional

# Ajouter le répertoire racine au path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Imports du projet
from src.processors.base import processor_factory
from src.processors.doc_processor_docling import DocProcessorDocling
from src.processors.doc_processor_nlp_docling import DocProcessorNLPDocling


class DoclingV2Demo:
    """Démonstrateur des processeurs Docling v2."""

    def __init__(self):
        """Initialise la démo."""
        self.test_documents = [
            # PDF existants dans le projet
            "/Users/cedric/Dev/projects/scorpiusProject/uploads/default/user_c3ccd051/2025/09/b99b5088405d1818.pdf",
            "/Users/cedric/Dev/projects/scorpiusProject/uploads/default/user_346a61d9/2025/09/87f480f8e7a741b9.pdf"
        ]

    def create_test_document(self) -> bytes:
        """Crée un document de test simulé."""
        return """
CAHIER DES CHARGES TECHNIQUES PARTICULIÈRES

1. OBJET DU MARCHÉ

Le présent marché a pour objet la fourniture et l'installation d'un système
de gestion documentaire numérique permettant de traiter les documents PDF
et d'extraire automatiquement les exigences techniques.

2. EXIGENCES TECHNIQUES

2.1 Exigences fonctionnelles
- Le système doit pouvoir traiter les documents PDF
- Compatible avec les formats Word et Excel
- Garantie de disponibilité 99.9%
- Interface utilisateur intuitive

2.2 Exigences techniques
- Architecture distribuée et scalable
- API REST pour l'intégration
- Support multilingue (français, anglais)
- Sauvegarde automatique des données

3. LIVRABLES

Le prestataire devra fournir:
1. Documentation technique complète
2. Code source documenté
3. Formation des utilisateurs
4. Support technique pendant 12 mois

4. CRITÈRES D'ÉVALUATION

Les offres seront évaluées selon:
- Prix: 30%
- Valeur technique: 50%
- Références: 20%
""".encode('utf-8')

    async def demo_basic_processor(self):
        """Démo du processeur Docling de base."""
        logger.info("🔍 DÉMO: DocProcessorDocling v2")
        logger.info("=" * 50)

        # Créer le processeur
        processor = DocProcessorDocling()

        logger.info(f"Processeur: {processor.name} v{processor.version}")
        logger.info(f"Extensions supportées: {processor.supported_extensions}")

        # Créer un document de test
        document_content = self.create_test_document()
        filename = "cctp_demo.pdf"

        # Traitement
        logger.info(f"\n📄 Traitement de {filename}...")
        start_time = time.time()

        result = await processor.process_document(
            file_content=document_content,
            filename=filename,
            mime_type="application/pdf"
        )

        processing_time = time.time() - start_time

        # Affichage des résultats
        logger.info(f"✅ Traitement terminé en {processing_time:.2f}s")
        logger.info(f"Succès: {result.success}")
        logger.info(f"Temps: {result.processing_time_ms}ms")
        logger.info(f"Processeur: {result.processor_name}")

        if result.errors:
            logger.info(f"Erreurs: {result.errors}")
        if result.warnings:
            logger.info(f"Warnings: {result.warnings}")

        # Contenu structuré
        if result.structured_content:
            structure = result.structured_content
            logger.info(f"\n📊 Contenu structuré:")
            logger.info(f"- Sections: {len(structure.get('sections', []))}")
            logger.info(f"- Tables: {len(structure.get('tables', []))}")
            logger.info(f"- Markdown: {'Disponible' if structure.get('markdown') else 'Non disponible'}")

        return result

    async def demo_nlp_processor(self):
        """Démo du processeur Docling avec NLP."""
        logger.info("\n🧠 DÉMO: DocProcessorNLPDocling v2")
        logger.info("=" * 50)

        # Créer le processeur
        processor = DocProcessorNLPDocling()

        logger.info(f"Processeur: {processor.name} v{processor.version}")

        # Créer un document de test
        document_content = self.create_test_document()
        filename = "cctp_nlp_demo.pdf"

        # Traitement
        logger.info(f"\n📄 Traitement NLP de {filename}...")
        start_time = time.time()

        result = await processor.process_document(
            file_content=document_content,
            filename=filename,
            mime_type="application/pdf"
        )

        processing_time = time.time() - start_time

        # Affichage des résultats
        logger.info(f"✅ Traitement NLP terminé en {processing_time:.2f}s")
        logger.info(f"Succès: {result.success}")
        logger.info(f"Temps total: {result.processing_time_ms}ms")
        logger.info(f"Processeur: {result.processor_name}")

        # Analyse NLP
        if result.structured_content:
            structure = result.structured_content
            logger.info(f"\n📊 Analyse NLP:")

            # Chunks
            chunks = structure.get('chunks', [])
            logger.info(f"- Chunks créés: {len(chunks)}")

            # Requirements
            requirements = structure.get('requirements', [])
            logger.info(f"- Requirements détectés: {len(requirements)}")

            if requirements:
                logger.info("\n📋 Exemples de requirements:")
                for i, req in enumerate(requirements[:5]):  # Premiers 5
                    req_type = req.get('type', 'unknown')
                    req_text = req.get('text', '')[:80] + "..." if len(req.get('text', '')) > 80 else req.get('text', '')
                    confidence = req.get('confidence', 0)
                    logger.info(f"  {i+1}. [{req_type}] {req_text} (conf: {confidence:.2f})")

            # Analyse NLP détaillée
            nlp_analysis = structure.get('nlp_analysis', {})
            if nlp_analysis:
                logger.info(f"\n🔍 Détails NLP:")
                logger.info(f"- Entités: {len(nlp_analysis.get('entities', []))}")
                logger.info(f"- Embeddings: {len(nlp_analysis.get('embeddings', []))}")
                logger.info(f"- Classification: {nlp_analysis.get('classification', {})}")

                # Summary si disponible
                summary = nlp_analysis.get('summary', '')
                if summary:
                    logger.info(f"- Résumé: {summary[:150]}...")

        return result

    async def demo_factory_usage(self):
        """Démo d'utilisation de la factory."""
        logger.info("\n🏭 DÉMO: Utilisation de la ProcessorFactory")
        logger.info("=" * 50)

        # Lister les processeurs disponibles
        processors = processor_factory.list_processors()
        logger.info(f"Processeurs enregistrés: {processors}")

        # Obtenir un processeur pour PDF
        pdf_processor = processor_factory.get_processor_for_file(
            filename="document.pdf",
            mime_type="application/pdf"
        )

        if pdf_processor:
            logger.info(f"✅ Processeur sélectionné: {pdf_processor.name} v{pdf_processor.version}")

            # Test avec la factory
            document_content = self.create_test_document()
            result = await pdf_processor.process_document(
                file_content=document_content,
                filename="factory_test.pdf",
                mime_type="application/pdf"
            )

            logger.info(f"Résultat factory - Succès: {result.success}")
            logger.info(f"Processeur utilisé: {result.processor_name}")
        else:
            logger.warning("❌ Aucun processeur trouvé pour les PDFs")

    async def demo_real_file(self, file_path: str):
        """Démo avec un vrai fichier PDF."""
        logger.info(f"\n📁 DÉMO: Traitement du fichier {file_path}")
        logger.info("=" * 50)

        if not Path(file_path).exists():
            logger.error(f"❌ Fichier non trouvé: {file_path}")
            return

        # Lire le fichier
        with open(file_path, 'rb') as f:
            file_content = f.read()

        filename = Path(file_path).name
        logger.info(f"Fichier: {filename} ({len(file_content)} bytes)")

        # Utiliser le processeur NLP complet
        processor = DocProcessorNLPDocling()

        # Traitement
        start_time = time.time()
        result = await processor.process_document(
            file_content=file_content,
            filename=filename,
            mime_type="application/pdf"
        )
        processing_time = time.time() - start_time

        # Résultats
        logger.info(f"✅ Fichier traité en {processing_time:.2f}s")
        logger.info(f"Succès: {result.success}")
        logger.info(f"Pages: {result.page_count}")
        logger.info(f"Mots: {result.word_count}")
        logger.info(f"Confiance: {result.confidence_score:.2%}")

        if result.structured_content:
            structure = result.structured_content
            requirements = structure.get('requirements', [])
            chunks = structure.get('chunks', [])

            logger.info(f"Requirements trouvés: {len(requirements)}")
            logger.info(f"Chunks créés: {len(chunks)}")

            # Aperçu du texte
            if result.raw_text:
                preview = result.raw_text[:300] + "..." if len(result.raw_text) > 300 else result.raw_text
                logger.info(f"\nAperçu du texte:\n{preview}")

    async def run_all_demos(self, file_path: Optional[str] = None):
        """Exécute toutes les démos."""
        logger.info("🚀 DÉMARRAGE DES DÉMOS DOCLING V2")
        logger.info("=" * 60)

        try:
            # Vérifier la disponibilité
            try:
                import docling
                logger.info(f"Docling version: {getattr(docling, '__version__', 'unknown')}")
            except ImportError:
                logger.warning("⚠️ Docling non installé - les démos montreront les fallbacks")

            # Démos
            await self.demo_basic_processor()
            await self.demo_nlp_processor()
            await self.demo_factory_usage()

            # Fichier réel si fourni
            if file_path:
                await self.demo_real_file(file_path)
            else:
                # Essayer avec un fichier existant
                for test_file in self.test_documents:
                    if Path(test_file).exists():
                        await self.demo_real_file(test_file)
                        break
                else:
                    logger.info("\n📄 Aucun fichier PDF trouvé pour la démo avec fichier réel")

            logger.info("\n" + "=" * 60)
            logger.info("🎉 DÉMOS TERMINÉES AVEC SUCCÈS!")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"❌ Erreur durant les démos: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """Fonction principale."""
    import argparse

    parser = argparse.ArgumentParser(description="Démo des processeurs Docling v2")
    parser.add_argument("--file", help="Chemin vers un fichier PDF à traiter")
    args = parser.parse_args()

    demo = DoclingV2Demo()
    await demo.run_all_demos(args.file)


if __name__ == "__main__":
    asyncio.run(main())