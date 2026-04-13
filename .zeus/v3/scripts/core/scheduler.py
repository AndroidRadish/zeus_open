"""
ZeusOpen v3 pure scheduler.

Only decides which tasks are ready and enqueues them.
Execution is handled by WorkerPool.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from task_queue.base import TaskQueue
from store.base import AsyncStateStore


class ZeusScheduler:
    """Dependency-aware scheduler that enqueues ready tasks without executing them."""

    def __init__(self, store: AsyncStateStore, queue: TaskQueue, bus=None, lease_timeout_seconds: float = 60.0) -> None:
        self.store = store
        self.queue = queue
        self.bus = bus
        self.lease_timeout_seconds = lease_timeout_seconds

    def _build_graph(self, tasks: list[dict[str, Any]]) -> dict[str, list[str]]:
        return {t["id"]: t.get("depends_on", []) for t in tasks if t.get("id")}

    def _get_ready_tasks(
        self,
        tasks: list[dict[str, Any]],
        pass_map: dict[str, bool],
        quarantined_ids: set[str],
        enqueued_ids: set[str],
    ) -> list[dict[str, Any]]:
        ready: list[dict[str, Any]] = []
        for t in tasks:
            tid = t["id"]
            if tid in enqueued_ids:
                continue
            if pass_map.get(tid, False):
                continue
            if t.get("status") in ("paused", "cancelled", "completed"):
                continue
            if tid in quarantined_ids:
                continue
            deps = t.get("depends_on", [])
            if not all(pass_map.get(d, False) for d in deps):
                continue
            if any(d in quarantined_ids for d in deps):
                continue
            ready.append(t)
        ready.sort(key=lambda t: (t.get("wave", 1), t["id"]))
        return ready

    async def _recover_expired_leases(self, tasks: list[dict[str, Any]]) -> list[str]:
        now = datetime.now(timezone.utc)
        recovered: list[str] = []
        for t in tasks:
            if t.get("status") != "running":
                continue
            heartbeat = t.get("heartbeat_at")
            if heartbeat is None:
                continue
            hb = datetime.fromisoformat(heartbeat) if isinstance(heartbeat, str) else heartbeat
            if hb.tzinfo is None:
                hb = hb.replace(tzinfo=timezone.utc)
            if (now - hb).total_seconds() > self.lease_timeout_seconds:
                await self.store.update_task_status(
                    t["id"], "pending", passes=False, worker_id=None
                )
                await self.store.log_event(
                    event_type="task.lease.recovered",
                    task_id=t["id"],
                    agent_id="zeus-scheduler",
                    payload={"previous_worker": t.get("worker_id")},
                )
                recovered.append(t["id"])
        return recovered

    async def tick(self, enqueued_ids: set[str]) -> list[dict[str, Any]]:
        """Evaluate once and enqueue all newly ready tasks.

        Returns the list of tasks that were enqueued in this tick.
        """
        tasks = await self.store.list_tasks()
        await self._recover_expired_leases(tasks)
        # Refresh tasks after recovery
        tasks = await self.store.list_tasks()
        pass_map = {t["id"]: t.get("passes", False) for t in tasks}
        quarantine = await self.store.list_quarantine()
        quarantined_ids = {q["task_id"] for q in quarantine}

        ready = self._get_ready_tasks(tasks, pass_map, quarantined_ids, enqueued_ids)
        for task in ready:
            await self.store.update_task_status(task["id"], "running")
            await self.queue.enqueue(task)
            enqueued_ids.add(task["id"])
            await self.store.log_event(
                event_type="task.enqueued",
                task_id=task["id"],
                agent_id="zeus-scheduler",
                wave=task.get("wave"),
                payload={"depends_on": task.get("depends_on", [])},
            )
            if self.bus:
                self.bus.emit(
                    "task.enqueued",
                    {"task_id": task["id"], "wave": task.get("wave"), "depends_on": task.get("depends_on", [])},
                )
        return ready

    async def run_once(self) -> dict[str, Any]:
        """Run a single scheduling pass and return summary."""
        enqueued: set[str] = set()
        ready = await self.tick(enqueued)
        return {
            "enqueued": len(ready),
            "task_ids": [t["id"] for t in ready],
        }

    async def mark_global_completed(self) -> None:
        await self.store.set_meta("scheduler_active", False)
        await self.store.log_event(
            event_type="global.completed",
            task_id="global",
            agent_id="zeus-scheduler",
            payload={},
        )
        if self.bus:
            self.bus.emit("global.completed", {})
