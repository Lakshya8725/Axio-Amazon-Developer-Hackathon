"""Business logic service for task management."""

from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.task import Task, TaskPriority, TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate


def create_task(db: Session, task_in: TaskCreate) -> Task:
    """Create and persist a new task."""
    task = Task(
        title=task_in.title.strip(),
        description=task_in.description.strip() if task_in.description else None,
        priority=task_in.priority.value if isinstance(task_in.priority, TaskPriority) else str(task_in.priority),
        status=TaskStatus.PENDING.value,
        due_date=task_in.due_date,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, task_id: int) -> Optional[Task]:
    """Retrieve a single task by ID."""
    return db.query(Task).filter(Task.id == task_id).first()


def list_tasks(
    db: Session,
    status: Optional[TaskStatus | str] = None,
    priority: Optional[TaskPriority | str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Tuple[List[Task], int]:
    """List tasks with optional filters for status, priority, and search."""
    query = db.query(Task)

    if status:
        status_val = status.value if isinstance(status, TaskStatus) else str(status)
        query = query.filter(Task.status == status_val)

    if priority:
        priority_val = priority.value if isinstance(priority, TaskPriority) else str(priority)
        query = query.filter(Task.priority == priority_val)

    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Task.title.ilike(search_pattern),
                Task.description.ilike(search_pattern),
            )
        )

    total = query.count()
    tasks = query.order_by(Task.created_at.desc()).offset(offset).limit(limit).all()
    return tasks, total


def update_task(db: Session, task_id: int, task_in: TaskUpdate) -> Optional[Task]:
    """Update fields on an existing task."""
    task = get_task(db, task_id)
    if not task:
        return None

    update_data = task_in.model_dump(exclude_unset=True)

    if "title" in update_data and update_data["title"] is not None:
        task.title = update_data["title"].strip()

    if "description" in update_data:
        task.description = update_data["description"].strip() if update_data["description"] else None

    if "priority" in update_data and update_data["priority"] is not None:
        p = update_data["priority"]
        task.priority = p.value if isinstance(p, TaskPriority) else str(p)

    if "status" in update_data and update_data["status"] is not None:
        s = update_data["status"]
        task.status = s.value if isinstance(s, TaskStatus) else str(s)

    if "due_date" in update_data:
        task.due_date = update_data["due_date"]

    db.commit()
    db.refresh(task)
    return task


def update_task_status(db: Session, task_id: int, status: TaskStatus | str) -> Optional[Task]:
    """Update only the status of an existing task."""
    task = get_task(db, task_id)
    if not task:
        return None

    status_val = status.value if isinstance(status, TaskStatus) else str(status)
    task.status = status_val
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task_id: int) -> bool:
    """Delete a task by ID."""
    task = get_task(db, task_id)
    if not task:
        return False
    db.delete(task)
    db.commit()
    return True
