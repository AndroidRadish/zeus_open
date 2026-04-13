# v3 Worker Heartbeat & Lease Recovery

## Decision Rationale

In a distributed Queue-Worker architecture, workers can crash or be killed without warning. Without a recovery mechanism, tasks they were processing remain stuck in the `running` state forever, blocking dependent tasks and silently losing work. This feature adds per-task heartbeats and automatic lease recovery to the scheduler.

## Execution Summary

### Schema changes
- `task_state.worker_id` — tracks which worker currently holds the lease
- `task_state.heartbeat_at` — timestamp of the last successful heartbeat
- Alembic migration `f51e5481fdc1` auto-generated and applied

### Store layer
- `AsyncStateStore.update_task_heartbeat(task_id, worker_id)` — bumps `heartbeat_at` to `func.now()`
- Implemented in `_SqlAlchemyStateStore` with an atomic `UPDATE ... SET worker_id=?, heartbeat_at=NOW()`

### Worker layer
- `ZeusWorker._execute` now:
  1. Calls `update_task_heartbeat` immediately when starting a task
  2. Spawns a background `asyncio.Task` that updates the heartbeat every 10 seconds
  3. Cancels the heartbeat task in `finally` when execution finishes or fails
  4. Clears `worker_id` on all terminal outcomes (completed/failed)

### Scheduler layer
- `ZeusScheduler` accepts `lease_timeout_seconds` (default 60s)
- At the beginning of every `tick()`, `_recover_expired_leases()`:
  1. Scans all `running` tasks
  2. Compares `heartbeat_at` against the timeout
  3. Resets expired tasks back to `pending` (with `worker_id=None`)
  4. Logs a `task.lease.recovered` event
- Recovered tasks are naturally re-enqueued in the same tick if their dependencies are satisfied

### Tests
- `test_update_task_heartbeat` — validates DB update
- `test_scheduler_recovers_expired_lease` — 120s-old heartbeat with 30s timeout gets recovered and re-enqueued
- `test_scheduler_does_not_recover_fresh_lease` — recent heartbeats are left alone

### Bug fix discovered during implementation
- `core/worker.py` was missing a top-level `import asyncio`. The nested `_heartbeat_loop` referenced `asyncio.sleep`, which caused a `NameError` in production. This went unnoticed earlier because `asyncio` happened to be present in some execution contexts. Added the explicit import.

### Verification
- `50/50` v3 tests passed (47 previous + 3 new heartbeat tests)
- `python .zeus/scripts/zeus_runner.py --status` reports v2 validation pass

## Target Impact

- **reliability** ↑↑↑ — Worker crashes no longer cause permanent task loss
- **multi_agent_efficiency** ↑↑↑ — Scheduler automatically redistributes recovered tasks to healthy workers
- **observability** ↑↑ — `task.lease.recovered` events make lease timeouts auditable
