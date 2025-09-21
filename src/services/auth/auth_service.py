"""User authentication service."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User, UserRole
from src.repositories.audit_repository import AuditRepository
from src.repositories.user_repository import UserRepository
from src.services.auth.jwt_service import JWTService
from src.services.auth.password_service import PasswordService


class AuthenticationError(Exception):
    """Custom exception for authentication errors."""
    pass


class AuthorizationError(Exception):
    """Custom exception for authorization errors."""
    pass


class AuthService:
    """
    Service for handling user authentication and authorization.

    Provides methods for:
    - User registration and login
    - Token management and refresh
    - Password management
    - User session tracking
    - Audit logging for security events
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize authentication service.

        Args:
            db_session: Async database session
        """
        self.db = db_session
        self.user_repo = UserRepository(db_session)
        self.audit_repo = AuditRepository(db_session)
        self.jwt_service = JWTService()
        self.password_service = PasswordService()

    async def register_user(
        self,
        email: str,
        password: str,
        full_name: str,
        role: UserRole = UserRole.BID_MANAGER,
        tenant_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> tuple[User, dict[str, str]]:
        """
        Register a new user.

        Args:
            email: User's email address
            password: Plain text password
            full_name: User's full name
            role: User role (default: BID_MANAGER)
            tenant_id: Tenant ID for multi-tenancy
            ip_address: Client IP address for audit
            user_agent: Client user agent for audit

        Returns:
            Tuple of (created_user, token_pair)

        Raises:
            AuthenticationError: If registration fails
            ValueError: If validation fails
        """
        try:
            # Validate password strength
            is_valid, errors = self.password_service.validate_password_strength(password)
            if not is_valid:
                raise AuthenticationError(f"Password validation failed: {'; '.join(errors)}")

            # Check if password is compromised
            if self.password_service.is_password_compromised(password):
                raise AuthenticationError("Password has been found in data breaches. Please choose a different password.")

            # Hash the password
            password_hash = self.password_service.hash_password(password)

            # Create the user
            user = await self.user_repo.create_user(
                email=email,
                password_hash=password_hash,
                full_name=full_name,
                role=role,
                tenant_id=tenant_id
            )

            # Generate token pair
            tokens = self.jwt_service.create_token_pair(
                user_id=user.id,
                email=user.email,
                role=user.role.value,
                tenant_id=tenant_id
            )

            # Log registration event
            await self.audit_repo.log_action(
                action="user_registered",
                resource_type="user",
                resource_id=user.id,
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    "email": email,
                    "role": role.value,
                    "registration_timestamp": datetime.utcnow().isoformat()
                },
                tenant_id=tenant_id
            )

            return user, tokens

        except ValueError as e:
            # User already exists or validation error
            raise AuthenticationError(str(e))
        except Exception as e:
            # Log failed registration attempt
            await self.audit_repo.log_action(
                action="user_registration_failed",
                resource_type="user",
                resource_id=UUID('00000000-0000-0000-0000-000000000000'),  # Placeholder
                user_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    "email": email,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                },
                tenant_id=tenant_id
            )
            raise AuthenticationError(f"Registration failed: {str(e)}")

    async def authenticate_user(
        self,
        email: str,
        password: str,
        tenant_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> tuple[User, dict[str, str]]:
        """
        Authenticate a user with email and password.

        Args:
            email: User's email address
            password: Plain text password
            tenant_id: Tenant ID for multi-tenancy
            ip_address: Client IP address for audit
            user_agent: Client user agent for audit

        Returns:
            Tuple of (authenticated_user, token_pair)

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Get user by email
            user = await self.user_repo.get_by_email(email, tenant_id=tenant_id)
            if not user:
                raise AuthenticationError("Invalid email or password")

            # Check if user is active
            if not user.is_active:
                raise AuthenticationError("User account is deactivated")

            # Verify password
            if not self.password_service.verify_password(password, user.password_hash):
                # Log failed login attempt
                await self.audit_repo.log_action(
                    action="login_failed",
                    resource_type="user",
                    resource_id=user.id,
                    user_id=user.id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    metadata={
                        "email": email,
                        "reason": "invalid_password",
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    tenant_id=tenant_id
                )
                raise AuthenticationError("Invalid email or password")

            # Generate token pair
            tokens = self.jwt_service.create_token_pair(
                user_id=user.id,
                email=user.email,
                role=user.role.value,
                tenant_id=tenant_id
            )

            # Log successful login
            await self.audit_repo.log_action(
                action="login_success",
                resource_type="user",
                resource_id=user.id,
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    "email": email,
                    "login_timestamp": datetime.utcnow().isoformat()
                },
                tenant_id=tenant_id
            )

            return user, tokens

        except AuthenticationError:
            # Re-raise authentication errors as-is
            raise
        except Exception as e:
            # Log unexpected error
            await self.audit_repo.log_action(
                action="login_error",
                resource_type="user",
                resource_id=UUID('00000000-0000-0000-0000-000000000000'),  # Placeholder
                user_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    "email": email,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                },
                tenant_id=tenant_id
            )
            raise AuthenticationError(f"Login failed: {str(e)}")

    async def refresh_token(
        self,
        refresh_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> dict[str, str]:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Valid refresh token
            ip_address: Client IP address for audit
            user_agent: Client user agent for audit

        Returns:
            New token pair

        Raises:
            AuthenticationError: If token refresh fails
        """
        try:
            # Verify refresh token and extract user ID
            payload = self.jwt_service.verify_refresh_token(refresh_token)
            user_id = UUID(payload["sub"])
            tenant_id = None
            if "tenant_id" in payload:
                tenant_id = UUID(payload["tenant_id"])

            # Get user from database
            user = await self.user_repo.get_by_id(user_id, tenant_id=tenant_id)
            if not user:
                raise AuthenticationError("User not found")

            # Check if user is still active
            if not user.is_active:
                raise AuthenticationError("User account is deactivated")

            # Generate new token pair
            tokens = self.jwt_service.create_token_pair(
                user_id=user.id,
                email=user.email,
                role=user.role.value,
                tenant_id=tenant_id
            )

            # Log token refresh
            await self.audit_repo.log_action(
                action="token_refreshed",
                resource_type="user",
                resource_id=user.id,
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    "email": user.email,
                    "refresh_timestamp": datetime.utcnow().isoformat()
                },
                tenant_id=tenant_id
            )

            return tokens

        except Exception as e:
            # Log failed token refresh
            await self.audit_repo.log_action(
                action="token_refresh_failed",
                resource_type="user",
                resource_id=UUID('00000000-0000-0000-0000-000000000000'),  # Placeholder
                user_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                },
                tenant_id=None
            )
            raise AuthenticationError(f"Token refresh failed: {str(e)}")

    async def logout_user(
        self,
        user_id: UUID,
        tenant_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Log out a user (primarily for audit logging).

        Args:
            user_id: User's UUID
            tenant_id: Tenant ID for multi-tenancy
            ip_address: Client IP address for audit
            user_agent: Client user agent for audit

        Returns:
            True if logout was logged successfully

        Note:
            With JWT tokens, logout is typically handled client-side
            by discarding the tokens. This method primarily logs the event.
        """
        try:
            # Log logout event
            await self.audit_repo.log_action(
                action="logout",
                resource_type="user",
                resource_id=user_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    "logout_timestamp": datetime.utcnow().isoformat()
                },
                tenant_id=tenant_id
            )
            return True

        except Exception:
            return False

    async def change_password(
        self,
        user_id: UUID,
        current_password: str,
        new_password: str,
        tenant_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Change user's password.

        Args:
            user_id: User's UUID
            current_password: Current password for verification
            new_password: New password to set
            tenant_id: Tenant ID for multi-tenancy
            ip_address: Client IP address for audit
            user_agent: Client user agent for audit

        Returns:
            True if password was changed successfully

        Raises:
            AuthenticationError: If password change fails
        """
        try:
            # Get user
            user = await self.user_repo.get_by_id(user_id, tenant_id=tenant_id)
            if not user:
                raise AuthenticationError("User not found")

            # Verify current password
            if not self.password_service.verify_password(current_password, user.password_hash):
                raise AuthenticationError("Current password is incorrect")

            # Validate new password strength
            is_valid, errors = self.password_service.validate_password_strength(new_password)
            if not is_valid:
                raise AuthenticationError(f"New password validation failed: {'; '.join(errors)}")

            # Check if new password is compromised
            if self.password_service.is_password_compromised(new_password):
                raise AuthenticationError("New password has been found in data breaches. Please choose a different password.")

            # Hash new password
            new_password_hash = self.password_service.hash_password(new_password)

            # Update password
            success = await self.user_repo.update_password(
                user_id=user_id,
                new_password_hash=new_password_hash,
                tenant_id=tenant_id
            )

            if success:
                # Log password change
                await self.audit_repo.log_action(
                    action="password_changed",
                    resource_type="user",
                    resource_id=user_id,
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    metadata={
                        "email": user.email,
                        "change_timestamp": datetime.utcnow().isoformat()
                    },
                    tenant_id=tenant_id
                )

            return success

        except AuthenticationError:
            # Re-raise authentication errors
            raise
        except Exception as e:
            # Log password change failure
            await self.audit_repo.log_action(
                action="password_change_failed",
                resource_type="user",
                resource_id=user_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                },
                tenant_id=tenant_id
            )
            raise AuthenticationError(f"Password change failed: {str(e)}")

    async def verify_token_and_get_user(
        self,
        access_token: str,
        required_role: Optional[UserRole] = None
    ) -> User:
        """
        Verify access token and return user.

        Args:
            access_token: JWT access token
            required_role: Optional role requirement for authorization

        Returns:
            User instance if token is valid and user exists

        Raises:
            AuthenticationError: If token is invalid
            AuthorizationError: If user doesn't have required role
        """
        try:
            # Verify token
            payload = self.jwt_service.verify_access_token(access_token)
            user_id = UUID(payload["sub"])
            tenant_id = None
            if "tenant_id" in payload:
                tenant_id = UUID(payload["tenant_id"])

            # Get user from database
            user = await self.user_repo.get_by_id(user_id, tenant_id=tenant_id)
            if not user:
                raise AuthenticationError("User not found")

            # Check if user is active
            if not user.is_active:
                raise AuthenticationError("User account is deactivated")

            # Check role requirement
            if required_role and user.role != required_role:
                raise AuthorizationError(f"Required role: {required_role.value}, user role: {user.role.value}")

            return user

        except (AuthenticationError, AuthorizationError):
            # Re-raise auth errors
            raise
        except Exception as e:
            raise AuthenticationError(f"Token verification failed: {str(e)}")

    async def get_user_by_token(self, access_token: str) -> Optional[User]:
        """
        Get user from access token without raising exceptions.

        Args:
            access_token: JWT access token

        Returns:
            User instance if token is valid, None otherwise
        """
        try:
            return await self.verify_token_and_get_user(access_token)
        except (AuthenticationError, AuthorizationError):
            return None

    async def check_user_permissions(
        self,
        user: User,
        resource_type: str,
        action: str,
        resource_id: Optional[UUID] = None
    ) -> bool:
        """
        Check if user has permission to perform action on resource.

        Args:
            user: User instance
            resource_type: Type of resource (e.g., 'document', 'bid_response')
            action: Action to perform (e.g., 'read', 'write', 'delete')
            resource_id: Optional specific resource ID

        Returns:
            True if user has permission, False otherwise

        Note:
            This is a basic implementation. In production, you might want
            a more sophisticated RBAC (Role-Based Access Control) system.
        """
        # Admin users have full access
        if user.is_admin:
            return True

        # Bid managers have full access to most resources
        if user.is_bid_manager:
            # Bid managers can perform most actions
            if action in ["read", "write", "create", "update"]:
                return True
            # But cannot delete certain critical resources
            if action == "delete" and resource_type in ["user", "audit_log"]:
                return False
            return True

        # Default: no permission
        return False
