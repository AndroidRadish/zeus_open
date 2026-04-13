"""
Worker heartbeat and scheduler lease recovery tests.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.engine import make_async_engine
from db.models import Base
from core.scheduler import ZeusScheduler
from core.worker_pool import WorkerPool
from dispatcher.mock import MockSubagentDispatcher
from store.sqlite_store import SQLiteStateStore
from task_queue.memory_queue import MemoryTaskQueue
from workspace.manager import WorkspaceManager
import json


@pytest_asyncio.fixture
async def sqlite_store(tmp_path):
    db_path = tmp_path / "hb.sqlite"
    store = SQLiteStateStore(f"sqlite+aiosqlite:///{db_path}")
    engine = make_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    yield store
    await store.close()


@pytest_asyncio.fixture
async def workspace_manager(tmp_path):
    (tmp_path / ".zeus" / "v3" / "config.json").parent.mkdir(parents=True)
    (tmp_path / ".zeus" / "v3" / "config.json").write_text(
        json.dumps({"project": {"name": "HB"}, "metrics": {"north_star": "n"}, "subagent": {"dispatcher": "mock"}}),
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("#\n", encoding="utf-8")
    yield WorkspaceManager(tmp_path, "v3")


@pytest.mark.asyncio
async def test_update_task_heartbeat(sqlite_store):
    await sqlite_store.upsert_task({"id": "T-HB-1", "status": "running", "wave": 1})
    await sqlite_store.update_task_heartbeat("T-HB-1", "worker-7")
    t = await sqlite_store.get_task("T-HB-1")
    assert t["worker_id"] == "worker-7"
    assert t["heartbeat_at"] is not None


@pytest.mark.asyncio
async def test_scheduler_recovers_expired_lease(sqlite_store):
    old_hb = datetime.now(timezone.utc) - timedelta(seconds=120)
    await sqlite_store.upsert_task({
        "id": "T-LEASE-1",
        "status": "running",
        "wave": 1,
        "worker_id": "worker-dead",
        "heartbeat_at": old_hb,
    })

    q = MemoryTaskQueue()
    scheduler = ZeusScheduler(sqlite_store, q, lease_timeout_seconds=30.0)
    ready = await scheduler.tick(set())

    # After recovery, task should be re-enqueued in the same tick (status -> running)
    assert any(r["id"] == "T-LEASE-1" for r in ready)
    t = await sqlite_store.get_task("T-LEASE-1")
    assert t["status"] == "running"
    assert t["worker_id"] is None


@pytest.mark.asyncio
async def test_scheduler_does_not_recover_fresh_lease(sqlite_store):
    fresh_hb = datetime.now(timezone.utc)
    await sqlite_store.upsert_task({
        "id": "T-LEASE-2",
        "status": "running",
        "wave": 1,
        "worker_id": "worker-alive",
        "heartbeat_at": fresh_hb,
    })

    q = MemoryTaskQueue()
    scheduler = ZeusScheduler(sqlite_store, q, lease_timeout_seconds=30.0)
    ready = await scheduler.tick(set())

    t = await sqlite_store.get_task("T-LEASE-2")
    assert t["status"] == "running"
    assert t["worker_id"] == "worker-alive"
