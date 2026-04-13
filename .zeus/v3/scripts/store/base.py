"""
Async state store abstraction for ZeusOpen v3.

Replaces v2 file-lock + task.json mutation with database-backed state.
"""
from __future__ import annotations

import abc
from typing import Any


class AsyncStateStore(abc.ABC):
    """Abstract async store for task/quarantine/scheduler/event state."""

    @abc.abstractmethod
    async def health(self) -> dict[str, Any]:
        """Return store health metadata."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # TaskState
    # ------------------------------------------------------------------
    @abc.abstractmethod
    async def upsert_task(self, task: dict[str, Any]) -> None:
        """Insert or replace a task state row."""
        raise NotImplementedError

    @abc.abstractmethod
    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abc.abstractmethod
    async def list_tasks(self, *, status: str | None = None, wave: int | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abc.abstractmethod
    async def update_task_status(self, task_id: str, status: str, passes: bool | None = None, **fields) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_task(self, task_id: str) -> None:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Quarantine
    # ------------------------------------------------------------------
    @abc.abstractmethod
    async def quarantine_task(self, task_id: str, reason: str, workspace: str | None = None, extra: dict | None = None) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def unquarantine_task(self, task_id: str) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def list_quarantine(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abc.abstractmethod
    async def is_quarantined(self, task_id: str) -> bool:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # SchedulerMeta
    # ------------------------------------------------------------------
    @abc.abstractmethod
    async def set_meta(self, key: str, value: Any) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_meta(self, key: str, default: Any = None) -> Any:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_meta(self, key: str) -> None:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # EventLog
    # ------------------------------------------------------------------
    @abc.abstractmethod
    async def log_event(
        self,
        event_type: str,
        task_id: str | None = None,
        agent_id: str | None = None,
        wave: int | None = None,
        payload: dict[str, Any] | None = None,
        ts: Any | None = None,
    ) -> int:
        """Append an event and return the generated event id."""
        raise NotImplementedError

    @abc.abstractmethod
    async def query_events(
        self,
        *,
        event_type: str | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError
