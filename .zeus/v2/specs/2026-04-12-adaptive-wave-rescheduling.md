# v2 Adaptive Wave Rescheduling Design Spec

> **Project**: zeus-open v2 enhancement  
> **Topic**: Dynamic task scheduling within and across waves to maximize concurrency slot utilization  
> **North Star Impact**: `multi_agent_efficiency` ↑↑, `developer_adoption_rate` ↑  
> **Future Backlog**: Auto-heal (Step 2) is documented but deferred to a later milestone.

---

## 1. Problem Statement

The current `zeus_orchestrator.py` uses a rigid wave boundary:

1. Load all tasks tagged with `wave == current_wave`.
2. Dispatch up to `max_parallel_agents` tasks concurrently.
3. Wait for the entire wave to finish before human approval unlocks the next wave.

This creates **slot waste**: if one task in Wave 2 blocks for 10 minutes (e.g., waiting on a slow external dependency or an Agent timeout), the remaining concurrency slots sit idle, and independent tasks from Wave 3 cannot start early.

## 2. Objectives

- **Zero idle slots**: As long as pending tasks exist anywhere in the project, keep `max_parallel_agents` busy (respecting `depends_on`, of course).
- **Backward compatibility**: The `task.json` schema remains valid for v1/main and for existing v2 dashboards that do not read the new optional fields.
- **Deterministic traceability**: Every rescheduling decision is logged to the Agent Bus so humans can audit why a task ran earlier than its original wave.
- **Minimal UI disruption**: The Web dashboard continues to show "Wave N" as the primary grouping, with a subtle indicator when a task has been rescheduled.

## 3. Guiding Principles

1. **Dependencies are the only hard gate** — `depends_on` must be `passes: true` before a task can dispatch, regardless of which wave it is in.
2. **Wave boundaries become soft scheduling hints** — `wave` is renamed conceptually to `original_wave`; the orchestrator computes a dynamic `scheduled_wave` at runtime.
3. **Approval gates stay at original wave boundaries** — Humans still approve transitions between original waves, but the system may have already executed some future-wave tasks during the previous wave.
4. **Local-first & offline** — No cloud dependencies; scheduling logic is pure Python inside `zeus_orchestrator.py`.

## 4. Architecture Changes

### 4.1 New Fields in `task.json` (optional, backward-compatible)

```json
{
  "tasks": [
    {
      "id": "T-011",
      "wave": 5,
      "original_wave": 5,
      "scheduled_wave": 5,
      "rescheduled_from": null,
      "depends_on": [],
      ...
    }
  ],
  "meta": {
    "current_wave": 5,
    "wave_approval_required": true,
    "max_parallel_agents": 3,
    "scheduling_mode": "adaptive"
  }
}
```

| Field | Meaning |
|---|---|
| `wave` | **Kept for legacy consumers.** Written equal to `scheduled_wave` at runtime so old scripts see a consistent value. |
| `original_wave` | The wave assigned during `zeus:plan`. Immutable. |
| `scheduled_wave` | The wave the task is currently expected to run in. Updated by the orchestrator when rescheduling happens. |
| `rescheduled_from` | If the task was moved earlier, records the previous `scheduled_wave`. Null otherwise. Used for audit logs. |

### 4.2 Orchestrator Scheduling Loop (v2.1)

Replace the current `load_wave(version, wave_number)` with a **Priority Queue** (`heapq`) driven by task readiness:

```python
# Pseudo-code
ready_tasks = [
    t for t in all_tasks
    if not t.passes
    and all(dep.passes for dep in t.depends_on)
    and t.scheduled_wave <= current_original_wave + 1  # lookahead window
]
# Priority key = (original_wave, task_id)  # lower original_wave still preferred
heapq.heapify(ready_tasks)
```

**Lookahead policy**:
- By default, the orchestrator is allowed to pull tasks from `original_wave == current_original_wave + 1`.
- This prevents the UI from jumping three waves ahead while the human is still reviewing Wave N.
- Configurable via `meta.lookahead_waves` (default: 1).

**Slot-filling algorithm** (`fill_slots_from_future_waves`):
1. Start dispatching tasks whose `scheduled_wave == current_original_wave`.
2. If a running task blocks and free slots > 0, pop the lowest `original_wave` task from the ready heap that belongs to the next wave.
3. Update its `scheduled_wave = current_original_wave` and `rescheduled_from = original_wave + 1`.
4. Emit `task.rescheduled` event to the Agent Bus.
5. Dispatch the task.

### 4.3 Agent Bus Events

New event types:

