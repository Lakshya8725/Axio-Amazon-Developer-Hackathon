"""Axio FastAPI Application entrypoint with integrated MCP Streamable HTTP server."""

import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings

from app.config import get_settings
from app.database import get_db, init_db
from app.models.task import TaskPriority, TaskStatus
from app.schemas.task import (
    TaskCreate,
    TaskUpdate,
    TaskRead,
    TaskListResponse,
)
from app.schemas.preference import (
    UserPreferenceRead,
    UserPreferenceSet,
    UserPreferencesResponse,
)
from app.services import task_service, preference_service
from app.tools.mcp_server import mcp_server

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("axio.api")


class DynamicMCPASGIApp:
    """ASGI application adapter allowing safe dynamic session manager recreation across lifespans."""

    def __init__(self, server):
        self.server = server
        self.session_manager: Optional[StreamableHTTPSessionManager] = None

    async def __call__(self, scope, receive, send):
        if self.session_manager is None:
            raise RuntimeError("MCP Streamable HTTP session manager is not active.")
        await self.session_manager.asgi_app(scope, receive, send)


mcp_dynamic_app = DynamicMCPASGIApp(mcp_server)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager: initialize SQLite tables and run MCP session manager."""
    logger.info("Initializing Axio persistence and database schema...")
    init_db()

    security_settings = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
        allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"],
    )

    session_manager = StreamableHTTPSessionManager(
        app=mcp_server._lowlevel_server,
        security_settings=security_settings,
    )
    mcp_dynamic_app.session_manager = session_manager

    logger.info("Starting MCP Streamable HTTP session manager...")
    async with session_manager.run():
        logger.info("Axio application online and ready.")
        yield

    mcp_dynamic_app.session_manager = None
    logger.info("Axio application and MCP session manager shut down.")


app = FastAPI(
    title="Axio - AI Personal Operator",
    description="Your intent. In action. Transforms natural-language requests into useful, verifiable actions.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for local frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount MCP Streamable HTTP endpoint
app.mount("/mcp", mcp_dynamic_app)


# --- Health & Inspection Routes ---

@app.get("/health", tags=["System"])
def get_health() -> Dict[str, Any]:
    """Health check endpoint reporting system status and MCP discovery point."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "0.1.0",
        "environment": settings.environment,
        "mcp_endpoint": "/mcp",
    }


# --- Task Management Routes ---

@app.get(
    "/api/tasks",
    response_model=TaskListResponse,
    tags=["Tasks"],
    summary="List tasks with filters",
)
def list_tasks(
    status: Optional[TaskStatus] = Query(None, description="Filter by task status"),
    priority: Optional[TaskPriority] = Query(None, description="Filter by urgency"),
    search: Optional[str] = Query(None, description="Keyword search in title and description"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
):
    """Retrieve persistent tasks filtered by status, priority, or search query."""
    tasks, total = task_service.list_tasks(
        db=db,
        status=status,
        priority=priority,
        search=search,
        limit=limit,
        offset=offset,
    )
    return TaskListResponse(
        tasks=[TaskRead.model_validate(t) for t in tasks],
        total=total,
        filters={
            "status": status.value if status else None,
            "priority": priority.value if priority else None,
            "search": search,
            "limit": limit,
            "offset": offset,
        },
    )


@app.post(
    "/api/tasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Tasks"],
    summary="Create a new task",
)
def create_task(
    task_in: TaskCreate,
    db: Session = Depends(get_db),
):
    """Create a new action task in SQLite persistence."""
    task = task_service.create_task(db=db, task_in=task_in)
    logger.info("Created task id=%d: '%s'", task.id, task.title)
    return TaskRead.model_validate(task)


@app.get(
    "/api/tasks/{task_id}",
    response_model=TaskRead,
    tags=["Tasks"],
    summary="Get task details",
)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve details for a specific task."""
    task = task_service.get_task(db=db, task_id=task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found",
        )
    return TaskRead.model_validate(task)


@app.patch(
    "/api/tasks/{task_id}",
    response_model=TaskRead,
    tags=["Tasks"],
    summary="Update task",
)
def update_task(
    task_id: int,
    task_in: TaskUpdate,
    db: Session = Depends(get_db),
):
    """Update status, title, description, priority, or due date of an existing task."""
    task = task_service.update_task(db=db, task_id=task_id, task_in=task_in)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found",
        )
    logger.info("Updated task id=%d: status=%s, priority=%s", task.id, task.status, task.priority)
    return TaskRead.model_validate(task)


@app.delete(
    "/api/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Tasks"],
    summary="Delete a task",
)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
):
    """Delete a task from persistent storage."""
    deleted = task_service.delete_task(db=db, task_id=task_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found",
        )
    logger.info("Deleted task id=%d", task_id)
    return None


# --- User & Operator Preferences Routes ---

@app.get(
    "/api/preferences",
    response_model=UserPreferencesResponse,
    tags=["Preferences"],
    summary="Get stored user preferences",
)
def get_preferences(
    category: Optional[str] = Query(None, description="Optional category filter"),
    db: Session = Depends(get_db),
):
    """Retrieve operator preferences and safety flags."""
    prefs = preference_service.get_preferences(db=db, category=category)
    return UserPreferencesResponse(preferences=prefs, category=category)


@app.put(
    "/api/preferences/{key}",
    response_model=UserPreferenceRead,
    tags=["Preferences"],
    summary="Update or set a preference",
)
def set_preference(
    key: str,
    pref_in: UserPreferenceSet,
    db: Session = Depends(get_db),
):
    """Create or update a configuration setting or user preference."""
    pref = preference_service.set_preference(
        db=db,
        key=key,
        value=pref_in.value,
        category=pref_in.category or "general",
        description=pref_in.description,
    )
    return UserPreferenceRead.model_validate(pref)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
