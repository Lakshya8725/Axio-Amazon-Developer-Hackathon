# -*- coding: utf-8 -*-
"""Tests for the orchestration endpoint and service.

The tests exercise:
1. Validation of empty and unsupported instructions.
2. Successful planning for the demo instruction.
3. Priority and due‑date ordering logic.
4. Detection of an existing interview‑preparation task.
5. Preview (dry_run) mode – no DB mutations.
6. Approval gating – skipped vs executed actions.
7. Error handling when a downstream service raises an exception.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta

from app.schemas.orchestration import AgentRunRequest, PlanResponse, ExecutionResult, PlanStep
from app.services import orchestration_service as orch_service
from app.main import app
from app.services import task_service, preference_service

# Fixtures from conftest are automatically available: `client`, `db_session`

# Helper to create a task directly via the service
def _create_task(db, title, priority="medium", due_date=None):
    task_in = task_service.TaskCreate(
        title=title,
        description="",
        priority=priority,
        due_date=due_date,
    )
    return task_service.create_task(db=db, task_in=task_in)


def test_empty_instruction_validation(client: TestClient):
    response = client.post("/api/agent/run", json={"instruction": "   "})
    assert response.status_code == 422  # Pydantic validation error
    assert "instruction" in response.text.lower()


def test_unsupported_instruction_returns_400(client: TestClient):
    response = client.post(
        "/api/agent/run",
        json={"instruction": "Do something completely unrelated"},
    )
    assert response.status_code == 400
    assert "Unable to interpret instruction" in response.json()["detail"]


def test_successful_planning_preview(client: TestClient, db_session):
    # Ensure no interview‑preparation task exists
    payload = {
        "instruction": "Organize my evening. Prioritize my unfinished tasks and leave time for interview preparation.",
        "dry_run": True,
        "approve": False,
    }
    response = client.post("/api/agent/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["interpreted_intent"].lower().startswith("organize my evening")
    # Expect three steps (retrieve, propose ordering, create interview task)
    assert len(data["plan"]) == 3
    # The create‑task step must be marked as requiring approval
    create_step = data["plan"][2]
    assert create_step["requires_approval"] is True
    # In preview mode the step should be skipped
    assert data["step_results"]["2"]["status"] == "skipped"
    # No new task should have been persisted
    interview = (
        db_session.query(task_service.Task)
        .filter(task_service.Task.title.ilike("%interview%preparation%"))
        .first()
    )
    assert interview is None


def test_priority_and_due_date_sorting(db_session):
    # Create tasks with differing priorities and due dates
    now = datetime.now(timezone.utc)
    _create_task(db_session, "Task urgent with date", priority="urgent", due_date=(now + timedelta(days=5)).isoformat())
    _create_task(db_session, "Task high no date", priority="high")
    _create_task(db_session, "Task medium early", priority="medium", due_date=(now + timedelta(days=1)).isoformat())
    _create_task(db_session, "Task low late", priority="low", due_date=(now + timedelta(days=10)).isoformat())
    # Retrieve incomplete tasks and sort them using the private helper
    incomplete = orch_service._retrieve_incomplete_tasks(db_session)
    sorted_tasks = orch_service._sort_tasks(incomplete)
    # Expected order: urgent → high → medium (earliest) → low (latest)
    titles = [t["title"] for t in sorted_tasks]
    assert titles[0] == "Task urgent with date"
    assert titles[1] == "Task high no date"
    assert titles[2] == "Task medium early"
    assert titles[3] == "Task low late"


def test_existing_interview_task_skips_creation(client: TestClient, db_session):
    # Seed an interview‑preparation task
    _create_task(db_session, "Interview preparation for upcoming interview", priority="high")
    payload = {
        "instruction": "Organize my evening. Prioritize my unfinished tasks and leave time for interview preparation.",
        "dry_run": True,
        "approve": False,
    }
    response = client.post("/api/agent/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    # Plan should contain only the first two steps (no create‑task step)
    assert len(data["plan"]) == 2


def test_approval_execution_creates_task(client: TestClient, db_session):
    payload = {
        "instruction": "Organize my evening. Prioritize my unfinished tasks and leave time for interview preparation.",
        "dry_run": False,
        "approve": True,
    }
    response = client.post("/api/agent/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    # The create‑task step should now be executed successfully
    assert data["step_results"]["2"]["status"] == "success"
    # Verify the task persisted in the DB
    interview = (
        db_session.query(task_service.Task)
        .filter(task_service.Task.title == "Interview preparation")
        .first()
    )
    assert interview is not None
    assert interview.priority == "high"


def test_readonly_step_in_preview_mode(client: TestClient, db_session):
    # Ensure at least one incomplete task exists
    _create_task(db_session, "Sample pending task", priority="low")
    payload = {
        "instruction": "Organize my evening. Prioritize my unfinished tasks and leave time for interview preparation.",
        "dry_run": True,
        "approve": False,
    }
    response = client.post("/api/agent/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    # First step (get_tasks) must succeed and contain a tasks list
    step0 = data["step_results"]["0"]
    assert step0["status"] == "success"
    assert isinstance(step0["output"], dict)
    assert "tasks" in step0["output"]
    # No mutation should have occurred
    total_tasks = db_session.query(task_service.Task).count()
    assert total_tasks >= 1


def test_service_error_handling(monkeypatch, client: TestClient, db_session):
    # Force task_service.list_tasks to raise an exception
    def explode(*args, **kwargs):
        raise RuntimeError("simulated failure")
    monkeypatch.setattr(task_service, "list_tasks", explode)
    payload = {
        "instruction": "Organize my evening. Prioritize my unfinished tasks and leave time for interview preparation.",
        "dry_run": False,
        "approve": False,
    }
    response = client.post("/api/agent/run", json=payload)
    assert response.status_code == 500
    assert "Internal server error" in response.json()["detail"]
def test_duplicate_prevention_on_repeat_approved(client: TestClient, db_session):
    payload = {
        "instruction": "Organize my evening. Prioritize my unfinished tasks and leave time for interview preparation.",
        "dry_run": False,
        "approve": True,
    }
    # First approved request should create the interview preparation task
    response1 = client.post("/api/agent/run", json=payload)
    assert response1.status_code == 200
    # Second approved request should not create a duplicate task
    response2 = client.post("/api/agent/run", json=payload)
    assert response2.status_code == 200
    interview_tasks = db_session.query(task_service.Task).filter(task_service.Task.title == "Interview preparation").all()
    assert len(interview_tasks) == 1


def test_sort_tasks_normalizes_mixed_timezones():
    soon = datetime.now(timezone.utc) + timedelta(hours=2)
    later = (datetime.now(timezone.utc) + timedelta(days=2)).replace(tzinfo=None)
    ordered = orch_service._sort_tasks(
        [
            {"title": "undated", "priority": "high", "due_date": None},
            {"title": "later", "priority": "high", "due_date": later},
            {"title": "sooner", "priority": "high", "due_date": soon},
        ]
    )
    assert [task["title"] for task in ordered] == ["sooner", "later", "undated"]


def test_preview_returns_priority_ordered_unfinished_tasks(client: TestClient, db_session):
    now = datetime.now(timezone.utc)
    _create_task(db_session, "Alpha urgent", priority="urgent", due_date=(now + timedelta(days=2)).isoformat())
    _create_task(db_session, "Beta low", priority="low", due_date=(now + timedelta(hours=1)).isoformat())
    done = _create_task(
        db_session,
        "Already finished",
        priority="urgent",
        due_date=(now + timedelta(hours=1)).isoformat(),
    )
    task_service.update_task_status(db_session, done.id, "completed")

    response = client.post(
        "/api/agent/run",
        json={
            "instruction": "Organize my evening. Prioritize my unfinished tasks and leave time for interview preparation.",
            "dry_run": True,
            "approve": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    read_titles = [task["title"] for task in data["step_results"]["0"]["output"]["tasks"]]
    propose = data["step_results"]["1"]
    titles = [task["title"] for task in propose["output"]["tasks"]]

    assert propose["status"] == "success"
    assert propose["output"]["ordered"] is True
    assert titles[0] == "Alpha urgent"
    assert titles.index("Alpha urgent") < titles.index("Beta low")
    assert "Already finished" not in titles
    assert "Already finished" not in read_titles
    assert "Interview preparation" not in titles
    assert db_session.query(task_service.Task).count() == 3


def test_unapproved_execution_skips_mutation(client: TestClient, db_session):
    response = client.post(
        "/api/agent/run",
        json={
            "instruction": "Organize my evening. Prioritize my unfinished tasks and leave time for interview preparation.",
            "dry_run": False,
            "approve": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["step_results"]["2"]["status"] == "skipped"
    assert "approval" in data["final_summary"].lower()
    interview = (
        db_session.query(task_service.Task)
        .filter(task_service.Task.title == "Interview preparation")
        .first()
    )
    assert interview is None
