"""Company repository for company profile operations."""

from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.company import CompanyProfile
from src.repositories.base import BaseRepository


class CompanyRepository(BaseRepository[CompanyProfile]):
    """
    Repository for CompanyProfile model with company-specific operations.

    Extends BaseRepository with company-specific methods:
    - SIRET-based lookups
    - Capability searches
    - Company metrics queries
    - Profile versioning
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize company repository."""
        super().__init__(CompanyProfile, db_session)

    async def create_company(
        self,
        company_name: str,
        siret: str,
        description: Optional[str] = None,
        capabilities: Optional[list] = None,
        certifications: Optional[list] = None,
        references: Optional[list] = None,
        team_size: Optional[int] = None,
        annual_revenue: Optional[Decimal] = None,
        founding_year: Optional[int] = None,
        contact_email: Optional[str] = None,
        contact_phone: Optional[str] = None,
        address: Optional[str] = None,
        tenant_id: Optional[UUID] = None
    ) -> CompanyProfile:
        """
        Create a new company profile.

        Args:
            company_name: Name of the company
            siret: French company registration number
            description: Company description
            capabilities: List of company capabilities
            certifications: List of company certifications
            references: List of project references
            team_size: Number of employees
            annual_revenue: Annual revenue in euros
            founding_year: Year company was founded
            contact_email: Contact email
            contact_phone: Contact phone number
            address: Company address
            tenant_id: Tenant ID for multi-tenancy

        Returns:
            Created company profile instance

        Raises:
            ValueError: If SIRET already exists
        """
        # Check if SIRET already exists
        existing_company = await self.get_by_siret(siret)
        if existing_company:
            raise ValueError(f"Company with SIRET {siret} already exists")

        return await self.create(
            company_name=company_name,
            siret=siret,
            description=description,
            capabilities_json=capabilities or [],
            certifications_json=certifications or [],
            references_json=references or [],
            team_size=team_size,
            annual_revenue=annual_revenue,
            founding_year=founding_year,
            contact_email=contact_email,
            contact_phone=contact_phone,
            address=address,
            tenant_id=tenant_id
        )

    async def get_by_siret(
        self,
        siret: str,
        include_deleted: bool = False,
        tenant_id: Optional[UUID] = None
    ) -> Optional[CompanyProfile]:
        """
        Get company by SIRET number.

        Args:
            siret: French company registration number
            include_deleted: Whether to include soft-deleted companies
            tenant_id: Tenant ID for isolation

        Returns:
            Company profile if found, None otherwise
        """
        return await self.get_by_field(
            field_name="siret",
            field_value=siret,
            include_deleted=include_deleted,
            tenant_id=tenant_id
        )

    async def get_by_name(
        self,
        company_name: str,
        include_deleted: bool = False,
        tenant_id: Optional[UUID] = None
    ) -> Optional[CompanyProfile]:
        """
        Get company by name (exact match).

        Args:
            company_name: Name of the company
            include_deleted: Whether to include soft-deleted companies
            tenant_id: Tenant ID for isolation

        Returns:
            Company profile if found, None otherwise
        """
        return await self.get_by_field(
            field_name="company_name",
            field_value=company_name,
            include_deleted=include_deleted,
            tenant_id=tenant_id
        )

    async def search_by_name(
        self,
        name_pattern: str,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[CompanyProfile]:
        """
        Search companies by name pattern (case-insensitive).

        Args:
            name_pattern: Pattern to search for in company names
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of matching company profiles
        """
        query = select(CompanyProfile).where(
            CompanyProfile.company_name.ilike(f"%{name_pattern}%")
        )

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(CompanyProfile.tenant_id == tenant_id)

        # Filter out soft-deleted records
        query = query.where(CompanyProfile.deleted_at.is_(None))

        # Apply pagination and ordering
        query = query.offset(skip).limit(limit).order_by(
            CompanyProfile.company_name.asc()
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_capabilities(
        self,
        company_id: UUID,
        capabilities: list[dict[str, Any]],
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Update company capabilities.

        Args:
            company_id: Company UUID
            capabilities: List of capability dictionaries
            tenant_id: Tenant ID for isolation

        Returns:
            True if capabilities were updated, False if company not found
        """
        return await self._update_json_field(
            company_id=company_id,
            field_name="capabilities_json",
            value=capabilities,
            tenant_id=tenant_id
        )

    async def add_capability(
        self,
        company_id: UUID,
        capability: dict[str, Any],
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Add a single capability to company.

        Args:
            company_id: Company UUID
            capability: Capability dictionary to add
            tenant_id: Tenant ID for isolation

        Returns:
            True if capability was added, False if company not found
        """
        company = await self.get_by_id(company_id, tenant_id=tenant_id)
        if company is None:
            return False

        capabilities = company.capabilities_json.copy()
        capabilities.append(capability)

        return await self.update_capabilities(
            company_id=company_id,
            capabilities=capabilities,
            tenant_id=tenant_id
        )

    async def update_certifications(
        self,
        company_id: UUID,
        certifications: list[dict[str, Any]],
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Update company certifications.

        Args:
            company_id: Company UUID
            certifications: List of certification dictionaries
            tenant_id: Tenant ID for isolation

        Returns:
            True if certifications were updated, False if company not found
        """
        return await self._update_json_field(
            company_id=company_id,
            field_name="certifications_json",
            value=certifications,
            tenant_id=tenant_id
        )

    async def add_certification(
        self,
        company_id: UUID,
        certification: dict[str, Any],
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Add a single certification to company.

        Args:
            company_id: Company UUID
            certification: Certification dictionary to add
            tenant_id: Tenant ID for isolation

        Returns:
            True if certification was added, False if company not found
        """
        company = await self.get_by_id(company_id, tenant_id=tenant_id)
        if company is None:
            return False

        certifications = company.certifications_json.copy()
        certifications.append(certification)

        return await self.update_certifications(
            company_id=company_id,
            certifications=certifications,
            tenant_id=tenant_id
        )

    async def update_references(
        self,
        company_id: UUID,
        references: list[dict[str, Any]],
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Update company references.

        Args:
            company_id: Company UUID
            references: List of reference dictionaries
            tenant_id: Tenant ID for isolation

        Returns:
            True if references were updated, False if company not found
        """
        return await self._update_json_field(
            company_id=company_id,
            field_name="references_json",
            value=references,
            tenant_id=tenant_id
        )

    async def add_reference(
        self,
        company_id: UUID,
        reference: dict[str, Any],
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Add a single reference to company.

        Args:
            company_id: Company UUID
            reference: Reference dictionary to add
            tenant_id: Tenant ID for isolation

        Returns:
            True if reference was added, False if company not found
        """
        company = await self.get_by_id(company_id, tenant_id=tenant_id)
        if company is None:
            return False

        references = company.references_json.copy()
        references.append(reference)

        return await self.update_references(
            company_id=company_id,
            references=references,
            tenant_id=tenant_id
        )

    async def update_metrics(
        self,
        company_id: UUID,
        team_size: Optional[int] = None,
        annual_revenue: Optional[Decimal] = None,
        founding_year: Optional[int] = None,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Update company metrics.

        Args:
            company_id: Company UUID
            team_size: Number of employees
            annual_revenue: Annual revenue in euros
            founding_year: Year company was founded
            tenant_id: Tenant ID for isolation

        Returns:
            True if metrics were updated, False if company not found
        """
        update_data = {}
        if team_size is not None:
            update_data["team_size"] = team_size
        if annual_revenue is not None:
            update_data["annual_revenue"] = annual_revenue
        if founding_year is not None:
            update_data["founding_year"] = founding_year

        if not update_data:
            return False

        updated_company = await self.update(
            id=company_id,
            update_data=update_data,
            tenant_id=tenant_id
        )
        return updated_company is not None

    async def update_contact_info(
        self,
        company_id: UUID,
        contact_email: Optional[str] = None,
        contact_phone: Optional[str] = None,
        address: Optional[str] = None,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Update company contact information.

        Args:
            company_id: Company UUID
            contact_email: Contact email
            contact_phone: Contact phone number
            address: Company address
            tenant_id: Tenant ID for isolation

        Returns:
            True if contact info was updated, False if company not found
        """
        update_data = {}
        if contact_email is not None:
            update_data["contact_email"] = contact_email
        if contact_phone is not None:
            update_data["contact_phone"] = contact_phone
        if address is not None:
            update_data["address"] = address

        if not update_data:
            return False

        updated_company = await self.update(
            id=company_id,
            update_data=update_data,
            tenant_id=tenant_id
        )
        return updated_company is not None

    async def increment_version(
        self,
        company_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Increment company profile version.

        Args:
            company_id: Company UUID
            tenant_id: Tenant ID for isolation

        Returns:
            True if version was incremented, False if company not found
        """
        company = await self.get_by_id(company_id, tenant_id=tenant_id)
        if company is None:
            return False

        updated_company = await self.update(
            id=company_id,
            update_data={"version": company.version + 1},
            tenant_id=tenant_id
        )
        return updated_company is not None

    async def siret_exists(
        self,
        siret: str,
        exclude_company_id: Optional[UUID] = None,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Check if SIRET already exists in the system.

        Args:
            siret: SIRET number to check
            exclude_company_id: Company ID to exclude from check (for updates)
            tenant_id: Tenant ID for isolation

        Returns:
            True if SIRET exists, False otherwise
        """
        query = select(CompanyProfile).where(CompanyProfile.siret == siret)

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(CompanyProfile.tenant_id == tenant_id)

        # Exclude specific company (useful for updates)
        if exclude_company_id is not None:
            query = query.where(CompanyProfile.id != exclude_company_id)

        # Only check non-deleted companies
        query = query.where(CompanyProfile.deleted_at.is_(None))

        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def get_companies_by_size(
        self,
        min_team_size: Optional[int] = None,
        max_team_size: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[CompanyProfile]:
        """
        Get companies filtered by team size.

        Args:
            min_team_size: Minimum team size
            max_team_size: Maximum team size
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of companies matching size criteria
        """
        query = select(CompanyProfile)

        # Apply size filters
        if min_team_size is not None:
            query = query.where(CompanyProfile.team_size >= min_team_size)
        if max_team_size is not None:
            query = query.where(CompanyProfile.team_size <= max_team_size)

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(CompanyProfile.tenant_id == tenant_id)

        # Filter out soft-deleted records
        query = query.where(CompanyProfile.deleted_at.is_(None))

        # Apply pagination and ordering
        query = query.offset(skip).limit(limit).order_by(
            CompanyProfile.team_size.desc().nulls_last()
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def _update_json_field(
        self,
        company_id: UUID,
        field_name: str,
        value: Any,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Helper method to update JSON fields.

        Args:
            company_id: Company UUID
            field_name: Name of the JSON field to update
            value: New value for the field
            tenant_id: Tenant ID for isolation

        Returns:
            True if field was updated, False if company not found
        """
        updated_company = await self.update(
            id=company_id,
            update_data={field_name: value},
            tenant_id=tenant_id
        )
        return updated_company is not None
