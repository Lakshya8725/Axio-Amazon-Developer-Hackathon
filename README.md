# Axio — AI Personal Operator

> **"Your intent. In action."**

Axio is a premium AI personal operator built for the **Amazon AppDev 2026 Hackathon** under the **Alexa+ AI Agents and Automation track**.

Unlike typical chatbots that merely generate conversational text, Axio transforms natural-language requests into verifiable actions. It maintains persistent task state and user preferences in SQLite, exposes verified tools over the official **Model Context Protocol (MCP)** using modern Streamable HTTP transport, and enforces human-in-the-loop approvals before consequential changes.

---

## Architecture Overview

```
                                      +--------------------------+
                                      |   MCP Clients / Agents   |
                                      +-------------+------------+
                                                    |
                                          Streamable HTTP (/mcp)
                                                    v
+--------------------------+          +--------------------------+
|  Web UI / REST Clients   | -------> |    FastAPI Application   |
+--------------------------+          +-------------+------------+
        (HTTP /api/*)                               |
                                                    v
                                      +--------------------------+
                                      |   Domain Service Layer   |
                                      +-------------+------------+
                                                    |
                                                    v
                                      +--------------------------+
                                      | SQLite DB (SQLAlchemy)   |
                                      +--------------------------+
```

- **Backend**: Python 3.10+ / 3.12+ with FastAPI.
- **MCP Server**: Official Python MCP SDK (`mcp>=1.3.0`, v2.x architecture) implementing **Streamable HTTP** transport conforming to MCP specification `2025-11-25`.
- **Persistence**: SQLite with SQLAlchemy ORM, foreign key enforcement, and automatic schema initialization.
- **Validation**: Pydantic v2 schemas with strict validation against empty strings, invalid statuses, and invalid priorities.
- **Testing**: Deterministic pytest test suite covering API contracts, persistence across database sessions, and live MCP protocol handshakes.

---

## Repository Structure

```
axio-ai-operator/
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore patterns
├── README.md                 # Project documentation
├── requirements.txt          # Root Python dependencies
├── backend/
│   ├── .env.example          # Backend-specific environment template
│   ├── requirements.txt      # Backend dependency manifest
│   ├── app/
│   │   ├── __init__.py       # Package marker
│   │   ├── config.py         # Pydantic BaseSettings environment loader
│   │   ├── database.py       # SQLAlchemy engine, sessionmaker, and init_db
│   │   ├── main.py           # FastAPI application & dynamic MCP Starlette mount
│   │   ├── models/           # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── task.py       # Task model (status, priority, due date)
│   │   │   └── preference.py # UserPreference model
│   │   ├── schemas/          # Pydantic v2 schemas
│   │   │   ├── __init__.py
│   │   │   ├── task.py       # Task validation & response schemas
│   │   │   └── preference.py # Preference schemas
│   │   ├── services/         # Business logic layer
│   │   │   ├── __init__.py
│   │   │   ├── task_service.py
│   │   │   └── preference_service.py
│   │   └── tools/            # MCP tool definitions & server
│   │       ├── __init__.py
│   │       └── mcp_server.py # Axio MCPServer with registered tools
│   └── tests/                # Automated test suite
│       ├── __init__.py
│       ├── conftest.py       # Isolated SQLite test fixtures & TestClient
│       ├── test_health.py    # Health check & service discovery tests
│       ├── test_tasks.py     # Task CRUD, filters, validation, & persistence tests
│       └── test_mcp.py       # MCP registration, direct calls, & live HTTP tests
└── scripts/
    └── verify_mcp_client.py  # End-to-end live MCP client verification script
```

---

## Windows Setup & Installation

### 1. Prerequisites
- **Windows 10 / 11**
- **Python 3.10+ or 3.12+**
- **Git for Windows**

### 2. Clone and Setup Environment

In PowerShell:
```powershell
# Navigate to repository directory
cd c:\Users\HP\OneDrive\Desktop\PROJECTS\AXIO-AMAZON-DEVELOPER

# (Optional) Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```

Default settings:
```ini
AXIO_ENV=development
AXIO_HOST=127.0.0.1
AXIO_PORT=8000
LOG_LEVEL=INFO
DATABASE_URL=sqlite:///./axio.db
MCP_SERVER_NAME=axio
MCP_SERVER_VERSION=0.1.0
MCP_MOUNT_PATH=/mcp
```

---

## Running the Application

### Option A: Unified Server (FastAPI + MCP Streamable HTTP)
Starts the FastAPI application and mounts the official MCP server on `/mcp`:
```powershell
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```
Once started:
- **Interactive OpenAPI Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Endpoint**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- **MCP Streamable HTTP Endpoint**: `http://127.0.0.1:8000/mcp`

