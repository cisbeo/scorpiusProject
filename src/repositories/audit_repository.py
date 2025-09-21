"""Audit repository for audit log operations."""

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.audit import AuditLog
from src.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditLog]):
    """
    Repository for AuditLog model with audit-specific operations.

    Extends BaseRepository with audit-specific methods:
    - Action-based queries
    - User activity tracking
    - Resource monitoring
    - Security event filtering
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize audit repository."""
        super().__init__(AuditLog, db_session)

    async def log_action(
        self,
        action: str,
        resource_type: str,
        resource_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        tenant_id: Optional[UUID] = None
    ) -> AuditLog:
        """
        Log an audit action.

        Args:
            action: Action performed (e.g., "create", "update", "delete")
            resource_type: Type of resource (e.g., "user", "document", "bid_response")
            resource_id: UUID of the affected resource
            user_id: UUID of the user performing the action (None for system events)
            ip_address: Client IP address
            user_agent: Client user agent string
            metadata: Additional metadata for the audit log
            tenant_id: Tenant ID for multi-tenancy

        Returns:
            Created audit log instance
        """
        return await self.create(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata_json=metadata or {},
            tenant_id=tenant_id
        )

    async def get_by_user(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        tenant_id: Optional[UUID] = None
    ) -> list[AuditLog]:
        """
        Get audit logs for a specific user.

        Args:
            user_id: UUID of the user
            skip: Number of records to skip
            limit: Maximum number of records to return
            action: Optional action filter
            resource_type: Optional resource type filter
            tenant_id: Tenant ID for isolation

        Returns:
            List of audit logs for the user
        """
        filters = {"user_id": user_id}
        if action:
            filters["action"] = action
        if resource_type:
            filters["resource_type"] = resource_type

        return await self.get_multi(
            skip=skip,
            limit=limit,
            tenant_id=tenant_id,
            **filters
        )

    async def get_by_resource(
        self,
        resource_type: str,
        resource_id: UUID,
        skip: int = 0,
        limit: int = 100,
        action: Optional[str] = None,
        tenant_id: Optional[UUID] = None
    ) -> list[AuditLog]:
        """
        Get audit logs for a specific resource.

        Args:
            resource_type: Type of resource
            resource_id: UUID of the resource
            skip: Number of records to skip
            limit: Maximum number of records to return
            action: Optional action filter
            tenant_id: Tenant ID for isolation

        Returns:
            List of audit logs for the resource
        """
        filters = {
            "resource_type": resource_type,
            "resource_id": resource_id
        }
        if action:
            filters["action"] = action

        return await self.get_multi(
            skip=skip,
            limit=limit,
            tenant_id=tenant_id,
            **filters
        )

    async def get_by_action(
        self,
        action: str,
        skip: int = 0,
        limit: int = 100,
        resource_type: Optional[str] = None,
        tenant_id: Optional[UUID] = None
    ) -> list[AuditLog]:
        """
        Get audit logs by action type.

        Args:
            action: Action to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return
            resource_type: Optional resource type filter
            tenant_id: Tenant ID for isolation

        Returns:
            List of audit logs with specified action
        """
        filters = {"action": action}
        if resource_type:
            filters["resource_type"] = resource_type

        return await self.get_multi(
            skip=skip,
            limit=limit,
            tenant_id=tenant_id,
            **filters
        )

    async def get_system_events(
        self,
        skip: int = 0,
        limit: int = 100,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        tenant_id: Optional[UUID] = None
    ) -> list[AuditLog]:
        """
        Get system events (logs without a user).

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            action: Optional action filter
            resource_type: Optional resource type filter
            tenant_id: Tenant ID for isolation

        Returns:
            List of system audit logs
        """
        query = select(AuditLog).where(AuditLog.user_id.is_(None))

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(AuditLog.tenant_id == tenant_id)

        # Apply filters
        if action:
            query = query.where(AuditLog.action == action)
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)

        # Filter out soft-deleted records
        query = query.where(AuditLog.deleted_at.is_(None))

        # Apply pagination and ordering
        query = query.offset(skip).limit(limit).order_by(
            AuditLog.created_at.desc()
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_user_events(
        self,
        skip: int = 0,
        limit: int = 100,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        tenant_id: Optional[UUID] = None
    ) -> list[AuditLog]:
        """
        Get user events (logs with a user).

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            action: Optional action filter
            resource_type: Optional resource type filter
            tenant_id: Tenant ID for isolation

        Returns:
            List of user audit logs
        """
        query = select(AuditLog).where(AuditLog.user_id.is_not(None))

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(AuditLog.tenant_id == tenant_id)

        # Apply filters
        if action:
            query = query.where(AuditLog.action == action)
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)

        # Filter out soft-deleted records
        query = query.where(AuditLog.deleted_at.is_(None))

        # Apply pagination and ordering
        query = query.offset(skip).limit(limit).order_by(
            AuditLog.created_at.desc()
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_recent_activity(
        self,
        hours: int = 24,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[UUID] = None,
        tenant_id: Optional[UUID] = None
    ) -> list[AuditLog]:
        """
        Get recent audit activity.

        Args:
            hours: Number of hours to look back
            skip: Number of records to skip
            limit: Maximum number of records to return
            user_id: Optional user filter
            tenant_id: Tenant ID for isolation

        Returns:
            List of recent audit logs
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        query = select(AuditLog).where(
            AuditLog.created_at >= cutoff_time
        )

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(AuditLog.tenant_id == tenant_id)

        # Apply user filter
        if user_id is not None:
            query = query.where(AuditLog.user_id == user_id)

        # Filter out soft-deleted records
        query = query.where(AuditLog.deleted_at.is_(None))

        # Apply pagination and ordering
        query = query.offset(skip).limit(limit).order_by(
            AuditLog.created_at.desc()
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_security_events(
        self,
        skip: int = 0,
        limit: int = 100,
        hours: int = 24,
        tenant_id: Optional[UUID] = None
    ) -> list[AuditLog]:
        """
        Get security-related audit events.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            hours: Number of hours to look back
            tenant_id: Tenant ID for isolation

        Returns:
            List of security audit logs
        """
        security_actions = [
            "login",
            "login_failed",
            "logout",
            "password_change",
            "permission_denied",
            "account_locked",
            "account_unlocked"
        ]

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        query = select(AuditLog).where(
            AuditLog.action.in_(security_actions),
            AuditLog.created_at >= cutoff_time
        )

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(AuditLog.tenant_id == tenant_id)

        # Filter out soft-deleted records
        query = query.where(AuditLog.deleted_at.is_(None))

        # Apply pagination and ordering
        query = query.offset(skip).limit(limit).order_by(
            AuditLog.created_at.desc()
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_by_ip_address(
        self,
        ip_address: str,
        skip: int = 0,
        limit: int = 100,
        hours: int = 24,
        tenant_id: Optional[UUID] = None
    ) -> list[AuditLog]:
        """
        Get audit logs from a specific IP address.

        Args:
            ip_address: IP address to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return
            hours: Number of hours to look back
            tenant_id: Tenant ID for isolation

        Returns:
            List of audit logs from the IP address
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        query = select(AuditLog).where(
            AuditLog.ip_address == ip_address,
            AuditLog.created_at >= cutoff_time
        )

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(AuditLog.tenant_id == tenant_id)

        # Filter out soft-deleted records
        query = query.where(AuditLog.deleted_at.is_(None))

        # Apply pagination and ordering
        query = query.offset(skip).limit(limit).order_by(
            AuditLog.created_at.desc()
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_with_user(
        self,
        audit_log_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> Optional[AuditLog]:
        """
        Get audit log with user relationship loaded.

        Args:
            audit_log_id: Audit log UUID
            tenant_id: Tenant ID for isolation

        Returns:
            Audit log with user if found, None otherwise
        """
        query = select(AuditLog).options(
            selectinload(AuditLog.user)
        ).where(AuditLog.id == audit_log_id)

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(AuditLog.tenant_id == tenant_id)

        # Filter out soft-deleted records
        query = query.where(AuditLog.deleted_at.is_(None))

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def count_by_action(
        self,
        action: str,
        hours: int = 24,
        user_id: Optional[UUID] = None,
        tenant_id: Optional[UUID] = None
    ) -> int:
        """
        Count audit logs by action within time period.

        Args:
            action: Action to count
            hours: Number of hours to look back
            user_id: Optional user filter
            tenant_id: Tenant ID for isolation

        Returns:
            Number of audit logs with specified action
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        query = select(AuditLog).where(
            AuditLog.action == action,
            AuditLog.created_at >= cutoff_time
        )

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(AuditLog.tenant_id == tenant_id)

        # Apply user filter
        if user_id is not None:
            query = query.where(AuditLog.user_id == user_id)

        # Filter out soft-deleted records
        query = query.where(AuditLog.deleted_at.is_(None))

        result = await self.db.execute(query)
        return len(result.scalars().all())

    async def cleanup_old_logs(
        self,
        days: int = 90,
        tenant_id: Optional[UUID] = None
    ) -> int:
        """
        Clean up audit logs older than specified days.

        Args:
            days: Number of days to keep logs
            tenant_id: Tenant ID for isolation

        Returns:
            Number of logs deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = select(AuditLog).where(
            AuditLog.created_at < cutoff_date
        )

        # Apply tenant isolation
        if tenant_id is not None:
            query = query.where(AuditLog.tenant_id == tenant_id)

        # Only delete non-deleted records
        query = query.where(AuditLog.deleted_at.is_(None))

        # Get logs to delete
        result = await self.db.execute(query)
        logs_to_delete = result.scalars().all()

        # Hard delete old logs
        count = 0
        for log in logs_to_delete:
            await self.db.delete(log)
            count += 1

        await self.db.commit()
        return count
