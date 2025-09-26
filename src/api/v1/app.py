"""FastAPI application initialization and configuration."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from src.api.v1.router import api_router
from src.core.config import get_settings
from src.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Handles startup and shutdown tasks:
    - Database initialization
    - Connection pool setup
    - Cleanup on shutdown
    """
    # Startup
    settings = get_settings()

    # Setup logging
    setup_logging(
        log_level=settings.log_level
    )

    # Initialize database (if needed)
    # In production, you might want to run migrations here

    yield

    # Shutdown
    # Cleanup tasks if needed


def create_application() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    settings = get_settings()

    # Create FastAPI application
    app = FastAPI(
        title="Scorpius Project API",
        description="""
        **French Procurement Bid Management System**

        A comprehensive API for managing French public procurement documents with intelligent analysis capabilities.

        ## Features

        * **Document Processing**: Upload and analyze procurement PDFs
        * **Capability Matching**: Match company capabilities with requirements
        * **Secure Authentication**: JWT-based user authentication
        * **Company Profiles**: Manage company information and capabilities
        * **Analysis Engine**: Intelligent bid recommendation system

        ## Authentication

        Most endpoints require authentication using JWT tokens:

        1. Register or login to get access tokens
        2. Include the token in the Authorization header: `Bearer <token>`
        3. Refresh tokens before they expire

        ## Document Processing Workflow

        1. **Upload** a procurement PDF document
        2. **Process** the document to extract requirements
        3. **Analyze** company capability match
        4. **Generate** bid responses (future feature)

        ## Rate Limiting

        API endpoints are rate limited to ensure fair usage:
        - Authentication: 10 requests per minute
        - Document upload: 5 uploads per minute
        - Other endpoints: 100 requests per minute
        """,
        version="1.0.0",
        openapi_url=f"/api/{settings.api_version}/openapi.json",
        docs_url=f"/api/{settings.api_version}/docs",
        redoc_url=f"/api/{settings.api_version}/redoc",
        lifespan=lifespan,
        # Security
        openapi_tags=[
            {
                "name": "Authentication",
                "description": "User authentication and token management"
            },
            {
                "name": "Documents",
                "description": "Document upload, processing, and retrieval"
            },
            {
                "name": "Company Profile",
                "description": "Company information and capabilities management"
            },
            {
                "name": "Analysis",
                "description": "Capability matching and bid analysis"
            },
            {
                "name": "Health",
                "description": "System health monitoring"
            },
            {
                "name": "Search",
                "description": "Vector search and RAG capabilities"
            }
        ]
    )

    # Add security headers middleware
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"]  # Allow all hosts in production for flexibility
        )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
        max_age=3600  # 1 hour
    )

    # Include API router
    app.include_router(
        api_router,
        prefix=f"/api/{settings.api_version}"
    )

    # Root endpoint
    @app.get("/", include_in_schema=False)
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "Scorpius Project API",
            "version": "1.0.0",
            "description": "French Procurement Bid Management System",
            "docs_url": f"/api/{settings.api_version}/docs",
            "openapi_url": f"/api/{settings.api_version}/openapi.json",
            "health_check": f"/api/{settings.api_version}/health"
        }

    # Health check at root level (for load balancers)
    @app.get("/health", include_in_schema=False)
    async def health():
        """Simple health check for load balancers."""
        return {"status": "ok"}

    return app


# Create application instance
app = create_application()
