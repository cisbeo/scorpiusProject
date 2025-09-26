"""Base repository with generic CRUD operations."""

from src.utils.datetime_utils import utc_now
from typing import Any, Generic, Optional, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.base import BaseModel

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):
    """
    Base repository providing common CRUD operations.

    Implements the Repository pattern with:
    - Generic CRUD operations
    - Soft delete support
    - Tenant isolation (prepared for multi-tenancy)
    - Async/await support
    - Query optimization
    """

    def __init__(self, model: type[ModelType], db_session: AsyncSession):
        """
        Initialize repository with model type and database session.

        Args:
            model: SQLAlchemy model class
            db_session: Async database session
        """
        self.model = model
        self.db = db_session

    async def create(self, **kwargs: Any) -> ModelType:
        """
        Create a new record.

        Args:
            **kwargs: Field values for the new record

        Returns:
            Created model instance
        """
        instance = self.model(**kwargs)
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def get_by_id(
        self,
        id: UUID,
        include_deleted: bool = False,
        tenant_id: Optional[UUID] = None
    ) -> Optional[ModelType]:
        """
        Get record by ID.

        Args:
            id: Record UUID
            include_deleted: Whether to include soft-deleted records
            tenant_id: Tenant ID for isolation (nullable for MVP)

        Returns:
            Model instance if found, None otherwise
        """
        query = select(self.model).where(self.model.id == id)

        # Apply tenant isolation if tenant_id is provided
        if tenant_id is not None:
            query = query.where(self.model.tenant_id == tenant_id)

        # Filter out soft-deleted records unless specifically requested
        if not include_deleted:
            query = query.where(self.model.deleted_at.is_(None))

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
        tenant_id: Optional[UUID] = None,
        **filters: Any
    ) -> list[ModelType]:
        """
        Get multiple records with pagination and filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            include_deleted: Whether to include soft-deleted records
            tenant_id: Tenant ID for isolation
            **filters: Additional filters to apply

        Returns:
            List of model instances
        """
        query = select(self.model)

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(self.model.tenant_id == tenant_id)

        # Filter out soft-deleted records
        if not include_deleted:
            query = query.where(self.model.deleted_at.is_(None))

        # Apply additional filters
        for field, value in filters.items():
            if hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == value)

        # Apply pagination
        query = query.offset(skip).limit(limit)

        # Order by created_at for consistent pagination
        query = query.order_by(self.model.created_at.desc())

        result = await self.db.execute(query)
        return result.scalars().all()

    async def update(
        self,
        id: UUID,
        update_data: dict[str, Any],
        tenant_id: Optional[UUID] = None
    ) -> Optional[ModelType]:
        """
        Update record by ID.

        Args:
            id: Record UUID
            update_data: Fields to update
            tenant_id: Tenant ID for isolation

        Returns:
            Updated model instance if found, None otherwise
        """
        instance = await self.get_by_id(id, tenant_id=tenant_id)
        if instance is None:
            return None

        # Update fields
        for field, value in update_data.items():
            if hasattr(instance, field):
                setattr(instance, field, value)

        # Force update of updated_at timestamp
        instance.updated_at = utc_now()

        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def delete(
        self,
        id: UUID,
        soft_delete: bool = True,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Delete record by ID.

        Args:
            id: Record UUID
            soft_delete: Whether to soft delete (True) or hard delete (False)
            tenant_id: Tenant ID for isolation

        Returns:
            True if record was deleted, False if not found
        """
        instance = await self.get_by_id(id, tenant_id=tenant_id)
        if instance is None:
            return False

        if soft_delete:
            instance.soft_delete()
            await self.db.commit()
        else:
            await self.db.delete(instance)
            await self.db.commit()

        return True

    async def restore(self, id: UUID, tenant_id: Optional[UUID] = None) -> bool:
        """
        Restore soft-deleted record.

        Args:
            id: Record UUID
            tenant_id: Tenant ID for isolation

        Returns:
            True if record was restored, False if not found
        """
        instance = await self.get_by_id(id, include_deleted=True, tenant_id=tenant_id)
        if instance is None or not instance.is_deleted:
            return False

        instance.restore()
        await self.db.commit()
        return True

    async def count(
        self,
        include_deleted: bool = False,
        tenant_id: Optional[UUID] = None,
        **filters: Any
    ) -> int:
        """
        Count records with optional filtering.

        Args:
            include_deleted: Whether to include soft-deleted records
            tenant_id: Tenant ID for isolation
            **filters: Additional filters to apply

        Returns:
            Number of matching records
        """
        query = select(self.model)

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(self.model.tenant_id == tenant_id)

        # Filter out soft-deleted records
        if not include_deleted:
            query = query.where(self.model.deleted_at.is_(None))

        # Apply additional filters
        for field, value in filters.items():
            if hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == value)

        result = await self.db.execute(query)
        return len(result.scalars().all())

    async def exists(
        self,
        id: UUID,
        include_deleted: bool = False,
        tenant_id: Optional[UUID] = None
    ) -> bool:
        """
        Check if record exists.

        Args:
            id: Record UUID
            include_deleted: Whether to include soft-deleted records
            tenant_id: Tenant ID for isolation

        Returns:
            True if record exists, False otherwise
        """
        instance = await self.get_by_id(id, include_deleted=include_deleted, tenant_id=tenant_id)
        return instance is not None

    async def get_by_field(
        self,
        field_name: str,
        field_value: Any,
        include_deleted: bool = False,
        tenant_id: Optional[UUID] = None
    ) -> Optional[ModelType]:
        """
        Get record by specific field value.

        Args:
            field_name: Name of the field to search by
            field_value: Value to search for
            include_deleted: Whether to include soft-deleted records
            tenant_id: Tenant ID for isolation

        Returns:
            Model instance if found, None otherwise
        """
        if not hasattr(self.model, field_name):
            return None

        query = select(self.model).where(getattr(self.model, field_name) == field_value)

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(self.model.tenant_id == tenant_id)

        # Filter out soft-deleted records
        if not include_deleted:
            query = query.where(self.model.deleted_at.is_(None))

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def bulk_create(self, instances_data: list[dict[str, Any]]) -> list[ModelType]:
        """
        Create multiple records in bulk.

        Args:
            instances_data: List of dictionaries with field values

        Returns:
            List of created model instances
        """
        instances = [self.model(**data) for data in instances_data]
        self.db.add_all(instances)
        await self.db.commit()

        # Refresh all instances
        for instance in instances:
            await self.db.refresh(instance)

        return instances

    async def bulk_update(
        self,
        updates: list[dict[str, Any]],
        tenant_id: Optional[UUID] = None
    ) -> list[ModelType]:
        """
        Update multiple records in bulk.

        Args:
            updates: List of dicts containing 'id' and update fields
            tenant_id: Tenant ID for isolation

        Returns:
            List of updated model instances
        """
        updated_instances = []

        for update_data in updates:
            if "id" not in update_data:
                continue

            instance_id = update_data.pop("id")
            instance = await self.update(instance_id, update_data, tenant_id=tenant_id)
            if instance:
                updated_instances.append(instance)

        return updated_instances
