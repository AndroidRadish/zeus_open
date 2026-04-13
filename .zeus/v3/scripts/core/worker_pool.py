"""
ZeusOpen v3 worker pool.

Manages a dynamic number of ZeusWorker coroutines.
"""
from __future__ import annotations

import asyncio
from typing import Any

from core.worker import ZeusWorker, Dispatcher
from task_queue.base import TaskQueue
from store.base import AsyncStateStore


class WorkerPool:
    """Pool of workers consuming from a shared queue."""

    def __init__(
        self,
        store: AsyncStateStore,
        queue: TaskQueue,
        max_workers: int = 3,
        dispatcher: Dispatcher | None = None,
    ) -> None:
        self.store = store
        self.queue = queue
        self.max_workers = max_workers
        self.dispatcher = dispatcher
        self._workers: list[ZeusWorker] = []
        self._tasks: set[asyncio.Task] = set()
        self._stop = False

    async def start(self) -> None:
        """Launch all worker coroutines."""
        for i in range(self.max_workers):
            worker = ZeusWorker(
                worker_id=f"worker-{i}",
                store=self.store,
                queue=self.queue,
                dispatcher=self.dispatcher,
            )
            self._workers.append(worker)
            t = asyncio.create_task(worker.run())
            self._tasks.add(t)

    async def stop(self, timeout: float = 10.0) -> None:
        """Signal all workers to stop and await their exit."""
        self._stop = True
        for worker in self._workers:
            worker.stop()
        if self._tasks:
            done, pending = await asyncio.wait(self._tasks, timeout=timeout)
            for t in pending:
                t.cancel()
            self._tasks.clear()
        self._workers.clear()

    async def __aenter__(self) -> "WorkerPool":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()
