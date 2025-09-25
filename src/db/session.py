"""Database session configuration and management."""

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

from src.core.config import get_settings

settings = get_settings()

# Determine if we're using SQLite for testing
database_url = settings.get_database_url(async_mode=False)
is_sqlite = str(database_url).startswith("sqlite")

# Configure engines based on database type
if is_sqlite:
    # SQLite configuration (for testing)
    sync_engine = create_engine(
        database_url,
        poolclass=NullPool,
        echo=settings.debug,
    )
    async_engine = create_async_engine(
        settings.get_database_url(async_mode=True),
        poolclass=NullPool,
        echo=settings.debug,
    )
else:
    # PostgreSQL configuration (for production)
    sync_engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        echo=settings.debug,
    )
    async_engine = create_async_engine(
        settings.get_database_url(async_mode=True),
        poolclass=NullPool,
        echo=settings.debug,
    )

# Session factories
SyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
)

AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def get_sync_db() -> Generator[Session, None, None]:
    """
    Get synchronous database session.

    Yields:
        Database session

    Example:
        ```python
        with get_sync_db() as db:
            user = db.query(User).first()
        ```
    """
    db = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get asynchronous database session.

    Yields:
        Async database session

    Example:
        ```python
        async with get_async_db() as db:
            result = await db.execute(select(User))
            users = result.scalars().all()
        ```
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def async_session_scope() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database session.

    Yields:
        Async database session

    Example:
        ```python
        async with async_session_scope() as session:
            await session.execute(...)
        ```
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


class DatabaseSessionManager:
    """Manager for database session lifecycle."""

    def __init__(self):
        self._engine = None
        self._sessionmaker = None

    async def init(self):
        """Initialize the database connection."""
        self._engine = create_async_engine(
            settings.get_database_url(async_mode=True),
            poolclass=NullPool,
            echo=settings.debug,
        )
        self._sessionmaker = async_sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self._engine,
            class_=AsyncSession,
        )

    async def close(self):
        """Close the database connection."""
        if self._engine:
            await self._engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session."""
        if not self._sessionmaker:
            raise RuntimeError("DatabaseSessionManager not initialized")

        async with self._sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


# Global session manager instance
db_manager = DatabaseSessionManager()

# Alias for FastAPI dependency injection
get_db = get_async_db
