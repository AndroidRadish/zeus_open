# ZeusOpen v3

> Production multi-agent framework for AI-driven software engineering.

ZeusOpen v3 is a ground-up rewrite of the v2 execution engine, focused on:
- **Database-centric state** (SQLite/PostgreSQL) instead of file-lock `task.json` mutation
- **Queue-Worker separation** enabling horizontal scaling
- **Real-time observability** via SSE and a Vue 3 dashboard
- **Agent Result Protocol (ARP)** — structured `zeus-result.json` as the source of truth
- **Multi-container deployment** with Docker Compose and Redis

---

## Quick Start (Local)

### 1. Install dependencies

```bash
cd .zeus/v3/scripts
pip install -r requirements.txt
```

Required packages (already installed in this environment):
- `fastapi`, `uvicorn`, `sse-starlette`
- `sqlalchemy[asyncio]`, `aiosqlite`, `asyncpg`, `alembic`
- `redis`, `pydantic-settings`
- `opentelemetry-api`, `opentelemetry-sdk` (optional, for tracing)

### 2. Ensure database schema

```bash
python -c "from db.engine import make_async_engine; from db.models import Base; import asyncio; e=make_async_engine('sqlite+aiosqlite:///./.zeus/v3/state.db'); asyncio.run(e.begin().__aenter__().conn.run_sync(Base.metadata.create_all))"
```

Or simply run `run.py` — it auto-creates the schema on first launch.

### 3. Run the full pipeline (scheduler + workers)

```bash
python run.py --project-root . --max-workers 3
```

This will:
1. Import `task.json` into the database
2. Start the worker pool
3. Run the scheduler loop until all tasks complete
4. Print a summary

### 4. Start the API server + Dashboard

```bash
python run.py --mode serve --project-root . --host 0.0.0.0 --port 8000
```

Open http://127.0.0.1:8000/dashboard in your browser.

---

## CLI Modes

`run.py` supports four execution modes via `--mode`:

| Mode | Description |
|------|-------------|
| `combined` (default) | Runs scheduler + worker pool in one process |
| `scheduler` | Scheduling loop only (enqueues ready tasks) |
| `worker` | Worker pool only (consumes queue) |
| `serve` | FastAPI server + SSE stream + Dashboard |

### Multi-process example (memory queue)

Terminal 1:
```bash
python run.py --mode scheduler
```

Terminal 2:
```bash
python run.py --mode worker --max-workers 2
```

### Multi-node example (Redis queue)

Terminal 1 (scheduler):
```bash
python run.py --mode scheduler --queue-backend redis --redis-url redis://localhost:6379/0
```

Terminal 2-3 (workers):
```bash
python run.py --mode worker --max-workers 3 --queue-backend redis --redis-url redis://localhost:6379/0
```

---

## Task Configuration

Tasks are defined in `.zeus/v3/task.json` (static plan) and imported into the database at runtime.

Example task:

```json
{
  "version": "v3",
  "updated_at": "2026-04-13T00:00:00Z",
  "tasks": [
    {
      "id": "T-101",
      "title": "Add metrics API",
      "description": "Implement /metrics/summary endpoint",
      "type": "feat",
      "wave": 1,
      "depends_on": [],
      "files": [".zeus/v3/scripts/api/server.py"]
    }
  ]
}
```

Run `python run.py --import-only` to import without executing.

---

## Workspace Backends

Choose how agent workspaces are created:

| Backend | Config | Use case |
|---------|--------|----------|
| `copytree` (default) | `"workspace": {"backend": "copytree"}` | Full project copy; simple and safe |
| `git_worktree` | `"workspace": {"backend": "git_worktree"}` | Zero-copy via `git worktree`; requires git repo |

---

## API Endpoints

Base URL: `http://127.0.0.1:8000`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/tasks` | List all tasks (filter by `?status=` or `?wave=`) |
| GET | `/tasks/{id}` | Get single task details |
| GET | `/events` | Query event log (paginated) |
| GET | `/events/stream` | **SSE** real-time event stream |
| GET | `/metrics/summary` | High-level metrics + pass rate |
| GET | `/metrics/tasks` | Per-task duration and status |
| GET | `/metrics/bottleneck` | Top-N slowest tasks |
| GET | `/metrics/blocked` | Dependency chains blocked by failure/quarantine |
| GET | `/dashboard/` | Vue 3 SPA dashboard |

---

## Docker Compose Deployment

```bash
cd .zeus/v3
docker compose up --build
```

Services:
- `redis` — Shared task queue
- `zeus-api` — FastAPI on port `8000`
- `zeus-scheduler` — Scheduling loop
- `zeus-worker` — 2 replica worker pool

Scale workers:
```bash
docker compose up --scale zeus-worker=4
```

---

## Dispatcher Modes

Configured in `.zeus/v3/config.json` under `subagent.dispatcher`:

| Dispatcher | Behavior |
|------------|----------|
| `mock` | Writes a stub `zeus-result.json` instantly |
| `kimi` | Spawns `kimi --prompt ... --work-dir ...` |
| `claude` | Spawns `claude -p ... --cwd ...` |
| `docker` | Runs a Docker container with writable workspace mount |
| `auto` | Detects `kimi` → `claude` → falls back to `mock` |

Docker dispatcher config example:

```json
{
  "subagent": {
    "dispatcher": "docker",
    "docker": {
      "image": "python:3.13-slim",
      "memory_limit": "512m",
      "cpu_limit": "1.5"
    }
  }
}
```

---

## OpenTelemetry Tracing

Enable console trace export:

```bash
python run.py --trace
```

Each scheduler run produces a `scheduler-run` span with child `scheduler-tick` spans.

---

## Development

### Build the dashboard

```bash
cd .zeus/v3/web
npm install
npm run build
```

This outputs into `.zeus/v3/scripts/api/static/`, which FastAPI serves at `/dashboard/`.

### Run tests

```bash
cd .zeus/v3/scripts
python -m pytest tests/ -v
```

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  task.json  │────▶│  Importer    │────▶│  State DB   │
│  (static)   │     │              │     │ (SQLite/PG) │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                 │
    ┌─────────────┐    ┌─────────────┐    ┌────▼──────┐
    │   Worker    │◄───│  TaskQueue  │◄───│ Scheduler │
    │   Pool      │    │(Memory/Redis│    │           │
    └──────┬──────┘    │ /SQLite)    │    └───────────┘
           │            └─────────────┘
           ▼
    ┌─────────────┐
    │  Workspace  │────▶ zeus-result.json
    │  Manager    │
    └─────────────┘
           │
           ▼
    ┌─────────────┐
    │  Dispatcher │
    │(mock/kimi/  │
    │claude/docker)│
    └─────────────┘
```

---

## Migration from v2

1. Copy your v2 `task.json` into `.zeus/v3/task.json`
2. Run `python run.py --import-only` to migrate runtime state into the v3 database
3. Start the scheduler / workers or Docker Compose stack
4. Open `/dashboard` for real-time monitoring
