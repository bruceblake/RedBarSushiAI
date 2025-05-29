# tests/e2e/conftest.py - FastAPI test configuration
import os
import sys
import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

# Add the project root to the path if needed
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set test environment
os.environ["TESTING"] = "True"
os.environ["FASTAPI_ENV"] = "testing"
os.environ["NO_X11"] = "1"
os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "1"

from app.main import app
from app.db_async import Base, get_db
from app.config import settings

# Override settings for testing
settings.INITIALIZE_MENU_DATABASE = False

# Test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@postgres:5432/redbarsushi_test"
)

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

# Create test session factory
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def setup_database():
    """Create test database schema."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(setup_database) -> AsyncGenerator[AsyncSession, None]:
    """Get test database session."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Get test client with database override."""
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    from unittest.mock import AsyncMock
    client = AsyncMock()
    client.chat.completions.create = AsyncMock()
    return client


@pytest.fixture
def mock_twilio_client():
    """Mock Twilio client for testing."""
    from unittest.mock import MagicMock
    client = MagicMock()
    return client


@pytest.fixture
async def sample_menu_item(db_session):
    """Create a sample menu item for testing."""
    from app.models.menu_async import MenuItem
    
    item = MenuItem(
        name="Test Roll",
        plu="TEST_PLU",
        price=1000,
        description="Test description",
        is_available=True
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return item
