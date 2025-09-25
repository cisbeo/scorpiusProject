#!/usr/bin/env python3
"""
Test script for Phase 3 implementation: API Endpoints.
This script tests the new tender endpoints.
"""

import asyncio
import sys
import json
import httpx
from pathlib import Path
from datetime import datetime, timedelta
from uuid import uuid4
from typing import Optional

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))


class TenderAPITester:
    """Test client for tender API endpoints."""

    def __init__(self, base_url: str = "http://localhost:8000/api/v1"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.auth_token = None
        self.test_tender_id = None
        self.test_document_ids = []

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def authenticate(self, email: str = "test@scorpius.fr", password: str = "Xw9!Kp2@Qm7"):
        """Authenticate and get JWT token."""
        response = await self.client.post(
            f"{self.base_url}/auth/login",
            json={"email": email, "password": password}
        )
        if response.status_code == 200:
            data = response.json()
            # Handle both old and new response formats
            if "tokens" in data:
                self.auth_token = data["tokens"]["access_token"]
            else:
                self.auth_token = data.get("access_token")
            self.client.headers["Authorization"] = f"Bearer {self.auth_token}"
            return True
        else:
            print(f"❌ Authentication failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    async def test_create_tender(self) -> bool:
        """Test tender creation endpoint."""
        test_reference = f"API-TEST-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        deadline = (datetime.utcnow() + timedelta(days=30)).isoformat()

        tender_data = {
            "reference": test_reference,
            "title": "Test Tender via API - Phase 3",
            "organization": "Test API Organization",
            "description": "This is a test tender created via the API endpoints",
            "deadline_date": deadline,
            "publication_date": datetime.utcnow().isoformat(),
            "budget_estimate": 750000.00
        }

        response = await self.client.post(
            f"{self.base_url}/tenders/",
            json=tender_data
        )

        if response.status_code == 201:
            tender = response.json()
            self.test_tender_id = tender["id"]
            print(f"✅ Tender created: {tender['reference']} (ID: {tender['id']})")
            return True
        else:
            print(f"❌ Failed to create tender: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    async def test_get_tender(self) -> bool:
        """Test getting a tender by ID."""
        if not self.test_tender_id:
            print("⚠️ No test tender ID available, skipping get test")
            return False

        response = await self.client.get(
            f"{self.base_url}/tenders/{self.test_tender_id}?include_documents=true"
        )

        if response.status_code == 200:
            tender = response.json()
            print(f"✅ Retrieved tender: {tender['title']}")
            print(f"   Status: {tender['status']}")
            print(f"   Documents: {tender.get('document_count', 0)}")
            return True
        else:
            print(f"❌ Failed to get tender: {response.status_code}")
            return False

    async def test_update_tender(self) -> bool:
        """Test updating a tender."""
        if not self.test_tender_id:
            print("⚠️ No test tender ID available, skipping update test")
            return False

        update_data = {
            "title": "Updated Test Tender - Phase 3 Complete",
            "description": "This tender has been updated via API"
        }

        response = await self.client.put(
            f"{self.base_url}/tenders/{self.test_tender_id}",
            json=update_data
        )

        if response.status_code == 200:
            tender = response.json()
            print(f"✅ Tender updated: {tender['title']}")
            return True
        else:
            print(f"❌ Failed to update tender: {response.status_code}")
            return False

    async def test_list_tenders(self) -> bool:
        """Test listing tenders with pagination."""
        response = await self.client.get(
            f"{self.base_url}/tenders/?page=1&page_size=10"
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Listed tenders: {len(data['items'])} items")
            print(f"   Total: {data['total']} tenders")
            print(f"   Pages: {data['total_pages']}")
            return True
        else:
            print(f"❌ Failed to list tenders: {response.status_code}")
            return False

    async def test_my_tenders(self) -> bool:
        """Test getting user's own tenders."""
        response = await self.client.get(
            f"{self.base_url}/tenders/my/tenders"
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ My tenders: {len(data['items'])} items")
            return True
        else:
            print(f"❌ Failed to get my tenders: {response.status_code}")
            return False

    async def test_search_tenders(self) -> bool:
        """Test searching tenders."""
        search_data = {
            "query": "Test",
            "status": None,
            "organization": None
        }

        response = await self.client.post(
            f"{self.base_url}/tenders/search?page=1&page_size=10",
            json=search_data
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Search results: {len(data['items'])} matches")
            return True
        else:
            print(f"❌ Failed to search tenders: {response.status_code}")
            return False

    async def test_expiring_tenders(self) -> bool:
        """Test getting expiring tenders."""
        response = await self.client.get(
            f"{self.base_url}/tenders/expiring?days_ahead=30"
        )

        if response.status_code == 200:
            tenders = response.json()
            print(f"✅ Expiring tenders: {len(tenders)} found")
            return True
        else:
            print(f"❌ Failed to get expiring tenders: {response.status_code}")
            return False

    async def test_update_status(self) -> bool:
        """Test updating tender status."""
        if not self.test_tender_id:
            print("⚠️ No test tender ID available, skipping status update test")
            return False

        status_data = {
            "status": "analyzing",
            "reason": "Starting analysis process"
        }

        response = await self.client.put(
            f"{self.base_url}/tenders/{self.test_tender_id}/status",
            json=status_data
        )

        if response.status_code == 200:
            tender = response.json()
            print(f"✅ Status updated to: {tender['status']}")
            return True
        else:
            print(f"❌ Failed to update status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    async def test_completeness(self) -> bool:
        """Test getting tender completeness."""
        if not self.test_tender_id:
            print("⚠️ No test tender ID available, skipping completeness test")
            return False

        response = await self.client.get(
            f"{self.base_url}/tenders/{self.test_tender_id}/completeness"
        )

        if response.status_code == 200:
            completeness = response.json()
            print(f"✅ Completeness: {completeness['completeness_score']}%")
            print(f"   Documents: {completeness['total_documents']}")
            print(f"   Can analyze: {completeness['can_analyze']}")
            return True
        else:
            print(f"❌ Failed to get completeness: {response.status_code}")
            return False

    async def test_ready_for_analysis(self) -> bool:
        """Test getting tenders ready for analysis."""
        response = await self.client.get(
            f"{self.base_url}/tenders/ready-for-analysis?page=1&page_size=10"
        )

        if response.status_code == 200:
            tenders = response.json()
            print(f"✅ Ready for analysis: {len(tenders)} tenders")
            return True
        else:
            print(f"❌ Failed to get ready tenders: {response.status_code}")
            return False

    async def test_delete_tender(self) -> bool:
        """Test deleting a tender."""
        if not self.test_tender_id:
            print("⚠️ No test tender ID available, skipping delete test")
            return False

        response = await self.client.delete(
            f"{self.base_url}/tenders/{self.test_tender_id}"
        )

        if response.status_code == 204:
            print(f"✅ Tender deleted successfully")
            self.test_tender_id = None
            return True
        else:
            print(f"❌ Failed to delete tender: {response.status_code}")
            return False


async def test_phase3_endpoints():
    """Main test function for Phase 3 endpoints."""

    print("🧪 Testing Phase 3 Implementation: API Endpoints")
    print("=" * 60)

    tester = TenderAPITester()
    results = {}

    try:
        # Authenticate first
        print("\n1. Authentication")
        print("-" * 30)
        auth_success = await tester.authenticate()
        if not auth_success:
            print("❌ Authentication failed, cannot continue tests")
            return False

        print("✅ Authenticated successfully")

        # Run tests
        print("\n2. CRUD Operations")
        print("-" * 30)

        tests = [
            ("Create Tender", tester.test_create_tender),
            ("Get Tender", tester.test_get_tender),
            ("Update Tender", tester.test_update_tender),
            ("List Tenders", tester.test_list_tenders),
            ("My Tenders", tester.test_my_tenders),
        ]

        for test_name, test_func in tests:
            print(f"\n📋 Testing: {test_name}")
            results[test_name] = await test_func()
            await asyncio.sleep(0.1)  # Small delay between tests

        print("\n3. Search and Filter")
        print("-" * 30)

        search_tests = [
            ("Search Tenders", tester.test_search_tenders),
            ("Expiring Tenders", tester.test_expiring_tenders),
        ]

        for test_name, test_func in search_tests:
            print(f"\n📋 Testing: {test_name}")
            results[test_name] = await test_func()
            await asyncio.sleep(0.1)

        print("\n4. Status and Analysis")
        print("-" * 30)

        status_tests = [
            ("Update Status", tester.test_update_status),
            ("Completeness", tester.test_completeness),
            ("Ready for Analysis", tester.test_ready_for_analysis),
        ]

        for test_name, test_func in status_tests:
            print(f"\n📋 Testing: {test_name}")
            results[test_name] = await test_func()
            await asyncio.sleep(0.1)

        print("\n5. Cleanup")
        print("-" * 30)
        results["Delete Tender"] = await tester.test_delete_tender()

        # Summary
        print("\n" + "=" * 60)
        print("🎉 Phase 3 API Endpoints Test Summary")
        print("=" * 60)

        passed = sum(1 for v in results.values() if v)
        total = len(results)

        for test_name, success in results.items():
            icon = "✅" if success else "❌"
            print(f"{icon} {test_name}: {'PASSED' if success else 'FAILED'}")

        print(f"\n📊 Results: {passed}/{total} tests passed")

        if passed == total:
            print("\n🚀 All Phase 3 API endpoints are working correctly!")
            print("The tender management API is ready for production use.")
            return True
        else:
            print(f"\n⚠️ {total - passed} tests failed. Please check the implementation.")
            return False

    except Exception as e:
        print(f"\n❌ Test suite failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await tester.close()


async def main():
    """Main test runner."""
    # First check if the API is running
    print("📡 Checking if API server is running...")
    print("If not, start it with: uvicorn src.api.v1.app:app --reload --port 8000")
    print()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/api/v1/health")
            if response.status_code == 200:
                print("✅ API server is running")
                print()
            else:
                print("⚠️ API server returned unexpected status")
    except Exception as e:
        print("❌ API server is not accessible. Please start it first with:")
        print("   uvicorn src.api.v1.app:app --reload --port 8000")
        print(f"   Error: {str(e)}")
        sys.exit(1)

    success = await test_phase3_endpoints()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())