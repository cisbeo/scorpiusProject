#!/usr/bin/env python3
"""
Test Script: Multi-Document Analysis for VSGP-AO Tender
========================================================

This script tests the complete pipeline for ingesting and analyzing
a multi-document tender (RC, CCAP, CCTP) using the Scorpius API.

Usage:
    python test_multi_document_analysis.py

Requirements:
    - API running on http://localhost:8000
    - Test documents in Examples/VSGP-AO/
    - PostgreSQL database operational
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
import logging
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_analysis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"
DOCUMENTS_DIR = Path("Examples/VSGP-AO")

# Test data
TEST_USER = {
    "email": "test-vsgp@example.com",
    "password": "TestVSGP2024!",
    "full_name": "Test VSGP User"
}

# Generate unique reference for each test run
test_id = str(uuid.uuid4())[:8]
TEST_TENDER = {
    "reference": f"VSGP-AO-2024-TEST-{test_id}",
    "title": "VSGP-AO-2024",
    "organization": "Test Organization",
    "description": "Test d'analyse multi-documents pour validation du pipeline complet",
    "deadline_date": (datetime.now() + timedelta(days=30)).isoformat()
}

DOCUMENT_MAPPING = {
    "RC.pdf": {"type": "rc", "description": "Règlement de Consultation"},
    "CCAP.pdf": {"type": "ccap", "description": "Clauses Administratives Particulières"},
    "CCTP.pdf": {"type": "cctp", "description": "Clauses Techniques Particulières"}
}

class TestResult:
    """Track test results and metrics."""

    def __init__(self):
        self.results = {}
        self.start_time = time.time()
        self.metrics = {
            "total_execution_time": 0,
            "documents_processed": 0,
            "processing_times": {},
            "api_response_times": {},
            "errors": [],
            "warnings": []
        }

    def add_result(self, test_name: str, success: bool, data: Any = None, duration: float = 0):
        """Add a test result."""
        self.results[test_name] = {
            "success": success,
            "data": data,
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        }
        logger.info(f"✅ {test_name}: {'PASSED' if success else 'FAILED'} ({duration:.2f}s)")

    def add_error(self, error: str):
        """Add an error."""
        self.metrics["errors"].append(error)
        logger.error(f"❌ Error: {error}")

    def add_warning(self, warning: str):
        """Add a warning."""
        self.metrics["warnings"].append(warning)
        logger.warning(f"⚠️ Warning: {warning}")

    def finalize(self):
        """Finalize test results."""
        self.metrics["total_execution_time"] = time.time() - self.start_time
        return {
            "summary": {
                "total_tests": len(self.results),
                "passed": sum(1 for r in self.results.values() if r["success"]),
                "failed": sum(1 for r in self.results.values() if not r["success"]),
                "total_duration": self.metrics["total_execution_time"]
            },
            "results": self.results,
            "metrics": self.metrics
        }

class ScorpiusAPIClient:
    """API client for Scorpius testing."""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=60.0)
        self.token = None
        self.headers = {"Content-Type": "application/json"}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def set_auth_token(self, token: str):
        """Set authentication token."""
        self.token = token
        self.headers["Authorization"] = f"Bearer {token}"

    async def make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an API request with error handling."""
        url = f"{API_BASE}{endpoint}"
        start_time = time.time()

        try:
            if method.upper() == "GET":
                response = await self.client.get(url, headers=self.headers, **kwargs)
            elif method.upper() == "POST":
                response = await self.client.post(url, headers=self.headers, **kwargs)
            elif method.upper() == "PUT":
                response = await self.client.put(url, headers=self.headers, **kwargs)
            elif method.upper() == "DELETE":
                response = await self.client.delete(url, headers=self.headers, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            duration = time.time() - start_time

            if response.status_code >= 400:
                logger.error(f"API Error {response.status_code}: {response.text}")
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text,
                    "duration": duration
                }

            return {
                "success": True,
                "status_code": response.status_code,
                "data": response.json() if response.content else {},
                "duration": duration
            }

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Request failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "duration": duration
            }

async def test_api_health(client: ScorpiusAPIClient, results: TestResult):
    """Test API health and availability."""
    logger.info("🔍 Testing API health...")

    # Test health endpoint
    response = await client.make_request("GET", "/health")
    results.add_result(
        "API Health Check",
        response["success"],
        response.get("data"),
        response.get("duration", 0)
    )

    return response["success"]

async def test_authentication(client: ScorpiusAPIClient, results: TestResult):
    """Test user registration and authentication."""
    logger.info("🔐 Testing authentication...")

    # Try to register user (might fail if exists, that's ok)
    register_response = await client.make_request(
        "POST",
        "/auth/register",
        json=TEST_USER
    )

    # Login
    login_response = await client.make_request(
        "POST",
        "/auth/login",
        json={"email": TEST_USER["email"], "password": TEST_USER["password"]}
    )

    if login_response["success"]:
        token = login_response["data"]["tokens"]["access_token"]
        client.set_auth_token(token)
        results.add_result(
            "User Authentication",
            True,
            {"token_length": len(token)},
            login_response["duration"]
        )
        return True
    else:
        results.add_error(f"Authentication failed: {login_response.get('error')}")
        return False

