"""Authentication schemas for API requests/responses."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from src.models.user import UserRole


class RegisterRequest(BaseModel):
    """Request schema for user registration."""

    email: EmailStr = Field(description="User's email address")
    password: str = Field(
        min_length=8,
        max_length=128,
        description="User's password"
    )
    full_name: str = Field(
        min_length=2,
        max_length=255,
        description="User's full name"
    )
    role: Optional[UserRole] = Field(
        default=UserRole.BID_MANAGER,
        description="User role"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!",
                "full_name": "John Doe",
                "role": "bid_manager"
            }
        }
    }


class LoginRequest(BaseModel):
    """Request schema for user login."""

    email: EmailStr = Field(description="User's email address")
    password: str = Field(description="User's password")

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!"
            }
        }
    }


class RefreshRequest(BaseModel):
    """Request schema for token refresh."""

    refresh_token: str = Field(description="Valid refresh token")

    model_config = {
        "json_schema_extra": {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }
    }


class UserResponse(BaseModel):
    """Response schema for user information."""

    id: UUID = Field(description="User's unique identifier")
    email: str = Field(description="User's email address")
    full_name: str = Field(description="User's full name")
    role: UserRole = Field(description="User's role")
    is_active: bool = Field(description="Whether the user account is active")
    tenant_id: Optional[UUID] = Field(description="Tenant ID for multi-tenancy")
    created_at: datetime = Field(description="Account creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "user@example.com",
                "full_name": "John Doe",
                "role": "bid_manager",
                "is_active": True,
                "tenant_id": None,
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z"
            }
        }
    }


class TokenResponse(BaseModel):
    """Response schema for authentication tokens."""

    access_token: str = Field(description="JWT access token")
    refresh_token: str = Field(description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(description="Access token expiration time in seconds")

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800
            }
        }
    }


class LoginResponse(BaseModel):
    """Response schema for successful login."""

    user: UserResponse = Field(description="User information")
    tokens: TokenResponse = Field(description="Authentication tokens")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "email": "user@example.com",
                    "full_name": "John Doe",
                    "role": "bid_manager",
                    "is_active": True,
                    "tenant_id": None,
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-01-15T10:30:00Z"
                },
                "tokens": {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                    "expires_in": 1800
                }
            }
        }
    }


class RefreshResponse(BaseModel):
    """Response schema for token refresh."""

    tokens: TokenResponse = Field(description="New authentication tokens")

    model_config = {
        "json_schema_extra": {
            "example": {
                "tokens": {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                    "expires_in": 1800
                }
            }
        }
    }
