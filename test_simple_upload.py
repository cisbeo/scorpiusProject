#!/usr/bin/env python3
"""Simple test for document upload and analysis via API."""

import asyncio
import aiohttp
import logging
import json
import uuid
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API configuration
API_BASE_URL = "http://localhost:8000/api/v1"

# Generate unique test user for this run
unique_id = str(uuid.uuid4())[:8]
TEST_USER = {
    "email": f"test-{unique_id}@scorpius.fr",
    "password": "TestPass2024!",
    "full_name": f"Test User {unique_id}",
    "company_name": f"Test Company {unique_id}"
}


async def register_and_login():
    """Register a new test user and get token."""
    async with aiohttp.ClientSession() as session:
        logger.info(f"Registering new user: {TEST_USER['email']}")

        # Register
        async with session.post(
            f"{API_BASE_URL}/auth/register",
            json=TEST_USER
        ) as resp:
            if resp.status == 201:
                data = await resp.json()
                logger.info(f"✅ User registered successfully")
                return data["tokens"]["access_token"]
            else:
                error = await resp.text()
                raise Exception(f"Registration failed: {error}")


async def upload_document(token: str, file_path: Path):
    """Upload a document via API."""
    async with aiohttp.ClientSession() as session:
        # Read file content
        with open(file_path, 'rb') as f:
            file_content = f.read()

        # Prepare form data
        form_data = aiohttp.FormData()
        form_data.add_field(
            'file',
            file_content,
            filename=file_path.name,
            content_type='application/pdf'
        )

        headers = {"Authorization": f"Bearer {token}"}

        logger.info(f"Uploading {file_path.name}...")
        async with session.post(
            f"{API_BASE_URL}/documents",
            data=form_data,
            headers=headers
        ) as resp:
            if resp.status in [200, 201]:
                data = await resp.json()
                logger.info(f"✅ Document uploaded successfully")
                return data
            else:
                error = await resp.text()
                logger.error(f"Upload failed ({resp.status}): {error}")
                return None


async def get_document_info(token: str, document_id: str):
    """Get document information."""
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {token}"}

        async with session.get(
            f"{API_BASE_URL}/documents/{document_id}",
            headers=headers
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data
            else:
                return None


async def test_simple_upload():
    """Test simple document upload and retrieval."""
    logger.info("=== Simple Document Upload Test ===\n")

    # Step 1: Register and login
    logger.info("Step 1: Authentication")
    try:
        token = await register_and_login()
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        return False

    # Step 2: Upload document
    logger.info("\nStep 2: Document Upload")
    doc_path = Path("/Users/cedric/Dev/projects/scorpiusProject/Examples/VSGP-AO/CCTP.pdf")

    if not doc_path.exists():
        logger.error(f"Document not found: {doc_path}")
        return False

    upload_result = await upload_document(token, doc_path)

    if not upload_result:
        logger.error("Upload failed")
        return False

    # Extract document ID
    document_id = upload_result.get("id") or upload_result.get("document_id")
    if not document_id:
        logger.error(f"No document ID in response: {upload_result}")
        return False

    logger.info(f"Document ID: {document_id}")
    logger.info(f"Status: {upload_result.get('status', 'N/A')}")

    # Wait for processing
    logger.info("\nWaiting 3 seconds for processing...")
    await asyncio.sleep(3)

    # Step 3: Get document information
    logger.info("\nStep 3: Retrieve Document Information")
    doc_info = await get_document_info(token, document_id)

    if doc_info:
        logger.info("✅ Document retrieved successfully")
        logger.info(f"Filename: {doc_info.get('filename', 'N/A')}")
        logger.info(f"Status: {doc_info.get('status', 'N/A')}")
        logger.info(f"File size: {doc_info.get('file_size', 'N/A')} bytes")

        # Check for extracted content
        if "extraction_metadata" in doc_info:
            metadata = doc_info["extraction_metadata"]
            if isinstance(metadata, dict):
                logger.info("\nExtraction metadata:")
                for key, value in metadata.items():
                    if key not in ["raw_text", "text"]:
                        logger.info(f"  {key}: {value}")
    else:
        logger.error("Failed to retrieve document")
        return False

    logger.info("\n✅ Test completed successfully!")
    return True


async def main():
    """Main function."""
    success = await test_simple_upload()

    if success:
        logger.info("\n" + "="*50)
        logger.info("🎉 SIMPLE UPLOAD TEST PASSED!")
        logger.info("="*50)
    else:
        logger.error("\n" + "="*50)
        logger.error("❌ SIMPLE UPLOAD TEST FAILED")
        logger.error("="*50)


if __name__ == "__main__":
    logger.info("Starting simple upload test...")
    logger.info("Make sure the API is running on http://localhost:8000")
    logger.info("-"*50)

    asyncio.run(main())