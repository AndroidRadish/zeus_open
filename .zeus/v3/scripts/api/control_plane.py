"""
Control plane for ZeusOpen v3 Dashboard.

Option B (watch-mode state machine):
- API only writes scheduler_meta.
- scheduler/worker processes watch DB state and self-manage lifecycle.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.bus import EventBus
from core.scheduler import ZeusScheduler
from importer import import_tasks_from_json
from store.sqlite_store import SQLiteStateStore
from task_queue.memory_queue import MemoryTaskQueue


class ControlPlane:
    """State-machine control plane: no subprocess management."""

    def __init__(
        self,
        store: SQLiteStateStore,
        bus: EventBus,
        project_root: Path,
        database_url: str,
    ) -> None:
        self.store = store
        self.bus = bus
        self.project_root = project_root
        self.database_url = database_url

    async def spawn_scheduler(self) -> int:
        target = await self.store.get_meta("scheduler_target_state", "stopped")
        actual = await self.store.get_meta("scheduler_actual_state", "unknown")
        if target == "running" and actual == "running":
            raise RuntimeError("Scheduler already running")
        # Ghost state recovery: if target says running but actual is dead, reset first
        if target == "running" and actual != "running":
            await self.store.set_meta("scheduler_target_state", "stopped")
            await self.store.set_meta("scheduler_actual_state", "stopped")
            await self.store.set_meta("scheduler_active", False)
            await self.store.log_event(
                event_type="scheduler.ghost.recovered",
                task_id="global",
                agent_id="control-plane",
                payload={"previous_actual": actual},
            )
        await self.store.set_meta("scheduler_target_state", "running")
        await self.store.set_meta("scheduler_actual_state", "running")
        await self.store.set_meta("scheduler_active", True)
        await self.store.log_event(
            event_type="scheduler.started",
            task_id="global",
            agent_id="control-plane",
            payload={},
        )
        # Return the current PID placeholder for backward compatibility
        return await self.store.get_meta("scheduler_pid", 0)

    async def stop_scheduler(self) -> None:
        await self.store.set_meta("scheduler_target_state", "stopped")
        await self.store.set_meta("scheduler_actual_state", "stopped")
        await self.store.set_meta("scheduler_active", False)

    async def spawn_workers(self, count: int) -> list[int]:
        await self.store.set_meta("worker_target_count", count)
        return []

    async def stop_workers(self) -> None:
        await self.store.set_meta("worker_target_count", 0)

    async def tick_once(self) -> dict[str, Any]:
        queue = MemoryTaskQueue()
        scheduler = ZeusScheduler(self.store, queue, self.bus)
        result = await scheduler.run_once()
        return result

    async def import_tasks(self) -> dict[str, Any]:
        task_json_path = self.project_root / ".zeus" / "v3" / "task.json"
        result = await import_tasks_from_json(self.store, task_json_path)
        await self.store.set_meta(
            "last_import_at", datetime.now(timezone.utc).isoformat()
        )
        return result

    async def global_run(self) -> dict[str, Any]:
        import_result = await self.import_tasks()
        # Reset passes=true for any task that is not completed so scheduler will pick them up
        tasks = await self.store.list_tasks()
        reset_count = 0
        for t in tasks:
            if t.get("passes") and t.get("status") != "completed":
                await self.store.update_task_status(t["id"], t.get("status", "pending"), passes=False, worker_id=None)
                reset_count += 1

        # Compute skipped reasons before starting scheduler
        tasks = await self.store.list_tasks()
        quarantine = await self.store.list_quarantine()
        quarantined_ids = {q["task_id"] for q in quarantine}
        pass_map = {t["id"]: t.get("passes", False) for t in tasks}
        skipped_reasons: dict[str, str] = {}
        for t in tasks:
            tid = t["id"]
            if pass_map.get(tid, False):
                skipped_reasons[tid] = "already passed"
                continue
            status = t.get("status", "pending")
            if status in ("paused", "cancelled"):
                skipped_reasons[tid] = f"status is {status}"
                continue
            if tid in quarantined_ids:
                skipped_reasons[tid] = "quarantined"
                continue
            deps = t.get("depends_on", [])
            if not all(pass_map.get(d, False) for d in deps):
                skipped_reasons[tid] = "dependencies not satisfied"
                continue
            if any(d in quarantined_ids for d in deps):
                skipped_reasons[tid] = "dependency quarantined"
                continue

        await self.spawn_scheduler()
        await self.spawn_workers(3)
        return {
            "imported_tasks": import_result["imported_tasks"],
            "reset_passes_count": reset_count,
            "scheduler_pid": await self.store.get_meta("scheduler_pid", 0),
            "worker_pids": [],
            "skipped_reasons": skipped_reasons,
        }

    async def status(self) -> dict[str, Any]:
        target = await self.store.get_meta("scheduler_target_state", "stopped")
        actual = await self.store.get_meta("scheduler_actual_state", "unknown")
        # If actual is unknown but target is running, reflect target optimistically
        running = (actual == "running" or actual == "unknown") and target == "running"
        scheduler_pid = await self.store.get_meta("scheduler_pid", None)
        worker_target = await self.store.get_meta("worker_target_count", 0)
        worker_actual = await self.store.get_meta("worker_actual_count", None)
        if worker_actual is None:
            worker_actual = worker_target
        queue_size = await self.store.get_meta("queue_size", 0)
        last_import_at = await self.store.get_meta("last_import_at", None)
        last_tick = await self.store.get_meta("last_scheduler_tick_at", None)

        recent_events = await self.store.query_events(limit=1)
        last_event_at = recent_events[0]["ts"] if recent_events else None
        running_tasks = await self.store.list_tasks(status="running")

        return {
            "scheduler": {"running": running, "pid": scheduler_pid, "state": actual, "last_tick_at": last_tick},
            "workers": {"count": worker_actual, "pids": [], "target": worker_target},
            "queue_size": queue_size,
            "last_import_at": last_import_at,
            "last_event_at": last_event_at,
            "running_tasks": running_tasks,
        }
