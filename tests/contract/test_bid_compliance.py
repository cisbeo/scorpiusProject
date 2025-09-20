"""Contract test for POST /bids/{id}/compliance-check endpoint."""

import pytest
from httpx import AsyncClient
import uuid

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_compliance_check_success(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test successful compliance check."""
    from src.models.bid_response import BidResponse
    from src.models.procurement_document import ProcurementDocument
    from src.models.extracted_requirements import ExtractedRequirements

    # Create document with requirements
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="rfp_with_requirements.pdf",
        stored_filename="stored.pdf",
        file_size=1024000,
        file_hash="hash123",
        upload_user_id="test-user-id",
        status="processed",
    )
    async_db.add(doc)

    req = ExtractedRequirements(
        document_id=document_id,
        technical_requirements=["Python", "FastAPI", "PostgreSQL"],
        functional_requirements=["API REST", "Authentication"],
        administrative_requirements=[
            "Insurance certificate",
            "Company registration",
            "Financial statements",
        ],
        financial_requirements=["Minimum revenue 1M EUR"],
        submission_requirements=["PDF format", "Digital signature"],
        extraction_confidence=0.90,
    )
    async_db.add(req)

    # Create complete bid
    bid_id = str(uuid.uuid4())
    bid = BidResponse(
        id=bid_id,
        document_id=document_id,
        user_id="test-user-id",
        executive_summary="Complete proposal",
        technical_response={
            "technologies": ["Python", "FastAPI", "PostgreSQL"],
            "architecture": "Microservices",
        },
        commercial_proposal={
            "price": 150000,
            "timeline": "4 months",
        },
        attachments=[
            {"name": "Insurance certificate", "type": "administrative"},
            {"name": "Company registration", "type": "administrative"},
            {"name": "Financial statements 2023", "type": "financial"},
        ],
        status="draft",
        version=1,
    )
    async_db.add(bid)
    await async_db.commit()

    response = await client.post(
        f"/api/v1/bids/{bid_id}/compliance-check",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify compliance result
    assert "data" in data
    compliance = data["data"]
    assert compliance["bid_id"] == bid_id
    assert compliance["is_compliant"] is True
    assert compliance["compliance_score"] >= 0.9
    assert compliance["administrative_complete"] is True
    assert compliance["technical_complete"] is True
    assert compliance["financial_complete"] is True
    assert len(compliance["missing_documents"]) == 0


@pytest.mark.asyncio
async def test_compliance_check_missing_documents(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test compliance check with missing documents."""
    from src.models.bid_response import BidResponse
    from src.models.procurement_document import ProcurementDocument
    from src.models.extracted_requirements import ExtractedRequirements

    # Create document with requirements
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="strict_rfp.pdf",
        stored_filename="stored.pdf",
        file_size=1024000,
        file_hash="hash456",
        upload_user_id="test-user-id",
        status="processed",
    )
    async_db.add(doc)

    req = ExtractedRequirements(
        document_id=document_id,
        administrative_requirements=[
            "Insurance certificate RC Pro",
            "Extrait Kbis < 3 mois",
            "Attestation fiscale",
            "Attestation URSSAF",
        ],
        financial_requirements=[
            "Bilan comptable N-1",
            "Garantie bancaire",
        ],
        extraction_confidence=0.85,
    )
    async_db.add(req)

    # Create incomplete bid (missing documents)
    bid_id = str(uuid.uuid4())
    bid = BidResponse(
        id=bid_id,
        document_id=document_id,
        user_id="test-user-id",
        executive_summary="Incomplete proposal",
        attachments=[
            {"name": "Insurance certificate", "type": "administrative"},
            # Missing: Kbis, Attestation fiscale, URSSAF, Bilan, Garantie
        ],
        status="draft",
        version=1,
    )
    async_db.add(bid)
    await async_db.commit()

    response = await client.post(
        f"/api/v1/bids/{bid_id}/compliance-check",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    compliance = data["data"]
    assert compliance["is_compliant"] is False
    assert compliance["compliance_score"] < 0.5
    assert compliance["administrative_complete"] is False
    assert compliance["financial_complete"] is False
    assert len(compliance["missing_documents"]) > 4
    assert "Extrait Kbis" in str(compliance["missing_documents"])


@pytest.mark.asyncio
async def test_compliance_check_technical_gaps(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test compliance check with technical requirement gaps."""
    from src.models.bid_response import BidResponse
    from src.models.procurement_document import ProcurementDocument
    from src.models.extracted_requirements import ExtractedRequirements

    # Create document with specific technical requirements
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="technical_rfp.pdf",
        stored_filename="stored.pdf",
        file_size=1024000,
        file_hash="hash789",
        upload_user_id="test-user-id",
        status="processed",
    )
    async_db.add(doc)

    req = ExtractedRequirements(
        document_id=document_id,
        technical_requirements=[
            "Java Spring Boot",
            "Angular 14+",
            "MongoDB",
            "Kubernetes orchestration",
            "CI/CD pipeline",
        ],
        extraction_confidence=0.88,
    )
    async_db.add(req)

    # Create bid with only partial technical response
    bid_id = str(uuid.uuid4())
    bid = BidResponse(
        id=bid_id,
        document_id=document_id,
        user_id="test-user-id",
        executive_summary="Partial technical proposal",
        technical_response={
            "technologies": ["Python", "React"],  # Wrong tech stack
            "ci_cd": "Jenkins pipeline",  # Has CI/CD
        },
        status="draft",
        version=1,
    )
    async_db.add(bid)
    await async_db.commit()

    response = await client.post(
        f"/api/v1/bids/{bid_id}/compliance-check",
        json={
            "check_options": {
                "strict_technical": True,
                "fuzzy_matching": False,
            }
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    compliance = data["data"]
    assert compliance["is_compliant"] is False
    assert compliance["technical_complete"] is False
    assert "technical_gaps" in compliance
    assert len(compliance["technical_gaps"]) >= 3  # Missing Java, Angular, MongoDB


@pytest.mark.asyncio
async def test_compliance_check_warnings(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test compliance check with warnings (compliant but issues noted)."""
    from src.models.bid_response import BidResponse
    from src.models.procurement_document import ProcurementDocument
    from src.models.extracted_requirements import ExtractedRequirements
    from datetime import datetime, timedelta

    # Create document with near deadline
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="urgent_rfp.pdf",
        stored_filename="stored.pdf",
        file_size=1024000,
        file_hash="hash111",
        upload_user_id="test-user-id",
        submission_deadline=datetime.utcnow() + timedelta(hours=2),  # Very soon
        status="processed",
    )
    async_db.add(doc)

    req = ExtractedRequirements(
        document_id=document_id,
        submission_requirements=["Submit before deadline", "PDF format"],
        extraction_confidence=0.90,
    )
    async_db.add(req)

    # Create technically complete bid
    bid_id = str(uuid.uuid4())
    bid = BidResponse(
        id=bid_id,
        document_id=document_id,
        user_id="test-user-id",
        executive_summary="Complete but rushed",
        technical_response={"complete": True},
        commercial_proposal={"price": 100000},
        status="draft",
        version=1,
    )
    async_db.add(bid)
    await async_db.commit()

    response = await client.post(
        f"/api/v1/bids/{bid_id}/compliance-check",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    compliance = data["data"]
    assert compliance["is_compliant"] is True  # Technically compliant
    assert "warnings" in compliance
    assert len(compliance["warnings"]) > 0
    assert any("deadline" in warning.lower() for warning in compliance["warnings"])


@pytest.mark.asyncio
async def test_compliance_check_suggestions(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test compliance check with improvement suggestions."""
    from src.models.bid_response import BidResponse
    from src.models.procurement_document import ProcurementDocument
    from src.models.extracted_requirements import ExtractedRequirements

    # Create document
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="improvement_rfp.pdf",
        stored_filename="stored.pdf",
        file_size=1024000,
        file_hash="hash222",
        upload_user_id="test-user-id",
        status="processed",
    )
    async_db.add(doc)

    req = ExtractedRequirements(
        document_id=document_id,
        evaluation_criteria={
            "technical": 40,
            "price": 30,
            "experience": 20,
            "innovation": 10,
        },
        extraction_confidence=0.85,
    )
    async_db.add(req)

    # Create minimal bid
    bid_id = str(uuid.uuid4())
    bid = BidResponse(
        id=bid_id,
        document_id=document_id,
        user_id="test-user-id",
        executive_summary="Basic proposal",
        technical_response={"basic": True},
        commercial_proposal={"price": 100000},
        # Missing: innovation aspects, detailed experience
        status="draft",
        version=1,
    )
    async_db.add(bid)
    await async_db.commit()

    response = await client.post(
        f"/api/v1/bids/{bid_id}/compliance-check",
        json={
            "check_options": {
                "include_suggestions": True,
                "analyze_scoring": True,
            }
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    compliance = data["data"]
    assert "suggestions" in compliance
    assert len(compliance["suggestions"]) > 0
    assert any("innovation" in sugg.lower() for sugg in compliance["suggestions"])
    assert "scoring_analysis" in compliance


@pytest.mark.asyncio
async def test_compliance_check_no_requirements(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test compliance check when requirements haven't been extracted."""
    from src.models.bid_response import BidResponse
    from src.models.procurement_document import ProcurementDocument

    # Create document without extracted requirements
    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="no_req.pdf",
        stored_filename="stored.pdf",
        file_size=1024,
        file_hash="hash",
        upload_user_id="test-user-id",
        status="processed",  # Processed but no requirements extracted
    )
    async_db.add(doc)

    bid_id = str(uuid.uuid4())
    bid = BidResponse(
        id=bid_id,
        document_id=document_id,
        user_id="test-user-id",
        executive_summary="Proposal",
        status="draft",
        version=1,
    )
    async_db.add(bid)
    await async_db.commit()

    response = await client.post(
        f"/api/v1/bids/{bid_id}/compliance-check",
        headers=auth_headers,
    )

    assert response.status_code == 404
    data = response.json()
    assert "errors" in data
    assert "requirements not found" in data["errors"][0]["message"].lower()