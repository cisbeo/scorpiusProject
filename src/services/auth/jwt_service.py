"""JWT token service for authentication."""

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

import jwt
from jwt.exceptions import DecodeError, ExpiredSignatureError, InvalidTokenError

from src.core.config import get_settings


class JWTService:
    """
    Service for handling JWT token operations.

    Provides methods for:
    - Creating access and refresh tokens
    - Verifying and decoding tokens
    - Token refresh logic
    - Security validation
    """

    def __init__(self):
        """Initialize JWT service with settings."""
        self.settings = get_settings()
        self.secret_key = self.settings.jwt_secret_key
        self.algorithm = self.settings.jwt_algorithm
        self.access_token_expire_minutes = self.settings.jwt_access_token_expire_minutes
        self.refresh_token_expire_days = self.settings.jwt_refresh_token_expire_days

    def create_access_token(
        self,
        user_id: UUID,
        email: str,
        role: str,
        tenant_id: Optional[UUID] = None,
        additional_claims: Optional[dict[str, Any]] = None
    ) -> str:
        """
        Create a JWT access token for a user.

        Args:
            user_id: User's UUID
            email: User's email address
            role: User's role (e.g., 'bid_manager', 'admin')
            tenant_id: Optional tenant ID for multi-tenancy
            additional_claims: Optional additional claims to include

        Returns:
            Encoded JWT access token string

        Raises:
            ValueError: If token generation fails
        """
        try:
            now = datetime.utcnow()
            expire = now + timedelta(minutes=self.access_token_expire_minutes)

            # Standard JWT claims
            payload = {
                "sub": str(user_id),  # Subject (user ID)
                "email": email,
                "role": role,
                "iat": now,  # Issued at
                "exp": expire,  # Expiration time
                "type": "access",  # Token type
                "jti": f"access_{user_id}_{int(now.timestamp())}",  # JWT ID for uniqueness
            }

            # Add tenant ID if provided (for multi-tenancy)
            if tenant_id is not None:
                payload["tenant_id"] = str(tenant_id)

            # Add any additional claims
            if additional_claims:
                payload.update(additional_claims)

            return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

        except Exception as e:
            raise ValueError(f"Failed to create access token: {str(e)}")

    def create_refresh_token(
        self,
        user_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> str:
        """
        Create a JWT refresh token for a user.

        Args:
            user_id: User's UUID
            tenant_id: Optional tenant ID for multi-tenancy

        Returns:
            Encoded JWT refresh token string

        Raises:
            ValueError: If token generation fails
        """
        try:
            now = datetime.utcnow()
            expire = now + timedelta(days=self.refresh_token_expire_days)

            payload = {
                "sub": str(user_id),
                "iat": now,
                "exp": expire,
                "type": "refresh",
                "jti": f"refresh_{user_id}_{int(now.timestamp())}",
            }

            # Add tenant ID if provided
            if tenant_id is not None:
                payload["tenant_id"] = str(tenant_id)

            return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

        except Exception as e:
            raise ValueError(f"Failed to create refresh token: {str(e)}")

    def verify_token(self, token: str) -> dict[str, Any]:
        """
        Verify and decode a JWT token.

        Args:
            token: JWT token string to verify

        Returns:
            Decoded token payload as dictionary

        Raises:
            ExpiredSignatureError: If token has expired
            InvalidTokenError: If token is invalid or malformed
            DecodeError: If token cannot be decoded
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": True}
            )
            return payload

        except ExpiredSignatureError:
            raise ExpiredSignatureError("Token has expired")
        except DecodeError:
            raise DecodeError("Token is invalid or malformed")
        except InvalidTokenError as e:
            raise InvalidTokenError(f"Invalid token: {str(e)}")

    def verify_access_token(self, token: str) -> dict[str, Any]:
        """
        Verify an access token and ensure it's the correct type.

        Args:
            token: JWT access token string

        Returns:
            Decoded token payload

        Raises:
            InvalidTokenError: If token is not an access token
            ExpiredSignatureError: If token has expired
            DecodeError: If token cannot be decoded
        """
        payload = self.verify_token(token)

        if payload.get("type") != "access":
            raise InvalidTokenError("Token is not an access token")

        return payload

    def verify_refresh_token(self, token: str) -> dict[str, Any]:
        """
        Verify a refresh token and ensure it's the correct type.

        Args:
            token: JWT refresh token string

        Returns:
            Decoded token payload

        Raises:
            InvalidTokenError: If token is not a refresh token
            ExpiredSignatureError: If token has expired
            DecodeError: If token cannot be decoded
        """
        payload = self.verify_token(token)

        if payload.get("type") != "refresh":
            raise InvalidTokenError("Token is not a refresh token")

        return payload

    def extract_user_id(self, token: str) -> UUID:
        """
        Extract user ID from a valid token.

        Args:
            token: JWT token string

        Returns:
            User UUID

        Raises:
            InvalidTokenError: If token is invalid or user ID cannot be extracted
        """
        try:
            payload = self.verify_token(token)
            user_id_str = payload.get("sub")

            if not user_id_str:
                raise InvalidTokenError("Token does not contain user ID")

            return UUID(user_id_str)

        except ValueError as e:
            raise InvalidTokenError(f"Invalid user ID in token: {str(e)}")

    def extract_tenant_id(self, token: str) -> Optional[UUID]:
        """
        Extract tenant ID from a valid token (if present).

        Args:
            token: JWT token string

        Returns:
            Tenant UUID if present, None otherwise

        Raises:
            InvalidTokenError: If token is invalid
        """
        try:
            payload = self.verify_token(token)
            tenant_id_str = payload.get("tenant_id")

            if tenant_id_str:
                return UUID(tenant_id_str)
            return None

        except ValueError as e:
            raise InvalidTokenError(f"Invalid tenant ID in token: {str(e)}")

    def is_token_expired(self, token: str) -> bool:
        """
        Check if a token is expired without raising an exception.

        Args:
            token: JWT token string

        Returns:
            True if token is expired, False otherwise
        """
        try:
            self.verify_token(token)
            return False
        except ExpiredSignatureError:
            return True
        except (DecodeError, InvalidTokenError):
            # If token is invalid, consider it as expired
            return True

    def get_token_expiration(self, token: str) -> Optional[datetime]:
        """
        Get the expiration time of a token.

        Args:
            token: JWT token string

        Returns:
            Expiration datetime if token is valid, None otherwise
        """
        try:
            payload = self.verify_token(token)
            exp_timestamp = payload.get("exp")

            if exp_timestamp:
                return datetime.utcfromtimestamp(exp_timestamp)
            return None

        except (ExpiredSignatureError, DecodeError, InvalidTokenError):
            return None

    def get_remaining_time(self, token: str) -> Optional[timedelta]:
        """
        Get the remaining time before token expiration.

        Args:
            token: JWT token string

        Returns:
            Remaining time as timedelta if token is valid, None otherwise
        """
        expiration = self.get_token_expiration(token)
        if expiration:
            remaining = expiration - datetime.utcnow()
            return remaining if remaining.total_seconds() > 0 else timedelta(0)
        return None

    def refresh_access_token(
        self,
        refresh_token: str,
        email: str,
        role: str,
        tenant_id: Optional[UUID] = None
    ) -> str:
        """
        Create a new access token using a valid refresh token.

        Args:
            refresh_token: Valid refresh token
            email: User's email address
            role: User's role
            tenant_id: Optional tenant ID

        Returns:
            New access token string

        Raises:
            InvalidTokenError: If refresh token is invalid
            ExpiredSignatureError: If refresh token has expired
        """
        # Verify the refresh token
        payload = self.verify_refresh_token(refresh_token)
        user_id = UUID(payload["sub"])

        # Create new access token
        return self.create_access_token(
            user_id=user_id,
            email=email,
            role=role,
            tenant_id=tenant_id
        )

    def decode_token_without_verification(self, token: str) -> Optional[dict[str, Any]]:
        """
        Decode token without signature verification (for debugging/inspection).

        Args:
            token: JWT token string

        Returns:
            Decoded payload if token can be decoded, None otherwise

        Warning:
            This method does NOT verify the token signature.
            Use only for debugging or inspection purposes.
        """
        try:
            return jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False}
            )
        except Exception:
            return None

    def create_token_pair(
        self,
        user_id: UUID,
        email: str,
        role: str,
        tenant_id: Optional[UUID] = None
    ) -> dict[str, str]:
        """
        Create both access and refresh tokens for a user.

        Args:
            user_id: User's UUID
            email: User's email address
            role: User's role
            tenant_id: Optional tenant ID

        Returns:
            Dictionary containing both access_token and refresh_token

        Raises:
            ValueError: If token generation fails
        """
        return {
            "access_token": self.create_access_token(
                user_id=user_id,
                email=email,
                role=role,
                tenant_id=tenant_id
            ),
            "refresh_token": self.create_refresh_token(
                user_id=user_id,
                tenant_id=tenant_id
            )
        }
