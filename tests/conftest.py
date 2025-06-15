import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from services.api.main import app
from services.api.db.session import Base, get_db
from services.api.core.config import settings

# Test database URL
TEST_SQLALCHEMY_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/test_evals"

# Create test engine
engine = create_async_engine(TEST_SQLALCHEMY_DATABASE_URL, echo=True)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)

# Create test database tables
@pytest.fixture(scope="session")
async def test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        await db.close()

# Test client with overridden get_db dependency
@pytest.fixture(scope="function")
async def client(test_db):
    async def override_get_db():
        try:
            yield test_db
        finally:
            await test_db.rollback()
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
