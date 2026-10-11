import os
import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.config import settings
from app.database import Base, get_db

# Use an in-memory SQLite database with StaticPool for isolated, concurrent test runs
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Configure temporary directories for test files."""
    test_storage_dir = Path(tempfile.mkdtemp(prefix="cert_test_storage_"))
    test_cert_dir = test_storage_dir / "certificates"
    test_arch_dir = test_storage_dir / "archives"
    test_cert_dir.mkdir(parents=True, exist_ok=True)
    test_arch_dir.mkdir(parents=True, exist_ok=True)

    # Override settings
    settings.STORAGE_DIR = test_storage_dir
    settings.CERTIFICATES_DIR = test_cert_dir
    settings.ARCHIVES_DIR = test_arch_dir

    yield

    # Clean up after test session
    shutil.rmtree(test_storage_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def init_test_db():
    """Create a fresh database schema for each test."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """Provide a standalone DB session for a test."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden database dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
