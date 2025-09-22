"""Authentication and authorization middleware for FastAPI."""

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.db.session import async_session_scope
from src.models.user import User, UserRole
from src.services.auth.auth_service import (
    AuthenticationError,
    AuthorizationError,
    AuthService,
)


class AuthMiddleware:
    """
    Authentication and authorization middleware.

    Provides decorators and utilities for:
    - Token validation
    - User authentication
    - Role-based authorization
    - Route protection
    """

    def __init__(self):
        """Initialize auth middleware."""
        self.security = HTTPBearer(auto_error=False)

    async def get_current_user(
        self,
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = None
    ) -> Optional[User]:
        """
        Get current authenticated user from request.

        Args:
            request: FastAPI request object
            credentials: Optional HTTP bearer credentials

        Returns:
            User instance if authenticated, None otherwise
        """
        if not credentials:
            return None

        try:
            # Get database session
            async with async_session_scope() as db:
                auth_service = AuthService(db)
                user = await auth_service.get_user_by_token(credentials.credentials)
                return user

        except Exception:
            return None

    async def require_auth(
        self,
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = None
    ) -> User:
        """
        Require user authentication.

        Args:
            request: FastAPI request object
            credentials: Optional HTTP bearer credentials

        Returns:
            Authenticated user instance

        Raises:
            HTTPException: If user is not authenticated
        """
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            # Get database session
            async with async_session_scope() as db:
                auth_service = AuthService(db)
                user = await auth_service.verify_token_and_get_user(credentials.credentials)
                return user

        except AuthenticationError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service error"
            )

    async def require_role(
        self,
        request: Request,
        required_role: UserRole,
        credentials: Optional[HTTPAuthorizationCredentials] = None
    ) -> User:
        """
        Require user authentication with specific role.

        Args:
            request: FastAPI request object
            required_role: Required user role
            credentials: Optional HTTP bearer credentials

        Returns:
            Authenticated user instance with required role

        Raises:
            HTTPException: If user is not authenticated or doesn't have required role
        """
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            # Get database session
            async with async_session_scope() as db:
                auth_service = AuthService(db)
                user = await auth_service.verify_token_and_get_user(
                    credentials.credentials,
                    required_role=required_role
                )
                return user

        except AuthenticationError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            )
        except AuthorizationError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service error"
            )

    async def require_admin(
        self,
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = None
    ) -> User:
        """
        Require admin authentication.

        Args:
            request: FastAPI request object
            credentials: Optional HTTP bearer credentials

        Returns:
            Authenticated admin user

        Raises:
            HTTPException: If user is not authenticated or not an admin
        """
        return await self.require_role(request, UserRole.ADMIN, credentials)

    async def require_bid_manager(
        self,
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = None
    ) -> User:
        """
        Require bid manager authentication.

        Args:
            request: FastAPI request object
            credentials: Optional HTTP bearer credentials

        Returns:
            Authenticated bid manager user

        Raises:
            HTTPException: If user is not authenticated or not a bid manager
        """
        return await self.require_role(request, UserRole.BID_MANAGER, credentials)

    async def check_resource_permission(
        self,
        user: User,
        resource_type: str,
        action: str,
        resource_id: Optional[UUID] = None
    ) -> bool:
        """
        Check if user has permission for resource action.

        Args:
            user: User instance
            resource_type: Type of resource
            action: Action to perform
            resource_id: Optional specific resource ID

        Returns:
            True if user has permission, False otherwise
        """
        try:
            # Get database session for permission check
            async with async_session_scope() as db:
                auth_service = AuthService(db)
                return await auth_service.check_user_permissions(
                    user=user,
                    resource_type=resource_type,
                    action=action,
                    resource_id=resource_id
                )
        except Exception:
            return False

    async def require_permission(
        self,
        request: Request,
        resource_type: str,
        action: str,
        resource_id: Optional[UUID] = None,
        credentials: Optional[HTTPAuthorizationCredentials] = None
    ) -> User:
        """
        Require user authentication and specific permission.

        Args:
            request: FastAPI request object
            resource_type: Type of resource
            action: Action to perform
            resource_id: Optional specific resource ID
            credentials: Optional HTTP bearer credentials

        Returns:
            Authenticated user with required permission

        Raises:
            HTTPException: If user lacks authentication or permission
        """
        # First require authentication
        user = await self.require_auth(request, credentials)

        # Check permission
        has_permission = await self.check_resource_permission(
            user=user,
            resource_type=resource_type,
            action=action,
            resource_id=resource_id
        )

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions for {action} on {resource_type}"
            )

        return user

    def get_client_ip(self, request: Request) -> Optional[str]:
        """
        Extract client IP address from request.

        Args:
            request: FastAPI request object

        Returns:
            Client IP address if available
        """
        # Try to get real IP from headers (for reverse proxy setups)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, get the first one
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to client host
        if request.client:
            return request.client.host

        return None

    def get_user_agent(self, request: Request) -> Optional[str]:
        """
        Extract user agent from request.

        Args:
            request: FastAPI request object

        Returns:
            User agent string if available
        """
        return request.headers.get("User-Agent")

    async def log_auth_event(
        self,
        request: Request,
        user: Optional[User],
        action: str,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
        """
        Log authentication/authorization events for audit.

        Args:
            request: FastAPI request object
            user: User instance (if available)
            action: Action being performed
            success: Whether the action was successful
            error_message: Optional error message for failed actions
        """
        try:
            async with async_session_scope() as db:
                from src.repositories.audit_repository import AuditRepository
                audit_repo = AuditRepository(db)

                await audit_repo.log_action(
                    action=f"auth_{action}",
                    resource_type="authentication",
                    resource_id=user.id if user else UUID('00000000-0000-0000-0000-000000000000'),
                    user_id=user.id if user else None,
                    ip_address=self.get_client_ip(request),
                    user_agent=self.get_user_agent(request),
                    metadata={
                        "path": str(request.url.path),
                        "method": request.method,
                        "success": success,
                        "error": error_message,
                        "timestamp": request.state.__dict__.get("request_time", "unknown")
                    },
                    tenant_id=getattr(user, 'tenant_id', None) if user else None
                )
        except Exception:
            # Don't let audit logging failures break the request
            pass


# Global instance for use in dependency injection
auth_middleware = AuthMiddleware()


# FastAPI dependencies for common auth patterns
from fastapi import Depends

# Create HTTPBearer security scheme
security = HTTPBearer()

async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[User]:
    """
    FastAPI dependency to get current user (optional).

    Args:
        request: FastAPI request object
        credentials: HTTP bearer credentials

    Returns:
        User instance if authenticated, None otherwise
    """
    return await auth_middleware.get_current_user(request, credentials)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    FastAPI dependency to require authentication.

    Args:
        request: FastAPI request object
        credentials: HTTP bearer credentials

    Returns:
        Authenticated user instance

    Raises:
        HTTPException: If user is not authenticated
    """
    return await auth_middleware.require_auth(request, credentials)


async def get_current_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    FastAPI dependency to require admin authentication.

    Args:
        request: FastAPI request object
        credentials: HTTP bearer credentials

    Returns:
        Authenticated admin user

    Raises:
        HTTPException: If user is not authenticated or not an admin
    """
    return await auth_middleware.require_admin(request, credentials)


async def get_current_bid_manager(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    FastAPI dependency to require bid manager authentication.

    Args:
        request: FastAPI request object
        credentials: HTTP bearer credentials

    Returns:
        Authenticated bid manager user

    Raises:
        HTTPException: If user is not authenticated or not a bid manager
    """
    return await auth_middleware.require_bid_manager(request, credentials)
