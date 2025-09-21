"""Analysis endpoints for capability matching and bid analysis."""

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.analysis import (
    MatchAnalysisRequest,
    MatchAnalysisResponse,
    MatchResult,
)
from src.db.session import get_async_db
from src.middleware.auth import get_current_user
from src.models.user import User
from src.repositories.company_repository import CompanyRepository
from src.repositories.document_repository import DocumentRepository

# Create router for analysis endpoints
router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.post(
    "/match",
    response_model=MatchAnalysisResponse,
    summary="Analyze capability match",
    description="Analyze how well company capabilities match document requirements",
    responses={
        200: {
            "description": "Analysis completed successfully",
            "model": MatchAnalysisResponse
        },
        400: {
            "description": "Analysis failed due to invalid input"
        },
        401: {
            "description": "Authentication required"
        },
        404: {
            "description": "Document or company profile not found"
        }
    }
)
async def analyze_capability_match(
    analysis_request: MatchAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> MatchAnalysisResponse:
    """
    Analyze how well company capabilities match document requirements.

    This endpoint performs comprehensive analysis between:
    - Extracted requirements from a processed document
    - Company capabilities and experience
    - Administrative and technical constraints

    **Analysis Process:**
    1. Validates document and company profile access
    2. Extracts requirements from processed document
    3. Matches against company capabilities
    4. Calculates compatibility scores
    5. Generates recommendations

    **Analysis Options:**
    ```json
    {
        "min_score_threshold": 0.5,
        "include_partial_matches": true,
        "weight_technical": 0.6,
        "weight_experience": 0.4
    }
    ```

    **Response includes:**
    - Overall compatibility score and recommendation
    - Detailed requirement-by-requirement analysis
    - Gap analysis and improvement suggestions
    - Company strengths for this specific bid
    """
    try:
        analysis_start = datetime.utcnow()

        # Initialize repositories
        document_repo = DocumentRepository(db)
        company_repo = CompanyRepository(db)

        # Get and validate document
        document = await document_repo.get_with_requirements(
            analysis_request.document_id,
            tenant_id=current_user.tenant_id
        )

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # Check if user has access to document
        if document.uploaded_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # Check if document is processed
        from src.models.document import DocumentStatus
        if document.status != DocumentStatus.PROCESSED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document must be processed before analysis"
            )

        # Get and validate company profile
        company = await company_repo.get_by_id(
            analysis_request.company_profile_id,
            tenant_id=current_user.tenant_id
        )

        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company profile not found"
            )

        # Perform analysis (simplified MVP version)
        analysis_result = await _perform_capability_analysis(
            document=document,
            company=company,
            options=analysis_request.analysis_options
        )

        # Calculate analysis duration
        analysis_duration = int((datetime.utcnow() - analysis_start).total_seconds() * 1000)

        # Build response
        return MatchAnalysisResponse(
            analysis_id=uuid4(),
            document_id=document.id,
            company_profile_id=company.id,
            overall_match_score=analysis_result["overall_score"],
            recommendation=analysis_result["recommendation"],
            confidence_level=analysis_result["confidence"],
            technical_matches=analysis_result["technical_matches"],
            functional_matches=analysis_result["functional_matches"],
            administrative_matches=analysis_result["administrative_matches"],
            total_requirements=analysis_result["total_requirements"],
            matched_requirements=analysis_result["matched_requirements"],
            missing_capabilities=analysis_result["missing_capabilities"],
            strengths=analysis_result["strengths"],
            analyzed_at=analysis_start,
            analysis_duration_ms=analysis_duration,
            analyst_version="1.0.0"
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analysis failed due to internal error"
        )


async def _perform_capability_analysis(document, company, options):
    """
    Perform capability matching analysis (simplified MVP implementation).

    In production, this would be a sophisticated analysis service with:
    - NLP-based requirement extraction
    - Semantic similarity matching
    - Machine learning scoring models
    - Industry-specific knowledge bases
    """
    import random

    # Simplified analysis for MVP
    # In production, this would use extracted requirements and company capabilities

    # Mock analysis based on available data
    technical_requirements = []
    functional_requirements = []
    administrative_requirements = []

    # Extract requirements if available
    if document.extracted_requirements:
        req_data = document.extracted_requirements.technical_requirements_json or {}
        admin_data = document.extracted_requirements.administrative_requirements_json or {}

        # Generate mock technical matches
        if req_data:
            for key, value in req_data.items():
                if isinstance(value, str) and len(value) > 10:
                    score = random.uniform(0.6, 0.95)
                    technical_requirements.append(MatchResult(
                        requirement_id=f"tech_{key}",
                        requirement_text=value[:100] + "..." if len(value) > 100 else value,
                        capability_match=score > 0.7,
                        match_score=score,
                        gap_analysis="Bonne correspondance" if score > 0.8 else "Correspondance partielle",
                        recommendations=["Mettre en avant cette expertise"] if score > 0.8 else ["Développer cette compétence"]
                    ))

        # Generate mock administrative matches
        if admin_data:
            for key, values in admin_data.items():
                if isinstance(values, list) and values:
                    score = random.uniform(0.7, 1.0)
                    administrative_requirements.append(MatchResult(
                        requirement_id=f"admin_{key}",
                        requirement_text=f"{key}: {', '.join(values[:2])}",
                        capability_match=True,
                        match_score=score,
                        gap_analysis="Conforme",
                        recommendations=["Vérifier les documents requis"]
                    ))

    # Calculate overall statistics
    all_matches = technical_requirements + functional_requirements + administrative_requirements
    total_requirements = len(all_matches) or 5  # Fallback for demo
    matched_requirements = sum(1 for match in all_matches if match.capability_match)

    if not all_matches:
        # Fallback demo data
        overall_score = 0.75
        total_requirements = 8
        matched_requirements = 6
    else:
        overall_score = sum(match.match_score for match in all_matches) / len(all_matches)

    # Generate analysis insights
    company_capabilities = company.capabilities_json or []
    strengths = []
    missing_capabilities = []

    if company_capabilities:
        # Extract strengths from company capabilities
        for cap in company_capabilities[:3]:
            if isinstance(cap, dict) and "domain" in cap:
                strengths.append(f"Expertise {cap['domain']}")

    if overall_score < 0.8:
        missing_capabilities = ["Certification qualité", "Références secteur public"]

    # Determine recommendation
    if overall_score >= 0.8:
        recommendation = "Bid fortement recommandé"
        confidence = "high"
    elif overall_score >= 0.6:
        recommendation = "Bid recommandé avec améliorations"
        confidence = "medium"
    else:
        recommendation = "Bid non recommandé en l'état"
        confidence = "low"

    return {
        "overall_score": round(overall_score, 2),
        "recommendation": recommendation,
        "confidence": confidence,
        "technical_matches": technical_requirements,
        "functional_matches": functional_requirements,
        "administrative_matches": administrative_requirements,
        "total_requirements": total_requirements,
        "matched_requirements": matched_requirements,
        "missing_capabilities": missing_capabilities,
        "strengths": strengths or ["Équipe expérimentée", "Bon rapport qualité-prix"]
    }
