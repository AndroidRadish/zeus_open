# v2 Multi-Agent Parallel & GUI Design Spec

> **Project**: zeus-open v2  
> **Topic**: Multi-agent parallel orchestration, Agent Bus, GUI Dashboard, Workflow Graph  
> **Architecture**: Hub-and-Spoke unified backend + dual frontend (PyQt desktop + Web)  
> **North Star Impact**: `developer_adoption_rate` ↑↑, `multi_agent_efficiency` ↑↑, `ui_usability` ↑↑

---

## 1. Design Overview

### 1.1 Problem Statement
The current `zeus_runner.py` (v1/main) operates in a single-wave, human-in-the-loop mode:
1. Read `task.json`
2. Print one task prompt to terminal
3. Wait for the human to copy-paste the prompt to an AI, write code, and return
4. Update `task.json` and proceed

This serial, manual hand-off becomes the bottleneck when a wave contains 3–5 independent tasks.

### 1.2 v2 Objectives
- **Parallel Execution**: Within a wave, dispatch multiple tasks to `Agent(coder)` instances concurrently.
- **Agent Communication**: Provide a machine-readable event bus (`JSONL`) and a human-readable discussion log (`Markdown`) so that engineers can inspect AI intent without blocking execution.
- **GUI Management**: A PyQt desktop client for daily use, plus a lightweight Web frontend for the open-source community.
- **Workflow Graph**: Auto-generate interactive dependency graphs from `task.json` + `roadmap.json`.
- **Pluggable Storage**: Default local file/SQLite store with an abstract interface ready for Tencent COS or Redis.
- **Human Override**: Humans remain heavily involved in **planning** (brainstorm/plan phases) and have read-only observability during execution. Approval gates exist at wave boundaries, not per task.

### 1.3 Guiding Principles
1. **Single source of truth**: `task.json`, `roadmap.json`, `prd.json` remain the canonical state.
2. **Local-first**: Works offline by default; cloud storage is opt-in.
3. **Backward compatibility**: v2 scripts must not break v1/main folder structures.
4. **Open-source friendly**: Web frontend requires no build step (single HTML + CDN).

---

## 2. Architecture

### 2.1 Hub-and-Spoke Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         HUB (Python Backend)                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │  Orchestrator   │  │   Agent Bus     │  │    Store (抽象层)    │  │
│  │ zeus_orchestrator│  │  agent_bus.py   │  │    store.py         │  │
│  └────────┬────────┘  └────────┬────────┘  └──────────┬──────────┘  │
│           │                    │                       │            │
│           └────────────────────┴───────────────────────┘            │
│                                │                                    │
│                     FastAPI (zeus_server.py)                        │
│                         localhost:8234                              │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
   ┌────▼────┐            ┌──────▼──────┐          ┌──────▼──────┐
   │ PyQt GUI │            │  Web UI     │          │  Push Bot   │
   │(desktop) │            │  (browser)  │          │ (future)    │
   └─────────┘            └─────────────┘          └─────────────┘
```

### 2.2 Execution Flow

1. **Plan Phase (Human-driven)**
   - Human + `Agent(plan)` produce `prd.json`, `task.json`, `roadmap.json` in `.zeus/v2/`.
   - Wave boundaries are frozen before execution starts.

2. **Execute Phase (Agent-autonomous with human observability)**
   - `zeus_orchestrator.py` reads `task.json` and identifies the current wave.
   - For each pending task in the wave, it constructs a rich prompt and delegates to `Agent(coder, prompt=..., workspace=...)`.
   - `agent_bus.py` creates:
     - `.zeus/v2/agent-logs/wave-{N}-events.jsonl`  → machine events
     - `.zeus/v2/agent-logs/wave-{N}-discussion.md` → human-readable chat log
   - Agents write code, run tests, and upon completion report back to the Orchestrator.
   - Orchestrator updates `task.json` (with file-locking), writes AI logs, and triggers `git commit`.
   - When the entire wave completes, the GUI shows a "Wave Complete" notification; human approval is required to enter the next wave.

3. **Observe Phase**
   - GUI/Web polls (or WebSockets) the FastAPI backend for live status.
   - `workflow_graph.py` generates Mermaid/Graphviz data on demand.

---

## 3. Core Components

### 3.1 zeus_orchestrator.py
**Responsibility**: Central dispatcher. Replaces the interactive `zeus_runner.py` loop for v2.

**Key Behaviors**:
- `load_wave(version, wave_number)` → returns pending tasks.
- `dispatch_task(task, bus, store)` → spawns `Agent(coder)` via `asyncio.create_task()`.
- `await_wave_completion(wave_number)` → waits until all tasks in the wave report `done` or `failed`.
- `transition_to_next_wave()` → updates `roadmap.json` wave pointer; requires human approval if `--auto` is not set.

**Concurrency Model**:
- Use `asyncio.Semaphore(max_parallel_agents)` to cap concurrent tasks (default: 3).
- Each Agent runs in an isolated temporary workspace folder to avoid file collisions during code generation.
- Final artifacts are merged back into the project root by the Orchestrator under a file lock.

### 3.2 agent_bus.py
**Responsibility**: Dual-channel logging — machine events + human discussion.

**Data Paths**:
```
.zeus/v2/agent-logs/
  wave-1-events.jsonl      ← structured events
  wave-1-discussion.md     ← human-readable narrative
