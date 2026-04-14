"""
ZeusOpen v3 SQLAlchemy async models.

Dynamic state storage for tasks, quarantine, scheduler meta, and event logs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Phase(Base):
    """Delivery phase grouping milestones."""

    __tablename__ = "phase"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(Text, default="")
    title_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    title_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    milestone_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    wave_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wave_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra: Mapped[Any] = mapped_column(JSON, nullable=True)


class Milestone(Base):
    """Milestone grouping tasks."""

    __tablename__ = "milestone"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(Text, default="")
    task_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    spec_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    story_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    extra: Mapped[Any] = mapped_column(JSON, nullable=True)


class TaskState(Base):
    """Mutable runtime state for each task."""

    __tablename__ = "task_state"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    story_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    passes: Mapped[bool] = mapped_column(default=False, index=True)
    wave: Mapped[int] = mapped_column(Integer, default=1, index=True)
    original_wave: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scheduled_wave: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rescheduled_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    depends_on: Mapped[list[str]] = mapped_column(JSON, default=list)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ai_log_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    files: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    milestone_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    extra: Mapped[Any] = mapped_column(JSON, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_task_state_status_wave", "status", "wave"),
        Index("ix_task_state_passes_wave", "passes", "wave"),
    )


class Quarantine(Base):
    """Failed tasks isolation zone."""

    __tablename__ = "quarantine"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    quarantined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    workspace: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[Any] = mapped_column(JSON, nullable=True)


class SchedulerMeta(Base):
    """Singleton-like scheduler state."""

    __tablename__ = "scheduler_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Mailbox(Base):
    """AgentBus message persistence."""

    __tablename__ = "mailbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    from_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_agent: Mapped[str | None] = mapped_column(String(64), index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    read: Mapped[bool] = mapped_column(default=False)


class EventLog(Base):
    """Structured event stream for observability and replay."""

    __tablename__ = "event_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    wave: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[Any] = mapped_column(JSON, nullable=True)
