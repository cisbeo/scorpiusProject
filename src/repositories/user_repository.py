"""User repository for user-specific data operations."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User, UserRole
from src.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """
    Repository for User model with user-specific operations.

    Extends BaseRepository with user-specific methods:
    - Email-based lookups
    - Role-based queries
    - Active user filtering
    - Authentication support
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize user repository."""
        super().__init__(User, db_session)

    async def get_by_email(
        self,
        email: str,
        include_deleted: bool = False,
        tenant_id: Optional[UUID] = None
    ) -> Optional[User]:
        """
        Get user by email address.

        Args:
            email: User's email address
            include_deleted: Whether to include soft-deleted users
            tenant_id: Tenant ID for isolation

        Returns:
            User instance if found, None otherwise
        """
        return await self.get_by_field(
            field_name="email",
            field_value=email.lower(),
            include_deleted=include_deleted,
            tenant_id=tenant_id
        )

    async def create_user(
        self,
        email: str,
        password_hash: str,
        full_name: str,
        role: UserRole = UserRole.BID_MANAGER,
        is_active: bool = True,
        tenant_id: Optional[UUID] = None
    ) -> User:
        """
        Create a new user with validation.

        Args:
            email: User's email address
            password_hash: Hashed password
            full_name: User's full name
            role: User role (default: BID_MANAGER)
            is_active: Whether user is active (default: True)
            tenant_id: Tenant ID for multi-tenancy

        Returns:
            Created user instance

        Raises:
            ValueError: If email already exists
        """
        # Check if email already exists
        existing_user = await self.get_by_email(email)
        if existing_user:
            raise ValueError(f"User with email {email} already exists")

        return await self.create(
            email=email.lower(),
            password_hash=password_hash,
            full_name=full_name,
            role=role,
            is_active=is_active,
            tenant_id=tenant_id
        )

    async def get_active_users(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[UUID] = None
    ) -> list[User]:
        """
        Get all active users with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation

        Returns:
            List of active user instances
        """
        return await self.get_multi(
            skip=skip,
            limit=limit,
            tenant_id=tenant_id,
            is_active=True
        )

    async def get_users_by_role(
        self,
        role: UserRole,
        skip: int = 0,
        limit: int = 100,
        include_inactive: bool = False,
        tenant_id: Optional[UUID] = None
    ) -> list[User]:
        """
        Get users by role with pagination.

        Args:
            role: User role to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return
            include_inactive: Whether to include inactive users
            tenant_id: Tenant ID for isolation

        Returns:
            List of user instances with specified role
        """
        filters = {"role": role}
        if not include_inactive:
            filters["is_active"] = True

        return await self.get_multi(
            skip=skip,
            limit=limit,
            tenant_id=tenant_id,
            **filters
        )

    async def activate_user(self, user_id: UUID, tenant_id: Optional[UUID] = None) -> bool:
        """
        Activate a user account.

        Args:
            user_id: User UUID
            tenant_id: Tenant ID for isolation

        Returns:
            True if user was activated, False if not found
        """
        updated_user = await self.update(
            id=user_id,
            update_data={"is_active": True},
            tenant_id=tenant_id
        )
        return updated_user is not None

    async def deactivate_user(self, user_id: UUID, tenant_id: Optional[UUID] = None) -> bool:
        """
        Deactivate a user account.

        Args:
            user_id: User UUID
            tenant_id: Tenant ID for isolation

        Returns:
            True if user was deactivated, False if not found
        """
        updated_user = await self.update(
            id=user_id,
            update_data={"is_active": False},
            tenant_id=tenant_id
        )
        return updated_user is not None

    async def update_password(
        self,
        user_id: UUID,
        new_password_hash: str,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Update user's password hash.

        Args:
            user_id: User UUID
            new_password_hash: New hashed password
            tenant_id: Tenant ID for isolation

        Returns:
            True if password was updated, False if user not found
        """
        updated_user = await self.update(
            id=user_id,
            update_data={"password_hash": new_password_hash},
            tenant_id=tenant_id
        )
        return updated_user is not None

    async def update_role(
        self,
        user_id: UUID,
        new_role: UserRole,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Update user's role.

        Args:
            user_id: User UUID
            new_role: New user role
            tenant_id: Tenant ID for isolation

        Returns:
            True if role was updated, False if user not found
        """
        updated_user = await self.update(
            id=user_id,
            update_data={"role": new_role},
            tenant_id=tenant_id
        )
        return updated_user is not None

    async def email_exists(
        self,
        email: str,
        exclude_user_id: Optional[UUID] = None,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Check if email already exists in the system.

        Args:
            email: Email address to check
            exclude_user_id: User ID to exclude from check (for updates)
            tenant_id: Tenant ID for isolation

        Returns:
            True if email exists, False otherwise
        """
        query = select(User).where(User.email == email.lower())

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(User.tenant_id == tenant_id)

        # Exclude specific user (useful for updates)
        if exclude_user_id is not None:
            query = query.where(User.id != exclude_user_id)

        # Only check active, non-deleted users
        query = query.where(
            User.is_active.is_(True),
            User.deleted_at.is_(None)
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def count_by_role(
        self,
        role: UserRole,
        include_inactive: bool = False,
        tenant_id: Optional[UUID] = None
    ) -> int:
        """
        Count users by role.

        Args:
            role: User role to count
            include_inactive: Whether to include inactive users
            tenant_id: Tenant ID for isolation

        Returns:
            Number of users with specified role
        """
        filters = {"role": role}
        if not include_inactive:
            filters["is_active"] = True

        return await self.count(tenant_id=tenant_id, **filters)

    async def get_admin_users(
        self,
        tenant_id: Optional[UUID] = None
    ) -> list[User]:
        """
        Get all active admin users.

        Args:
            tenant_id: Tenant ID for isolation

        Returns:
            List of active admin users
        """
        return await self.get_users_by_role(
            role=UserRole.ADMIN,
            include_inactive=False,
            tenant_id=tenant_id
        )
