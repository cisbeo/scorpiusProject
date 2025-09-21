"""Company profile endpoints for managing company information."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.company import (
    CompanyProfileCreateRequest,
    CompanyProfileResponse,
    CompanyProfileUpdateRequest,
)
from src.db.session import get_async_db
from src.middleware.auth import get_current_user
from src.models.user import User
from src.repositories.company_repository import CompanyRepository

# Create router for company endpoints
router = APIRouter(prefix="/company-profile", tags=["Company Profile"])


@router.get(
    "",
    response_model=CompanyProfileResponse,
    summary="Get company profile",
    description="Retrieve the company profile for the current tenant",
    responses={
        200: {
            "description": "Company profile information",
            "model": CompanyProfileResponse
        },
        401: {
            "description": "Authentication required"
        },
        404: {
            "description": "Company profile not found"
        }
    }
)
async def get_company_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> CompanyProfileResponse:
    """
    Retrieve the company profile for the current user's tenant.

    **Response includes:**
    - Complete company information
    - Capabilities and certifications
    - Project references
    - Contact information
    - Company metrics

    Returns the first company profile found for the user's tenant.
    In MVP, each tenant has one company profile.
    """
    try:
        company_repo = CompanyRepository(db)

        # For MVP, we'll get the first company profile for the tenant
        # In future versions, users might be associated with specific companies
        companies = await company_repo.get_multi(
            skip=0,
            limit=1,
            tenant_id=current_user.tenant_id
        )

        if not companies:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company profile not found"
            )

        company = companies[0]

        # Convert JSON fields to proper format for response
        response_data = {
            **company.dict(),
            "capabilities": company.capabilities_json,
            "certifications": company.certifications_json,
            "references": company.references_json
        }

        return CompanyProfileResponse.model_validate(response_data)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve company profile"
        )


@router.post(
    "",
    response_model=CompanyProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create company profile",
    description="Create a new company profile",
    responses={
        201: {
            "description": "Company profile successfully created",
            "model": CompanyProfileResponse
        },
        400: {
            "description": "Company profile creation failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Company with SIRET 12345678901234 already exists"
                    }
                }
            }
        },
        401: {
            "description": "Authentication required"
        },
        422: {
            "description": "Validation error"
        }
    }
)
async def create_company_profile(
    company_data: CompanyProfileCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> CompanyProfileResponse:
    """
    Create a new company profile.

    **Request includes:**
    - Basic company information (name, SIRET, description)
    - Capabilities with technologies and experience
    - Certifications with validity dates
    - Project references
    - Company metrics (team size, revenue, founding year)
    - Contact information

    **SIRET Validation:**
    - Must be exactly 14 digits
    - Must be unique in the system

    **Capabilities Format:**
    ```json
    {
        "domain": "Développement web",
        "technologies": ["Python", "FastAPI", "React"],
        "experience_years": 5
    }
    ```

    **Certifications Format:**
    ```json
    {
        "name": "ISO 27001",
        "valid_until": "2025-12-31",
        "issuer": "AFNOR"
    }
    ```
    """
    try:
        company_repo = CompanyRepository(db)

        # Create company profile
        company = await company_repo.create_company(
            company_name=company_data.company_name,
            siret=company_data.siret,
            description=company_data.description,
            capabilities=company_data.capabilities or [],
            certifications=company_data.certifications or [],
            references=company_data.references or [],
            team_size=company_data.team_size,
            annual_revenue=company_data.annual_revenue,
            founding_year=company_data.founding_year,
            contact_email=company_data.contact_email,
            contact_phone=company_data.contact_phone,
            address=company_data.address,
            tenant_id=current_user.tenant_id
        )

        # Convert JSON fields to proper format for response
        response_data = {
            **company.dict(),
            "capabilities": company.capabilities_json,
            "certifications": company.certifications_json,
            "references": company.references_json
        }

        return CompanyProfileResponse.model_validate(response_data)

    except ValueError as e:
        # SIRET already exists or validation error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create company profile"
        )


@router.put(
    "",
    response_model=CompanyProfileResponse,
    summary="Update company profile",
    description="Update existing company profile",
    responses={
        200: {
            "description": "Company profile successfully updated",
            "model": CompanyProfileResponse
        },
        401: {
            "description": "Authentication required"
        },
        404: {
            "description": "Company profile not found"
        },
        422: {
            "description": "Validation error"
        }
    }
)
async def update_company_profile(
    company_data: CompanyProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> CompanyProfileResponse:
    """
    Update existing company profile.

    **Request body:**
    - All fields are optional
    - Only provided fields will be updated
    - Arrays (capabilities, certifications, references) replace the entire array

    **Partial Update Example:**
    ```json
    {
        "team_size": 30,
        "capabilities": [
            {
                "domain": "Développement web",
                "technologies": ["Python", "FastAPI", "React", "Vue.js"],
                "experience_years": 6
            }
        ]
    }
    ```

    Updates increment the profile version automatically.
    """
    try:
        company_repo = CompanyRepository(db)

        # Get existing company profile
        companies = await company_repo.get_multi(
            skip=0,
            limit=1,
            tenant_id=current_user.tenant_id
        )

        if not companies:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company profile not found"
            )

        company = companies[0]

        # Build update data from non-None fields
        update_data = {}

        # Basic fields
        if company_data.company_name is not None:
            update_data["company_name"] = company_data.company_name
        if company_data.description is not None:
            update_data["description"] = company_data.description

        # Structured data - update entire arrays
        if company_data.capabilities is not None:
            await company_repo.update_capabilities(
                company.id, company_data.capabilities, current_user.tenant_id
            )
        if company_data.certifications is not None:
            await company_repo.update_certifications(
                company.id, company_data.certifications, current_user.tenant_id
            )
        if company_data.references is not None:
            await company_repo.update_references(
                company.id, company_data.references, current_user.tenant_id
            )

        # Company metrics
        metrics_updated = False
        metrics_data = {}
        if company_data.team_size is not None:
            metrics_data["team_size"] = company_data.team_size
            metrics_updated = True
        if company_data.annual_revenue is not None:
            metrics_data["annual_revenue"] = company_data.annual_revenue
            metrics_updated = True
        if company_data.founding_year is not None:
            metrics_data["founding_year"] = company_data.founding_year
            metrics_updated = True

        if metrics_updated:
            await company_repo.update_metrics(
                company.id,
                **metrics_data,
                tenant_id=current_user.tenant_id
            )

        # Contact information
        contact_updated = False
        contact_data = {}
        if company_data.contact_email is not None:
            contact_data["contact_email"] = company_data.contact_email
            contact_updated = True
        if company_data.contact_phone is not None:
            contact_data["contact_phone"] = company_data.contact_phone
            contact_updated = True
        if company_data.address is not None:
            contact_data["address"] = company_data.address
            contact_updated = True

        if contact_updated:
            await company_repo.update_contact_info(
                company.id,
                **contact_data,
                tenant_id=current_user.tenant_id
            )

        # Update basic fields if any
        if update_data:
            await company_repo.update(
                company.id,
                update_data,
                tenant_id=current_user.tenant_id
            )

        # Increment version
        await company_repo.increment_version(company.id, current_user.tenant_id)

        # Get updated company
        updated_company = await company_repo.get_by_id(company.id, tenant_id=current_user.tenant_id)

        # Convert JSON fields to proper format for response
        response_data = {
            **updated_company.dict(),
            "capabilities": updated_company.capabilities_json,
            "certifications": updated_company.certifications_json,
            "references": updated_company.references_json
        }

        return CompanyProfileResponse.model_validate(response_data)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update company profile"
        )
