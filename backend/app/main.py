"""Axio FastAPI Application entrypoint with integrated MCP Streamable HTTP server."""

import html
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings

from .config import get_settings
from .database import get_db, init_db
from .models.task import TaskPriority, TaskStatus
from .schemas.task import (
    TaskCreate,
    TaskUpdate,
    TaskRead,
    TaskListResponse,
)
from .schemas.preference import (
    UserPreferenceRead,
    UserPreferenceSet,
    UserPreferencesResponse,
)
from .services import task_service, preference_service
from .tools.mcp_server import mcp_server
from .schemas.orchestration import AgentRunRequest, PlanResponse
from .services.orchestration_service import run_orchestration

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

# Local operator UIs (Next.js on :3000 and the static fallback on :8080).
# A wildcard origin cannot be combined with credentialed requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:8080",
        "http://localhost:8080",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount MCP Streamable HTTP endpoint
app.mount("/mcp", mcp_dynamic_app)


def service_index_payload() -> Dict[str, Any]:
    """Public discovery document for the API root."""
    return {
        "app": settings.app_name,
        "tagline": "Your intent. In action.",
        "status": "online",
        "version": "0.1.0",
        "environment": settings.environment,
        "operator_ui": "http://127.0.0.1:3000",
        "health": "/health",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "mcp_endpoint": "/mcp",
        "agent": "/api/agent/run",
        "tasks": "/api/tasks",
    }


def _service_home_html(payload: Dict[str, Any]) -> str:
    """Browser page for the API root. API clients still receive JSON."""
    app_name = html.escape(str(payload["app"]))
    version = html.escape(str(payload["version"]))
    environment = html.escape(str(payload["environment"]))
    operator = html.escape(str(payload["operator_ui"]))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{app_name} — API</title>
  <style>
    :root {{ color-scheme: dark; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      font-family: "Segoe UI", ui-sans-serif, system-ui, sans-serif;
      color: #f4f7fb;
      background:
        radial-gradient(720px 360px at 0% 0%, rgba(126, 231, 255, 0.16), transparent 55%),
        radial-gradient(540px 320px at 100% 0%, rgba(183, 166, 255, 0.12), transparent 50%),
        #07080c;
    }}
    main {{
      width: min(720px, 100%);
      margin: 0 auto;
      padding: 48px 24px 72px;
    }}
    .eyebrow {{
      margin: 0;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      font-size: 12px;
      color: #7ee7ff;
    }}
    h1 {{
      margin: 16px 0 0;
      font-size: 64px;
      font-weight: 520;
      letter-spacing: -0.04em;
    }}
    .tag {{ margin: 8px 0 0; font-size: 20px; color: #93a0b4; }}
    .lead {{ max-width: 36rem; margin: 28px 0 0; line-height: 1.6; color: #d5deea; }}
    .cta {{
      display: inline-block;
      margin-top: 28px;
      padding: 12px 18px;
      border-radius: 999px;
      background: #7ee7ff;
      color: #071016;
      font-weight: 650;
      text-decoration: none;
    }}
    ul {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 28px 0 0;
      padding: 0;
      list-style: none;
    }}
    li a {{
      display: inline-block;
      padding: 8px 12px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 999px;
      color: #f4f7fb;
      text-decoration: none;
    }}
    .meta {{ margin-top: 36px; font-family: ui-monospace, monospace; font-size: 12px; color: #6d7b90; }}
  </style>
</head>
<body>
  <main>
    <p class="eyebrow">Amazon AppDev · Alexa+</p>
    <h1>{app_name}</h1>
    <p class="tag">Your intent. In action.</p>
    <p class="lead">This address is the Axio API, and it is online. Open the operator to preview a plan, approve the write, and read the verified result.</p>
    <a class="cta" href="{operator}">Open the operator</a>
    <ul>
      <li><a href="/health">Health</a></li>
      <li><a href="/docs">API docs</a></li>
      <li><a href="/redoc">ReDoc</a></li>
    </ul>
    <p class="meta">{app_name} {version} · {environment} · MCP /mcp · agent POST /api/agent/run</p>
  </main>
</body>
</html>"""


# --- Health & Inspection Routes ---

@app.get("/", tags=["System"], summary="Service index", response_model=None)
def service_index(request: Request):
    """Browser visitors get a service page. Other clients get the discovery JSON."""
    payload = service_index_payload()
    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse(_service_home_html(payload))
    return payload


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


@app.post(
    "/api/agent/run",
    response_model=PlanResponse,
    tags=["Agent"],
    summary="Run orchestration agent",
)
def run_agent(request: AgentRunRequest, db: Session = Depends(get_db)) -> PlanResponse:
    """Execute orchestration based on natural language request.
    Returns a detailed plan and execution results. Errors are mapped to
    appropriate HTTP responses without exposing internal tracebacks.
    """
    try:
        return run_orchestration(request, db)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Orchestration execution failed: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.host, port=settings.port, reload=True)
