"""Company profile schemas for API requests/responses."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CompanyProfileResponse(BaseModel):
    """Response schema for company profile information."""

    id: UUID = Field(description="Company profile unique identifier")
    company_name: str = Field(description="Company name")
    siret: str = Field(description="French company registration number (SIRET)")
    description: Optional[str] = Field(description="Company description")

    # Structured data
    capabilities: list[dict[str, Any]] = Field(description="Company capabilities")
    certifications: list[dict[str, Any]] = Field(description="Company certifications")
    references: list[dict[str, Any]] = Field(description="Project references")

    # Company metrics
    team_size: Optional[int] = Field(description="Number of employees")
    annual_revenue: Optional[Decimal] = Field(description="Annual revenue in euros")
    founding_year: Optional[int] = Field(description="Year company was founded")

    # Contact information
    contact_email: Optional[str] = Field(description="Contact email")
    contact_phone: Optional[str] = Field(description="Contact phone number")
    address: Optional[str] = Field(description="Company address")

    # Metadata
    version: int = Field(description="Profile version")
    tenant_id: Optional[UUID] = Field(description="Tenant ID for multi-tenancy")
    created_at: datetime = Field(description="Profile creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "company_name": "InnoTech Solutions",
                "siret": "12345678901234",
                "description": "Société spécialisée dans le développement de solutions numériques innovantes",
                "capabilities": [
                    {
                        "domain": "Développement web",
                        "technologies": ["Python", "FastAPI", "React"],
                        "experience_years": 5
                    }
                ],
                "certifications": [
                    {
                        "name": "ISO 27001",
                        "valid_until": "2025-12-31",
                        "issuer": "AFNOR"
                    }
                ],
                "references": [
                    {
                        "client": "Ministère de l'Éducation",
                        "project": "Plateforme e-learning",
                        "year": 2023,
                        "budget": 150000
                    }
                ],
                "team_size": 25,
                "annual_revenue": 2500000.00,
                "founding_year": 2018,
                "contact_email": "contact@innotech-solutions.fr",
                "contact_phone": "+33 1 23 45 67 89",
                "address": "123 Rue de la Tech, 75001 Paris",
                "version": 1,
                "tenant_id": None,
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z"
            }
        }
    }


class CompanyProfileCreateRequest(BaseModel):
    """Request schema for creating company profile."""

    company_name: str = Field(min_length=2, max_length=255, description="Company name")
    siret: str = Field(min_length=14, max_length=14, description="French SIRET number")
    description: Optional[str] = Field(max_length=2000, description="Company description")

    # Structured data
    capabilities: Optional[list[dict[str, Any]]] = Field(default=[], description="Company capabilities")
    certifications: Optional[list[dict[str, Any]]] = Field(default=[], description="Company certifications")
    references: Optional[list[dict[str, Any]]] = Field(default=[], description="Project references")

    # Company metrics
    team_size: Optional[int] = Field(ge=1, le=100000, description="Number of employees")
    annual_revenue: Optional[Decimal] = Field(ge=0, description="Annual revenue in euros")
    founding_year: Optional[int] = Field(ge=1800, le=2024, description="Year company was founded")

    # Contact information
    contact_email: Optional[str] = Field(max_length=255, description="Contact email")
    contact_phone: Optional[str] = Field(max_length=20, description="Contact phone number")
    address: Optional[str] = Field(max_length=500, description="Company address")

    model_config = {
        "json_schema_extra": {
            "example": {
                "company_name": "InnoTech Solutions",
                "siret": "12345678901234",
                "description": "Société spécialisée dans le développement de solutions numériques",
                "capabilities": [
                    {
                        "domain": "Développement web",
                        "technologies": ["Python", "FastAPI", "React"],
                        "experience_years": 5
                    }
                ],
                "certifications": [
                    {
                        "name": "ISO 27001",
                        "valid_until": "2025-12-31",
                        "issuer": "AFNOR"
                    }
                ],
                "references": [
                    {
                        "client": "Ministère de l'Éducation",
                        "project": "Plateforme e-learning",
                        "year": 2023,
                        "budget": 150000
                    }
                ],
                "team_size": 25,
                "annual_revenue": 2500000.00,
                "founding_year": 2018,
                "contact_email": "contact@innotech-solutions.fr",
                "contact_phone": "+33 1 23 45 67 89",
                "address": "123 Rue de la Tech, 75001 Paris"
            }
        }
    }


class CompanyProfileUpdateRequest(BaseModel):
    """Request schema for updating company profile."""

    company_name: Optional[str] = Field(None, min_length=2, max_length=255, description="Company name")
    description: Optional[str] = Field(None, max_length=2000, description="Company description")

    # Structured data
    capabilities: Optional[list[dict[str, Any]]] = Field(None, description="Company capabilities")
    certifications: Optional[list[dict[str, Any]]] = Field(None, description="Company certifications")
    references: Optional[list[dict[str, Any]]] = Field(None, description="Project references")

    # Company metrics
    team_size: Optional[int] = Field(None, ge=1, le=100000, description="Number of employees")
    annual_revenue: Optional[Decimal] = Field(None, ge=0, description="Annual revenue in euros")
    founding_year: Optional[int] = Field(None, ge=1800, le=2024, description="Year company was founded")

    # Contact information
    contact_email: Optional[str] = Field(None, max_length=255, description="Contact email")
    contact_phone: Optional[str] = Field(None, max_length=20, description="Contact phone number")
    address: Optional[str] = Field(None, max_length=500, description="Company address")

    model_config = {
        "json_schema_extra": {
            "example": {
                "description": "Société spécialisée dans le développement de solutions numériques innovantes pour le secteur public",
                "team_size": 30,
                "annual_revenue": 3000000.00,
                "capabilities": [
                    {
                        "domain": "Développement web",
                        "technologies": ["Python", "FastAPI", "React", "Vue.js"],
                        "experience_years": 6
                    },
                    {
                        "domain": "Intelligence artificielle",
                        "technologies": ["TensorFlow", "PyTorch", "scikit-learn"],
                        "experience_years": 3
                    }
                ]
            }
        }
    }