```

**Event Schema (JSONL)**:
```json
{
  "ts": "2026-04-10T15:00:00Z",
  "type": "task.started",
  "wave": 1,
  "task_id": "T-001",
  "agent_id": "coder-0",
  "payload": { "files_touched": ["src/foo.py"] }
}
```

Event types: `task.started`, `task.progress`, `task.completed`, `task.failed`, `agent.message`, `wave.completed`.

**Discussion Markdown Format**:
```markdown
# Wave 1 Discussion Log

## 15:00:00 — coder-0 (T-001)
Started working on `T-001: Bootstrap repository structure`.  
Plan: create `src/orchestrator/` and add `__init__.py`.

## 15:02:15 — coder-1 (T-002)
Started working on `T-002: Implement agent bus`.  
Noting that `T-001` is creating `src/orchestrator/` — I will import from there.

## 15:05:30 — coder-0 (T-001)
Completed. Files: `src/orchestrator/__init__.py`, `src/orchestrator/core.py`.  
Commit: `a1b2c3d`.
```

### 3.3 store.py (Pluggable Storage Abstraction)
**Interface**:
```python
class AbstractStore:
    def read_json(self, path: str) -> dict: ...
    def write_json(self, path: str, data: dict) -> None: ...
    def append_line(self, path: str, line: str) -> None: ...
    def lock(self, path: str): ...  # context manager
