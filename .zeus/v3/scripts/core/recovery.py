"""
Scheduler state recovery for ZeusOpen v3.

On API restart, resets any tasks stuck in 'running' back to 'pending'
so the scheduler can re-dispatch them safely.
"""
from __future__ import annotations

from typing import Any

from store.base import AsyncStateStore


async def recover_running_tasks(store: AsyncStateStore) -> list[str]:
    """Recover tasks that were left in 'running' status and return their IDs."""
    running = await store.list_tasks(status="running")
    recovered: list[str] = []
    for t in running:
        tid = t["id"]
        await store.update_task_status(
            tid, "pending", passes=False, worker_id=None
        )
        await store.log_event(
            event_type="task.recovered",
            task_id=tid,
            agent_id="zeus-scheduler",
            payload={"previous_status": "running", "reason": "scheduler_restart"},
        )
        recovered.append(tid)
    return recovered
