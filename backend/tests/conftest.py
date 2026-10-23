"""Pytest configuration and fixtures for Axio test suite."""

import os
import tempfile
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.models.task import Task
from app.models.preference import UserPreference
from app.services.preference_service import seed_default_preferences
from app.main import app


@pytest.fixture(scope="session")
def test_db_path():
    """Create a temporary sqlite database file for the test session."""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="axio_test_")
    os.close(fd)
    yield path
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


@pytest.fixture(scope="session")
def test_engine(test_db_path):
    """Engine connected to the isolated test database."""
    engine = create_engine(
        f"sqlite:///{test_db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="session")
def TestingSessionLocal(test_engine):
    """Session factory for test database."""
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture
def db_session(TestingSessionLocal):
    """Provide a clean database session per test with rolled-back transactions."""
    session = TestingSessionLocal()
    # Seed default preferences for test session
    seed_default_preferences(session)
    yield session
    # Cleanup tasks after each test
    session.query(Task).delete()
    session.commit()
    session.close()


@pytest.fixture
def client(TestingSessionLocal, db_session):
    """TestClient wired to the test database session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
