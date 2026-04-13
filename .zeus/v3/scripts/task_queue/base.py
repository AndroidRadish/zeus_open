"""
Task queue abstraction for ZeusOpen v3.

Decouples the scheduler from execution by providing a persistent task queue.
"""
from __future__ import annotations

import abc
from typing import Any


class TaskQueue(abc.ABC):
    """Abstract async queue for task dispatching."""

    @abc.abstractmethod
    async def enqueue(self, task: dict[str, Any]) -> None:
        """Add a task to the queue."""
        raise NotImplementedError

    @abc.abstractmethod
    async def dequeue(self) -> dict[str, Any] | None:
        """Retrieve the next task. Blocks until one is available or returns None if empty."""
        raise NotImplementedError

    @abc.abstractmethod
    async def ack(self, task_id: str) -> None:
        """Acknowledge successful completion of a task."""
        raise NotImplementedError

    @abc.abstractmethod
    async def nack(self, task_id: str, reason: str) -> None:
        """Negative acknowledge — task failed and should be retried or dead-lettered."""
        raise NotImplementedError

    @abc.abstractmethod
    async def size(self) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    async def close(self) -> None:
        raise NotImplementedError
