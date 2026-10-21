"""Business logic service for user and operator preferences."""

from typing import Optional, Dict
from sqlalchemy.orm import Session
from app.models.preference import UserPreference

DEFAULT_PREFERENCES = [
    {
        "key": "confirm_consequential_actions",
        "value": "true",
        "category": "security",
        "description": "Require explicit operator confirmation before executing irreversible or impactful actions.",
    },
    {
        "key": "default_task_priority",
        "value": "medium",
        "category": "workflow",
        "description": "Default priority assigned when an inbound task does not specify priority.",
    },
    {
        "key": "notification_channel",
        "value": "in_app",
        "category": "notifications",
        "description": "Primary channel for delivery of action alerts and workflow updates.",
    },
    {
        "key": "operator_mode",
        "value": "autonomous_supervised",
        "category": "general",
        "description": "Operating mode governing AI action autonomy and checkpointing.",
    },
]


def seed_default_preferences(db: Session) -> None:
    """Seed initial system preferences if the table is currently empty."""
    count = db.query(UserPreference).count()
    if count == 0:
        for pref in DEFAULT_PREFERENCES:
            db_pref = UserPreference(
                key=pref["key"],
                value=pref["value"],
                category=pref["category"],
                description=pref["description"],
            )
            db.add(db_pref)
        db.commit()


def get_preference(db: Session, key: str) -> Optional[UserPreference]:
    """Retrieve a preference record by key."""
    return db.query(UserPreference).filter(UserPreference.key == key).first()


def get_preferences(db: Session, category: Optional[str] = None) -> Dict[str, str]:
    """Retrieve dictionary of preferences, optionally filtered by category."""
    query = db.query(UserPreference)
    if category:
        query = query.filter(UserPreference.category == category)
    rows = query.all()
    return {row.key: row.value for row in rows}


def set_preference(
    db: Session,
    key: str,
    value: str,
    category: str = "general",
    description: Optional[str] = None,
) -> UserPreference:
    """Set or update a preference key-value pair."""
    pref = get_preference(db, key)
    if pref:
        pref.value = value
        if category:
            pref.category = category
        if description is not None:
            pref.description = description
    else:
        pref = UserPreference(
            key=key,
            value=value,
            category=category,
            description=description,
        )
        db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref
