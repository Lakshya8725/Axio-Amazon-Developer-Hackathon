# Axio Backend API Contract
**Milestone L1 — Backend Foundation**
**Audience:** Smriti (Frontend Lead) & Lakshya (Backend Lead)  
**Base URL:** `http://127.0.0.1:8000`
**Interactive OpenAPI Docs:** `http://127.0.0.1:8000/docs`
**ReDoc Specification:** `http://127.0.0.1:8000/redoc`

---

## 1. Overview & Architecture

Axio is a proactive AI personal operator ("Your intent. In action."). The backend provides a typed REST API powered by **FastAPI**, **SQLAlchemy ORM**, **Pydantic v2**, and **SQLite** persistence.

- All request bodies and response payloads are strictly JSON formatted (`application/json`).
- DateTime values adhere strictly to **ISO 8601** UTC timestamps (e.g., `2026-10-25T14:30:00Z`).
- Database records persist across application restarts in local SQLite (`axio.db`).

---

## 2. CORS Configuration

The FastAPI backend allows local development origins and keeps credentialed requests valid:
- **Allowed Origins:** `http://127.0.0.1:3000`, `http://localhost:3000`, `http://127.0.0.1:8080`, `http://localhost:8080`, plus any `http` or `https` localhost / `127.0.0.1` port
- **Allowed Methods:** `GET`, `POST`, `PATCH`, `PUT`, `DELETE`, `OPTIONS`
- **Allowed Headers:** `*`
- **Allow Credentials:** `true`

---

## 3. Data Models & Enums

### Task Status Enum (`status`)
Allowed status values for tasks:
| Value | Description |
|---|---|
| `pending` | Task registered, queued for action, default state upon creation |
| `in_progress` | Execution in progress by user or autonomous agent |
| `completed` | Task successfully resolved and verified |
| `cancelled` | Task dismissed or aborted |

### Task Priority Enum (`priority`)
Allowed urgency levels for tasks:
| Value | Description |
|---|---|
| `low` | Background / non-urgent item |
| `medium` | Standard action item (default) |
| `high` | High-priority action requiring prompt attention |
| `urgent` | Critical blocker or immediate deadline |

### Task Object Schema (`TaskRead`)
```typescript
interface Task {
  id: number;                   // Unique integer identifier (auto-incrementing)
  title: string;                // 1 to 255 chars, cannot be pure whitespace
  description: string | null;   // Optional rich context / action details
  priority: "low" | "medium" | "high" | "urgent"; // Default: "medium"
  status: "pending" | "in_progress" | "completed" | "cancelled"; // Default: "pending"
  due_date: string | null;      // ISO 8601 datetime or null
  created_at: string;           // ISO 8601 UTC timestamp
  updated_at: string;           // ISO 8601 UTC timestamp
}
```

---

## 4. REST Endpoints

### 4.1 Service index
`GET /`

The API root is a real route.

- **Browser request** (`Accept: text/html`): an HTML service page with a link to the operator at `http://127.0.0.1:3000`, plus health and docs.
- **Other clients:** JSON discovery document.

```json
{
  "app": "Axio",
  "tagline": "Your intent. In action.",
  "status": "online",
  "version": "0.1.0",
  "environment": "development",
  "operator_ui": "http://127.0.0.1:3000",
  "health": "/health",
  "docs": "/docs",
  "openapi": "/openapi.json",
  "mcp_endpoint": "/mcp",
  "agent": "/api/agent/run",
  "tasks": "/api/tasks"
}
```

### 4.2 System Health
`GET /health`
Returns system status, active version, and MCP endpoint discovery.

- **Request:** None
- **Response `200 OK`:**
```json
{
  "status": "healthy",
  "app": "Axio",
  "version": "0.1.0",
  "environment": "development",
  "mcp_endpoint": "/mcp"
}
```

---

### 4.3 List Tasks
`GET /api/tasks`
Retrieve a list of tasks with optional filtering and pagination.

