"""
Database session management for the API.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
import os
from typing import AsyncGenerator

# Database URL from environment variables
DATABASE_URL = os.getenv(
    "SQLALCHEMY_DATABASE_URI",
    "postgresql+asyncpg://postgres:postgres@postgres:5432/evals"
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=bool(os.getenv("SQL_ECHO", "False").lower() == "true"),
    pool_pre_ping=True,
    pool_recycle=3600,
    poolclass=NullPool  # Use NullPool for asyncpg
)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function that yields database sessions.
    
    Yields:
        AsyncSession: Database session
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

async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        # Create all tables
        from . import models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)

async def close_db() -> None:
    """Close database connections."""
    if engine is not None:
        await engine.dispose()