async def test_tender_creation(client: ScorpiusAPIClient, results: TestResult):
    """Test tender creation."""
    logger.info("📋 Creating tender...")

    response = await client.make_request(
        "POST",
        "/tenders/",
        json=TEST_TENDER
    )

    if response["success"]:
        tender_id = response["data"]["id"]
        results.add_result(
            "Tender Creation",
            True,
            {"tender_id": tender_id},
            response["duration"]
        )
        return tender_id
    else:
        results.add_error(f"Tender creation failed: {response.get('error')}")
        return None

async def test_document_upload(client: ScorpiusAPIClient, results: TestResult, tender_id: str):
    """Test document upload and processing."""
    logger.info("📄 Uploading documents...")

    uploaded_docs = []

    for filename, doc_info in DOCUMENT_MAPPING.items():
        file_path = DOCUMENTS_DIR / filename

        if not file_path.exists():
            results.add_warning(f"Document not found: {file_path}")
            continue

        logger.info(f"Uploading {filename}...")

        # Upload document
        with open(file_path, "rb") as f:
            files = {"file": (filename, f, "application/pdf")}
            data = {
                "document_type": doc_info["type"],
                "tender_id": tender_id
            }

            # Remove Content-Type header for multipart upload
            headers_without_content_type = {k: v for k, v in client.headers.items() if k != "Content-Type"}

            start_time = time.time()
            try:
                response = await client.client.post(
                    f"{API_BASE}/documents",
                    headers=headers_without_content_type,
                    files=files,
                    data=data
                )
                duration = time.time() - start_time

                if response.status_code < 400:
                    doc_data = response.json()
                    uploaded_docs.append(doc_data)
                    results.add_result(
                        f"Document Upload - {filename}",
                        True,
                        {"document_id": doc_data["id"], "status": doc_data["status"]},
                        duration
                    )
                elif response.status_code == 400 and "already exists" in response.text:
                    # Document already exists, extract ID from error message
                    import re
                    match = re.search(r'ID: ([a-f0-9-]+)', response.text)
                    if match:
                        existing_id = match.group(1)
                        uploaded_docs.append({
                            "id": existing_id,
                            "original_filename": filename,
                            "document_type": doc_info["type"],
                            "status": "existing"
                        })
                        results.add_result(
                            f"Document Reuse - {filename}",
                            True,
                            {"document_id": existing_id, "status": "existing"},
                            duration
                        )
                    else:
                        results.add_error(f"Upload failed for {filename}: {response.text}")
                else:
                    results.add_error(f"Upload failed for {filename}: {response.text}")

            except Exception as e:
                results.add_error(f"Upload exception for {filename}: {str(e)}")

    return uploaded_docs

async def associate_documents_to_tender(client: ScorpiusAPIClient, results: TestResult, tender_id: str, uploaded_docs: list):
    """Associate uploaded documents with the tender."""
    logger.info("🔗 Associating documents to tender...")

    for doc in uploaded_docs:
        # Get the document type from the original mapping or use the uploaded one
        doc_type = doc.get("document_type", "other")
        if doc_type == "OTHER":
            doc_type = "other"

        response = await client.make_request(
            "POST",
            f"/tenders/{tender_id}/documents",
            json={
                "document_id": doc["id"],
                "document_type": doc_type.lower(),
                "is_mandatory": True
            }
        )

        if response["success"]:
            results.add_result(
                f"Document Association - {doc['original_filename']}",
                True,
                {"document_id": doc["id"]},
                response["duration"]
            )
        else:
            results.add_error(f"Failed to associate {doc['original_filename']}: {response.get('error')}")

    return True

async def wait_for_processing(client: ScorpiusAPIClient, results: TestResult, document_ids: list):
    """Wait for document processing to complete."""
    logger.info("⏳ Waiting for document processing...")

    max_wait = 300  # 5 minutes max
    check_interval = 5  # Check every 5 seconds
    start_time = time.time()

    while time.time() - start_time < max_wait:
        all_processed = True
        processing_status = {}

        for doc_id in document_ids:
            response = await client.make_request("GET", f"/documents/{doc_id}")
            if response["success"]:
                status = response["data"]["status"]
                processing_status[doc_id] = status
                if status not in ["processed", "failed"]:
                    all_processed = False
            else:
                all_processed = False

        if all_processed:
            results.add_result(
                "Document Processing Completion",
                True,
                processing_status,
                time.time() - start_time
            )
            return True

        logger.info(f"Processing status: {processing_status}")
        await asyncio.sleep(check_interval)

    results.add_error("Document processing timeout")
    return False

