# Axio — AI Personal Operator

> **"Your intent. In action."**

Axio is an AI personal operator built for the **Amazon AppDev 2026 Hackathon** under the **Alexa+ AI Agents and Automation track**.

It turns one instruction into a plan you can inspect, then into a verified change. Persistent tasks and preferences live in SQLite. Tools are exposed over the official **Model Context Protocol (MCP)** using Streamable HTTP. Consequential writes wait for an explicit approval.

The agent in this repository is deterministic. It recognizes one demo instruction and does not call a live language model:

> Organize my evening. Prioritize my unfinished tasks and leave time for interview preparation.

---

## Demo

1. Start the API and the operator (commands below).
2. Open [http://127.0.0.1:3000](http://127.0.0.1:3000). The status pill should say **Operator live**.
3. If the ledger is empty, choose **Load evening sample**. The sample does not insert the interview task.
4. Leave the instruction as the evening line above and choose **Preview plan**. Nothing is written.
5. If interview preparation is not already in the ledger, confirm the write and choose **Approve and execute**.
6. Preview again. Axio reports that nothing needs a write and does not create a duplicate.

[http://127.0.0.1:8000](http://127.0.0.1:8000) is the API home. A browser shows the service page. An API client receives the same discovery data as JSON.

---

## Architecture

```
                                      +--------------------------+
                                      |   MCP Clients / Agents   |
                                      +-------------+------------+
                                                    |
                                          Streamable HTTP (/mcp)
                                                    v
+--------------------------+          +--------------------------+
|  Operator UI / REST      | -------> |    FastAPI Application   |
+--------------------------+          +-------------+------------+
        (HTTP /api/*)                               |
                                                    v
                                      +--------------------------+
                                      |   Domain Service Layer   |
                                      |   Tasks, preferences,    |
                                      |   evening orchestration  |
                                      +-------------+------------+
                                                    |
                                                    v
                                      +--------------------------+
                                      | SQLite DB (SQLAlchemy)   |
                                      +--------------------------+
```

- **Operator UI**: Next.js, React, TypeScript, and Tailwind CSS in `web/`.
- **Backend**: Python 3.10+ with FastAPI. Local development uses Python 3.11.
- **MCP server**: Official Python MCP SDK (`mcp>=1.3.0`, v2.x) implementing **Streamable HTTP**, MCP specification `2025-11-25`, mounted at `/mcp`.
- **Persistence**: SQLite with SQLAlchemy, foreign-key enforcement, and automatic schema initialization.
- **Validation**: Pydantic v2. Empty titles, unknown statuses, and unknown priorities are rejected.
- **Orchestration**: `POST /api/agent/run` builds the evening plan in-process. Preview (`dry_run: true`) does not mutate tasks. A write requires `approve: true`.
- **Testing**: pytest against a temporary SQLite database, including API contracts, MCP handshakes, approval gating, ordering, and duplicate prevention.

`frontend/` is a small static fallback on the same API. The product surface is `web/`.

---

## Repository structure

```
Axio-Amazon-Developer-Hackathon/
├── .env.example
├── .gitignore
├── README.md
├── API_CONTRACT.md
├── requirements.txt
├── pytest.ini
├── web/                          # Next.js operator
│   ├── src/app/
│   ├── src/components/
│   └── src/lib/                  # Typed API client
├── frontend/                     # Static fallback
├── scripts/
│   ├── seed_demo.py
│   ├── verify_mcp_client.py
│   └── verify_milestone_l1.py
└── backend/
    ├── app/
    │   ├── main.py               # FastAPI app, service home, MCP mount
    │   ├── config.py
    │   ├── database.py
    │   ├── models/
    │   ├── schemas/              # Tasks, preferences, orchestration
    │   ├── services/             # Tasks, preferences, evening plan
    │   └── tools/mcp_server.py
    └── tests/
        ├── test_health.py
        ├── test_tasks.py
        ├── test_mcp.py
        └── test_orchestration.py
```

---

## Setup

### Prerequisites

- Python 3.10 or newer (3.11 is what this demo uses)
- Node.js 20 or newer
- Git

### macOS or Linux

From the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Start the API:

```bash
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In a second terminal, start the operator:

```bash
cd web
npm install
npm run dev
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000).

### Windows

In PowerShell, from the repository root:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd web
npm install
npm run dev
```

### Environment

`.env.example` is the template. Defaults:

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

The operator calls `/axio-api`, and Next.js proxies that to `http://127.0.0.1:8000`. Override the proxy with `API_PROXY_TARGET`. Set `NEXT_PUBLIC_API_BASE_URL` only if the browser should call FastAPI directly. Do not put secrets in `NEXT_PUBLIC_*` variables.

Seed the evening tasks without creating the interview block:

```bash
python scripts/seed_demo.py
```

---

## Running

| Surface | Address |
|---|---|
| Operator | [http://127.0.0.1:3000](http://127.0.0.1:3000) |
| API home | [http://127.0.0.1:8000](http://127.0.0.1:8000) |
| OpenAPI | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) |
| Health | [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) |
| MCP Streamable HTTP | `http://127.0.0.1:8000/mcp` |

The MCP server is mounted inside the FastAPI process. A standalone entry point also exists:

```bash
python -m backend.app.tools.mcp_server
```

---

## Testing

From the repository root, with the virtual environment active:

```bash
python -m pytest -q
```

The suite runs in isolation on a temporary SQLite database. It covers health and the service index, task CRUD, preferences, MCP registration and a live Streamable HTTP handshake, plan preview, approval gating, evening ordering, and duplicate interview-task prevention. Current count: **31 tests**.

---

## MCP client check

With the API running:

```bash
python scripts/verify_mcp_client.py --url http://127.0.0.1:8000/mcp
```

The script initializes a session, lists four tools (`get_tasks`, `create_task`, `update_task_status`, `get_user_preferences`), creates a task, and reads it back. That script writes into the local `axio.db`. The pytest MCP tests can do the same when they use the process database. Delete those rows from the ledger if they show up behind **Show finished**.

---

## API

Full request and response shapes are in [API_CONTRACT.md](API_CONTRACT.md).

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Service home. HTML in a browser, JSON for API clients |
| `GET` | `/health` | Status, version, environment, MCP path |
| `GET` | `/api/tasks` | List tasks (`status`, `priority`, `search`, `limit`, `offset`) |
| `POST` | `/api/tasks` | Create a task. New tasks start as `pending` |
| `GET` | `/api/tasks/{task_id}` | One task |
| `PATCH` | `/api/tasks/{task_id}` | Update title, description, priority, status, or due date |
| `DELETE` | `/api/tasks/{task_id}` | Delete a task |
| `GET` | `/api/preferences` | Operator preferences |
| `PUT` | `/api/preferences/{key}` | Set a preference |
| `POST` | `/api/agent/run` | Preview or execute the evening plan |

`POST /api/agent/run` accepts `instruction`, `dry_run` (default `false`), and `approve` (default `false`). Preview skips state-changing tools. A step that requires approval is skipped unless `approve` is true. The supported instruction is the evening line in the demo above.

### MCP tools

| Tool | Parameters | Purpose |
|---|---|---|
| `get_tasks` | `status`, `priority`, `search`, `limit` | Read tasks |
| `create_task` | `title`, `description`, `priority`, `due_date` | Create a validated task |
| `update_task_status` | `task_id`, `status` | `pending`, `in_progress`, `completed`, `cancelled` |
| `get_user_preferences` | `category` | Read preferences, including the confirmation policy |

Priorities are `low`, `medium`, `high`, and `urgent`. The evening order is priority, then earliest due date. Tasks without a due date come after dated tasks of the same priority. Completed and cancelled tasks stay out of that order.

---

## Safety

- Inputs are checked against explicit enums and constraints before they reach the database.
- SQLAlchemy uses parameterized queries. SQLite foreign keys are enabled with a runtime PRAGMA.
- MCP transport security allows `127.0.0.1`, `localhost`, and `[::1]`.
- Tests use a temporary database and clean it up.
- The seeded preference `confirm_consequential_actions` defaults to true. The operator still requires its own confirmation before it sends an approved run.
- Preview does not create or edit tasks. The execute button sends the instruction that was previewed, not a later edit in the text box.
