# ZeusOpen v3

> Production multi-agent framework for AI-driven software engineering.

ZeusOpen v3 is a ground-up rewrite of the v2 execution engine, focused on:
- **Database-centric state** (SQLite/PostgreSQL) instead of file-lock `task.json` mutation
- **Queue-Worker separation** enabling horizontal scaling
- **Real-time observability** via SSE and a Vue 3 dashboard
- **Agent Result Protocol (ARP)** — structured `zeus-result.json` as the source of truth
- **Multi-container deployment** with Docker Compose and Redis

---

## Quick Start

### One-liner: run everything locally

```bash
cd .zeus/v3/scripts
python run.py --project-root . --max-workers 3
```

This imports `task.json`, starts the scheduler + worker pool, runs until completion, and prints a summary.

### Start the API server + Dashboard

```bash
python run.py --mode serve --project-root . --host 0.0.0.0 --port 8000
```

Open http://127.0.0.1:8000/dashboard

The dashboard includes:
- **Overview** — live metrics, task list, and event stream
- **Tasks** — inline actions (Retry / Cancel / Pause / Resume / Quarantine / Logs / Detail)
- **Task Detail Drawer** — slide-out panel showing full task fields, dependencies, and activity logs
- **Events** — real-time SSE event log with progress highlights and searchable history
- **Metrics** — bottleneck analysis, blocked dependency chains, and per-task duration stats
- **Graph** — task dependency graph (SVG / Mermaid / ECharts)
- **Phases** — phase & milestone CRUD with drill-down to task lists
- **Mailbox** — AgentBus point-to-point message inbox with send form
- **Control** — scheduler / worker management and one-click global run
- **Hot Reload** — automatically re-imports `task.json` changes in `serve` mode and broadcasts `config.reloaded` via SSE

**Front-end architecture**: the dashboard uses **Pinia** for global state management (`taskStore`, `eventStore`, `uiStore`), eliminating props-drilling and making the UI fully reactive to SSE events.

### Check status without running

```bash
python run.py --status
```

---

## Execution Modes

`run.py` supports four modes via `--mode`:

| Mode | Description |
|------|-------------|
| `combined` (default) | Scheduler + worker pool in one process |
| `scheduler` | Scheduling loop only (enqueues ready tasks) |
| `worker` | Worker pool only (consumes queue) |
| `serve` | FastAPI server + SSE stream + Dashboard |

### Multi-process local example

Terminal 1:
```bash
python run.py --mode scheduler
```

Terminal 2:
```bash
python run.py --mode worker --max-workers 2
```

### Redis-backed distributed example

Terminal 1 (scheduler):
```bash
python run.py --mode scheduler --queue-backend redis --redis-url redis://localhost:6379/0
```

Terminal 2-N (workers):
```bash
python run.py --mode worker --max-workers 3 --queue-backend redis --redis-url redis://localhost:6379/0
```

---

## Task Configuration

Tasks are defined in `.zeus/v3/task.json` (static plan) and imported into the database at runtime.

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

Choose how agent workspaces are created in `.zeus/v3/config.json`:

| Backend | Config | Use case |
|---------|--------|----------|
| `copytree` (default) | `"workspace": {"backend": "copytree"}` | Full project copy; simple and safe |
| `git_worktree` | `"workspace": {"backend": "git_worktree"}` | Zero-copy via `git worktree`; requires git repo |

---

## API Endpoints

Base URL: `http://127.0.0.1:8000`