async def test_tender_analysis(client: ScorpiusAPIClient, results: TestResult, tender_id: str):
    """Test tender analysis."""
    logger.info("🧠 Running tender analysis...")

    response = await client.make_request(
        "POST",
        f"/tenders/{tender_id}/analyze"
    )

    results.add_result(
        "Tender Analysis",
        response["success"],
        response.get("data"),
        response.get("duration", 0)
    )

    return response["success"]

async def test_completeness_check(client: ScorpiusAPIClient, results: TestResult, tender_id: str):
    """Test tender completeness check."""
    logger.info("✅ Checking tender completeness...")

    response = await client.make_request("GET", f"/tenders/{tender_id}/completeness")

    if response["success"]:
        completeness = response["data"]
        results.add_result(
            "Tender Completeness Check",
            True,
            completeness,
            response["duration"]
        )
        return completeness
    else:
        results.add_error(f"Completeness check failed: {response.get('error')}")
        return None

async def generate_test_report(results: TestResult):
    """Generate comprehensive test report."""
    logger.info("📊 Generating test report...")

    final_results = results.finalize()

    # Write detailed report to file
    report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(final_results, f, indent=2)

    # Print summary
    summary = final_results["summary"]
    logger.info("=" * 60)
    logger.info("📈 TEST EXECUTION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total Tests: {summary['total_tests']}")
    logger.info(f"Passed: {summary['passed']}")
    logger.info(f"Failed: {summary['failed']}")
    logger.info(f"Success Rate: {(summary['passed']/summary['total_tests']*100):.1f}%")
    logger.info(f"Total Duration: {summary['total_duration']:.2f}s")
    logger.info(f"Report saved: {report_file}")

    if final_results["metrics"]["errors"]:
        logger.info("\n❌ ERRORS:")
        for error in final_results["metrics"]["errors"]:
            logger.info(f"  - {error}")

    if final_results["metrics"]["warnings"]:
        logger.info("\n⚠️ WARNINGS:")
        for warning in final_results["metrics"]["warnings"]:
            logger.info(f"  - {warning}")

async def clean_database():
    """Clean all test data from database before running tests."""
    logger.info("🧹 Cleaning database...")

    import os
    from sqlalchemy import create_engine, text

    # Get database URL and create synchronous connection
    database_url = os.environ.get('DATABASE_URL', 'postgresql+asyncpg://scorpius:scorpius@db:5432/scorpius_mvp')
    sync_url = database_url.replace('+asyncpg', '')

    engine = create_engine(sync_url)

    try:
        with engine.connect() as conn:
            # Delete data in correct order to avoid foreign key violations
            conn.execute(text("DELETE FROM processing_events"))
            conn.execute(text("DELETE FROM extracted_requirements"))
            conn.execute(text("DELETE FROM compliance_checks"))
            conn.execute(text("DELETE FROM bid_responses"))
            conn.execute(text("DELETE FROM capability_matches"))
            conn.execute(text("DELETE FROM procurement_documents"))
            conn.execute(text("DELETE FROM procurement_tenders"))
            conn.execute(text("DELETE FROM company_profiles"))
            conn.execute(text("DELETE FROM audit_logs"))
            conn.execute(text("DELETE FROM users"))
            conn.commit()
            logger.info("✅ Database cleaned successfully")
    except Exception as e:
        logger.error(f"❌ Failed to clean database: {str(e)}")
        # Continue anyway as the test might still work
    finally:
        engine.dispose()

async def main():
    """Main test execution."""
    logger.info("🚀 Starting Multi-Document Analysis Test")
    logger.info("=" * 60)

    # Clean database before running tests
    await clean_database()

    results = TestResult()

    async with ScorpiusAPIClient() as client:
        # Phase 1: Health Check
        if not await test_api_health(client, results):
            logger.error("API health check failed. Aborting tests.")
            return

        # Phase 2: Authentication
        if not await test_authentication(client, results):
            logger.error("Authentication failed. Aborting tests.")
            return

        # Phase 3: Tender Creation
        tender_id = await test_tender_creation(client, results)
        if not tender_id:
            logger.error("Tender creation failed. Aborting tests.")
            return

        # Phase 4: Document Upload
        uploaded_docs = await test_document_upload(client, results, tender_id)
        if not uploaded_docs:
            logger.error("No documents uploaded successfully. Aborting tests.")
            return

        document_ids = [doc["id"] for doc in uploaded_docs]

        # Phase 5: Associate documents to tender
        await associate_documents_to_tender(client, results, tender_id, uploaded_docs)

        # Phase 6: Wait for Processing
        if not await wait_for_processing(client, results, document_ids):
            logger.warning("Document processing incomplete, continuing with tests...")

        # Phase 7: Completeness Check
        await test_completeness_check(client, results, tender_id)

        # Phase 8: Tender Analysis
        await test_tender_analysis(client, results, tender_id)

    # Generate final report
    await generate_test_report(results)
    logger.info("🎉 Test execution completed!")

if __name__ == "__main__":
    asyncio.run(main())