### Option B: Standalone MCP Server
To run the MCP server independently on a dedicated port:
```powershell
python -m backend.app.tools.mcp_server
```

---

## Testing

Run the automated test suite with pytest:
```powershell
python -m pytest backend/tests -v
```

All 17 tests run in isolation against a clean temporary SQLite database:
- `backend/tests/test_health.py`:
  - `test_health_check` (PASS)
- `backend/tests/test_mcp.py`:
  - `test_mcp_tool_registration` (PASS)
  - `test_mcp_tool_direct_invocation` (PASS)
  - `test_mcp_tool_validation_and_error_handling` (PASS)
  - `test_mcp_streamable_http_session_and_protocol` (PASS)
- `backend/tests/test_tasks.py`:
  - `test_create_task_minimal` (PASS)
  - `test_create_task_full` (PASS)
  - `test_create_task_validation_errors` (PASS)
  - `test_get_task_by_id` (PASS)
  - `test_get_task_not_found` (PASS)
  - `test_patch_task_status` (PASS)
  - `test_patch_task_invalid_status` (PASS)
  - `test_patch_task_fields` (PASS)
  - `test_list_tasks_and_filters` (PASS)
  - `test_delete_task` (PASS)
  - `test_database_persistence_across_sessions` (PASS)
  - `test_user_preferences_api` (PASS)

---

## Verifying with a Real MCP Client

With the server running on `http://127.0.0.1:8000`, run the verification script:
```powershell
python scripts/verify_mcp_client.py --url http://127.0.0.1:8000/mcp
```

### Verified Output:
```text
[1/4] Connecting to Axio MCP server at: http://127.0.0.1:8000/mcp
[2/4] Initializing protocol session...
      Connected to server: axio (version: 0.1.0)
[3/4] Discovering tools...
      Discovered 4 tools:
       - get_tasks: List existing tasks from Axio's persistent store with optional fi...
       - create_task: Create a new persistent task in Axio. Requires a title. Optional ...
       - update_task_status: Update the execution status of an existing task by ID. Allowed st...
       - get_user_preferences: Retrieve configured user and operator preferences (such as confir...
[4/4] Invoking 'create_task' via MCP Streamable HTTP...
      Result: Task 'Verify MCP Streamable HTTP Client' created with ID 6.
      Invoking 'get_tasks' filtered by task ID 6...
      Found 1 matching tasks in persistence store.

 MCP Client Verification Passed Successfully!
```

---

## API & MCP Reference

### REST Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service health status and metadata |
| `GET` | `/api/tasks` | List tasks with filters (`status`, `priority`, `search`, `limit`, `offset`) |
| `POST` | `/api/tasks` | Create a new action task |
| `GET` | `/api/tasks/{task_id}` | Retrieve specific task details |
| `PATCH` | `/api/tasks/{task_id}` | Update status, title, description, or priority |
| `DELETE` | `/api/tasks/{task_id}` | Remove task from persistence |
| `GET` | `/api/preferences` | Retrieve stored operator preferences |
| `PUT` | `/api/preferences/{key}` | Set or update a preference key-value pair |

### MCP Tools (Streamable HTTP `/mcp`)

| Tool Name | Parameters | Description |
|---|---|---|
| `get_tasks` | `status`, `priority`, `search`, `limit` | Query tasks from SQLite persistence |
| `create_task` | `title`, `description`, `priority`, `due_date` | Register a new task with validation |
| `update_task_status` | `task_id`, `status` | Transition task state (`pending`, `in_progress`, `completed`, `cancelled`) |
| `get_user_preferences` | `category` | Retrieve operator preferences (e.g. security confirmation policy) |

---

## Security & Reliability Design

1. **Deterministic Arguments**: All MCP tools and REST endpoints validate input types and values against explicit enums and constraints before touching the database.
2. **Safe Persistence**: SQLAlchemy ORM with parameterized queries prevents SQL injection. SQLite foreign keys are enforced via runtime PRAGMAs.
3. **DNS Rebinding Protection**: Localhost MCP transport security limits allowed hosts and origins to `127.0.0.1`, `localhost`, and `[::1]`.
4. **Isolated Test Database**: Automated tests run on ephemeral temporary SQLite files and clean up after execution.
5. **Human Approval Safeguards**: Default seeded user preferences enforce `confirm_consequential_actions = true` for high-impact operator workflows.

---

## Next Milestone: Phase 2

- **Next.js 14+ / TypeScript / Tailwind CSS** operator dashboard.
- Workflow execution planner with multi-step action breakdown.
- Consequential action approval modal with verifiable audit trail.
- Alexa+ Agent skill bridge integration.