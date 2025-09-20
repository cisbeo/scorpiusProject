"""Global test configuration and fixtures."""

import asyncio
import os
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import Settings, get_settings
from src.db.base import Base
from src.db.session import AsyncSessionLocal

# Override settings for testing
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test_scorpius"


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Get test settings."""
    return Settings(
        app_env="testing",
        database_url="postgresql://test:test@localhost:5432/test_scorpius",
        jwt_secret_key="test-secret-key",
        secret_key="test-app-secret",
    )


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_db(settings) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for testing."""
    # Create test database engine
    engine = create_async_engine(
        settings.get_database_url(async_mode=True),
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session

    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
def sync_db(settings) -> Generator[Session, None, None]:
    """Create sync database session for testing."""
    # Create test database engine
    engine = create_engine(
        settings.get_database_url(async_mode=False),
        echo=False,
    )

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Create session
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    session = SessionLocal()
    yield session

    # Clean up
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(settings) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing API endpoints."""
    # Import here to avoid circular imports
    from src.api.v1.app import app

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers(settings) -> dict:
    """Create authentication headers for testing."""
    from jose import jwt

    # Create test token
    token_data = {
        "sub": "test-user-id",
        "email": "test@example.com",
        "role": "bid_manager",
    }
    token = jwt.encode(
        token_data,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(settings) -> dict:
    """Create admin authentication headers for testing."""
    from jose import jwt

    # Create admin token
    token_data = {
        "sub": "admin-user-id",
        "email": "admin@example.com",
        "role": "admin",
    }
    token = jwt.encode(
        token_data,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_pdf_file():
    """Create a sample PDF file for testing."""
    import io
    from pypdf2 import PdfWriter, PdfReader

    # Create a simple PDF
    pdf_writer = PdfWriter()
    pdf_writer.add_blank_page(width=200, height=200)

    # Write to bytes
    pdf_bytes = io.BytesIO()
    pdf_writer.write(pdf_bytes)
    pdf_bytes.seek(0)

    return pdf_bytes


@pytest.fixture
def sample_user_data():
    """Sample user registration data."""
    return {
        "email": "test.user@example.com",
        "password": "SecurePassword123!",
        "full_name": "Test User",
        "role": "bid_manager",
    }


@pytest.fixture
def sample_company_data():
    """Sample company profile data."""
    return {
        "company_name": "Test Company SARL",
        "siret": "12345678901234",
        "description": "Test company description",
        "capabilities_json": [
            {"name": "Web Development", "keywords": ["Python", "FastAPI"]},
            {"name": "Cloud Services", "keywords": ["AWS", "Docker"]},
        ],
        "certifications_json": [
            {"name": "ISO 9001", "valid_until": "2025-12-31"},
        ],
        "team_size": 50,
        "annual_revenue": 5000000.00,
    }


@pytest.fixture
def sample_document_data():
    """Sample procurement document data."""
    return {
        "title": "Test Procurement",
        "reference_number": "TEST-2024-001",
        "buyer_organization": "Test Organization",
        "submission_deadline": "2024-12-31T23:59:59Z",
        "requirements_json": {
            "technical": ["Requirement 1", "Requirement 2"],
            "functional": ["Requirement 3"],
        },
        "evaluation_criteria_json": {
            "price": 40,
            "technical": 35,
            "experience": 25,
        },
    }


# Markers for test categories
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.contract = pytest.mark.contract
pytest.mark.performance = pytest.mark.performance