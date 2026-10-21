"""Axio MCP Server exposing action tools via Streamable HTTP."""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from mcp.server.mcpserver import MCPServer
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models.task import TaskPriority, TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate
from app.services import task_service, preference_service

logger = logging.getLogger("axio.mcp")
settings = get_settings()


def task_to_dict(task) -> Dict[str, Any]:
    """Helper to convert a Task ORM instance to a clean JSON-serializable dict."""
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "status": task.status,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


def create_mcp_server() -> MCPServer:
    """Instantiate and configure the official Axio MCP Server with registered action tools."""
    server = MCPServer(
        name=settings.mcp_server_name,
        instructions=(
            "Axio is a proactive AI personal operator. "
            "Use get_tasks to inspect existing actions, create_task to register new action items, "
            "update_task_status to reflect execution milestones, and get_user_preferences "
            "to check operating guidelines and security boundaries."
        ),
        version=settings.mcp_server_version,
    )

    @server.tool(
        name="get_tasks",
        description=(
            "List existing tasks from Axio's persistent store with optional filters "
            "for status ('pending', 'in_progress', 'completed', 'cancelled'), "
            "priority ('low', 'medium', 'high', 'urgent'), search term, and limit."
        ),
    )
    def get_tasks(
        status: Optional[str] = None,
        priority: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Query tasks with server-side validation."""
        valid_statuses = {s.value for s in TaskStatus}
        if status and status.lower() not in valid_statuses:
            return {
                "success": False,
                "error": f"Invalid status '{status}'. Must be one of: {sorted(valid_statuses)}",
            }

        valid_priorities = {p.value for p in TaskPriority}
        if priority and priority.lower() not in valid_priorities:
            return {
                "success": False,
                "error": f"Invalid priority '{priority}'. Must be one of: {sorted(valid_priorities)}",
            }

        safe_limit = max(1, min(limit, 100))

        with SessionLocal() as db:
            tasks, total = task_service.list_tasks(
                db=db,
                status=status.lower() if status else None,
                priority=priority.lower() if priority else None,
                search=search,
                limit=safe_limit,
            )
            return {
                "success": True,
                "total": total,
                "count": len(tasks),
                "tasks": [task_to_dict(t) for t in tasks],
            }

    @server.tool(
        name="create_task",
        description=(
            "Create a new persistent task in Axio. Requires a title. "
            "Optional parameters include description, priority ('low', 'medium', 'high', 'urgent'), "
            "and due_date (ISO 8601 string, e.g. '2026-10-25T14:00:00Z')."
        ),
    )
    def create_task(
        title: str,
        description: Optional[str] = None,
        priority: str = "medium",
        due_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create and persist a new task with validation."""
        if not title or not title.strip():
            return {"success": False, "error": "Task title cannot be empty."}

        priority_lower = priority.lower().strip()
        valid_priorities = {p.value for p in TaskPriority}
        if priority_lower not in valid_priorities:
            return {
                "success": False,
                "error": f"Invalid priority '{priority}'. Must be one of: {sorted(valid_priorities)}",
            }

        parsed_due_date = None
        if due_date:
            try:
                # Handle 'Z' suffix or standard ISO strings
                cleaned_date = due_date.replace("Z", "+00:00")
                parsed_due_date = datetime.fromisoformat(cleaned_date)
            except ValueError:
                return {
                    "success": False,
                    "error": f"Invalid due_date format: '{due_date}'. Expected ISO 8601 string.",
                }

        task_in = TaskCreate(
            title=title.strip(),
            description=description.strip() if description else None,
            priority=TaskPriority(priority_lower),
            due_date=parsed_due_date,
        )

        with SessionLocal() as db:
            task = task_service.create_task(db=db, task_in=task_in)
            logger.info("MCP created task id=%d title='%s'", task.id, task.title)
            return {
                "success": True,
                "message": f"Task '{task.title}' created with ID {task.id}.",
                "task": task_to_dict(task),
            }

    @server.tool(
        name="update_task_status",
        description=(
            "Update the execution status of an existing task by ID. "
            "Allowed status values: 'pending', 'in_progress', 'completed', 'cancelled'."
        ),
    )
    def update_task_status(task_id: int, status: str) -> Dict[str, Any]:
        """Update task status with validation."""
        if task_id <= 0:
            return {"success": False, "error": "task_id must be a positive integer."}

        status_lower = status.lower().strip()
        valid_statuses = {s.value for s in TaskStatus}
        if status_lower not in valid_statuses:
            return {
                "success": False,
                "error": f"Invalid status '{status}'. Must be one of: {sorted(valid_statuses)}",
            }

        with SessionLocal() as db:
            task = task_service.update_task_status(
                db=db,
                task_id=task_id,
                status=TaskStatus(status_lower),
            )
            if not task:
                return {
                    "success": False,
                    "error": f"Task with ID {task_id} not found.",
                }

            logger.info("MCP updated task id=%d to status=%s", task.id, task.status)
            return {
                "success": True,
                "message": f"Task {task.id} status updated to '{task.status}'.",
                "task": task_to_dict(task),
            }

    @server.tool(
        name="get_user_preferences",
        description=(
            "Retrieve configured user and operator preferences (such as confirmation policies, "
            "default priorities, or notification channels), optionally filtered by category "
            "('security', 'workflow', 'notifications', 'general')."
        ),
    )
    def get_user_preferences(category: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve stored user preferences."""
        with SessionLocal() as db:
            prefs = preference_service.get_preferences(db=db, category=category)
            return {
                "success": True,
                "category": category,
                "count": len(prefs),
                "preferences": prefs,
            }

    return server


# Global instance configured for the application
mcp_server = create_mcp_server()


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    init_db()
    logger.info("Starting standalone Axio MCP Server over Streamable HTTP on %s:%d%s", settings.host, settings.port, settings.mcp_mount_path)
    asyncio.run(
        mcp_server.run_streamable_http_async(
            host=settings.host,
            port=settings.port,
            streamable_http_path=settings.mcp_mount_path,
        )
    )
