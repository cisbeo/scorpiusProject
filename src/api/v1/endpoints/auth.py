"""Authentication endpoints for user registration, login, and token management."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from src.core.config import get_settings
from src.db.session import get_async_db

# Helper functions defined at the end of this file
from src.services.auth import AuthenticationError, AuthService

# Create router for authentication endpoints
router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


@router.post(
    "/register",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with email and password",
    responses={
        201: {
            "description": "User successfully registered",
            "model": LoginResponse
        },
        400: {
            "description": "Registration failed due to validation errors",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Email already exists or password validation failed"
                    }
                }
            }
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "email"],
                                "msg": "field required",
                                "type": "value_error.missing"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def register_user(
    request: Request,
    user_data: RegisterRequest,
    db: AsyncSession = Depends(get_async_db)
) -> LoginResponse:
    """
    Register a new user account.

    This endpoint creates a new user account with the provided information
    and returns both user data and authentication tokens.

    - **email**: Valid email address (will be normalized to lowercase)
    - **password**: Strong password meeting security requirements
    - **full_name**: User's full name
    - **role**: User role (defaults to 'bid_manager')

    Password requirements:
    - At least 8 characters long
    - Contains uppercase and lowercase letters
    - Contains at least one digit
    - Contains at least one special character
    """
    try:
        # Get client information for audit logging
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)

        # Initialize auth service
        auth_service = AuthService(db)

        # Register user
        user, tokens = await auth_service.register_user(
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
            role=user_data.role,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Create response
        user_response = UserResponse.model_validate(user)
        token_response = TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_in=settings.jwt_access_token_expire_minutes * 60
        )

        return LoginResponse(
            user=user_response,
            tokens=token_response
        )

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception:
        # Log unexpected errors but don't expose details
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed due to internal error"
        )


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user",
    description="Authenticate user with email and password",
    responses={
        200: {
            "description": "User successfully authenticated",
            "model": LoginResponse
        },
        401: {
            "description": "Authentication failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid email or password"
                    }
                }
            }
        },
        422: {
            "description": "Validation error"
        }
    }
)
async def login_user(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_async_db)
) -> LoginResponse:
    """
    Authenticate a user with email and password.

    This endpoint validates user credentials and returns authentication tokens
    along with user information if login is successful.

    - **email**: User's registered email address
    - **password**: User's password

    Returns JWT tokens that should be used for subsequent API requests.
    The access token has a short expiration time, while the refresh token
    can be used to obtain new access tokens.
    """
    try:
        # Get client information for audit logging
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)

        # Initialize auth service
        auth_service = AuthService(db)

        # Authenticate user
        user, tokens = await auth_service.authenticate_user(
            email=login_data.email,
            password=login_data.password,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Create response
        user_response = UserResponse.model_validate(user)
        token_response = TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_in=settings.jwt_access_token_expire_minutes * 60
        )

        return LoginResponse(
            user=user_response,
            tokens=token_response
        )

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception:
        # Log unexpected errors but don't expose details
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed due to internal error"
        )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Get new access token using refresh token",
    responses={
        200: {
            "description": "Tokens successfully refreshed",
            "model": RefreshResponse
        },
        401: {
            "description": "Invalid or expired refresh token",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Token refresh failed: Invalid or expired refresh token"
                    }
                }
            }
        },
        422: {
            "description": "Validation error"
        }
    }
)
async def refresh_token(
    request: Request,
    refresh_data: RefreshRequest,
    db: AsyncSession = Depends(get_async_db)
) -> RefreshResponse:
    """
    Refresh access token using a valid refresh token.

    This endpoint allows clients to obtain new authentication tokens
    without requiring the user to log in again. The refresh token
    must be valid and not expired.

    - **refresh_token**: Valid JWT refresh token

    Returns new access and refresh tokens. The old tokens are invalidated
    (in stateless JWT implementation, they expire naturally).

    Security note: Refresh tokens have longer expiration times but should
    be stored securely and rotated regularly.
    """
    try:
        # Get client information for audit logging
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)

        # Initialize auth service
        auth_service = AuthService(db)

        # Refresh tokens
        tokens = await auth_service.refresh_token(
            refresh_token=refresh_data.refresh_token,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Create response
        token_response = TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_in=settings.jwt_access_token_expire_minutes * 60
        )

        return RefreshResponse(tokens=token_response)

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception:
        # Log unexpected errors but don't expose details
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed due to internal error"
        )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout user",
    description="Logout user (for audit logging)",
    responses={
        204: {
            "description": "User successfully logged out"
        },
        401: {
            "description": "Authentication required"
        }
    }
)
async def logout_user(
    request: Request,
    current_user = Depends(lambda r, db=Depends(get_async_db): get_current_user_from_request(r, db))
) -> None:
    """
    Logout the current user.

    This endpoint primarily serves for audit logging purposes since JWT tokens
    are stateless. Clients should discard tokens on logout.

    The actual token invalidation happens client-side by discarding the tokens.
    This endpoint logs the logout event for security auditing.

    Requires valid authentication token in Authorization header.
    """
    try:
        # Get client information for audit logging
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)

        # Initialize auth service for logout logging
        auth_service = AuthService(current_user.db)

        # Log logout event
        await auth_service.logout_user(
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Return 204 No Content (successful logout)
        return

    except Exception:
        # Even if audit logging fails, logout should succeed
        # since JWT tokens are stateless
        return


# Helper function to extract current user from request
async def get_current_user_from_request(request: Request, db: AsyncSession):
    """Helper to get current user from request for logout endpoint."""
    from fastapi.security import HTTPBearer

    from src.middleware.auth import auth_middleware

    security = HTTPBearer()
    credentials = await security(request)

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    user = await auth_middleware.require_auth(request, credentials)
    # Attach db session to user for logout logging
    user.db = db
    return user


def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    # Try to get real IP from headers (for reverse proxy setups)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fallback to client host
    if request.client:
        return request.client.host

    return "unknown"


def get_user_agent(request: Request) -> str:
    """Extract user agent from request."""
    return request.headers.get("User-Agent", "unknown")
