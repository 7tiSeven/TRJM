"""
TRJM Gateway - Database Session Management
===========================================
Async SQLAlchemy session and connection handling
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from ..core.config import settings
from ..core.logging import logger

# =============================================================================
# Engine Configuration
# =============================================================================

# Create async engine with connection pooling
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,  # Enable connection health checks
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,  # Recycle connections after 30 minutes
)

# Create session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# =============================================================================
# Session Dependency
# =============================================================================


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.

    Yields:
        AsyncSession: Database session

    Example:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions.

    Usage:
        async with get_db_context() as db:
            result = await db.execute(query)
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# =============================================================================
# Database Lifecycle
# =============================================================================


async def init_db() -> None:
    """
    Initialize database connection and verify connectivity.
    """
    try:
        async with engine.begin() as conn:
            # Test connection
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection established")
    except Exception as e:
        logger.error("Failed to connect to database", error=str(e))
        raise


async def close_db() -> None:
    """
    Close database connection pool.
    """
    await engine.dispose()
    logger.info("Database connection pool closed")


# =============================================================================
# Health Check
# =============================================================================


async def check_db_health() -> bool:
    """
    Check database connectivity.

    Returns:
        bool: True if database is healthy, False otherwise
    """
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning("Database health check failed", error=str(e))
        return False
