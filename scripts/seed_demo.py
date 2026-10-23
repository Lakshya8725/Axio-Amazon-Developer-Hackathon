#!/usr/bin/env python3
"""Insert the evening demo tasks when they are not already present.

The interview-preparation task is intentionally absent. Axio creates it only
after the operator approves the plan.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "backend"))

from app.database import SessionLocal, init_db  # noqa: E402
from app.schemas.task import TaskCreate  # noqa: E402
from app.services import task_service  # noqa: E402


def _samples():
    now = datetime.now(timezone.utc)
    return [
        {
            "title": "Confirm recruiter callback",
            "description": "Lock the conversation before the evening block.",
            "priority": "urgent",
            "due_date": now + timedelta(hours=3),
            "status": "pending",
        },
        {
            "title": "Draft hackathon demo outline",
            "description": "Sequence the live path: intent, preview, approval, result.",
            "priority": "high",
            "due_date": now + timedelta(hours=6),
            "status": "in_progress",
        },
        {
            "title": "Finish system design revision",
            "description": "One focused pass on the last open questions.",
            "priority": "high",
            "due_date": now + timedelta(hours=26),
            "status": "pending",
        },
        {
            "title": "Leave a 45-minute workout window",
            "description": "Protect time so the evening plan stays realistic.",
            "priority": "medium",
            "due_date": None,
            "status": "pending",
        },
        {
            "title": "Reply to family about dinner",
            "description": "A short message so it does not spill into focus time.",
            "priority": "low",
            "due_date": now + timedelta(hours=30),
            "status": "pending",
        },
        {
            "title": "Send yesterday's standup notes",
            "description": "Already done. Axio should leave this out of the evening order.",
            "priority": "low",
            "due_date": now - timedelta(hours=20),
            "status": "completed",
        },
    ]


def main() -> None:
    init_db()
    db = SessionLocal()
    created = 0
    try:
        for sample in _samples():
            existing, _ = task_service.list_tasks(db, search=sample["title"], limit=20)
            if any(task.title == sample["title"] for task in existing):
                continue
            task = task_service.create_task(
                db,
                TaskCreate(
                    title=sample["title"],
                    description=sample["description"],
                    priority=sample["priority"],
                    due_date=sample["due_date"],
                ),
            )
            if sample["status"] != "pending":
                task_service.update_task_status(db, task.id, sample["status"])
            created += 1
    finally:
        db.close()
    print(f"Seed complete. Created {created} task{'s' if created != 1 else ''}.")


if __name__ == "__main__":
    main()
