"""Orchestration service that turns natural‑language instructions into a concrete plan
and optionally executes it using the existing backend services.

The implementation is deterministic and does **not** rely on any LLM.
It supports the demo use‑case described in the milestone:
\"Organize my evening. Prioritize my unfinished tasks and leave time for interview preparation.\"
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any

from fastapi import HTTPException

from sqlalchemy.orm import Session

from ..schemas.orchestration import (
    AgentRunRequest,
    PlanResponse,
    PlanStep,
    ExecutionResult,
)
from ..services import task_service, preference_service
from ..models.task import TaskPriority, TaskStatus

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _interpret_instruction(instruction: str) -> Dict[str, Any]:
    """Very simple deterministic parser for the demo instruction.

    Returns a dictionary with keys that drive the planning logic.
    If the instruction cannot be understood, raises HTTPException(400).
    """
    lowered = instruction.lower().strip()
    # Only support the exact demo phrasing for now.
    if "organize my evening" in lowered and "interview preparation" in lowered:
        return {"type": "organize_evening"}
    # Fallback – unknown intent
    raise HTTPException(
        status_code=400,
        detail="Unable to interpret instruction – only the demo phrasing is supported.",
    )


def _retrieve_incomplete_tasks(db: Session) -> List[Dict[str, Any]]:
    """Fetch tasks whose status is not completed or cancelled.
    Returns list of task dicts ready for sorting.
    """
    tasks, _ = task_service.list_tasks(
        db=db,
        status=TaskStatus.PENDING.value,
        priority=None,
        search=None,
        limit=100,
        offset=0,
    )
    # Also include in_progress tasks that are still pending work
    more, _ = task_service.list_tasks(
        db=db,
        status=TaskStatus.IN_PROGRESS.value,
        priority=None,
        search=None,
        limit=100,
        offset=0,
    )
    all_tasks = tasks + more
    return [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "priority": t.priority,
            "due_date": t.due_date,
            "status": t.status,
        }
        for t in all_tasks
    ]


def _priority_score(priority: Any) -> int:
    # Higher number = higher priority for sorting descending
    if isinstance(priority, TaskPriority):
        priority = priority.value
    mapping = {"urgent": 4, "high": 3, "medium": 2, "low": 1}
    return mapping.get(str(priority or "").lower(), 0)


def _due_sort_value(value: Any) -> datetime:
    """Normalize due dates so aware and naive timestamps can be compared.

    SQLite often returns naive datetimes. ``datetime.max`` is also naive,
    and mixing the two raises TypeError. Missing dates sort last.
    """
    if not isinstance(value, datetime):
        return datetime.max.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _sort_tasks(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort by priority (high → low) then by due_date (earliest first).
    Tasks without due_date are placed after those with a date.
    """
    def sort_key(t: Dict[str, Any]):
        pr = _priority_score(t.get("priority")) * -1  # negative for descending
        return (pr, _due_sort_value(t.get("due_date")))
    return sorted(tasks, key=sort_key)


def _serialize_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """Return a JSON-safe task snapshot for plan step output."""
    due = task.get("due_date")
    if isinstance(due, datetime):
        due = _due_sort_value(due).isoformat().replace("+00:00", "Z")
    priority = task.get("priority")
    if isinstance(priority, TaskPriority):
        priority = priority.value
    status = task.get("status")
    if isinstance(status, TaskStatus):
        status = status.value
    return {
        "id": task.get("id"),
        "title": task.get("title"),
        "description": task.get("description"),
        "priority": priority,
        "status": status,
        "due_date": due,
    }


def _interview_task_exists(db: Session) -> bool:
    # Very simple detection: task title contains the words "interview" and "preparation"
    tasks, _ = task_service.list_tasks(
        db=db,
        status=None,
        priority=None,
        search="interview preparation",
        limit=10,
        offset=0,
    )
    return any("interview" in t.title.lower() and "preparation" in t.title.lower() for t in tasks)


def _build_plan(request: AgentRunRequest, db: Session) -> List[PlanStep]:
    """Create an ordered list of PlanStep objects based on the instruction.
    """
    intent = _interpret_instruction(request.instruction)
    steps: List[PlanStep] = []
    # Step 1 – retrieve tasks (read‑only, never requires approval)
    steps.append(
        PlanStep(
            name="Retrieve existing tasks",
            tool="get_tasks",
            arguments={},
            requires_approval=False,
            expected_result="List of incomplete tasks",
        )
    )
    # Step 2 – propose ordering (virtual, no external call)
    steps.append(
        PlanStep(
            name="Propose ordered task list",
            tool="get_tasks",  # reuse tool for consistency, no real call needed
            arguments={},
            requires_approval=False,
            expected_result="Ordered list based on priority and due date",
        )
    )
    # Step 3 – optionally create interview‑preparation task
    if intent["type"] == "organize_evening":
        if not _interview_task_exists(db):
            steps.append(
                PlanStep(
                    name="Create interview preparation task",
                    tool="create_task",
                    arguments={
                        "title": "Interview preparation",
                        "description": "Allocate time for interview prep before evening tasks",
                        "priority": "high",
                    },
                    requires_approval=True,
                    expected_result="New task ID for interview preparation",
                )
            )
    return steps


