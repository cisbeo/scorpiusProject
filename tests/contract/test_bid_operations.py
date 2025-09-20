"""Contract tests for bid response operations (GET, UPDATE, DELETE)."""

import pytest
from httpx import AsyncClient
import uuid

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_get_bid_success(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test successful bid retrieval."""
    from src.models.bid_response import BidResponse
    from datetime import datetime

    # Create test bid
    bid_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    bid = BidResponse(
        id=bid_id,
        document_id=document_id,
        user_id="test-user-id",
        executive_summary="Comprehensive proposal for your project",
        technical_response={
            "approach": "Agile methodology",
            "technologies": ["Python", "React"],
        },
        commercial_proposal={
            "total_price": 100000.00,
            "timeline": "3 months",
        },
        status="draft",
        version=1,
    )
    async_db.add(bid)
    await async_db.commit()

    response = await client.get(
        f"/api/v1/bids/{bid_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "data" in data
    assert "meta" in data

    bid_data = data["data"]
    assert bid_data["id"] == bid_id
    assert bid_data["document_id"] == document_id
    assert bid_data["executive_summary"] == "Comprehensive proposal for your project"
    assert bid_data["status"] == "draft"
    assert bid_data["version"] == 1


@pytest.mark.asyncio
async def test_list_bids_success(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test listing user's bids."""
    from src.models.bid_response import BidResponse

    # Create multiple bids
    for i in range(3):
        bid = BidResponse(
            document_id=str(uuid.uuid4()),
            user_id="test-user-id",
            executive_summary=f"Bid {i}",
            status="draft" if i < 2 else "submitted",
            version=1,
        )
        async_db.add(bid)
    await async_db.commit()

    response = await client.get(
        "/api/v1/bids",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert "data" in data
    assert len(data["data"]) >= 3


@pytest.mark.asyncio
async def test_update_bid_success(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test successful bid update."""
    from src.models.bid_response import BidResponse

    # Create initial bid
    bid_id = str(uuid.uuid4())
    bid = BidResponse(
        id=bid_id,
        document_id=str(uuid.uuid4()),
        user_id="test-user-id",
        executive_summary="Initial summary",
        status="draft",
        version=1,
    )
    async_db.add(bid)
    await async_db.commit()

    # Update bid
    update_data = {
        "executive_summary": "Updated comprehensive summary with more details",
        "technical_response": {
            "architecture": "Microservices",
            "stack": "Python/React/PostgreSQL",
        },
        "commercial_proposal": {
            "total_price": 125000.00,
            "payment_schedule": "Monthly",
        },
    }

    response = await client.put(
        f"/api/v1/bids/{bid_id}",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    bid_data = data["data"]
    assert bid_data["executive_summary"] == update_data["executive_summary"]
    assert bid_data["version"] == 2  # Version should increment


@pytest.mark.asyncio
async def test_update_bid_submitted_error(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test that submitted bids cannot be updated."""
    from src.models.bid_response import BidResponse

    # Create submitted bid
    bid_id = str(uuid.uuid4())
    bid = BidResponse(
        id=bid_id,
        document_id=str(uuid.uuid4()),
        user_id="test-user-id",
        executive_summary="Final bid",
        status="submitted",  # Already submitted
        version=1,
    )
    async_db.add(bid)
    await async_db.commit()

    response = await client.put(
        f"/api/v1/bids/{bid_id}",
        json={"executive_summary": "Try to update"},
        headers=auth_headers,
    )

    assert response.status_code == 409  # Conflict
    data = response.json()
    assert "errors" in data
    assert "cannot update submitted bid" in data["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_submit_bid_success(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test bid submission."""
    from src.models.bid_response import BidResponse
    from src.models.compliance_check import ComplianceCheck

    # Create draft bid
    bid_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    bid = BidResponse(
        id=bid_id,
        document_id=document_id,
        user_id="test-user-id",
        executive_summary="Complete proposal",
        technical_response={"complete": True},
        commercial_proposal={"price": 100000},
        status="draft",
        version=1,
    )
    async_db.add(bid)

    # Add compliance check (required for submission)
    compliance = ComplianceCheck(
        bid_response_id=bid_id,
        administrative_complete=True,
        technical_complete=True,
        financial_complete=True,
        missing_documents=[],
        compliance_score=1.0,
        is_compliant=True,
    )
    async_db.add(compliance)
    await async_db.commit()

    response = await client.post(
        f"/api/v1/bids/{bid_id}/submit",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    bid_data = data["data"]
    assert bid_data["status"] == "submitted"
    assert "submitted_at" in bid_data


@pytest.mark.asyncio
async def test_submit_bid_not_compliant(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test submitting non-compliant bid."""
    from src.models.bid_response import BidResponse
    from src.models.compliance_check import ComplianceCheck

    # Create bid with failed compliance
    bid_id = str(uuid.uuid4())
    bid = BidResponse(
        id=bid_id,
        document_id=str(uuid.uuid4()),
        user_id="test-user-id",
        executive_summary="Incomplete proposal",
        status="draft",
        version=1,
    )
    async_db.add(bid)

    # Add failing compliance check
    compliance = ComplianceCheck(
        bid_response_id=bid_id,
        administrative_complete=False,
        technical_complete=True,
        financial_complete=False,
        missing_documents=["Insurance certificate", "Financial statement"],
        compliance_score=0.4,
        is_compliant=False,
    )
    async_db.add(compliance)
    await async_db.commit()

    response = await client.post(
        f"/api/v1/bids/{bid_id}/submit",
        headers=auth_headers,
    )

    assert response.status_code == 400  # Bad request
    data = response.json()
    assert "errors" in data
    assert "not compliant" in data["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_clone_bid_success(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test cloning a bid for reuse."""
    from src.models.bid_response import BidResponse

    # Create original bid
    original_id = str(uuid.uuid4())
    bid = BidResponse(
        id=original_id,
        document_id=str(uuid.uuid4()),
        user_id="test-user-id",
        executive_summary="Original proposal",
        technical_response={"stack": "Python/React"},
        commercial_proposal={"price": 80000},
        status="submitted",
        version=1,
    )
    async_db.add(bid)
    await async_db.commit()

    # Clone for new document
    new_document_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/bids/{original_id}/clone",
        json={"target_document_id": new_document_id},
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()

    cloned_bid = data["data"]
    assert cloned_bid["id"] != original_id  # New ID
    assert cloned_bid["document_id"] == new_document_id
    assert cloned_bid["executive_summary"] == "Original proposal"
    assert cloned_bid["status"] == "draft"  # Reset to draft
    assert cloned_bid["version"] == 1  # Reset version


@pytest.mark.asyncio
async def test_delete_bid_success(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test soft deleting a bid."""
    from src.models.bid_response import BidResponse

    # Create bid
    bid_id = str(uuid.uuid4())
    bid = BidResponse(
        id=bid_id,
        document_id=str(uuid.uuid4()),
        user_id="test-user-id",
        executive_summary="To be deleted",
        status="draft",
        version=1,
    )
    async_db.add(bid)
    await async_db.commit()

    response = await client.delete(
        f"/api/v1/bids/{bid_id}",
        headers=auth_headers,
    )

    assert response.status_code == 204  # No content

    # Verify bid is soft-deleted
    response = await client.get(
        f"/api/v1/bids/{bid_id}",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_export_bid_pdf(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test exporting bid as PDF."""
    from src.models.bid_response import BidResponse

    # Create complete bid
    bid_id = str(uuid.uuid4())
    bid = BidResponse(
        id=bid_id,
        document_id=str(uuid.uuid4()),
        user_id="test-user-id",
        executive_summary="Professional proposal",
        technical_response={
            "methodology": "Agile",
            "team": "5 developers",
        },
        commercial_proposal={
            "price": 150000,
            "timeline": "6 months",
        },
        status="submitted",
        version=1,
    )
    async_db.add(bid)
    await async_db.commit()

    response = await client.get(
        f"/api/v1/bids/{bid_id}/export?format=pdf",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "content-disposition" in response.headers