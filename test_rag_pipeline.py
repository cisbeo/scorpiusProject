#!/usr/bin/env python
"""Test script for RAG pipeline end-to-end validation."""

import asyncio
import json
import aiohttp
from pathlib import Path
import tempfile

BASE_URL = "http://localhost:8000/api/v1"

# Sample PDF content as base64 (simple test PDF with text)
SAMPLE_PDF_CONTENT = """
CAHIER DES CLAUSES TECHNIQUES PARTICULIÈRES (CCTP)

ARTICLE 1 - OBJET DU MARCHÉ
Le présent marché a pour objet la fourniture et l'installation d'un système informatique complet
pour la modernisation des services administratifs.

ARTICLE 2 - SPÉCIFICATIONS TECHNIQUES
2.1 Matériel requis:
- 50 ordinateurs de bureau avec processeurs Intel Core i5 minimum
- 10 serveurs rack avec redondance
- Infrastructure réseau complète

2.2 Logiciels requis:
- Système d'exploitation Windows 11 Professional
- Suite bureautique Microsoft Office 2021
- Logiciel de gestion documentaire

ARTICLE 3 - DÉLAIS D'EXÉCUTION
La livraison et l'installation complète devront être réalisées dans un délai de 3 mois
à compter de la notification du marché.

ARTICLE 4 - GARANTIE ET MAINTENANCE
Une garantie de 3 ans est exigée sur l'ensemble du matériel fourni.
Un contrat de maintenance préventive devra être proposé.
"""


async def test_rag_pipeline():
    """Test the complete RAG pipeline."""

    async with aiohttp.ClientSession() as session:
        print("🚀 Starting RAG Pipeline Test")
        print("=" * 50)

        # Step 1: Check RAG stats before
        print("\n📊 Step 1: Checking initial RAG statistics...")
        async with session.get(f"{BASE_URL}/rag/stats") as resp:
            stats_before = await resp.json()
            print(f"  Documents: {stats_before['documents']['total_documents']}")
            print(f"  Embeddings: {stats_before['vector_store']['total_embeddings']}")
            print(f"  Coverage: {stats_before['documents']['indexing_coverage_percentage']}%")

        # Step 2: Create a test PDF file
        print("\n📄 Step 2: Creating test document...")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(SAMPLE_PDF_CONTENT)
            test_file_path = f.name

        # Step 3: Upload document for indexing
        print("\n📤 Step 3: Uploading document for processing and indexing...")
        try:
            with open(test_file_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('file', f, filename='test_cctp.txt', content_type='text/plain')
                data.add_field('processing_strategy', 'fast')
                data.add_field('processor', 'pypdf2')

                async with session.post(f"{BASE_URL}/upload-async", data=data) as resp:
                    if resp.status == 200:
                        upload_result = await resp.json()
                        document_id = upload_result['id']
                        print(f"  Document uploaded: {document_id}")
                        print(f"  Status: {upload_result['status']}")
                    else:
                        error = await resp.text()
                        print(f"  ❌ Upload failed: {error}")
                        return
        finally:
            Path(test_file_path).unlink(missing_ok=True)

        # Step 4: Wait for processing to complete
        print("\n⏳ Step 4: Waiting for document processing...")
        max_attempts = 30
        for i in range(max_attempts):
            await asyncio.sleep(2)
            async with session.get(f"{BASE_URL}/documents/{document_id}/status") as resp:
                status = await resp.json()
                current_status = status['status']
                print(f"  Attempt {i+1}/{max_attempts}: {current_status}")

                if current_status == 'processed':
                    print("  ✅ Document processed successfully!")
                    if 'processing_duration_ms' in status:
                        print(f"  Processing time: {status['processing_duration_ms']}ms")
                    break
                elif current_status == 'failed':
                    print(f"  ❌ Processing failed: {status.get('error_message', 'Unknown error')}")
                    return
        else:
            print("  ⚠️ Processing timeout - document may still be processing")

        # Step 5: Check RAG stats after indexing
        print("\n📊 Step 5: Checking RAG statistics after indexing...")
        async with session.get(f"{BASE_URL}/rag/stats") as resp:
            stats_after = await resp.json()
            print(f"  Documents: {stats_after['documents']['total_documents']}")
            print(f"  Indexed: {stats_after['documents']['indexed_documents']}")
            print(f"  Embeddings: {stats_after['vector_store']['total_embeddings']}")
            print(f"  Coverage: {stats_after['documents']['indexing_coverage_percentage']}%")

        # Step 6: Test RAG queries
        print("\n🔍 Step 6: Testing RAG queries...")

        test_queries = [
            "Quel est l'objet du marché?",
            "Combien d'ordinateurs sont requis?",
            "Quelle est la durée de garantie exigée?",
            "Quel est le délai d'exécution?",
        ]

        for query in test_queries:
            print(f"\n  Query: {query}")

            payload = {
                "query": query,
                "top_k": 3,
                "include_sources": True
            }

            async with session.post(f"{BASE_URL}/rag/query", json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print(f"  Answer: {result['answer'][:200]}...")
                    print(f"  Confidence: {result['confidence']:.2f}")
                    print(f"  Sources found: {len(result.get('sources', []))}")
                else:
                    error = await resp.text()
                    print(f"  ❌ Query failed: {error}")

        # Step 7: Test semantic search
        print("\n🔎 Step 7: Testing semantic search...")
        search_payload = {
            "query": "système informatique modernisation",
            "top_k": 5,
            "similarity_threshold": 0.5
        }

        async with session.post(f"{BASE_URL}/rag/search", json=search_payload) as resp:
            if resp.status == 200:
                search_results = await resp.json()
                print(f"  Found {search_results['total_results']} matching chunks")
                print(f"  Search type: {search_results['search_type']}")

                if search_results['results']:
                    best_match = search_results['results'][0]
                    print(f"  Best match score: {best_match['score']:.3f}")
                    print(f"  Text preview: {best_match['text'][:100]}...")
            else:
                error = await resp.text()
                print(f"  ❌ Search failed: {error}")

        print("\n✨ RAG Pipeline test completed!")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_rag_pipeline())