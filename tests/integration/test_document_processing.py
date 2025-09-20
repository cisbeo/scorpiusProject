"""Integration test for complete document processing flow."""

import pytest
from httpx import AsyncClient
import io
import uuid

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_complete_document_processing_flow(
    client: AsyncClient,
    auth_headers: dict,
    sample_pdf_file: io.BytesIO,
    async_db,
):
    """Test complete flow: upload -> process -> extract requirements -> match capabilities."""
    from src.models.company_profile import CompanyProfile

    # Step 1: Create company profile first
    profile = CompanyProfile(
        user_id="test-user-id",
        company_name="Tech Solutions",
        siret="12345678901234",
        capabilities=[
            {"name": "Python Development", "keywords": ["Python", "FastAPI", "Django"]},
            {"name": "Cloud Services", "keywords": ["AWS", "Azure", "Docker"]},
        ],
        team_size=30,
        annual_revenue=2000000.00,
    )
    async_db.add(profile)
    await async_db.commit()

    # Step 2: Upload document
    files = {
        "file": ("test_rfp.pdf", sample_pdf_file, "application/pdf"),
    }
    upload_response = await client.post(
        "/api/v1/documents",
        files=files,
        headers=auth_headers,
    )
    assert upload_response.status_code == 201
    document = upload_response.json()["data"]
    document_id = document["id"]

    # Step 3: Process document
    process_response = await client.post(
        f"/api/v1/documents/{document_id}/process",
        json={
            "processing_options": {
                "extract_requirements": True,
                "extract_dates": True,
                "extract_criteria": True,
            }
        },
        headers=auth_headers,
    )
    assert process_response.status_code == 202
    process_data = process_response.json()["data"]
    assert process_data["status"] == "processing"

    # Step 4: Simulate processing completion (in real scenario, would wait)
    from src.models.procurement_document import ProcurementDocument
    from src.models.extracted_requirements import ExtractedRequirements
    from sqlalchemy import select

    # Update document status
    result = await async_db.execute(
        select(ProcurementDocument).where(ProcurementDocument.id == document_id)
    )
    doc = result.scalar_one()
    doc.status = "processed"
    doc.title = "Test Procurement Project"
    doc.reference_number = "TEST-2024-001"

    # Add extracted requirements
    requirements = ExtractedRequirements(
        document_id=document_id,
        technical_requirements=["Python", "FastAPI", "PostgreSQL", "Docker"],
        functional_requirements=["REST API", "Authentication", "Dashboard"],
        administrative_requirements=["Insurance", "Company registration"],
        evaluation_criteria={"technical": 50, "price": 30, "experience": 20},
        extraction_confidence=0.85,
    )
    async_db.add(requirements)
    await async_db.commit()

    # Step 5: Get document with requirements
    get_response = await client.get(
        f"/api/v1/documents/{document_id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 200
    doc_data = get_response.json()["data"]
    assert doc_data["status"] == "processed"

    # Step 6: Get requirements
    req_response = await client.get(
        f"/api/v1/documents/{document_id}/requirements",
        headers=auth_headers,
    )
    assert req_response.status_code == 200
    req_data = req_response.json()["data"]
    assert len(req_data["technical_requirements"]) == 4

    # Step 7: Perform capability matching
    match_response = await client.post(
        "/api/v1/analysis/match",
        json={
            "document_id": document_id,
            "analysis_options": {
                "deep_analysis": True,
                "include_suggestions": True,
            }
        },
        headers=auth_headers,
    )
    assert match_response.status_code == 200
    match_data = match_response.json()["data"]
    assert "overall_match_score" in match_data
    assert match_data["overall_match_score"] > 0.5  # Some match expected


@pytest.mark.asyncio
async def test_multiple_document_processing(
    client: AsyncClient,
    auth_headers: dict,
    sample_pdf_file: io.BytesIO,
):
    """Test processing multiple documents concurrently."""
    import asyncio

    # Upload multiple documents
    upload_tasks = []
    for i in range(3):
        # Reset file position
        sample_pdf_file.seek(0)
        files = {
            "file": (f"document_{i}.pdf", sample_pdf_file.read(), "application/pdf"),
        }
        task = client.post(
            "/api/v1/documents",
            files=files,
            headers=auth_headers,
        )
        upload_tasks.append(task)

    upload_responses = await asyncio.gather(*upload_tasks)

    document_ids = []
    for response in upload_responses:
        assert response.status_code == 201
        document_ids.append(response.json()["data"]["id"])

    # Process all documents concurrently
    process_tasks = [
        client.post(
            f"/api/v1/documents/{doc_id}/process",
            headers=auth_headers,
        )
        for doc_id in document_ids
    ]
    process_responses = await asyncio.gather(*process_tasks)

    for response in process_responses:
        assert response.status_code == 202

    # List documents to verify
    list_response = await client.get(
        "/api/v1/documents",
        headers=auth_headers,
    )
    assert list_response.status_code == 200
    documents = list_response.json()["data"]
    assert len(documents) >= 3


@pytest.mark.asyncio
async def test_document_search_and_filter(
    client: AsyncClient,
    auth_headers: dict,
    async_db,
):
    """Test document search and filtering capabilities."""
    from src.models.procurement_document import ProcurementDocument
    from datetime import datetime, timedelta

    # Create documents with different attributes
    documents_data = [
        {
            "original_filename": "infrastructure_project.pdf",
            "title": "Infrastructure Cloud Migration",
            "reference_number": "INFRA-2024-001",
            "buyer_organization": "Ministry of Digital",
            "submission_deadline": datetime.utcnow() + timedelta(days=30),
            "status": "processed",
        },
        {
            "original_filename": "software_development.pdf",
            "title": "Custom Software Development",
            "reference_number": "DEV-2024-002",
            "buyer_organization": "Public Agency X",
            "submission_deadline": datetime.utcnow() + timedelta(days=15),
            "status": "processed",
        },
        {
            "original_filename": "consulting_services.pdf",
            "title": "Digital Transformation Consulting",
            "reference_number": "CONSULT-2024-003",
            "buyer_organization": "Ministry of Digital",
            "submission_deadline": datetime.utcnow() + timedelta(days=45),
            "status": "uploaded",
        },
    ]

    for doc_data in documents_data:
        doc = ProcurementDocument(
            **doc_data,
            stored_filename=f"stored_{doc_data['original_filename']}",
            file_size=1024000,
            file_hash=f"hash_{doc_data['reference_number']}",
            upload_user_id="test-user-id",
        )
        async_db.add(doc)
    await async_db.commit()

    # Test search by keyword
    search_response = await client.get(
        "/api/v1/documents?search=Cloud",
        headers=auth_headers,
    )
    assert search_response.status_code == 200
    results = search_response.json()["data"]
    assert len(results) >= 1
    assert "Cloud" in results[0]["title"]

    # Test filter by status
    status_response = await client.get(
        "/api/v1/documents?status=processed",
        headers=auth_headers,
    )
    assert status_response.status_code == 200
    results = status_response.json()["data"]
    assert all(doc["status"] == "processed" for doc in results)

    # Test filter by date range
    date_from = datetime.utcnow().isoformat()
    date_to = (datetime.utcnow() + timedelta(days=20)).isoformat()
    date_response = await client.get(
        f"/api/v1/documents?date_from={date_from}&date_to={date_to}",
        headers=auth_headers,
    )
    assert date_response.status_code == 200
    results = date_response.json()["data"]
    # Should include document with 15-day deadline
    assert any("DEV-2024-002" in doc.get("reference_number", "") for doc in results)


@pytest.mark.asyncio
async def test_document_versioning(
    client: AsyncClient,
    auth_headers: dict,
    sample_pdf_file: io.BytesIO,
    async_db,
):
    """Test document versioning and updates."""
    # Upload initial version
    files = {
        "file": ("version1.pdf", sample_pdf_file, "application/pdf"),
    }
    upload_response = await client.post(
        "/api/v1/documents",
        files=files,
        headers=auth_headers,
    )
    assert upload_response.status_code == 201
    document_v1 = upload_response.json()["data"]
    document_id = document_v1["id"]

    # Update document metadata
    from src.models.procurement_document import ProcurementDocument
    from sqlalchemy import select

    result = await async_db.execute(
        select(ProcurementDocument).where(ProcurementDocument.id == document_id)
    )
    doc = result.scalar_one()
    doc.title = "Updated Title"
    doc.reference_number = "REF-V2-001"
    doc.version = 2
    await async_db.commit()

    # Get updated document
    get_response = await client.get(
        f"/api/v1/documents/{document_id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 200
    document_v2 = get_response.json()["data"]
    assert document_v2["title"] == "Updated Title"
    assert document_v2["version"] == 2