def _execute_step(step: PlanStep, db: Session, dry_run: bool, approve: bool) -> ExecutionResult:
    """Execute a single step using the concrete service functions.
    Returns an ExecutionResult describing success/failure.
    """
    if step.requires_approval and not approve:
        return ExecutionResult(status="skipped", detail="Step requires explicit approval")

    if dry_run and step.tool in {"create_task", "update_task_status"}:
        return ExecutionResult(status="skipped", detail="Dry‑run mode – mutation not performed")

    # Real tool execution. Ordering is read-only and must return the actual sequence.
    try:
        if step.tool == "get_tasks" and step.name.startswith("Propose"):
            ordered = [_serialize_task(task) for task in _sort_tasks(_retrieve_incomplete_tasks(db))]
            return ExecutionResult(
                status="success",
                detail="Ordered unfinished tasks by priority, then earliest due date.",
                output={"total": len(ordered), "tasks": ordered, "ordered": True},
            )
        if step.tool == "get_tasks":
            tasks = [_serialize_task(task) for task in _retrieve_incomplete_tasks(db)]
            return ExecutionResult(
                status="success",
                detail="Unfinished tasks only. Completed and cancelled work is excluded.",
                output={"total": len(tasks), "tasks": tasks, "ordered": False},
            )
        elif step.tool == "create_task":
            args = step.arguments
            # Guard against duplicate interview‑preparation tasks: if a task with the same title already exists, reuse it.
            existing = None
            try:
                tasks, _ = task_service.list_tasks(
                    db=db,
                    status=None,
                    priority=None,
                    search=args.get("title", ""),
                    limit=10,
                    offset=0,
                )
                for t in tasks:
                    if t.title.strip().lower() == args.get("title", "").strip().lower():
                        existing = t
                        break
            except Exception:
                existing = None
            if existing:
                return ExecutionResult(
                    status="success",
                    output={"id": existing.id, "title": existing.title},
                    detail="Task already exists – reused",
                )
            # No existing task – create a new one as before
            task_in = task_service.TaskCreate(
                title=args["title"],
                description=args.get("description"),
                priority=args.get("priority", "medium"),
                due_date=args.get("due_date"),
            )
            task = task_service.create_task(db=db, task_in=task_in)
            return ExecutionResult(
                status="success",
                output={"id": task.id, "title": task.title},
                detail="Task created",
            )
        elif step.tool == "update_task_status":
            args = step.arguments
            task = task_service.update_task_status(
                db=db,
                task_id=args["task_id"],
                status=args["status"],
            )
            if not task:
                return ExecutionResult(status="failed", detail="Task not found")
            return ExecutionResult(
                status="success",
                output={"id": task.id, "status": task.status},
                detail="Status updated",
            )
        else:
            return ExecutionResult(status="failed", detail=f"Unsupported tool {step.tool}")
    except Exception as exc:
        return ExecutionResult(status="failed", detail=str(exc))


def run_orchestration(request: AgentRunRequest, db: Session) -> PlanResponse:
    """Main entry point used by the FastAPI endpoint.

    Generates a plan, optionally executes it, and returns a detailed response.
    """
    request_id = str(uuid.uuid4())
    plan = _build_plan(request, db)
    step_results: Dict[int, ExecutionResult] = {}
    for idx, step in enumerate(plan):
        result = _execute_step(step, db, request.dry_run, request.approve)
        step_results[idx] = result
    any_failed = any(result.status == "failed" for result in step_results.values())
    any_skipped = any(result.status == "skipped" for result in step_results.values())
    if request.dry_run:
        summary = "Preview completed – no state‑changing actions performed."
    elif any_failed:
        summary = "Orchestration completed with errors. Review step results."
    elif any_skipped:
        summary = "Orchestration finished. Steps that required approval were skipped."
    else:
        summary = "Orchestration executed successfully."
    interpreted_intent = request.instruction.strip()
    return PlanResponse(
        request_id=request_id,
        interpreted_intent=interpreted_intent,
        plan=plan,
        step_results=step_results,
        final_summary=summary,
    )
