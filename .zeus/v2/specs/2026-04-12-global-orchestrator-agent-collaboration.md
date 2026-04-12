# Spec: Global Orchestrator & Agent Collaboration

> **Project**: zeus-open v2 enhancement  
> **Topic**: Break wave execution locks while preserving wave as a planning/observation dimension; enable real-time agent collaboration and per-agent traceability  
> **North Star Impact**: `multi_agent_efficiency` ↑↑↑, `developer_adoption_rate` ↑↑, `observability` ↑↑

---

## 1. Problem Statement

### 1.1 Wave is both a plan view and an execution lock
Currently, `zeus_orchestrator.py` dispatches tasks wave-by-wave. Even with adaptive slot filling (M-005), the runtime boundary is still the current wave. This creates artificial throughput ceilings when later waves have ready tasks whose dependencies happen to finish early.

### 1.2 Agents are isolated but cannot collaborate
Each agent gets its own workspace and prompt, yet there is no lightweight channel for one agent to ask another a question, delegate a micro-task, or share an intermediate result. The `AgentBus` is a unidirectional event logger, not a message bus.

### 1.3 Logs are wave-centric, not agent-centric
When debugging a specific agent (e.g., `kimi-agent-T-003`), operators must grep through `.zeus/v2/agent-logs/wave-{n}-events.jsonl`. As concurrency increases, this becomes unmanageable.

## 2. Objectives

- Introduce a **GlobalScheduler** that treats `wave` as a planning/observation field while dispatching strictly by global dependency readiness.
- Add a **quarantine zone** for failed tasks so they do not block unrelated downstream tasks.
- Extend `agent_bus.py` with a **Mailbox protocol** for point-to-point agent messaging.
- Restructure `agent-logs` to be **agent-centric** (one directory per dispatched agent).
- Update the Web UI with a **Global Execution** view, an **Agent Message Stream**, and a **per-agent log browser**.

## 3. Architecture

### 3.1 GlobalScheduler

New module (or class inside `zeus_orchestrator.py`): `GlobalScheduler`

Responsibilities:
1. Maintain a global ready-queue of tasks whose `depends_on` are all satisfied (by `passes` or quarantine-exemption if configured).
2. Consume tasks up to `max_parallel` without respecting wave boundaries.
3. On task failure, move the task to a `quarantine` list inside `task.json` (or mark `status="quarantine"`). Emit `task.quarantined` event.
4. Continue scheduling any downstream tasks that do **not** transitively depend on the quarantined task.
5. Keep `wave` purely for UI grouping and reporting; never use it as a dispatch gate.

Backward compatibility:
- Existing `await_wave_completion(wave_number)` is retained as a thin wrapper that filters the global state by `wave`, but the preferred entry point becomes `run_global()`.
- `meta.current_wave` in `task.json` can still advance, but it now reflects "the highest wave with any dispatched task" rather than a hard gate.

### 3.2 Quarantine Zone

Schema addition in `task.json`:
```json
{
  "meta": { ... },
  "tasks": [ ... ],
  "quarantine": [
    {
      "task_id": "T-003",
      "reason": "dispatcher_timeout",
      "quarantined_at": "2026-04-12T10:00:00Z",
      "workspace": ".zeus/v2/agent-workspaces/..."
    }
  ]
}
```

Rules:
- A task in `quarantine` is treated as **not passed** for dependency resolution.
- If another ready task does **not** depend (directly or transitively) on a quarantined task, it may proceed.
- The Web UI "Global Execution" view shows a dedicated **Quarantine** panel.

### 3.3 Agent Mailbox Protocol

Extension to `agent_bus.py`:

```python
class AgentBus:
    ...
    def send_mail(self, to_agent_id: str, from_agent_id: str, payload: dict) -> None:
        """Persist a message to the recipient's mailbox."""

    def read_mail(self, agent_id: str, since: str | None = None) -> list[dict]:
        """Return messages addressed to agent_id, optionally filtered by timestamp."""
```

Persistence:
- `.zeus/v2/agent-logs/mailbox/{agent_id}.jsonl`
- Each line: `{"ts": "...", "from": "...", "payload": {...}}`

Agent-side consumption:
- `zeus_server.py` exposes `GET /mailbox/{agent_id}`.
- Alternatively, an agent in its workspace can poll a lightweight `.mailbox.jsonl` symlink copied into the workspace (optional future enhancement).

### 3.4 Agent-Centric ai-logs

New directory layout:
```
.zeus/v2/agent-logs/
  mailbox/
    kimi-agent-T-003.jsonl
    mock-agent-T-001.jsonl
  kimi-agent-T-003/
    activity.md
    reasoning.jsonl
    events.jsonl
  mock-agent-T-001/
    activity.md
    reasoning.jsonl
    events.jsonl
```

Changes:
- `AgentBus` constructor accepts `agent_id` and writes to the agent-specific path.
- `zeus_orchestrator.py` constructs `bus = AgentBus(agent_id=..., task_id=..., ...)` per dispatch.
- Legacy wave-level logs (`wave-{n}-events.jsonl` and `wave-{n}-discussion.md`) remain as **aggregated copies** for backward compatibility.

### 3.5 Web UI Additions

New endpoints in `zeus_server.py`:
- `GET /global/status` — returns `{running: [...], quarantine: [...], ready: [...], completed_count, total_count}`
- `GET /mailbox/{agent_id}` — returns messages for an agent
- `GET /agents/{agent_id}/logs` — returns `{activity: "...", reasoning: [...], events: [...]}`

New/updated UI panels in `index.html`:
1. **Global Execution** tab
   - Running tasks (cross-wave, with agent_id badges)
   - Ready queue preview
   - Quarantine list with "View workspace" links
2. **Agent Collaboration** tab
   - Live message stream (polling or WebSocket future-ready)
   - Filter by sender / recipient
3. **Agent Logs** tab
   - Dropdown to select an agent
   - Render `activity.md`, `reasoning.jsonl`, and `events.jsonl`

## 4. Task Breakdown

| Wave | Task | Description |
|------|------|-------------|
| 10 | T-030 | Implement `GlobalScheduler` with quarantine and wave-as-view semantics |
| 10 | T-031 | Implement Agent `Mailbox` protocol in `agent_bus.py` |
| 10 | T-032 | Restructure `agent-logs` to agent-centric directories |
| 11 | T-033 | Web UI Global Execution, Agent Collaboration, and per-agent log browser |
| 11 | T-034 | Integration tests, backward-compatibility validation, and documentation |

## 5. Acceptance Criteria

- [ ] `GlobalScheduler` dispatches tasks across wave boundaries based solely on dependency readiness.
- [ ] Failed tasks enter `quarantine` and do not block unrelated downstream tasks.
- [ ] `agent_bus.py` supports `send_mail` / `read_mail`; messages persist as JSONL.
- [ ] Each dispatched agent writes logs to `.zeus/v2/agent-logs/{agent_id}/`.
- [ ] Web UI provides Global Execution, Agent Collaboration, and Agent Logs tabs.
- [ ] All existing tests pass; new tests cover global scheduling, mailbox delivery, and agent log isolation.
- [ ] `zeus-execute-v2.md` documents GlobalScheduler, Mailbox, and agent log layout.
