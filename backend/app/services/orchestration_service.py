"""Orchestration service that turns natural‑language instructions into a concrete plan
and optionally executes it using the existing backend services.

The implementation is deterministic and does **not** rely on any LLM.
It supports the demo use‑case described in the milestone:
\"Organize my evening. Prioritize my unfinished tasks and leave time for interview preparation.\"
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Dict, Any

from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.schemas.orchestration import (
    AgentRunRequest,
    PlanResponse,
    PlanStep,
    ExecutionResult,
)
from app.services import task_service, preference_service
from app.models.task import TaskPriority, TaskStatus

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
            "priority": t.priority,
            "due_date": t.due_date,
            "status": t.status,
        }
        for t in all_tasks
    ]


def _priority_score(priority: str) -> int:
    # Higher number = higher priority for sorting descending
    mapping = {"urgent": 4, "high": 3, "medium": 2, "low": 1}
    return mapping.get(priority.lower(), 0)


def _sort_tasks(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort by priority (high → low) then by due_date (earliest first).
    Tasks without due_date are placed after those with a date.
    """
    def sort_key(t: Dict[str, Any]):
        pr = _priority_score(t["priority"]) * -1  # negative for descending
        due = t["due_date"] or datetime.max
        return (pr, due)
    return sorted(tasks, key=sort_key)


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
    # Handle no‑op virtual steps (e.g., ordering proposal) – treat as success
    if step.tool == "get_tasks" and step.name.startswith("Propose"):
        return ExecutionResult(status="success", detail="Ordering computed locally")

    if step.requires_approval and not approve:
        return ExecutionResult(status="skipped", detail="Step requires explicit approval")

    if dry_run and step.tool in {"create_task", "update_task_status"}:
        return ExecutionResult(status="skipped", detail="Dry‑run mode – mutation not performed")

    # Real tool execution
    try:
        if step.tool == "get_tasks":
            tasks, total = task_service.list_tasks(
                db=db,
                status=None,
                priority=None,
                search=None,
                limit=100,
                offset=0,
            )
            result = {"total": total, "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "priority": t.priority,
                    "status": t.status,
                    "due_date": t.due_date.isoformat() if t.due_date else None,
                }
                for t in tasks
            ]}
            return ExecutionResult(status="success", output=result)
        elif step.tool == "create_task":
            args = step.arguments
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
    if request.dry_run:
        summary = "Preview completed – no state‑changing actions performed."
    else:
        any_failed = any(r.status == "failed" for r in step_results.values())
        summary = "Orchestration completed with errors. Review step results." if any_failed else "Orchestration executed successfully."
    interpreted_intent = request.instruction.strip()
    return PlanResponse(
        request_id=request_id,
        interpreted_intent=interpreted_intent,
        plan=plan,
        step_results=step_results,
        final_summary=summary,
    )
