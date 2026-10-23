"""Task Pydantic validation schemas."""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator
from ..models.task import TaskPriority, TaskStatus


class TaskBase(BaseModel):
    """Base fields for task payloads."""

    title: str = Field(..., min_length=1, max_length=255, description="Brief task summary")
    description: Optional[str] = Field(None, description="Detailed task context or instructions")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="Task urgency level")
    due_date: Optional[datetime] = Field(None, description="Optional target deadline in ISO format")

    @field_validator("title")
    @classmethod
    def validate_title_not_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Task title cannot be empty or blank whitespace.")
        return stripped


class TaskCreate(TaskBase):
    """Payload to create a new task."""
    pass


class TaskUpdate(BaseModel):
    """Payload for partial updates to an existing task."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    due_date: Optional[datetime] = None

    @field_validator("title")
    @classmethod
    def validate_title_not_empty(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            stripped = value.strip()
            if not stripped:
                raise ValueError("Task title cannot be empty or blank whitespace.")
            return stripped
        return value



class TaskStatusUpdate(BaseModel):
    """Payload dedicated to status transitions."""

    status: TaskStatus = Field(..., description="Target status transition")


class TaskRead(BaseModel):
    """Full task record representation."""

    id: int
    title: str
    description: Optional[str]
    priority: str
    status: str
    due_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("due_date", "created_at", "updated_at")
    def serialize_timestamp(self, value: datetime | None) -> str | None:
        """Emit UTC timestamps with a Z suffix, including naive SQLite values."""
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.isoformat().replace("+00:00", "Z")


class TaskListResponse(BaseModel):
    """Structured list of tasks with total count and metadata."""

    tasks: List[TaskRead]
    total: int
    filters: Dict[str, Any] = Field(default_factory=dict)