```

**Implementations**:
- `LocalStore`: Uses `pathlib` + `filelock`.
- `TencentCosStore` (future): Uses `qcloud_cos` SDK.
- `RedisStore` (future): Uses `redis-py` for distributed locks.

### 3.4 zeus_server.py (FastAPI Backend)
**Responsibility**: Serves both GUI and Web frontend; exposes state and control endpoints.

**Endpoints**:
| Method | Path | Description |
|--------|------|-------------|
| GET | `/status` | Global project status (active wave, completed tasks, validation) |
| GET | `/wave/{n}` | Tasks in wave `n` with live agent states |
| GET | `/agents` | List of currently running agents |
| GET | `/events?wave={n}&limit=50` | Stream of JSONL events |
| GET | `/discussion?wave={n}` | Raw Markdown discussion log |
| POST | `/wave/{n}/approve` | Human approves transition to next wave |
| GET | `/graph/mermaid` | Mermaid source for workflow graph |
| GET | `/graph/svg` | Rendered SVG of workflow graph |

**Startup**:
```bash
python .zeus/v2/scripts/zeus_server.py --port 8234 --store local
```

### 3.5 zeus_gui.py (PyQt Desktop Client)
**Responsibility**: The primary daily driver for the human engineer.

**Views**:
1. **Dashboard**: Wave progress bars, task pass/fail counts, recent commits.
2. **Agent Monitor**: Live list of running agents with last-seen timestamp.
3. **Discussion Reader**: Rendered Markdown viewer for `wave-N-discussion.md`.
4. **Graph Viewer**: Embedded web engine (QWebEngineView) rendering the Mermaid graph from `/graph/svg`.
5. **Approval Gate**: Modal dialog when a wave completes, asking "Approve next wave? / Pause / Retry failed tasks".

**Packaging**:
- Optional PyInstaller `.exe` for Windows users who want a true desktop app.

### 3.6 zeus_web.py / index.html (Web Frontend)
**Responsibility**: Zero-build web interface for open-source users.

**Tech Stack**:
- Single `index.html`
- CDN: Vue 3 (or vanilla JS) + Tailwind CSS + Mermaid.js
- Polling every 2s to `/status` and `/events`

**Features**:
- Read-only dashboard (status + graph)
- Discussion log viewer
- No approval controls by default (to avoid accidental remote clicks); can be enabled with `--web-approvals` flag on the server.

### 3.7 workflow_graph.py
**Responsibility**: Generate visual dependency graphs from `task.json`.

**Output Formats**:
- `to_mermaid()` → Mermaid flowchart source (for Web/QWebEngineView)
- `to_graphviz()` → DOT source (for static PDF/PNG export)

**Graph Rules**:
- Nodes = tasks, colored by status (`pending`=gray, `in_progress`=blue, `done`=green, `failed`=red)
- Edges = `depends_on` relationships
- Wave boundaries rendered as dashed swimlanes

---

## 4. Data Contracts & Concurrency Control

### 4.1 task.json v2 Extension
Backward-compatible additions:
```json
{
  "tasks": [
    {
      "id": "T-001",
      "story_id": "US-001",
      "title": "...",
      "wave": 1,
      "depends_on": [],
      "passes": false,
      "agent_id": "coder-0",
      "started_at": "2026-04-10T15:00:00Z",
      "finished_at": null,
      "commit_sha": null,
      "log_path": ".zeus/v2/ai-logs/2026-04-10T15-00-00-T-001.md"
    }
  ],
  "meta": {
    "current_wave": 1,
    "wave_approval_required": true,
    "max_parallel_agents": 3
  }
}
```

### 4.2 File Lock Protocol
To prevent multiple Agents from corrupting `task.json`:
1. Orchestrator holds a **coarse lock** on `task.json` while merging batch updates.
2. Individual Agents do **not** write to `task.json` directly. They report completion to the Orchestrator via the Agent Bus.
3. Orchestrator applies updates in a single write transaction.

### 4.3 Agent Workspace Isolation
Each Agent receives:
- A temporary working directory: `.zeus/v2/agent-workspaces/{agent_id}-{task_id}/`
- A read-only mount/symlink of the project source
- Write permissions only inside its temp dir
- On completion, the Orchestrator diffs the temp dir and applies selected files to the project root.

---

## 5. Error Handling & Retry

| Scenario | Behavior |
|----------|----------|
| Agent timeout (>10 min) | Orchestrator marks task `failed`, emits `task.failed` event, unlocks slot for next task |
| Agent produces invalid JSON | Retry once with a "fix JSON format" prompt; if still failing, mark failed |
| Git commit fails | Pause wave, surface error in GUI/Web, wait for human intervention |
| File lock contention (>5s) | Back-off and retry; if persistent, escalate to human |
| Task dependency violated | Validation error before dispatch; do not start wave until `depends_on` in previous waves are `passes: true` |

---

## 6. Testing Strategy

### 6.1 Unit Tests
- `test_orchestrator.py`: mock Agent dispatch, verify wave sequencing and file locking
- `test_agent_bus.py`: verify JSONL event serialization and Markdown formatting
- `test_store.py`: verify `LocalStore` read/write/lock semantics
- `test_workflow_graph.py`: verify Mermaid output for sample `task.json`

### 6.2 Integration Tests
- Spin up `zeus_server.py` on a test port, hit all API endpoints with `httpx`
- Run a 2-wave mini project with mock Agents to ensure end-to-end state correctness

### 6.3 GUI Tests
- Smoke test: launch PyQt GUI, verify Dashboard and Graph tabs render without crash

---

## 7. Acceptance Criteria

A v2 implementation is considered complete when **all** of the following are true:

1. **Parallel Execution**
   - [ ] `zeus_orchestrator.py` can execute 3 tasks in the same wave concurrently (with mocked Agents) in < 30 seconds.
   - [ ] `task.json` remains valid JSON and free of corruption after 10 concurrent updates.

2. **Agent Bus**
   - [ ] Every wave produces both `wave-N-events.jsonl` and `wave-N-discussion.md`.
   - [ ] A human can open `discussion.md` and understand what each Agent did and why without reading code.

3. **Backend**
   - [ ] `zeus_server.py` starts successfully and serves `/status`, `/events`, `/graph/mermaid`.
   - [ ] Web frontend (`index.html`) renders the dashboard without build tools.

4. **GUI**
   - [ ] PyQt desktop GUI launches, shows wave progress, and displays the workflow graph.
   - [ ] GUI shows an approval dialog when a wave completes.

5. **Graph Generation**
   - [ ] `workflow_graph.py` produces a Mermaid diagram that correctly colors tasks by status and draws `depends_on` edges.

6. **Backward Compatibility**
   - [ ] Running `python .zeus/scripts/zeus_runner.py --status` on `main` still works exactly as before.
   - [ ] v2 files live exclusively under `.zeus/v2/`; no overwrite of `.zeus/main/`.

7. **Documentation**
   - [ ] `skills/zeus-execute-v2.md` is written explaining how to use the new parallel mode.
   - [ ] README is updated with GUI/Web startup instructions.

---

## 8. Recommended Task Breakdown (for planning)

| Wave | Tasks | Theme |
|------|-------|-------|
| 1 | T-001: `store.py` abstraction + local file lock<br>T-002: `agent_bus.py` JSONL + Markdown dual writer<br>T-003: `workflow_graph.py` Mermaid/Graphviz generator | Infrastructure |
| 2 | T-004: `zeus_orchestrator.py` async dispatch + wave logic<br>T-005: `zeus_server.py` FastAPI backend | Core Engine |
| 3 | T-006: `zeus_gui.py` PyQt dashboard + graph viewer<br>T-007: `index.html` Web frontend | Dual Frontend |
| 4 | T-008: Integration tests + end-to-end demo<br>T-009: Documentation (`zeus-execute-v2.md`, README)<br>T-010: Final validation & backward-compat check | Polish & Ship |

---

*Spec written by AI on 2026-04-10. Ready for human review before planning.*
