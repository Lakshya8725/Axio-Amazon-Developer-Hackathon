"""Automated tests for persistent task management and user preferences."""

from datetime import datetime, timezone
from app.models.task import Task, TaskPriority, TaskStatus
from app.schemas.task import TaskCreate
from app.services import task_service


def test_create_task_minimal(client):
    """Create task with minimal required payload."""
    payload = {"title": "Inspect repository structure"}
    response = client.post("/api/tasks", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["title"] == "Inspect repository structure"
    assert data["description"] is None
    assert data["priority"] == "medium"
    assert data["status"] == "pending"
    assert data["due_date"] is None
    assert "created_at" in data
    assert "updated_at" in data


def test_create_task_full(client):
    """Create task with complete payload including priority and due date."""
    due = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc).isoformat()
    payload = {
        "title": "Configure MCP transport",
        "description": "Establish streamable HTTP server using official SDK",
        "priority": "high",
        "due_date": due,
    }
    response = client.post("/api/tasks", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Configure MCP transport"
    assert data["description"] == "Establish streamable HTTP server using official SDK"
    assert data["priority"] == "high"
    assert data["status"] == "pending"
    assert data["due_date"] is not None


def test_create_task_validation_errors(client):
    """Verify server rejects empty titles and invalid priorities."""
    # Empty title
    res_empty = client.post("/api/tasks", json={"title": "   "})
    assert res_empty.status_code == 422

    # Missing title
    res_missing = client.post("/api/tasks", json={})
    assert res_missing.status_code == 422

    # Invalid priority
    res_bad_pri = client.post("/api/tasks", json={"title": "Valid", "priority": "critical_super"})
    assert res_bad_pri.status_code == 422


def test_get_task_by_id(client):
    """Retrieve an existing task by ID."""
    created = client.post("/api/tasks", json={"title": "Retrieve me"}).json()
    task_id = created["id"]

    response = client.get(f"/api/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["id"] == task_id
    assert response.json()["title"] == "Retrieve me"


def test_get_task_not_found(client):
    """Requesting non-existent task returns 404."""
    response = client.get("/api/tasks/999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_patch_task_status(client):
    """Update task status transition from pending to in_progress to completed."""
    created = client.post("/api/tasks", json={"title": "Execute step"}).json()
    task_id = created["id"]

    # Transition to in_progress
    res1 = client.patch(f"/api/tasks/{task_id}", json={"status": "in_progress"})
    assert res1.status_code == 200
    assert res1.json()["status"] == "in_progress"

    # Transition to completed
    res2 = client.patch(f"/api/tasks/{task_id}", json={"status": "completed"})
    assert res2.status_code == 200
    assert res2.json()["status"] == "completed"


def test_patch_task_invalid_status(client):
    """Reject invalid status values with 422."""
    created = client.post("/api/tasks", json={"title": "Status test"}).json()
    task_id = created["id"]

    response = client.patch(f"/api/tasks/{task_id}", json={"status": "done_and_dusted"})
    assert response.status_code == 422


def test_patch_task_fields(client):
    """Update title and priority on an existing task."""
    created = client.post("/api/tasks", json={"title": "Initial title", "priority": "low"}).json()
    task_id = created["id"]

    response = client.patch(f"/api/tasks/{task_id}", json={"title": "Revised title", "priority": "urgent"})
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Revised title"
    assert data["priority"] == "urgent"


def test_list_tasks_and_filters(client):
    """Verify filtering tasks by status, priority, and keyword search."""
    # Seed tasks
    client.post("/api/tasks", json={"title": "Deploy API", "priority": "urgent"})
    client.post("/api/tasks", json={"title": "Write unit tests", "priority": "high"})
    client.post("/api/tasks", json={"title": "Update README docs", "priority": "low"})

    # Mark first task as completed
    all_res = client.get("/api/tasks").json()
    assert all_res["total"] >= 3

    first_id = all_res["tasks"][0]["id"]
    client.patch(f"/api/tasks/{first_id}", json={"status": "completed"})

    # Filter by status
    completed_res = client.get("/api/tasks?status=completed").json()
    assert completed_res["total"] >= 1
    assert all(t["status"] == "completed" for t in completed_res["tasks"])

    # Filter by priority
    urgent_res = client.get("/api/tasks?priority=urgent").json()
    assert all(t["priority"] == "urgent" for t in urgent_res["tasks"])

    # Search keyword
    search_res = client.get("/api/tasks?search=README").json()
    assert search_res["total"] >= 1
    assert any("README" in t["title"] for t in search_res["tasks"])


def test_delete_task(client):
    """Delete task returns 204, subsequent lookup returns 404."""
    created = client.post("/api/tasks", json={"title": "Ephemeral task"}).json()
    task_id = created["id"]

    del_res = client.delete(f"/api/tasks/{task_id}")
    assert del_res.status_code == 204

    get_res = client.get(f"/api/tasks/{task_id}")
    assert get_res.status_code == 404


def test_database_persistence_across_sessions(TestingSessionLocal):
    """Directly test that task writes in SQLite persist across distinct database sessions."""
    # Session 1: Create task
    session1 = TestingSessionLocal()
    task_in = TaskCreate(
        title="Persistent SQLite Task",
        description="Must survive session closure",
        priority=TaskPriority.HIGH,
    )
    task = task_service.create_task(session1, task_in)
    saved_id = task.id
    session1.close()

    # Session 2: Open completely separate session and verify presence
    session2 = TestingSessionLocal()
    fetched = task_service.get_task(session2, saved_id)
    assert fetched is not None
    assert fetched.id == saved_id
    assert fetched.title == "Persistent SQLite Task"
    assert fetched.priority == "high"
    assert fetched.status == "pending"

    # Cleanup
    task_service.delete_task(session2, saved_id)
    session2.close()


def test_user_preferences_api(client):
    """Verify default seeded user preferences and updating a preference."""
    # List preferences
    res = client.get("/api/preferences")
    assert res.status_code == 200
    prefs = res.json()["preferences"]
    assert "confirm_consequential_actions" in prefs
    assert prefs["confirm_consequential_actions"] == "true"

    # Set / update preference
    put_res = client.put(
        "/api/preferences/confirm_consequential_actions",
        json={"value": "strict", "category": "security", "description": "Strict human-in-the-loop confirmation"},
    )
    assert put_res.status_code == 200
    assert put_res.json()["value"] == "strict"

    # Verify updated value
    verify_res = client.get("/api/preferences?category=security")
    assert verify_res.json()["preferences"]["confirm_consequential_actions"] == "strict"
