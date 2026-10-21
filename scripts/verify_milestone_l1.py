"""Comprehensive verification script for Milestone L1: Backend Foundation."""

import os
import sys
import tempfile
from datetime import datetime, timezone
from fastapi.testclient import TestClient

# Ensure repo root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
from app.models.task import Task
from app.services.preference_service import seed_default_preferences


def run_milestone_l1_verification():
    print("=" * 60)
    print("AXIO MILESTONE L1: BACKEND FOUNDATION VERIFICATION")
    print("=" * 60)

    # 1. Use a temporary SQLite database on disk
    temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db", prefix="axio_l1_verify_")
    os.close(temp_db_fd)
    db_url = f"sqlite:///{temp_db_path}"
    print(f"\n[Step 1] Initializing persistent SQLite database at: {temp_db_path}")

    engine1 = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine1)
    SessionMaker1 = sessionmaker(autocommit=False, autoflush=False, bind=engine1)

    with SessionMaker1() as seed_session:
        seed_default_preferences(seed_session)

    # Wire TestClient to this SQLite database
    def get_test_db():
        db = SessionMaker1()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = get_test_db
    client1 = TestClient(app)

    # 2. Test GET /health
    print("\n[Step 2] Testing GET /health...")
    health_res = client1.get("/health")
    assert health_res.status_code == 200, f"Expected 200, got {health_res.status_code}"
    health_data = health_res.json()
    print(f"       Status: {health_data['status']}")
    print(f"       App: {health_data['app']} (v{health_data['version']})")
    assert health_data["status"] == "healthy"

    # 3. Test POST /api/tasks
    print("\n[Step 3] Testing POST /api/tasks (Creation & Validation)...")
    task_payload = {
        "title": "Set up Alexa+ Operator Bridge",
        "description": "Connect natural language intents to autonomous action sequences",
        "priority": "urgent",
        "due_date": "2026-11-05T15:00:00Z"
    }
    create_res = client1.post("/api/tasks", json=task_payload)
    assert create_res.status_code == 201, f"Expected 201, got {create_res.status_code}"
    created_task = create_res.json()
    task_id = created_task["id"]
    print(f"       Created Task ID: {task_id}")
    print(f"       Title: '{created_task['title']}'")
    print(f"       Priority: '{created_task['priority']}' | Status: '{created_task['status']}'")
    assert created_task["priority"] == "urgent"
    assert created_task["status"] == "pending"

    # 4. Test Validation Rejections
    print("\n[Step 4] Testing Input Validation & Error Envelopes...")
    # Empty title
    err_empty = client1.post("/api/tasks", json={"title": "   "})
    assert err_empty.status_code == 422, f"Expected 422, got {err_empty.status_code}"
    print(f"       Empty title rejection: 422 Unprocessable Entity (Verified)")

    # Invalid priority
    err_pri = client1.post("/api/tasks", json={"title": "Test", "priority": "super_critical"})
    assert err_pri.status_code == 422, f"Expected 422, got {err_pri.status_code}"
    print(f"       Invalid priority rejection: 422 Unprocessable Entity (Verified)")

    # 5. Test GET /api/tasks
    print("\n[Step 5] Testing GET /api/tasks (Listing & Filtering)...")
    list_res = client1.get("/api/tasks?priority=urgent")
    assert list_res.status_code == 200
    list_data = list_res.json()
    print(f"       Total Tasks Found: {list_data['total']}")
    assert list_data["total"] >= 1
    assert any(t["id"] == task_id for t in list_data["tasks"])

    # 6. Test PATCH /api/tasks/{task_id}
    print(f"\n[Step 6] Testing PATCH /api/tasks/{task_id} (State Transition)...")
    patch_res = client1.patch(
        f"/api/tasks/{task_id}",
        json={"status": "in_progress", "description": "Action sequence execution underway"}
    )
    assert patch_res.status_code == 200
    patched_task = patch_res.json()
    print(f"       Updated Status: '{patched_task['status']}'")
    print(f"       Updated Description: '{patched_task['description']}'")
    assert patched_task["status"] == "in_progress"

    # 7. Test Missing Task (404)
    print("\n[Step 7] Testing Missing Task (404 Not Found)...")
    missing_res = client1.get("/api/tasks/88888")
    assert missing_res.status_code == 404
    print(f"       Missing Task Response: {missing_res.status_code} ({missing_res.json()['detail']})")

    # 8. Test SQLite Persistence Across Complete Application & Engine Restart
    print("\n[Step 8] Testing Persistence Across Complete Process/Session Restart...")
    # Dispose first engine & client
    client1.close()
    engine1.dispose()

    # Reconnect with a new engine & session factory to the exact same file
    engine2 = create_engine(db_url, connect_args={"check_same_thread": False})
    SessionMaker2 = sessionmaker(autocommit=False, autoflush=False, bind=engine2)

    def get_test_db_2():
        db = SessionMaker2()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = get_test_db_2
    client2 = TestClient(app)

    restarted_get = client2.get(f"/api/tasks/{task_id}")
    assert restarted_get.status_code == 200, "Task was lost after database restart!"
    restarted_data = restarted_get.json()
    print(f"       Recovered Task ID: {restarted_data['id']}")
    print(f"       Recovered Title: '{restarted_data['title']}'")
    print(f"       Recovered Status: '{restarted_data['status']}'")
    assert restarted_data["id"] == task_id
    assert restarted_data["status"] == "in_progress"
    print("       Persistence Across Restarts: VERIFIED")

    # Cleanup
    client2.close()
    engine2.dispose()
    app.dependency_overrides.clear()
    if os.path.exists(temp_db_path):
        try:
            os.remove(temp_db_path)
        except OSError:
            pass

    print("\n" + "=" * 60)
    print("ALL MILESTONE L1 REQUIREMENTS VERIFIED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_milestone_l1_verification()
