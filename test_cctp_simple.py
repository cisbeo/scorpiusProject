#!/usr/bin/env python3
"""Simple test of CCTP document with RAG improvements."""

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

# Disable verbose loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def test_cctp_rag():
    """Test the RAG pipeline with CCTP document."""
    from src.processors.pdf_processor import PDFProcessor
    from src.services.ai.mistral_service import get_mistral_service
    from src.services.ai.chunking_service import ChunkingService
    from src.services.ai.prompt_templates import PromptTemplates
    from src.processors.base import ProcessingResult
    import uuid

    logger.info("=== Testing CCTP with RAG Improvements ===")

    # Load CCTP document
    doc_path = Path("/Users/cedric/Dev/projects/scorpiusProject/Examples/VSGP-AO/CCTP.pdf")

    if not doc_path.exists():
        logger.error(f"Document not found: {doc_path}")
        return

    # Initialize services
    pdf_processor = PDFProcessor()
    mistral_service = get_mistral_service()
    chunking_service = ChunkingService()

    # Step 1: Process PDF
    logger.info(f"\n--- Step 1: Processing {doc_path.name} ---")

    with open(doc_path, 'rb') as f:
        file_content = f.read()

    # Process with PDF processor
    result = await pdf_processor.process_document(
        file_content=file_content,
        filename=doc_path.name
    )

    if not result.success:
        logger.error(f"PDF processing failed: {result.metadata.get('error')}")
        return

    logger.info(f"✅ PDF processed successfully")
    logger.info(f"   - Extracted {len(result.raw_text)} characters")
    logger.info(f"   - Pages: {result.metadata.get('pages', 'N/A')}")

    # Step 2: Create chunks
    logger.info(f"\n--- Step 2: Creating Chunks ---")

    chunks = await chunking_service.chunk_document(
        processing_result=result,
        document_id=str(uuid.uuid4())
    )

    logger.info(f"✅ Created {len(chunks)} chunks")

    # Show sample chunks
    if chunks:
        logger.info(f"Sample chunk 1: {chunks[0]['chunk_text'][:100]}...")
        if len(chunks) > 10:
            logger.info(f"Sample chunk 10: {chunks[9]['chunk_text'][:100]}...")

    # Step 3: Test embedding cache
    logger.info(f"\n--- Step 3: Testing Embedding Cache ---")

    # Test with first 5 chunks
    test_chunks = [chunk["chunk_text"] for chunk in chunks[:5]]

    # First pass - API calls
    start = time.time()
    embeddings1 = await mistral_service.generate_embeddings_batch(
        test_chunks,
        batch_size=3,
        show_progress=False
    )
    time1 = time.time() - start
    logger.info(f"First pass (API): {time1:.2f}s for {len(test_chunks)} chunks")

    # Second pass - should use cache
    start = time.time()
    embeddings2 = await mistral_service.generate_embeddings_batch(
        test_chunks,
        batch_size=3,
        show_progress=False
    )
    time2 = time.time() - start
    logger.info(f"Second pass (cache): {time2:.2f}s")

    if time2 > 0:
        logger.info(f"🚀 Cache speedup: {time1/time2:.1f}x faster")

    # Step 4: Test RAG queries with improved prompts
    logger.info(f"\n--- Step 4: Testing RAG Queries ---")

    # Select relevant chunks for context (first 3 chunks as sample)
    context = "\n\n".join([chunk["chunk_text"] for chunk in chunks[:3]])

    test_queries = [
        "Quel est l'objet principal du marché décrit dans le CCTP?",
        "Quelles sont les normes techniques à respecter?"
    ]

    for query in test_queries[:1]:  # Test just one query to avoid rate limits
        logger.info(f"\n📝 Query: {query}")

        # Generate prompt with template
        prompt = PromptTemplates.rag_query_prompt(
            query=query,
            context=context[:2000]  # Limit context size
        )

        try:
            # Wait to avoid rate limits
            await asyncio.sleep(5)

            # Generate response
            response = await mistral_service.generate_completion(
                prompt=prompt,
                max_tokens=150,
                temperature=0.1
            )

            logger.info(f"✅ Response: {response[:300]}...")

        except Exception as e:
            logger.warning(f"Query failed (rate limit): {str(e)[:100]}")

    # Step 5: Test with source tracking
    logger.info(f"\n--- Step 5: Query with Source Tracking ---")

    context_chunks = [
        {"text": chunks[0]["chunk_text"][:200], "page_number": 1},
        {"text": chunks[1]["chunk_text"][:200], "page_number": 2} if len(chunks) > 1 else {"text": "N/A", "page_number": 1}
    ]

    prompt_with_sources = PromptTemplates.rag_query_with_sources_prompt(
        "Quelle est la durée du marché?",
        context_chunks
    )

    logger.info("Generated prompt with source tracking")

    # Step 6: Show statistics
    logger.info(f"\n--- Step 6: Final Statistics ---")

    stats = mistral_service.get_usage_stats()
    logger.info(f"📊 API Statistics:")
    logger.info(f"   - Total requests: {stats['total_requests']}")
    logger.info(f"   - Cache saves: {stats['cache_saves']}")
    logger.info(f"   - Cost saved: ${stats['estimated_savings_usd']:.4f}")

    if 'cache_stats' in stats:
        cache_stats = stats['cache_stats']
        logger.info(f"💾 Cache Performance:")
        logger.info(f"   - Hit rate: {cache_stats['hit_rate']}")
        logger.info(f"   - Total hits: {cache_stats['cache_hits']}")

    logger.info(f"\n✅ Test Complete! Successfully processed CCTP with {len(chunks)} chunks")

    return {
        "success": True,
        "chunks": len(chunks),
        "cache_saves": stats['cache_saves'],
        "text_extracted": len(result.raw_text)
    }


async def main():
    """Main test function."""
    try:
        result = await test_cctp_rag()

        if result and result["success"]:
            logger.info("\n" + "="*50)
            logger.info("🎉 CCTP RAG Pipeline Test Successful!")
            logger.info(f"📄 Extracted: {result['text_extracted']} characters")
            logger.info(f"📦 Chunks: {result['chunks']}")
            logger.info(f"💰 Cache saves: {result['cache_saves']}")
            logger.info("="*50)

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())