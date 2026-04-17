"""
Shared SQLAlchemy-backed implementation for AsyncStateStore.
Used by both SQLiteStateStore and PostgresStateStore.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.models import EventLog, Mailbox, Milestone, Phase, PlanHistory, Quarantine, SchedulerMeta, TaskState
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
        "milestone_id": obj.milestone_id,
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


def _phase_to_dict(obj: Phase) -> dict[str, Any]:
    return {
        "id": obj.id,
        "title": obj.title,
        "title_en": obj.title_en,
        "title_zh": obj.title_zh,
        "summary": obj.summary,
        "summary_en": obj.summary_en,
        "summary_zh": obj.summary_zh,
        "status": obj.status,
        "progress_percent": obj.progress_percent,
        "milestone_ids": obj.milestone_ids,
        "wave_start": obj.wave_start,
        "wave_end": obj.wave_end,
        "extra": obj.extra,
    }


def _milestone_to_dict(obj: Milestone) -> dict[str, Any]:
    return {
        "id": obj.id,
        "title": obj.title,
        "task_ids": obj.task_ids,
        "status": obj.status,
        "progress_percent": obj.progress_percent,
        "spec_ref": obj.spec_ref,
        "story_ids": obj.story_ids,
        "extra": obj.extra,
    }


def _resolve_aggregate_status(statuses: list[str]) -> str:
    if any(s == "failed" for s in statuses):
        return "failed"
    if any(s == "running" for s in statuses):
        return "running"
    if all(s == "completed" for s in statuses):
        return "completed"
    return "pending"


def _mailbox_to_dict(obj: Mailbox) -> dict[str, Any]:
    return {
        "id": obj.id,
        "ts": obj.ts.isoformat() if obj.ts else None,
        "task_id": obj.task_id,
        "from_agent": obj.from_agent,
        "to_agent": obj.to_agent,
        "message": obj.message,
        "read": obj.read,
    }


def _planhistory_to_dict(obj: PlanHistory) -> dict[str, Any]:
    return {
        "id": obj.id,
        "ts": obj.ts.isoformat() if obj.ts else None,
        "entity_type": obj.entity_type,
        "entity_id": obj.entity_id,
        "action": obj.action,
        "changed_by": obj.changed_by,
        "snapshot_before": obj.snapshot_before,
        "snapshot_after": obj.snapshot_after,
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

    # Phase ------------------------------------------------------------
    async def upsert_phase(self, phase: dict[str, Any]) -> None:
        async with self._session_factory() as session:
            existing = await session.get(Phase, phase["id"])
            if existing:
                for k, v in phase.items():
                    if hasattr(existing, k) and k != "id":
                        setattr(existing, k, v)
            else:
                session.add(Phase(**phase))
            await session.commit()

    async def _enrich_milestone(self, session, obj: Milestone) -> dict[str, Any]:
        data = _milestone_to_dict(obj)
        statuses: list[str] = []
        task_ids = obj.task_ids or []
        if task_ids:
            result = await session.execute(select(TaskState).where(TaskState.id.in_(task_ids)))
            statuses = [t.status for t in result.scalars().all()]
        if not statuses:
            result = await session.execute(select(TaskState).where(TaskState.milestone_id == obj.id))
            statuses = [t.status for t in result.scalars().all()]
        if statuses:
            completed = sum(1 for s in statuses if s == "completed")
            data["progress_percent"] = int((completed / len(statuses)) * 100)
            data["status"] = _resolve_aggregate_status(statuses)
        return data

    async def _enrich_phase(self, session, obj: Phase) -> dict[str, Any]:
        data = _phase_to_dict(obj)
        ms_ids = obj.milestone_ids or []
        if not ms_ids:
            return data
        result = await session.execute(select(Milestone).where(Milestone.id.in_(ms_ids)))
        milestones = result.scalars().all()
        if not milestones:
            return data
        ms_data = [await self._enrich_milestone(session, ms) for ms in milestones]
        data["progress_percent"] = int(sum(m["progress_percent"] for m in ms_data) / len(ms_data))
        data["status"] = _resolve_aggregate_status([m["status"] for m in ms_data])
        return data

    async def get_phase(self, phase_id: str) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            obj = await session.get(Phase, phase_id)
            if not obj:
                return None
            return await self._enrich_phase(session, obj)

    async def list_phases(self) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            result = await session.execute(select(Phase))
            rows = result.scalars().all()
            return [await self._enrich_phase(session, r) for r in rows]

    async def delete_phase(self, phase_id: str) -> None:
        async with self._session_factory() as session:
            await session.execute(delete(Phase).where(Phase.id == phase_id))
            await session.commit()

    # Milestone --------------------------------------------------------
    async def upsert_milestone(self, milestone: dict[str, Any]) -> None:
        async with self._session_factory() as session:
            existing = await session.get(Milestone, milestone["id"])
            if existing:
                for k, v in milestone.items():
                    if hasattr(existing, k) and k != "id":
                        setattr(existing, k, v)
            else:
                session.add(Milestone(**milestone))
            await session.commit()

    async def get_milestone(self, milestone_id: str) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            obj = await session.get(Milestone, milestone_id)
            if not obj:
                return None
            return await self._enrich_milestone(session, obj)

    async def list_milestones(self) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            result = await session.execute(select(Milestone))
            rows = result.scalars().all()
            return [await self._enrich_milestone(session, r) for r in rows]

    async def delete_milestone(self, milestone_id: str) -> None:
        async with self._session_factory() as session:
            await session.execute(delete(Milestone).where(Milestone.id == milestone_id))
            await session.commit()

    async def list_tasks_by_milestone(self, milestone_id: str) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            stmt = select(TaskState).where(TaskState.milestone_id == milestone_id)
            result = await session.execute(stmt)
            return [_taskstate_to_dict(r) for r in result.scalars().all()]

    # Mailbox ----------------------------------------------------------
    async def send_message(self, message: dict[str, Any]) -> int:
        async with self._session_factory() as session:
            obj = Mailbox(
                task_id=message.get("task_id"),
                from_agent=message.get("from_agent"),
                to_agent=message.get("to_agent"),
                message=message.get("message"),
                read=message.get("read", False),
            )
            session.add(obj)
            await session.commit()
            return obj.id

    async def list_messages(self, to_agent: str | None = None, read: bool | None = None, limit: int = 100) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            stmt = select(Mailbox)
            if to_agent is not None:
                stmt = stmt.where(Mailbox.to_agent == to_agent)
            if read is not None:
                stmt = stmt.where(Mailbox.read == read)
            stmt = stmt.order_by(Mailbox.id.desc()).limit(limit)
            result = await session.execute(stmt)
            return [_mailbox_to_dict(r) for r in result.scalars().all()]

    async def mark_message_read(self, message_id: int, read: bool = True) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(Mailbox).where(Mailbox.id == message_id).values(read=read)
            )
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

    # PlanHistory ------------------------------------------------------
    async def log_plan_history(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        *,
        changed_by: str | None = None,
        snapshot_before: dict[str, Any] | None = None,
        snapshot_after: dict[str, Any] | None = None,
    ) -> int:
        async with self._session_factory() as session:
            obj = PlanHistory(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                changed_by=changed_by,
                snapshot_before=snapshot_before,
                snapshot_after=snapshot_after,
            )
            session.add(obj)
            await session.commit()
            return obj.id

    async def query_plan_history(
        self,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            stmt = select(PlanHistory)
            if entity_type is not None:
                stmt = stmt.where(PlanHistory.entity_type == entity_type)
            if entity_id is not None:
                stmt = stmt.where(PlanHistory.entity_id == entity_id)
            stmt = stmt.order_by(PlanHistory.id.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [_planhistory_to_dict(r) for r in result.scalars().all()]

    # Plan Export ------------------------------------------------------
    async def export_plan(self, *, include_runtime: bool = False) -> dict[str, Any]:
        async with self._session_factory() as session:
            tasks_result = await session.execute(select(TaskState))
            phases_result = await session.execute(select(Phase))
            milestones_result = await session.execute(select(Milestone))

            tasks = []
            for t in tasks_result.scalars().all():
                d = {
                    "id": t.id,
                    "story_id": t.story_id,
                    "title": t.title,
                    "description": t.description,
                    "wave": t.wave,
                    "original_wave": t.original_wave,
                    "scheduled_wave": t.scheduled_wave,
                    "rescheduled_from": t.rescheduled_from,
                    "depends_on": t.depends_on,
                    "ai_log_ref": t.ai_log_ref,
                    "files": t.files,
                    "milestone_id": t.milestone_id,
                    "extra": t.extra,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                if include_runtime:
                    d["status"] = t.status
                    d["passes"] = t.passes
                    d["commit_sha"] = t.commit_sha
                    d["worker_id"] = t.worker_id
                    d["heartbeat_at"] = t.heartbeat_at.isoformat() if t.heartbeat_at else None
                    d["updated_at"] = t.updated_at.isoformat() if t.updated_at else None
                tasks.append(d)

            return {
                "version": "v3",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "tasks": tasks,
                "phases": [_phase_to_dict(p) for p in phases_result.scalars().all()],
                "milestones": [_milestone_to_dict(m) for m in milestones_result.scalars().all()],
            }
