"""
Shared SQLAlchemy-backed implementation for AsyncStateStore.
Used by both SQLiteStateStore and PostgresStateStore.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.models import EventLog, Quarantine, SchedulerMeta, TaskState
from store.base import AsyncStateStore


def _taskstate_to_dict(obj: TaskState) -> dict[str, Any]:
    return {
        "id": obj.id,
        "story_id": obj.story_id,
        "title": obj.title,
        "description": obj.description,
        "status": obj.status,
        "passes": obj.passes,
        "wave": obj.wave,
        "original_wave": obj.original_wave,
        "scheduled_wave": obj.scheduled_wave,
        "rescheduled_from": obj.rescheduled_from,
        "depends_on": obj.depends_on,
        "commit_sha": obj.commit_sha,
        "ai_log_ref": obj.ai_log_ref,
        "files": obj.files,
        "extra": obj.extra,
        "worker_id": obj.worker_id,
        "heartbeat_at": obj.heartbeat_at.isoformat() if obj.heartbeat_at else None,
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }


def _quarantine_to_dict(obj: Quarantine) -> dict[str, Any]:
    return {
        "task_id": obj.task_id,
        "reason": obj.reason,
        "quarantined_at": obj.quarantined_at.isoformat() if obj.quarantined_at else None,
        "workspace": obj.workspace,
        "extra": obj.extra,
    }


def _eventlog_to_dict(obj: EventLog) -> dict[str, Any]:
    return {
        "id": obj.id,
        "ts": obj.ts.isoformat() if obj.ts else None,
        "event_type": obj.event_type,
        "task_id": obj.task_id,
        "agent_id": obj.agent_id,
        "wave": obj.wave,
        "payload": obj.payload,
    }


class _SqlAlchemyStateStore(AsyncStateStore):
    """Concrete SQLAlchemy implementation."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def health(self) -> dict[str, Any]:
        return {"type": "sqlalchemy", "ok": True}

    # TaskState --------------------------------------------------------
    async def upsert_task(self, task: dict[str, Any]) -> None:
        async with self._session_factory() as session:
            existing = await session.get(TaskState, task["id"])
            if existing:
                for k, v in task.items():
                    if hasattr(existing, k) and k != "id":
                        setattr(existing, k, v)
            else:
                session.add(TaskState(**task))
            await session.commit()

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            obj = await session.get(TaskState, task_id)
            return _taskstate_to_dict(obj) if obj else None

    async def list_tasks(self, *, status: str | None = None, wave: int | None = None) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            stmt = select(TaskState)
            if status is not None:
                stmt = stmt.where(TaskState.status == status)
            if wave is not None:
                stmt = stmt.where(TaskState.wave == wave)
            result = await session.execute(stmt)
            return [_taskstate_to_dict(r) for r in result.scalars().all()]

    async def update_task_status(self, task_id: str, status: str, passes: bool | None = None, **fields) -> None:
        async with self._session_factory() as session:
            updates: dict[str, Any] = {"status": status}
            if passes is not None:
                updates["passes"] = passes
            updates.update(fields)
            await session.execute(update(TaskState).where(TaskState.id == task_id).values(**updates))
            await session.commit()

    async def update_task_heartbeat(self, task_id: str, worker_id: str) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(TaskState)
                .where(TaskState.id == task_id)
                .values(worker_id=worker_id, heartbeat_at=func.now())
            )
            await session.commit()

    async def delete_task(self, task_id: str) -> None:
        async with self._session_factory() as session:
            await session.execute(delete(TaskState).where(TaskState.id == task_id))
            await session.commit()

    # Quarantine -------------------------------------------------------
    async def quarantine_task(self, task_id: str, reason: str, workspace: str | None = None, extra: dict | None = None) -> None:
        async with self._session_factory() as session:
            existing = await session.get(Quarantine, task_id)
            if existing:
                existing.reason = reason
                existing.workspace = workspace or existing.workspace
                if extra:
                    existing.extra = extra
            else:
                session.add(Quarantine(task_id=task_id, reason=reason, workspace=workspace, extra=extra))
            await session.commit()

    async def unquarantine_task(self, task_id: str) -> None:
        async with self._session_factory() as session:
            await session.execute(delete(Quarantine).where(Quarantine.task_id == task_id))
            await session.commit()

    async def list_quarantine(self) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            result = await session.execute(select(Quarantine))
            return [_quarantine_to_dict(r) for r in result.scalars().all()]

    async def is_quarantined(self, task_id: str) -> bool:
        async with self._session_factory() as session:
            obj = await session.get(Quarantine, task_id)
            return obj is not None

    # SchedulerMeta ----------------------------------------------------
    async def set_meta(self, key: str, value: Any) -> None:
        async with self._session_factory() as session:
            existing = await session.get(SchedulerMeta, key)
            if existing:
                existing.value = value
            else:
                session.add(SchedulerMeta(key=key, value=value))
            await session.commit()

    async def get_meta(self, key: str, default: Any = None) -> Any:
        async with self._session_factory() as session:
            obj = await session.get(SchedulerMeta, key)
            return obj.value if obj else default

    async def delete_meta(self, key: str) -> None:
        async with self._session_factory() as session:
            await session.execute(delete(SchedulerMeta).where(SchedulerMeta.key == key))
            await session.commit()

    # EventLog ---------------------------------------------------------
    async def log_event(
        self,
        event_type: str,
        task_id: str | None = None,
        agent_id: str | None = None,
        wave: int | None = None,
        payload: dict[str, Any] | None = None,
        ts: Any | None = None,
    ) -> int:
        async with self._session_factory() as session:
            kwargs: dict[str, Any] = dict(
                event_type=event_type,
                task_id=task_id,
                agent_id=agent_id,
                wave=wave,
                payload=payload,
            )
            if ts is not None:
                kwargs["ts"] = ts
            obj = EventLog(**kwargs)
            session.add(obj)
            await session.commit()
            return obj.id

    async def query_events(
        self,
        *,
        event_type: str | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            stmt = select(EventLog)
            if event_type is not None:
                stmt = stmt.where(EventLog.event_type == event_type)
            if task_id is not None:
                stmt = stmt.where(EventLog.task_id == task_id)
            if agent_id is not None:
                stmt = stmt.where(EventLog.agent_id == agent_id)
            stmt = stmt.order_by(EventLog.id.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [_eventlog_to_dict(r) for r in result.scalars().all()]
