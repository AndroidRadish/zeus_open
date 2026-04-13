"""
MetricsCollector for ZeusOpen v3.

Aggregates execution stats from EventLog and TaskState.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from store.base import AsyncStateStore


class MetricsCollector:
    """Collect metrics from the state store."""

    def __init__(self, store: AsyncStateStore) -> None:
        self.store = store

    async def task_metrics(self) -> list[dict[str, Any]]:
        """Return per-task metrics including duration and outcome."""
        tasks = await self.store.list_tasks()
        events = await self.store.query_events(limit=10000)

        # Index events by task_id and event_type for fast lookup
        event_map: dict[str, dict[str, datetime]] = {}
        for ev in events:
            tid = ev.get("task_id")
            if not tid:
                continue
            et = ev.get("event_type")
            ts = ev.get("ts")
            if not et or not ts:
                continue
            event_map.setdefault(tid, {})[et] = datetime.fromisoformat(ts)

        results = []
        for t in tasks:
            tid = t["id"]
            em = event_map.get(tid, {})
            started = em.get("task.started")
            completed = em.get("task.completed") or em.get("task.failed")
            duration_ms = None
            if started and completed:
                duration_ms = int((completed - started).total_seconds() * 1000)

            results.append({
                "task_id": tid,
                "status": t.get("status"),
                "passes": t.get("passes", False),
                "wave": t.get("wave"),
                "duration_ms": duration_ms,
                "started_at": started.isoformat() if started else None,
                "finished_at": completed.isoformat() if completed else None,
            })
        return results

    async def bottleneck_tasks(self, top_n: int = 5) -> list[dict[str, Any]]:
        """Identify the longest-running tasks."""
        metrics = await self.task_metrics()
        # Filter tasks that have a recorded duration
        with_dur = [m for m in metrics if m.get("duration_ms") is not None]
        with_dur.sort(key=lambda x: x["duration_ms"], reverse=True)
        return with_dur[:top_n]

    async def blocked_chains(self) -> list[dict[str, Any]]:
        """Find dependency chains that are currently blocked by quarantine or failure."""
        tasks = await self.store.list_tasks()
        quarantine = await self.store.list_quarantine()
        qset = {q["task_id"] for q in quarantine}
        failed_or_quarantined = {t["id"] for t in tasks if t["status"] == "failed"} | qset

        task_map = {t["id"]: t for t in tasks}

        # Build reverse dependency map (who depends on me)
        dependents: dict[str, list[str]] = {}
        for t in tasks:
            for dep in t.get("depends_on", []):
                dependents.setdefault(dep, []).append(t["id"])

        # BFS from each blocked root to find blocked subtree size
        chains = []
        visited_roots = set()
        for blocked in failed_or_quarantined:
            if blocked in visited_roots:
                continue
            visited_roots.add(blocked)
            queue = list(dependents.get(blocked, []))
            blocked_count = 0
            blocked_ids = []
            while queue:
                tid = queue.pop(0)
                task = task_map.get(tid)
                if not task:
                    continue
                if task.get("status") in ("pending", "running"):
                    blocked_count += 1
                    blocked_ids.append(tid)
                # Even if already failed/quarantined, its dependents may still be blocked
                for child in dependents.get(tid, []):
                    queue.append(child)
            chains.append({
                "blocked_by": blocked,
                "blocked_task_count": blocked_count,
                "blocked_task_ids": blocked_ids,
            })

        chains.sort(key=lambda x: x["blocked_task_count"], reverse=True)
        return chains

    async def summary(self) -> dict[str, Any]:
        """High-level summary (same shape as /metrics/summary)."""
        tasks = await self.store.list_tasks()
        total = len(tasks)
        completed = sum(1 for t in tasks if t["status"] == "completed")
        failed = sum(1 for t in tasks if t["status"] == "failed")
        pending = sum(1 for t in tasks if t["status"] == "pending")
        running = sum(1 for t in tasks if t["status"] == "running")
        quarantined = len(await self.store.list_quarantine())
        evaluated = completed + failed
        pass_rate = (completed / evaluated) if evaluated else 0.0

        # Avg duration
        tm = await self.task_metrics()
        durations = [m["duration_ms"] for m in tm if m.get("duration_ms") is not None]
        avg_duration_ms = int(sum(durations) / len(durations)) if durations else None

        return {
            "total_tasks": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "running": running,
            "quarantined": quarantined,
            "pass_rate": round(pass_rate, 4),
            "avg_duration_ms": avg_duration_ms,
        }
