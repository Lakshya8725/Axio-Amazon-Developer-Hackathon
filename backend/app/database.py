"""Database connection, session management, and base model declarative."""

from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from .config import get_settings

settings = get_settings()

# For SQLite, check_same_thread=False allows access across async threads
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

# Enable foreign keys for SQLite
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a database session and ensures clean closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables and seed initial defaults."""
    # Import models so they are registered with Base.metadata
    from .models.task import Task  # noqa: F401
    from .models.preference import UserPreference  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Seed default user preferences if none exist
    db = SessionLocal()
    try:
        from .services.preference_service import seed_default_preferences
        seed_default_preferences(db)
    finally:
        db.close()
