"""API dependencies for FastAPI routes."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from structlog import get_logger

from src.config.settings import get_settings

logger = get_logger(__name__)

# Global database engine and session factory
_engine = None
_session_factory = None


def get_database_engine():
    """Get or create database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        database_url = settings.database.postgresql.connection_string
        _engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=settings.database.postgresql.pool_size,
            max_overflow=settings.database.postgresql.max_overflow,
        )
        logger.info("Database engine created", database_url=database_url.split("@")[1] if "@" in database_url else "configured")
    return _engine


def get_session_factory():
    """Get or create session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_database_engine()
        _session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.

    Yields:
        AsyncSession: Database session
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