```json
{
  "ts": "2026-04-12T15:00:00Z",
  "type": "task.rescheduled",
  "wave": 5,
  "task_id": "T-012",
  "agent_id": null,
  "payload": {
    "original_wave": 6,
    "new_wave": 5,
    "reason": "slot_available_while_wave_blocked"
  }
}
```

### 4.4 Store.py Updates

`store.py` needs a batch update helper so the orchestrator can rewrite `scheduled_wave` for multiple tasks under a single file lock:

```python
class AbstractStore:
    ...
    def update_json_fields(self, path: str, updates: list[tuple[str, dict]]) -> None:
        """Atomically update multiple top-level list items by ID."""
```

This is implemented in `LocalStore` using the existing `filelock` context manager.

## 5. Web UI Changes

### 5.1 Dashboard Task Table
- Show `scheduled_wave` as the current grouping.
- For rescheduled tasks, add a small badge: "原 Wave 6" (tooltip shows `rescheduled_from`).

### 5.2 Wave Progress Bar
- Progress bar title changes from "Wave 5 进度" to "Wave 5 进度（含提前调度）" when any rescheduled tasks are present.
- Denominator uses tasks whose `scheduled_wave == current_wave`, not `original_wave`.

### 5.3 Graph View
- Node color continues to reflect status (`done`, `pending`, etc.).
- Optional: node border becomes dashed if `original_wave != scheduled_wave`.

## 6. Error Handling & Edge Cases

| Scenario | Behavior |
|---|---|
| A rescheduled task fails | It blocks the next original wave only if its `original_wave` was the next wave. Otherwise, the orchestrator continues with other ready tasks. |
| Human clicks "Approve next wave" while future tasks are already running | The approval simply increments `meta.current_wave`. Already-running tasks are not interrupted. |
| `task.json` is edited manually during execution | Coarse file lock prevents corruption; if the edit changes `depends_on`, the next scheduling loop will recompute readiness. |
| All tasks in current wave finish, but no future tasks were pulled | Normal behavior: wait for human approval. |
| `lookahead_waves = 0` | Disables adaptive rescheduling; restores legacy v2.0 behavior. |

## 7. Testing Strategy

### 7.1 Unit Tests (`test_orchestrator.py`)
- Mock 3 tasks in Wave 1 and 2 tasks in Wave 2 with no cross-dependencies.
- Block task 1 artificially; assert that Wave 2 tasks are dispatched before task 1 unblocks.
- Assert `scheduled_wave` and `rescheduled_from` are written correctly.

### 7.2 State Consistency Test
- Run 10 concurrent scheduling updates against `task.json` via `LocalStore`.
- Assert JSON remains valid and no task is lost or duplicated.

### 7.3 Integration Test
- Start `zeus_server.py`, seed a project with 2 waves, trigger orchestration via API.
- Poll `/wave/1` and verify that a Wave 2 task appears in the Wave 1 list after the first task blocks.

## 8. Acceptance Criteria

- [ ] `task.json` schema supports `original_wave`, `scheduled_wave`, and `rescheduled_from`.
- [ ] `zeus_orchestrator.py` uses a priority queue and fills empty slots from `lookahead_waves == 1`.
- [ ] Every reschedule action produces a `task.rescheduled` JSONL event.
- [ ] Web UI correctly displays rescheduled tasks without build tools.
- [ ] Integration test confirms slot utilization improvement (Wave 2 task starts while Wave 1 task is blocked).
- [ ] Backward compatibility: `python .zeus/scripts/zeus_runner.py --status` on `main` remains unaffected.

## 9. Task Breakdown (for planning)

| Wave | Task | Description |
|------|------|-------------|
| 5 | T-011 | Extend `task.json` schema and `store.py` with `original_wave` / `scheduled_wave` / `rescheduled_from` fields and batch update helper |
| 6 | T-012 | Refactor `zeus_orchestrator.py` scheduling loop to priority-queue + adaptive slot filling |
| 7 | T-013 | Update Web UI dashboard to display rescheduled task badges and corrected wave progress |
| 7 | T-014 | Add unit/integration tests for adaptive rescheduling and state consistency |

---

## 10. Future Backlog: Auto-heal (Step 2)

**Deferred to a later milestone** (tentatively M-006 or v3).

- Introduce a `zeus-fixer` Agent that is dispatched when a task fails on test/lint/build errors.
- Run in isolated workspace; max 3 attempts; forced detailed `ai-log` per attempt.
- Requires `heal_classifier` to distinguish "automatically fixable" errors from architectural/design failures.
- High risk of code drift and opacity; will be specced only after T-011~T-014 are shipped and observability patterns mature.