- **Query Parameters:**
  - `status` *(optional string)*: Filter by status (`pending`, `in_progress`, `completed`, `cancelled`)
  - `priority` *(optional string)*: Filter by priority (`low`, `medium`, `high`, `urgent`)
  - `search` *(optional string)*: Case-insensitive substring match on `title` or `description`
  - `limit` *(optional int, default: 50, min: 1, max: 100)*: Maximum items to return
  - `offset` *(optional int, default: 0, min: 0)*: Number of items to skip for pagination

- **Response `200 OK`:**
```json
{
  "tasks": [
    {
      "id": 1,
      "title": "Prepare Amazon AppDev 2026 demo deck",
      "description": "Outline autonomous operator architecture and live MCP tooling",
      "priority": "high",
      "status": "pending",
      "due_date": "2026-10-31T18:00:00Z",
      "created_at": "2026-10-20T13:00:00Z",
      "updated_at": "2026-10-20T13:00:00Z"
    }
  ],
  "total": 1,
  "filters": {
    "status": null,
    "priority": null,
    "search": null,
    "limit": 50,
    "offset": 0
  }
}
```

---

### 4.4 Create Task
`POST /api/tasks`
Creates a new persistent task.

- **Request Headers:** `Content-Type: application/json`
- **Request Body (`TaskCreate`):**
```json
{
  "title": "Configure MCP Streamable HTTP transport",
  "description": "Mount official Python MCP session manager on /mcp",
  "priority": "urgent",
  "due_date": "2026-10-25T12:00:00Z"
}
```
*Note: `title` is required. `description`, `priority` (defaults to `"medium"`), and `due_date` (defaults to `null`) are optional.*

- **Response `201 Created`:**
```json
{
  "id": 2,
  "title": "Configure MCP Streamable HTTP transport",
  "description": "Mount official Python MCP session manager on /mcp",
  "priority": "urgent",
  "status": "pending",
  "due_date": "2026-10-25T12:00:00Z",
  "created_at": "2026-10-20T13:05:00Z",
  "updated_at": "2026-10-20T13:05:00Z"
}
```

---

### 4.5 Get Task By ID
`GET /api/tasks/{task_id}`
Retrieve a single task by its integer identifier.

- **Response `200 OK`:**
```json
{
  "id": 2,
  "title": "Configure MCP Streamable HTTP transport",
  "description": "Mount official Python MCP session manager on /mcp",
  "priority": "urgent",
  "status": "pending",
  "due_date": "2026-10-25T12:00:00Z",
  "created_at": "2026-10-20T13:05:00Z",
  "updated_at": "2026-10-20T13:05:00Z"
}
```

- **Error `404 Not Found`:**
```json
{
  "detail": "Task with ID 999 not found"
}
```

---

### 4.6 Update Task (Partial Patch)
`PATCH /api/tasks/{task_id}`
Update one or more mutable fields of an existing task.

- **Request Headers:** `Content-Type: application/json`
- **Request Body (`TaskUpdate` - all fields optional):**
```json
{
  "status": "in_progress",
  "priority": "high",
  "description": "Updated context: session manager mounting tested"
}
```

- **Response `200 OK`:**
```json
{
  "id": 2,
  "title": "Configure MCP Streamable HTTP transport",
  "description": "Updated context: session manager mounting tested",
  "priority": "high",
  "status": "in_progress",
  "due_date": "2026-10-25T12:00:00Z",
  "created_at": "2026-10-20T13:05:00Z",
  "updated_at": "2026-10-20T13:10:00Z"
}
```

- **Error `404 Not Found`:**
```json
{
  "detail": "Task with ID 999 not found"
}
```

---

### 4.7 Delete Task
`DELETE /api/tasks/{task_id}`
Permanently remove a task from persistent storage.

- **Response `204 No Content`** (empty body)
- **Error `404 Not Found`:**
```json
{
  "detail": "Task with ID 999 not found"
}
```

---

### 4.8 User Preferences API
Endpoints for reading and writing operator safety configurations (e.g. `confirm_consequential_actions`).