### Tasks
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/tasks` | List tasks (`?status=`, `?wave=`) |
| GET | `/tasks/{id}` | Task details |
| POST | `/tasks/{id}/retry` | Retry failed/quarantined task |
| POST | `/tasks/{id}/cancel` | Cancel task |
| POST | `/tasks/{id}/pause` | Pause pending task |
| POST | `/tasks/{id}/resume` | Resume paused task |
| POST | `/tasks/{id}/quarantine` | Manually quarantine |
| POST | `/tasks/{id}/unquarantine` | Remove from quarantine |
| POST | `/tasks/{id}/progress` | Progress report (HTTP) |

### Events & Observability
| GET | `/events` | Query event log |
| GET | `/events/stream` | **SSE** real-time events |
| GET | `/agents/{id}/logs` | Agent activity + reasoning logs |
| GET | `/workflow/graph?format=svg\|mermaid\|echarts` | Dependency graph |

### Metrics
| GET | `/metrics/summary` | High-level metrics + pass rate |
| GET | `/metrics/tasks` | Per-task duration/status |
| GET | `/metrics/bottleneck` | Top-N slowest tasks |
| GET | `/metrics/blocked` | Blocked dependency chains |

### Phases & Milestones
| GET | `/phases` | List phases |
| GET | `/phases/{id}` | Phase details with milestones |
| POST | `/phases` | Create phase |
| PUT | `/phases/{id}` | Update phase |
| DELETE | `/phases/{id}` | Delete phase |
| GET | `/milestones` | List milestones |
| GET | `/milestones/{id}` | Milestone details with tasks |
| POST | `/milestones` | Create milestone |
| PUT | `/milestones/{id}` | Update milestone |
| DELETE | `/milestones/{id}` | Delete milestone |

### AgentBus Mailbox
| GET | `/mailbox?to_agent=&read=` | List messages |
| POST | `/mailbox` | Send message (`{from_agent, to_agent, message}`) |
| POST | `/mailbox/{id}/read` | Mark message as read |

### Control Plane
| GET | `/control/status` | Scheduler + worker + queue status |
| POST | `/control/scheduler/start` | Start scheduler subprocess |
| POST | `/control/scheduler/stop` | Stop scheduler subprocess |
| POST | `/control/scheduler/tick` | Trigger one scheduler tick |
| POST | `/control/workers/scale` | Scale workers (`{"count": 3}`) |
| POST | `/control/workers/stop` | Stop all workers |
| POST | `/control/import` | Re-import `task.json` |
| POST | `/control/global/run` | One-click import + scheduler + workers |
| POST | `/control/project/switch` | Switch project without restart |

### Dashboard
| GET | `/dashboard/` | Vue 3 SPA |

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

## Kubernetes Deployment

```bash
cd .zeus/v3/k8s
kubectl apply -f namespace.yaml
kubectl apply -f pvc.yaml
kubectl apply -f redis.yaml
kubectl apply -f zeus-api.yaml
kubectl apply -f zeus-scheduler.yaml
kubectl apply -f zeus-worker.yaml
```

Components:
- `redis` — In-cluster Redis service
- `zeus-api` — LoadBalancer Service on port 80
- `zeus-scheduler` — Singleton scheduler Deployment
- `zeus-worker` — Deployment with HPA (2-10 replicas, CPU 70%)
- `zeus-state-pvc` — Shared SQLite state volume (ReadWriteMany)

> **Note:** `ReadWriteMany` requires a CSI driver that supports it (e.g., NFS, EFS, Azure Files). For single-node clusters, use `hostPath` or switch to a single-replica SQLite setup.

---

## Control Plane

When running the API server locally (`--mode serve`), an embedded `ControlPlane` is enabled by default. It lets the Dashboard start/stop scheduler and worker subprocesses via `/control/*` endpoints.

To disable it (recommended for Docker/K8s where orchestration is external):
```bash
# Windows
set ZEUS_CONTROL_PLANE_ENABLED=false
# Linux/macOS
export ZEUS_CONTROL_PLANE_ENABLED=false
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

Docker dispatcher example:

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

## AgentBus Mailbox

v3 includes point-to-point messaging for cross-agent collaboration:

```python
# From a worker or dispatcher
await bus.post(task_id="T-1", agent_id="zeus-agent-T-1", message="Need file X", to_agent="zeus-agent-T-2")

# Receive (with optional timeout)
msg = await bus.recv("zeus-agent-T-2", timeout=5.0)
```

Messages are persisted in the database and browsable via the Dashboard **Mailbox** tab.

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

Current status: **73/73 tests passing**.

---

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│  task.json  │───▶│   Importer   │───▶│   State DB  │
│  (static)   │    │              │    │(SQLite/PG)  │
└─────────────┘    └──────────────┘    └──────┬──────┘
                                                │
    ┌─────────────┐   ┌─────────────┐   ┌─────▼─────┐
    │   Worker    │◄──│  TaskQueue  │◄──│ Scheduler │
    │    Pool     │    │Memory/Redis/│   │           │
    └──────┬──────┘    │   SQLite    │   └───────────┘
           │            └─────────────┘
           │
    ┌──────▼──────┐
    │  Workspace  │────▶ zeus-result.json
    │   Manager   │
    └──────┬──────┘
           │
    ┌──────▼──────┐
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
