"""User preference Pydantic validation schemas."""

from datetime import datetime
from typing import Optional, Dict
from pydantic import BaseModel, ConfigDict, Field


class UserPreferenceRead(BaseModel):
    """User preference item schema."""

    key: str
    value: str
    category: str
    description: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserPreferenceSet(BaseModel):
    """Payload to create or update a user preference."""

    value: str = Field(..., description="Configuration or preference value")
    category: Optional[str] = Field("general", description="Logical category grouping")
    description: Optional[str] = Field(None, description="Human-readable explanation of setting")


class UserPreferencesResponse(BaseModel):
    """Grouped user preferences response."""

    preferences: Dict[str, str]
    category: Optional[str] = None