- `GET /api/preferences` (optional `?category=security`)
- `PUT /api/preferences/{key}`
  ```json
  {
    "value": "true",
    "category": "security",
    "description": "Prompt operator before executing high-impact external actions"
  }
  ```

---

### 4.9 Agent Orchestration
`POST /api/agent/run`

**Purpose**: Transform a natural‑language instruction into an ordered plan and optionally execute it.

**Supported instruction types**: Currently only the demo phrase "Organize my evening. Prioritize my unfinished tasks and leave time for interview preparation." is recognized. Other instructions return a `400` error.

**Request body** (`AgentRunRequest`):
```json
{
  "instruction": "string (required, non‑empty)",
  "dry_run": false,
  "approve": false
}
```
- `dry_run` (default `false`): when `true` the plan is generated and read‑only steps are executed, but any state‑changing actions (`create_task`, `update_task_status`) are skipped.
- `approve` (default `false`): required to run steps flagged `requires_approval`. If `false`, those steps are reported as `skipped`.

**Response body** (`PlanResponse`):
```json
{
  "request_id": "uuid",
  "interpreted_intent": "string",
  "plan": [
    {
      "name": "string",
      "tool": "get_tasks" | "create_task" | "update_task_status" | "get_user_preferences",
      "arguments": {},
      "requires_approval": false,
      "expected_result": "string"
    }
  ],
  "step_results": {
    "0": {"status": "success"|"failed"|"skipped", "detail": "string", "output": {...}},
    "1": {"status": "..."}
  },
  "final_summary": "string"
}
```
Each step includes its execution `status`. Steps that require approval but are not approved are marked `skipped`. In preview mode all mutation steps are also `skipped`.

The read step returns unfinished tasks only (`pending` and `in_progress`). The "Propose ordered task list" step is also read-only. Its `output` is the evening order:

```json
{
  "ordered": true,
  "total": 1,
  "tasks": [
    {
      "id": 1,
      "title": "Confirm recruiter callback",
      "description": "Lock the conversation before the evening block.",
      "priority": "urgent",
      "status": "pending",
      "due_date": "2026-10-23T18:00:00Z"
    }
  ]
}
```

Sort order is priority (urgent, high, medium, low), then earliest due date. Tasks without a due date come after dated tasks of the same priority. Completed and cancelled tasks are excluded. Preview does not create the interview-preparation task. A later approved run reuses that task instead of inserting a duplicate. If a non-preview run skips steps because `approve` is false, `final_summary` says those steps were skipped.

**Error responses**:
- `422 Unprocessable Entity` – validation errors (e.g., empty instruction).
- `400 Bad Request` – instruction could not be interpreted.
- `500 Internal Server Error` – unexpected failures inside the service.

**PowerShell example**:
```powershell
$payload = @{
    instruction = "Organize my evening. Prioritize my unfinished tasks and leave time for interview preparation."
    dry_run    = $true
    approve    = $false
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/agent/run -Body $payload -ContentType 'application/json'
```
Replace `dry_run` with `$false` and `approve` with `$true` to execute the plan.

---


## 5. Error Responses & Format

FastAPI produces standardized RFC-compliant error envelopes:

### Validation Error (`422 Unprocessable Entity`)
Returned when payload fails type, length, or enum constraints.
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "title"],
      "msg": "String should have at least 1 characters",
      "input": ""
    }
  ]
}
```

### Resource Missing (`404 Not Found`)
```json
{
  "detail": "Task with ID 42 not found"
}
```

---

## 6. Local Setup & Quickstart

### Prerequisites
- Python 3.10+ (Windows 10/11 tested)
- Git for Windows

### Setup Environment
```powershell
# In repository root:
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

### Start the Server
```powershell
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

### Run Automated Backend Tests
```powershell
python -m pytest backend/tests -v
```
The pytest suite executes in isolation using a temporary SQLite database. From the repository root: `python -m pytest`.
