"""
ZeusOpen v3 worker.

Consumes tasks from a queue, executes them via a dispatcher,
reads the Agent Result Protocol (ARP), and updates the state store.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Awaitable, Callable

from task_queue.base import TaskQueue
from schemas.zeus_result import ZeusResult
from store.base import AsyncStateStore


Dispatcher = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


async def _mock_dispatcher(task: dict[str, Any]) -> dict[str, Any]:
    """Default mock dispatcher for testing."""
    await asyncio.sleep(0.05)
    return {
        "status": "completed",
        "changed_files": [],
        "test_summary": {"passed": 1, "failed": 0, "skipped": 0},
        "commit_sha": "mock",
        "artifacts": {},
    }


class ZeusWorker:
    """Single worker that loops over the queue until told to stop."""

    def __init__(
        self,
        worker_id: str,
        store: AsyncStateStore,
        queue: TaskQueue,
        dispatcher: Dispatcher | None = None,
    ) -> None:
        self.worker_id = worker_id
        self.store = store
        self.queue = queue
        self.dispatcher = dispatcher or _mock_dispatcher
        self._stop = False

    async def run(self) -> None:
        while not self._stop:
            task = await self.queue.dequeue()
            if task is None:
                await asyncio.sleep(0.1)
                continue
            await self._execute(task)

    def stop(self) -> None:
        self._stop = True

    async def _execute(self, task: dict[str, Any]) -> None:
        tid = task["id"]
        await self.store.log_event(
            event_type="task.started",
            task_id=tid,
            agent_id=self.worker_id,
            wave=task.get("wave"),
            payload={},
        )
        try:
            result = await self.dispatcher(task)
            zeus_result = ZeusResult.model_validate(result)
        except Exception as exc:
            await self.store.log_event(
                event_type="task.failed",
                task_id=tid,
                agent_id=self.worker_id,
                payload={"error": str(exc)},
            )
            await self.store.update_task_status(tid, "failed", passes=False)
            await self.queue.nack(tid, reason=str(exc))
            return

        if zeus_result.status == "completed":
            await self.store.update_task_status(
                tid,
                "completed",
                passes=True,
                commit_sha=zeus_result.commit_sha,
            )
            await self.store.log_event(
                event_type="task.completed",
                task_id=tid,
                agent_id=self.worker_id,
                payload={"changed_files": zeus_result.changed_files, "test_summary": zeus_result.test_summary.model_dump()},
            )
            await self.queue.ack(tid)
        else:
            await self.store.update_task_status(tid, "failed", passes=False)
            await self.store.log_event(
                event_type="task.failed",
                task_id=tid,
                agent_id=self.worker_id,
                payload={"status": zeus_result.status, "artifacts": zeus_result.artifacts},
            )
            await self.queue.nack(tid, reason=zeus_result.artifacts.get("error", "partial_or_failed"))
