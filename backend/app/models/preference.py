"""User preference persistence model."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from ..database import Base


class UserPreference(Base):
    """SQLAlchemy model representing stored operator and user preferences."""

    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(Text, nullable=False)
    category = Column(String(50), nullable=False, default="general", index=True)
    description = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<UserPreference(key='{self.key}', category='{self.category}')>"
