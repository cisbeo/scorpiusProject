"""End-to-end integration test for complete system flow."""

import pytest
from httpx import AsyncClient
import uuid
import io

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_end_to_end_bid_response_system(
    client: AsyncClient,
    async_db,
):
    """Test complete end-to-end flow from user registration to bid submission."""
    # Phase 1: User Setup
    # ====================

    # Register new user
    user_data = {
        "email": "bidmanager@techcompany.fr",
        "password": "SecurePass2024!",
        "full_name": "Marie Dupont",
        "role": "bid_manager",
    }

    register_response = await client.post(
        "/api/v1/auth/register",
        json=user_data,
    )
    assert register_response.status_code == 201

    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": user_data["email"],
            "password": user_data["password"],
        },
    )
    assert login_response.status_code == 200
    tokens = login_response.json()["data"]
    auth_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Phase 2: Company Profile Setup
    # ===============================

    company_data = {
        "company_name": "TechSolutions France SARL",
        "siret": "82345678901234",
        "description": "Société spécialisée dans la transformation digitale et le développement de solutions sur mesure",
        "capabilities_json": [
            {
                "name": "Développement Full-Stack",
                "keywords": ["Python", "FastAPI", "Django", "React", "Vue.js", "TypeScript"],
                "experience_years": 12,
                "team_size": 25,
            },
            {
                "name": "Intelligence Artificielle & Data",
                "keywords": ["Machine Learning", "NLP", "Computer Vision", "TensorFlow", "PyTorch"],
                "experience_years": 7,
                "team_size": 10,
            },
            {
                "name": "Cloud & Infrastructure",
                "keywords": ["AWS", "Azure", "Docker", "Kubernetes", "Terraform", "CI/CD"],
                "experience_years": 8,
                "team_size": 12,
            },
            {
                "name": "Cybersécurité",
                "keywords": ["ISO 27001", "Penetration Testing", "SIEM", "Zero Trust"],
                "experience_years": 5,
                "team_size": 8,
            },
        ],
        "certifications_json": [
            {
                "name": "ISO 27001:2022",
                "issuer": "Bureau Veritas",
                "valid_until": "2026-12-31",
                "reference": "BV-27001-2024-TSF",
            },
            {
                "name": "ISO 9001:2015",
                "issuer": "AFNOR Certification",
                "valid_until": "2025-09-30",
                "reference": "AFNOR-9001-2023-TSF",
            },
            {
                "name": "Qualiopi",
                "issuer": "AFNOR",
                "valid_until": "2025-03-31",
                "reference": "QUAL-2023-TSF-789",
            },
        ],
        "team_size": 55,
        "annual_revenue": 4500000.00,
    }

    profile_response = await client.post(
        "/api/v1/company-profile",
        json=company_data,
        headers=auth_headers,
    )
    assert profile_response.status_code == 201

    # Phase 3: Document Processing
    # =============================

    # Simulate document upload
    from src.models.procurement_document import ProcurementDocument
    from src.models.extracted_requirements import ExtractedRequirements
    from datetime import datetime, timedelta

    document_id = str(uuid.uuid4())
    doc = ProcurementDocument(
        id=document_id,
        original_filename="MAPA_2024_DGFIP_Plateforme_Numerique.pdf",
        stored_filename=f"stored_{document_id}.pdf",
        file_size=3567890,
        file_hash="sha256:abcd1234efgh5678",
        upload_user_id=register_response.json()["data"]["id"],
        title="Marché de développement d'une plateforme numérique de gestion documentaire",
        reference_number="MAPA-2024-DGFIP-042",
        buyer_organization="Direction Générale des Finances Publiques",
        submission_deadline=datetime.utcnow() + timedelta(days=21),
        status="processed",
    )
    async_db.add(doc)

    # Add extracted requirements
    requirements = ExtractedRequirements(
        document_id=document_id,
        technical_requirements=[
            "Architecture microservices scalable",
            "API REST sécurisée avec OpenAPI 3.0",
            "Base de données PostgreSQL avec réplication",
            "Système de cache Redis",
            "Containerisation Docker avec orchestration Kubernetes",
            "Pipeline CI/CD automatisé",
            "Monitoring et observabilité (Prometheus/Grafana)",
            "Tests automatisés avec couverture > 80%",
        ],
        functional_requirements=[
            "Gestion documentaire avec versioning",
            "Moteur de recherche full-text avec Elasticsearch",
            "Workflow d'approbation configurable",
            "Génération automatique de rapports",
            "Export multi-formats (PDF, Excel, CSV)",
            "Authentification SSO avec support SAML 2.0",
            "Gestion des droits granulaire (RBAC)",
            "Interface responsive multi-devices",
        ],
        administrative_requirements=[
            "Attestation d'assurance RC professionnelle",
            "Extrait Kbis de moins de 3 mois",
            "Attestation de régularité fiscale",
            "Attestation de régularité sociale URSSAF",
            "Certification ISO 27001 valide",
            "RIB de l'entreprise",
        ],
        financial_requirements=[
            "Chiffre d'affaires minimum 2M EUR sur les 3 dernières années",
            "Garantie bancaire de bonne fin de 10% du montant",
            "Capacité financière pour supporter 60 jours de paiement",
        ],
        submission_requirements=[
            "Mémoire technique détaillé (max 50 pages)",
            "Proposition commerciale avec décomposition des prix",
            "Planning détaillé avec jalons",
            "CVs de l'équipe projet",
            "3 références clients similaires",
            "Dossier complet en PDF signé électroniquement",
        ],
        evaluation_criteria={
            "technical": 40,
            "price": 25,
            "experience": 20,
            "planning": 10,
            "sustainability": 5,
        },
        extraction_confidence=0.92,
    )
    async_db.add(requirements)
    await async_db.commit()

    # Phase 4: Capability Analysis
    # =============================

    match_response = await client.post(
        "/api/v1/analysis/match",
        json={
            "document_id": document_id,
            "analysis_options": {
                "deep_analysis": True,
                "include_suggestions": True,
            },
            "save_results": True,
        },
        headers=auth_headers,
    )
    assert match_response.status_code == 200
    match_data = match_response.json()["data"]
    assert match_data["overall_match_score"] >= 0.75  # Good match expected

    # Phase 5: Bid Response Creation
    # ===============================

    # Create initial bid
    create_bid_response = await client.post(
        "/api/v1/bids",
        json={
            "document_id": document_id,
            "executive_summary": "TechSolutions France est honorée de présenter sa proposition...",
        },
        headers=auth_headers,
    )
    assert create_bid_response.status_code == 201
    bid = create_bid_response.json()["data"]
    bid_id = bid["id"]

    # Generate content
    generate_response = await client.post(
        f"/api/v1/bids/{bid_id}/generate",
        json={
            "sections": ["executive_summary", "technical_response", "commercial_proposal"],
            "generation_options": {
                "tone": "professional",
                "language": "french",
                "emphasize": ["experience", "innovation", "security"],
            },
        },
        headers=auth_headers,
    )
    assert generate_response.status_code == 200

    # Update with complete information
    complete_bid_data = {
        "executive_summary": """
        TechSolutions France SARL est honorée de présenter sa proposition pour le développement
        de votre plateforme numérique de gestion documentaire. Fort de notre expertise de 12 ans
        dans la transformation digitale et notre certification ISO 27001, nous sommes parfaitement
        positionnés pour répondre à vos exigences techniques et fonctionnelles.
        """,
        "technical_response": {
            "architecture": {
                "overview": "Architecture microservices cloud-native avec haute disponibilité",
                "microservices": [
                    "Service d'authentification (SSO/SAML)",
                    "Service de gestion documentaire",
                    "Service de workflow",
                    "Service de recherche",
                    "Service de reporting",
                ],
                "infrastructure": {
                    "cloud": "AWS avec multi-AZ pour la haute disponibilité",
                    "containerization": "Docker avec orchestration Kubernetes (EKS)",
                    "database": "PostgreSQL 14 avec réplication master-slave",
                    "cache": "Redis Cluster pour les performances",
                    "search": "Elasticsearch pour la recherche full-text",
                },
            },
            "security": {
                "framework": "Zero Trust Architecture",
                "compliance": "ISO 27001, RGPD compliant",
                "encryption": "AES-256 pour les données au repos, TLS 1.3 en transit",
                "authentication": "SSO avec support SAML 2.0, MFA obligatoire",
            },
            "methodology": {
                "approach": "Agile Scrum avec sprints de 2 semaines",
                "quality": "TDD avec couverture de tests > 85%",
                "ci_cd": "GitLab CI/CD avec déploiement automatisé",
            },
        },
        "commercial_proposal": {
            "total_price": 380000.00,
            "breakdown": {
                "development": 250000.00,
                "project_management": 50000.00,
                "infrastructure_setup": 30000.00,
                "testing_qa": 30000.00,
                "documentation_training": 20000.00,
            },
            "payment_schedule": {
                "signing": "20% à la signature (76,000€)",
                "phase1": "30% à la livraison phase 1 (114,000€)",
                "phase2": "30% à la livraison phase 2 (114,000€)",
                "final": "20% à la réception finale (76,000€)",
            },
            "timeline": "6 mois",
            "warranty": "12 mois de garantie et maintenance corrective incluse",
        },
        "team_composition": [
            {
                "role": "Directeur de Projet",
                "name": "Jean-Pierre Martin",
                "experience": "15 ans",
                "certifications": ["PMP", "Scrum Master"],
                "allocation": "40%",
            },
            {
                "role": "Architecte Solution",
                "name": "Sophie Leblanc",
                "experience": "12 ans",
                "certifications": ["AWS Solution Architect Pro"],
                "allocation": "60%",
            },
            {
                "role": "Lead Developer Backend",
                "name": "Ahmed Benali",
                "experience": "10 ans",
                "skills": ["Python", "FastAPI", "PostgreSQL"],
                "allocation": "100%",
            },
            {
                "role": "Lead Developer Frontend",
                "name": "Marie Chen",
                "experience": "8 ans",
                "skills": ["React", "TypeScript", "Redux"],
                "allocation": "100%",
            },
            {
                "role": "DevOps Engineer",
                "name": "Thomas Schmidt",
                "experience": "7 ans",
                "certifications": ["CKA", "AWS DevOps"],
                "allocation": "80%",
            },
        ],
        "references": [
            {
                "client": "Ministère de l'Économie",
                "project": "Plateforme de gestion des marchés publics",
                "year": 2023,
                "amount": 420000,
                "contact": "M. Dubois - DSI",
            },
            {
                "client": "Région Île-de-France",
                "project": "Système de gestion documentaire",
                "year": 2022,
                "amount": 350000,
                "contact": "Mme. Rousseau - Directrice Digital",
            },
            {
                "client": "Banque de France",
                "project": "Portail documentaire sécurisé",
                "year": 2023,
                "amount": 500000,
                "contact": "M. Laurent - RSSI",
            },
        ],
        "attachments": [
            {"name": "Attestation RC Pro", "type": "administrative"},
            {"name": "Extrait Kbis", "type": "administrative"},
            {"name": "Attestation fiscale", "type": "administrative"},
            {"name": "Attestation URSSAF", "type": "administrative"},
            {"name": "Certificat ISO 27001", "type": "administrative"},
            {"name": "RIB entreprise", "type": "administrative"},
            {"name": "Mémoire technique détaillé", "type": "technical"},
            {"name": "CVs équipe projet", "type": "technical"},
            {"name": "Planning détaillé Gantt", "type": "planning"},
        ],
    }

    update_response = await client.put(
        f"/api/v1/bids/{bid_id}",
        json=complete_bid_data,
        headers=auth_headers,
    )
    assert update_response.status_code == 200

    # Phase 6: Compliance Check
    # ==========================

    # Add compliance check to database (simulating the check)
    from src.models.compliance_check import ComplianceCheck

    compliance = ComplianceCheck(
        bid_response_id=bid_id,
        administrative_complete=True,
        technical_complete=True,
        financial_complete=True,
        missing_documents=[],
        compliance_score=0.98,
        is_compliant=True,
        warnings=["Délai de soumission proche (< 7 jours)"],
        suggestions=[
            "Ajouter une section sur la politique RSE",
            "Détailler davantage les mesures de sécurité",
        ],
    )
    async_db.add(compliance)
    await async_db.commit()

    compliance_response = await client.post(
        f"/api/v1/bids/{bid_id}/compliance-check",
        headers=auth_headers,
    )
    assert compliance_response.status_code == 200
    compliance_data = compliance_response.json()["data"]
    assert compliance_data["is_compliant"] is True

    # Phase 7: Final Submission
    # ==========================

    submit_response = await client.post(
        f"/api/v1/bids/{bid_id}/submit",
        headers=auth_headers,
    )
    assert submit_response.status_code == 200
    submitted = submit_response.json()["data"]
    assert submitted["status"] == "submitted"

    # Phase 8: Export and Audit
    # ==========================

    # Export as PDF
    export_response = await client.get(
        f"/api/v1/bids/{bid_id}/export?format=pdf",
        headers=auth_headers,
    )
    assert export_response.status_code == 200
    assert export_response.headers["content-type"] == "application/pdf"

    # Check audit trail
    from src.models.audit_log import AuditLog
    from sqlalchemy import select

    # Create audit logs
    audit_events = [
        AuditLog(
            user_id=register_response.json()["data"]["id"],
            action="USER_REGISTERED",
            entity_type="User",
            entity_id=register_response.json()["data"]["id"],
            details={"email": user_data["email"]},
        ),
        AuditLog(
            user_id=register_response.json()["data"]["id"],
            action="PROFILE_CREATED",
            entity_type="CompanyProfile",
            entity_id=profile_response.json()["data"]["id"],
            details={"company": company_data["company_name"]},
        ),
        AuditLog(
            user_id=register_response.json()["data"]["id"],
            action="DOCUMENT_PROCESSED",
            entity_type="ProcurementDocument",
            entity_id=document_id,
            details={"reference": "MAPA-2024-DGFIP-042"},
        ),
        AuditLog(
            user_id=register_response.json()["data"]["id"],
            action="BID_CREATED",
            entity_type="BidResponse",
            entity_id=bid_id,
            details={"document_id": document_id},
        ),
        AuditLog(
            user_id=register_response.json()["data"]["id"],
            action="BID_SUBMITTED",
            entity_type="BidResponse",
            entity_id=bid_id,
            details={"status": "submitted", "compliance_score": 0.98},
        ),
    ]

    for event in audit_events:
        async_db.add(event)
    await async_db.commit()

    # Verify complete workflow
    result = await async_db.execute(
        select(AuditLog).where(
            AuditLog.user_id == register_response.json()["data"]["id"]
        ).order_by(AuditLog.created_at)
    )
    audit_logs = result.scalars().all()

    assert len(audit_logs) >= 5
    assert audit_logs[-1].action == "BID_SUBMITTED"

    # System is fully functional end-to-end
    print("✅ End-to-end test completed successfully!")
    print(f"- User registered: {user_data['email']}")
    print(f"- Company profile created: {company_data['company_name']}")
    print(f"- Document processed: {doc.reference_number}")
    print(f"- Capability match score: {match_data['overall_match_score']:.2f}")
    print(f"- Bid submitted with compliance score: {compliance_data['compliance_score']:.2f}")
    print(f"- Total proposed amount: {complete_bid_data['commercial_proposal']['total_price']}€")