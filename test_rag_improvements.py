#!/usr/bin/env python3
"""Test script for RAG pipeline improvements."""

import asyncio
import logging
from pathlib import Path
import json
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Disable some verbose loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def test_rag_with_cache():
    """Test the RAG pipeline with Redis caching enabled."""
    from src.services.ai.mistral_service import get_mistral_service
    from src.services.ai.prompt_templates import PromptTemplates
    import uuid

    logger.info("=== Testing RAG Pipeline with Improvements ===")

    # Initialize services
    mistral_service = get_mistral_service()

    # Test document content
    test_document = """
    MARCHÉ PUBLIC DE FOURNITURES ET SERVICES

    Article 1 - Objet du marché
    Le présent marché a pour objet la fourniture et l'installation d'un système
    de gestion électronique des documents (GED) pour l'administration.

    Article 2 - Exigences techniques
    Le système doit répondre aux exigences suivantes:
    - Capacité de stockage minimum de 10TB
    - Support des formats PDF, DOCX, XLSX
    - Interface web responsive
    - Authentification SSO
    - Chiffrement des données au repos et en transit

    Article 3 - Délais de livraison
    La livraison complète du système doit être effectuée dans un délai de 6 mois
    à compter de la notification du marché.

    Article 4 - Budget
    Le budget maximal alloué à ce projet est de 150 000 euros HT.

    Article 5 - Critères de sélection
    Les offres seront évaluées selon les critères suivants:
    - Prix: 40%
    - Qualité technique: 35%
    - Délais: 15%
    - Service après-vente: 10%
    """

    # Test 1: Generate embeddings with cache
    logger.info("\n--- Test 1: Embeddings with Cache ---")

    # First call - should hit API
    start_time = time.time()
    embedding1 = await mistral_service.generate_embedding(
        "Test de cache pour les embeddings"
    )
    first_call_time = time.time() - start_time
    logger.info(f"First embedding call took: {first_call_time:.2f}s")

    # Second call - should hit cache
    start_time = time.time()
    embedding2 = await mistral_service.generate_embedding(
        "Test de cache pour les embeddings"  # Same text
    )
    cache_call_time = time.time() - start_time
    logger.info(f"Cached embedding call took: {cache_call_time:.2f}s")
    logger.info(f"Cache speedup: {first_call_time / cache_call_time:.1f}x faster")

    # Test 2: Batch embeddings with cache
    logger.info("\n--- Test 2: Batch Embeddings ---")

    test_chunks = [
        "Premier chunk de test",
        "Deuxième chunk de test",
        "Troisième chunk de test",
        "Premier chunk de test",  # Duplicate - should use cache
        "Quatrième chunk de test"
    ]

    embeddings = await mistral_service.generate_embeddings_batch(
        test_chunks,
        batch_size=3,
        show_progress=True
    )

    logger.info(f"Generated {len(embeddings)} embeddings")
    stats = mistral_service.get_usage_stats()
    logger.info(f"Cache saves: {stats.get('cache_saves', 0)}")
    logger.info(f"Estimated savings: ${stats.get('estimated_savings_usd', 0):.2f}")

    # Test 3: Test improved prompt templates
    logger.info("\n--- Test 3: Improved Prompt Templates ---")

    # Test RAG query prompt
    context = test_document
    query = "Quel est le budget maximal du projet?"

    prompt = PromptTemplates.rag_query_prompt(query, context)
    logger.info("Generated RAG prompt (first 200 chars):")
    logger.info(prompt[:200] + "...")

    # Generate response using the prompt
    response = await mistral_service.generate_completion(prompt)
    logger.info(f"Response: {response}")

    # Test 4: Query with sources
    logger.info("\n--- Test 4: Query with Source Tracking ---")

    context_chunks = [
        {"text": "Le budget maximal alloué est de 150 000 euros HT.", "page_number": 1},
        {"text": "Délai de livraison: 6 mois", "page_number": 2},
    ]

    prompt_with_sources = PromptTemplates.rag_query_with_sources_prompt(
        "Quel est le budget et le délai?",
        context_chunks
    )

    response_with_sources = await mistral_service.generate_completion(prompt_with_sources)
    logger.info(f"Response with sources: {response_with_sources}")

    # Test 5: Procurement analysis
    logger.info("\n--- Test 5: Procurement Analysis ---")

    analysis_prompt = PromptTemplates.procurement_analysis_prompt(
        "Quelles sont les principales exigences techniques?",
        test_document,
        "CCTP"
    )

    analysis = await mistral_service.generate_completion(analysis_prompt)
    logger.info(f"Procurement analysis: {analysis[:500]}...")

    # Display final statistics
    logger.info("\n--- Final Statistics ---")
    final_stats = mistral_service.get_usage_stats()
    logger.info(json.dumps(final_stats, indent=2))

    # Test cache statistics if available
    if "cache_stats" in final_stats:
        cache_stats = final_stats["cache_stats"]
        logger.info(f"Cache hit rate: {cache_stats.get('hit_rate', 'N/A')}")
        logger.info(f"Total cache hits: {cache_stats.get('cache_hits', 0)}")
        logger.info(f"Total cache misses: {cache_stats.get('cache_misses', 0)}")


async def test_full_document_pipeline():
    """Test the full document processing pipeline."""
    from src.services.document_pipeline import DocumentProcessingPipeline
    from pathlib import Path
    import uuid

    logger.info("\n=== Testing Full Document Pipeline ===")

    # Find the CCTP document
    doc_path = Path("/Users/cedric/Dev/projects/scorpiusProject/Examples/VSGP-AO/CCTP-CVC.pdf")

    if not doc_path.exists():
        logger.error(f"Document not found: {doc_path}")
        return

    # Initialize pipeline
    pipeline = DocumentProcessingPipeline()

    # Process document
    logger.info(f"Processing document: {doc_path.name}")

    with open(doc_path, 'rb') as f:
        result = await pipeline.process_document(
            file_content=f.read(),
            filename=doc_path.name,
            document_type="CCTP",
            document_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            tenant_id=None
        )

    if result["success"]:
        logger.info("Document processed successfully!")
        logger.info(f"Processing time: {result['processing_time_ms']}ms")
        logger.info(f"Extracted {len(result.get('raw_text', ''))} characters")
        logger.info(f"Indexed: {result.get('indexed', False)}")
    else:
        logger.error(f"Processing failed: {result}")


async def main():
    """Main test function."""
    try:
        # Test RAG improvements
        await test_rag_with_cache()

        # Optional: Test full pipeline (commented out to avoid long processing)
        # await test_full_document_pipeline()

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())