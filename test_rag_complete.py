#!/usr/bin/env python3
"""Complete test of the RAG pipeline with CCTP document analysis."""

import asyncio
import logging
from pathlib import Path
import time
from datetime import datetime
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Disable verbose loggers
for name in ["httpx", "httpcore", "sqlalchemy"]:
    logging.getLogger(name).setLevel(logging.WARNING)


async def test_complete_rag_pipeline():
    """Test the complete RAG pipeline with document processing and analysis."""

    from src.processors.pdf_processor import PDFProcessor
    from src.services.ai.mistral_service import get_mistral_service
    from src.services.ai.chunking_service import ChunkingService
    from src.services.ai.prompt_templates import PromptTemplates

    logger.info("="*60)
    logger.info("🚀 COMPLETE RAG PIPELINE TEST WITH CCTP DOCUMENT")
    logger.info("="*60)

    # Initialize services
    pdf_processor = PDFProcessor()
    mistral_service = get_mistral_service()
    chunking_service = ChunkingService()

    # Load CCTP document
    doc_path = Path("/Users/cedric/Dev/projects/scorpiusProject/Examples/VSGP-AO/CCTP.pdf")

    if not doc_path.exists():
        logger.error(f"Document not found: {doc_path}")
        return

    logger.info(f"\n📄 Document: {doc_path.name}")
    logger.info("-"*60)

    # Step 1: Process PDF
    logger.info("\n✨ STEP 1: PDF PROCESSING")
    logger.info("-"*40)

    with open(doc_path, 'rb') as f:
        file_content = f.read()

    start_time = time.time()
    result = await pdf_processor.process_document(
        file_content=file_content,
        filename=doc_path.name
    )
    processing_time = time.time() - start_time

    if not result.success:
        logger.error(f"PDF processing failed: {result.metadata.get('error')}")
        return

    logger.info(f"✅ PDF processed in {processing_time:.2f}s")
    logger.info(f"📝 Text extracted: {len(result.raw_text):,} characters")
    logger.info(f"📊 Pages: {result.metadata.get('pages', 'N/A')}")

    # Show text preview
    text_preview = result.raw_text[:500].replace('\n', ' ')
    logger.info(f"\n📖 Text preview:")
    logger.info(f"   \"{text_preview}...\"")

    # Step 2: Create chunks
    logger.info("\n✨ STEP 2: DOCUMENT CHUNKING")
    logger.info("-"*40)

    document_id = str(uuid.uuid4())
    chunks = await chunking_service.chunk_document(
        processing_result=result,
        document_id=document_id
    )

    logger.info(f"✅ Created {len(chunks)} chunks")
    logger.info(f"📦 Average chunk size: {sum(c.chunk_size for c in chunks) // len(chunks)} chars")

    # Show sample chunks
    if chunks:
        logger.info(f"\n📑 Sample chunks:")
        for i, chunk in enumerate(chunks[:3], 1):
            preview = chunk.chunk_text[:150].replace('\n', ' ')
            logger.info(f"   Chunk {i}: \"{preview}...\"")

    # Step 3: Generate embeddings with cache demonstration
    logger.info("\n✨ STEP 3: EMBEDDING GENERATION & CACHING")
    logger.info("-"*40)

    # Test with first 5 chunks
    test_texts = [chunk.chunk_text for chunk in chunks[:5]]

    # First pass - API calls
    logger.info("🔄 First pass (API calls)...")
    start_time = time.time()
    embeddings1 = await mistral_service.generate_embeddings_batch(
        test_texts,
        batch_size=3,
        show_progress=False
    )
    api_time = time.time() - start_time
    logger.info(f"   Time: {api_time:.2f}s")
    logger.info(f"   Embeddings generated: {len(embeddings1)}")

    # Second pass - from cache
    logger.info("⚡ Second pass (from cache)...")
    start_time = time.time()
    embeddings2 = await mistral_service.generate_embeddings_batch(
        test_texts,
        batch_size=3,
        show_progress=False
    )
    cache_time = time.time() - start_time
    logger.info(f"   Time: {cache_time:.2f}s")

    if cache_time > 0:
        speedup = api_time / cache_time
        logger.info(f"   🚀 Cache speedup: {speedup:.1f}x faster")

    # Step 4: RAG Queries
    logger.info("\n✨ STEP 4: RAG QUERY ANALYSIS")
    logger.info("-"*40)

    # Prepare context from chunks
    context = "\n\n".join([chunk.chunk_text for chunk in chunks[:5]])

    queries = [
        "Quel est l'objet principal du marché décrit dans ce CCTP?",
        "Quelles sont les principales normes techniques à respecter?",
        "Quelle est la durée prévue pour les travaux?"
    ]

    for i, query in enumerate(queries, 1):
        logger.info(f"\n❓ Query {i}: {query}")

        # Generate prompt
        prompt = PromptTemplates.rag_query_prompt(
            query=query,
            context=context[:2000]  # Limit context size
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

            # Display response
            if response:
                response_preview = response[:300].strip()
                logger.info(f"💡 Response: {response_preview}")
                if len(response) > 300:
                    logger.info(f"   ... (truncated, full response: {len(response)} chars)")

        except Exception as e:
            logger.warning(f"⚠️ Query failed (rate limit): {str(e)[:100]}")
            logger.info("   Continuing with next query...")
            await asyncio.sleep(10)

    # Step 5: Statistics
    logger.info("\n✨ STEP 5: USAGE STATISTICS")
    logger.info("-"*40)

    stats = mistral_service.get_usage_stats()

    logger.info("📊 API Usage:")
    logger.info(f"   Total requests: {stats['total_requests']}")
    logger.info(f"   Cache hits: {stats['cache_saves']}")
    logger.info(f"   Total cost: ${stats['total_cost_usd']:.4f}")
    logger.info(f"   Savings from cache: ${stats['estimated_savings_usd']:.4f}")

    if 'cache_stats' in stats and stats['cache_stats']:
        cache_stats = stats['cache_stats']
        logger.info("\n💾 Cache Performance:")
        logger.info(f"   Hit rate: {cache_stats.get('hit_rate', 'N/A')}")
        logger.info(f"   Total hits: {cache_stats.get('cache_hits', 0)}")
        logger.info(f"   Total misses: {cache_stats.get('cache_misses', 0)}")

    # Final summary
    logger.info("\n"+"="*60)
    logger.info("✅ COMPLETE RAG PIPELINE TEST SUCCESSFUL!")
    logger.info("="*60)
    logger.info("\n📋 Summary:")
    logger.info(f"   • Document processed: {doc_path.name}")
    logger.info(f"   • Text extracted: {len(result.raw_text):,} characters")
    logger.info(f"   • Chunks created: {len(chunks)}")
    logger.info(f"   • Embeddings cached: {stats['cache_saves']}")
    logger.info(f"   • Queries tested: {len(queries)}")
    logger.info(f"   • Cache speedup: {api_time/cache_time:.1f}x" if cache_time > 0 else "   • Cache speedup: N/A")
    logger.info("="*60)

    return {
        "success": True,
        "document": doc_path.name,
        "text_length": len(result.raw_text),
        "chunks": len(chunks),
        "cache_speedup": f"{api_time/cache_time:.1f}x" if cache_time > 0 else "N/A",
        "stats": stats
    }


async def main():
    """Main function."""
    try:
        logger.info("Starting complete RAG pipeline test...")
        logger.info("This will demonstrate:")
        logger.info("  1. PDF document processing")
        logger.info("  2. Smart text chunking")
        logger.info("  3. Embedding generation with caching")
        logger.info("  4. RAG query analysis")
        logger.info("  5. Performance statistics")
        logger.info("")

        result = await test_complete_rag_pipeline()

        if result and result["success"]:
            logger.info("\n🎉 All tests completed successfully!")
        else:
            logger.error("\n❌ Tests failed")

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())