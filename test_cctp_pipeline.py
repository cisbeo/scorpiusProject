#!/usr/bin/env python3
"""Test the complete RAG pipeline with CCTP document."""

import asyncio
import logging
from pathlib import Path
import json
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Disable verbose loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def test_cctp_document():
    """Test the full pipeline with CCTP document."""
    from src.services.document_pipeline import DocumentPipelineService
    from src.services.ai.mistral_service import get_mistral_service
    from src.services.ai.chunking_service import ChunkingService
    from src.services.ai.prompt_templates import PromptTemplates
    import uuid

    logger.info("=== Testing CCTP Document Processing ===")

    # Find the CCTP document
    doc_path = Path("/Users/cedric/Dev/projects/scorpiusProject/Examples/VSGP-AO/CCTP.pdf")

    if not doc_path.exists():
        logger.error(f"Document not found: {doc_path}")
        return

    # Initialize services
    pipeline = DocumentPipelineService()
    mistral_service = get_mistral_service()

    # Generate unique IDs for this test
    document_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    # Step 1: Process the document
    logger.info(f"\n--- Step 1: Processing {doc_path.name} ---")
    start_time = time.time()

    with open(doc_path, 'rb') as f:
        result = await pipeline.process_document(
            file_content=f.read(),
            filename=doc_path.name,
            document_type="CCTP",
            document_id=document_id,
            user_id=user_id,
            tenant_id=None
        )

    processing_time = time.time() - start_time

    if not result["success"]:
        logger.error(f"Document processing failed: {result}")
        return

    logger.info(f"✅ Document processed successfully in {processing_time:.2f}s")
    logger.info(f"   - Processing time: {result['processing_time_ms']}ms")
    logger.info(f"   - Extracted text length: {len(result.get('raw_text', ''))} characters")
    logger.info(f"   - Indexed: {result.get('indexed', False)}")

    # Step 2: Create chunks and embeddings
    logger.info(f"\n--- Step 2: Chunking and Indexing ---")

    chunking_service = ChunkingService()

    # Create processing result for chunking
    from src.models.processing_result import ProcessingResult
    processing_result = ProcessingResult(
        success=True,
        processor_name="pdf",
        processing_time_ms=result['processing_time_ms'],
        raw_text=result.get('raw_text', ''),
        structured_content=result.get('structured_content', {}),
        metadata=result.get('metadata', {})
    )

    # Perform chunking
    chunks = await chunking_service.chunk_document(
        processing_result=processing_result,
        document_id=document_id
    )

    logger.info(f"✅ Created {len(chunks)} chunks from the document")

    # Step 3: Generate embeddings with caching
    logger.info(f"\n--- Step 3: Generating Embeddings (with cache) ---")

    # Extract text from chunks
    chunk_texts = [chunk["chunk_text"] for chunk in chunks[:10]]  # Test with first 10 chunks

    # First pass - will hit API
    start_time = time.time()
    embeddings_first = await mistral_service.generate_embeddings_batch(
        chunk_texts,
        batch_size=5,
        show_progress=True
    )
    first_pass_time = time.time() - start_time
    logger.info(f"First pass (API calls): {first_pass_time:.2f}s")

    # Second pass - should use cache
    start_time = time.time()
    embeddings_cached = await mistral_service.generate_embeddings_batch(
        chunk_texts,
        batch_size=5,
        show_progress=False
    )
    cache_pass_time = time.time() - start_time
    logger.info(f"Second pass (from cache): {cache_pass_time:.2f}s")
    logger.info(f"🚀 Cache speedup: {first_pass_time / cache_pass_time:.1f}x faster")

    # Step 4: Test RAG queries
    logger.info(f"\n--- Step 4: Testing RAG Queries ---")

    test_queries = [
        "Quels sont les systèmes de chauffage mentionnés dans le CCTP?",
        "Quelle est la durée des travaux prévue?",
        "Quelles sont les normes de sécurité à respecter?",
        "Quel est le système de ventilation requis?",
        "Quelles sont les exigences pour la climatisation?"
    ]

    # Test with limited context to avoid rate limits
    sample_context = result.get('raw_text', '')[:2000]  # First 2000 chars

    for query in test_queries[:2]:  # Test only 2 queries to avoid rate limits
        logger.info(f"\nQuery: {query}")

        # Create prompt with template
        prompt = PromptTemplates.rag_query_prompt(
            query=query,
            context=sample_context
        )

        try:
            # Add delay to respect rate limits
            await asyncio.sleep(5)

            # Generate response
            response = await mistral_service.generate_completion(
                prompt=prompt,
                max_tokens=200,
                temperature=0.1
            )

            logger.info(f"Response: {response[:200]}...")

        except Exception as e:
            logger.warning(f"Query failed (likely rate limit): {e}")
            logger.info("Continuing with next query after delay...")
            await asyncio.sleep(10)

    # Step 5: Display statistics
    logger.info(f"\n--- Step 5: Final Statistics ---")

    stats = mistral_service.get_usage_stats()
    logger.info("API Usage Statistics:")
    logger.info(f"  - Total requests: {stats['total_requests']}")
    logger.info(f"  - Cache saves: {stats['cache_saves']}")
    logger.info(f"  - Estimated savings: ${stats['estimated_savings_usd']:.4f}")
    logger.info(f"  - Total cost: ${stats['total_cost_usd']:.4f}")

    if 'cache_stats' in stats:
        cache_stats = stats['cache_stats']
        logger.info("\nCache Performance:")
        logger.info(f"  - Hit rate: {cache_stats['hit_rate']}")
        logger.info(f"  - Total hits: {cache_stats['cache_hits']}")
        logger.info(f"  - Total misses: {cache_stats['cache_misses']}")

    logger.info("\n✅ CCTP Pipeline Test Complete!")

    return {
        "success": True,
        "document_id": document_id,
        "chunks_created": len(chunks),
        "cache_speedup": f"{first_pass_time / cache_pass_time:.1f}x" if cache_pass_time > 0 else "N/A",
        "stats": stats
    }


async def main():
    """Main test function."""
    try:
        result = await test_cctp_document()

        if result and result["success"]:
            logger.info("\n=== Test Summary ===")
            logger.info(f"✅ Successfully processed CCTP document")
            logger.info(f"📄 Document ID: {result['document_id']}")
            logger.info(f"📊 Chunks created: {result['chunks_created']}")
            logger.info(f"⚡ Cache speedup: {result['cache_speedup']}")

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())