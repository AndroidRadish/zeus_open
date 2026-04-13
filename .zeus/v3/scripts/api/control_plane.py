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
        current = await self.store.get_meta("scheduler_target_state", "stopped")
        if current == "running":
            raise RuntimeError("Scheduler already running")
        await self.store.set_meta("scheduler_target_state", "running")
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
        await self.spawn_scheduler()
        await self.spawn_workers(3)
        return {
            "imported_tasks": import_result["imported_tasks"],
            "scheduler_pid": await self.store.get_meta("scheduler_pid", 0),
            "worker_pids": [],
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
        return {
            "scheduler": {"running": running, "pid": scheduler_pid, "state": actual},
            "workers": {"count": worker_actual, "pids": [], "target": worker_target},
            "queue_size": queue_size,
            "last_import_at": last_import_at,
        }
