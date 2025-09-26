#!/usr/bin/env python3
"""Test complet du pipeline RAG via les APIs avec upload de document."""

import asyncio
import aiohttp
import logging
import json
import time
from pathlib import Path
import base64

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API configuration
API_BASE_URL = "http://localhost:8000/api/v1"
TEST_USER = {
    "email": "test-rag-demo@scorpius.fr",
    "password": "DemoPass2024!",
    "full_name": "Test RAG Demo User",
    "company_name": "Test RAG Demo"
}

async def register_or_login():
    """Register a test user or login if already exists."""
    async with aiohttp.ClientSession() as session:
        # Try to register
        logger.info("Attempting to register test user...")
        try:
            async with session.post(
                f"{API_BASE_URL}/auth/register",
                json=TEST_USER
            ) as resp:
                if resp.status == 201:
                    data = await resp.json()
                    logger.info(f"✅ User registered successfully")
                    return data["tokens"]["access_token"]
                elif resp.status == 400:
                    logger.info("User already exists, attempting login...")
        except Exception as e:
            logger.warning(f"Registration failed: {e}")

        # Try to login
        async with session.post(
            f"{API_BASE_URL}/auth/login",
            json={
                "email": TEST_USER["email"],
                "password": TEST_USER["password"]
            }
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                logger.info(f"✅ Logged in successfully")
                return data["tokens"]["access_token"]
            else:
                error = await resp.text()
                raise Exception(f"Login failed: {error}")


async def upload_document(token: str, file_path: Path):
    """Upload a document via API."""
    async with aiohttp.ClientSession() as session:
        # Read file content first
        with open(file_path, 'rb') as f:
            file_content = f.read()

        # Prepare the file upload with content
        form_data = aiohttp.FormData()
        form_data.add_field(
            'file',
            file_content,
            filename=file_path.name,
            content_type='application/pdf'
        )

        # Add optional processing options as JSON string
        processing_options = json.dumps({
            "document_type": "CCTP",
            "extract_metadata": True
        })
        form_data.add_field('processing_options', processing_options)

        headers = {"Authorization": f"Bearer {token}"}

        logger.info(f"Uploading {file_path.name}...")
        async with session.post(
            f"{API_BASE_URL}/documents",  # Correct endpoint
            data=form_data,
            headers=headers
        ) as resp:
            if resp.status in [200, 201]:
                data = await resp.json()
                logger.info(f"✅ Document uploaded successfully")
                logger.info(f"   Document ID: {data.get('id', data.get('document_id', 'N/A'))}")
                logger.info(f"   Status: {data.get('status', 'N/A')}")
                logger.info(f"   Processing time: {data.get('processing_time_ms', 'N/A')}ms")
                return data
            elif resp.status == 400:
                error = await resp.text()
                # Check if document already exists
                if "already exists" in error:
                    # Extract document ID from error message
                    import re
                    match = re.search(r'ID: ([a-f0-9-]+)', error)
                    if match:
                        doc_id = match.group(1)
                        logger.info(f"📋 Document already exists with ID: {doc_id}")
                        return {"id": doc_id, "status": "existing"}
                raise Exception(f"Upload failed ({resp.status}): {error}")
            else:
                error = await resp.text()
                raise Exception(f"Upload failed ({resp.status}): {error}")


async def analyze_document_simple(token: str, document_id: str):
    """Get basic analysis of the uploaded document."""
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {token}"}

        # Try to get document details/analysis
        logger.info(f"\n📝 Getting document analysis for ID: {document_id}")

        try:
            # First, check if document is processed
            async with session.get(
                f"{API_BASE_URL}/documents/{document_id}",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"✅ Document retrieved successfully")

                    # Display document info
                    logger.info(f"\n📄 Document Information:")
                    logger.info(f"   - Filename: {data.get('filename', 'N/A')}")
                    logger.info(f"   - Status: {data.get('status', 'N/A')}")
                    logger.info(f"   - Created: {data.get('created_at', 'N/A')}")

                    # Check for extracted content
                    if "extracted_text" in data:
                        text_preview = data["extracted_text"][:500] if data["extracted_text"] else "No text extracted"
                        logger.info(f"\n📝 Extracted Text Preview:")
                        logger.info(f"{text_preview}...")

                    # Check for metadata
                    if "metadata" in data and data["metadata"]:
                        logger.info(f"\n📊 Document Metadata:")
                        for key, value in data["metadata"].items():
                            if key not in ["raw_text", "extracted_text"]:
                                logger.info(f"   - {key}: {value}")

                    return data
                else:
                    error = await resp.text()
                    logger.error(f"Failed to get document: {error}")
                    return None

        except Exception as e:
            logger.error(f"Error getting document analysis: {e}")
            return None


async def get_document_details(token: str, document_id: str):
    """Get details about the processed document."""
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {token}"}

        async with session.get(
            f"{API_BASE_URL}/documents/{document_id}",
            headers=headers
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                logger.info("\n📄 Document Details:")
                logger.info(f"   - Title: {data.get('filename', 'N/A')}")
                logger.info(f"   - Type: {data.get('document_type', 'N/A')}")
                logger.info(f"   - Status: {data.get('processing_status', 'N/A')}")
                logger.info(f"   - Chunks created: {data.get('chunk_count', 'N/A')}")
                logger.info(f"   - Text extracted: {data.get('text_length', 'N/A')} chars")
                logger.info(f"   - Created at: {data.get('created_at', 'N/A')}")
                return data
            else:
                logger.error(f"Failed to get document details: {resp.status}")
                return None


async def test_full_rag_pipeline():
    """Test the complete RAG pipeline via API."""
    logger.info("=== Testing Complete RAG Pipeline via API ===\n")

    # Step 1: Authentication
    logger.info("--- Step 1: Authentication ---")
    token = await register_or_login()

    # Step 2: Upload CCTP document
    logger.info("\n--- Step 2: Document Upload ---")
    doc_path = Path("/Users/cedric/Dev/projects/scorpiusProject/Examples/VSGP-AO/CCTP.pdf")

    if not doc_path.exists():
        logger.error(f"Document not found: {doc_path}")
        return

    upload_result = await upload_document(token, doc_path)
    document_id = upload_result.get("id") or upload_result.get("document_id")

    if not document_id:
        logger.error(f"No document ID in response: {upload_result}")
        return

    # Wait for processing to complete
    logger.info("Waiting for document processing...")
    await asyncio.sleep(5)

    # Step 3: Get document details
    logger.info("\n--- Step 3: Document Information ---")
    doc_details = await get_document_details(token, document_id)

    # Step 4: Get document analysis
    logger.info("\n--- Step 4: Document Analysis ---")
    analysis = await analyze_document_simple(token, document_id)

    # Step 5: Summary
    logger.info("\n--- Step 5: Analysis Summary ---")
    logger.info(f"✅ Document processed: {doc_path.name}")
    logger.info(f"📊 Document ID: {document_id}")

    if doc_details:
        logger.info(f"📄 Status: {doc_details.get('processing_status', 'N/A')}")
        if "text_length" in doc_details:
            logger.info(f"📝 Text extracted: {doc_details.get('text_length', 0)} characters")
        if "chunk_count" in doc_details:
            logger.info(f"📦 Chunks created: {doc_details.get('chunk_count', 0)}")

    logger.info("\n✅ Complete RAG Pipeline Test Finished Successfully!")

    return {
        "success": True,
        "document_id": document_id,
        "document_details": doc_details,
        "analysis": analysis
    }


async def main():
    """Main test function."""
    try:
        result = await test_full_rag_pipeline()

        if result and result["success"]:
            logger.info("\n" + "="*60)
            logger.info("🎉 RAG API TEST COMPLETED SUCCESSFULLY!")
            logger.info(f"📄 Document ID: {result['document_id']}")

            if result.get('document_details'):
                details = result['document_details']
                logger.info(f"📊 Document Status: {details.get('processing_status', 'N/A')}")
                if 'text_length' in details:
                    logger.info(f"📝 Text Length: {details['text_length']} chars")
                if 'chunk_count' in details:
                    logger.info(f"📦 Chunks: {details['chunk_count']}")

            logger.info("="*60)

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)


if __name__ == "__main__":
    # Make sure the API is running
    logger.info("Starting RAG API test...")
    logger.info("Make sure the API is running on http://localhost:8000")
    logger.info("-"*60)

    asyncio.run(main())