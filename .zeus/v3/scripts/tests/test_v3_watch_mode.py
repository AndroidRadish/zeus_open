"""
Watch-mode tests for ZeusOpen v3 Option B.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.scheduler import ZeusScheduler
from core.worker_pool import WorkerPool
from db.engine import make_async_engine
from db.models import Base
from dispatcher.mock import MockSubagentDispatcher
from store.sqlite_store import SQLiteStateStore
from task_queue.memory_queue import MemoryTaskQueue
from workspace.manager import WorkspaceManager


@pytest_asyncio.fixture
async def sqlite_store(tmp_path):
    db_path = tmp_path / "watch.sqlite"
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
        json.dumps(
            {
                "project": {"name": "TestProj"},
                "metrics": {"north_star": "test-coverage"},
                "subagent": {"dispatcher": "mock"},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("# main\n", encoding="utf-8")
    yield WorkspaceManager(tmp_path, version="v3")


@pytest.mark.asyncio
async def test_scheduler_runs_when_target_is_running(sqlite_store):
    store = sqlite_store
    q = MemoryTaskQueue()
    await store.upsert_task(
        {"id": "T-WATCH-1", "status": "pending", "wave": 1, "depends_on": []}
    )
    scheduler = ZeusScheduler(store, q)

    await store.set_meta("scheduler_target_state", "running")
    target = await store.get_meta("scheduler_target_state", "stopped")
    assert target == "running"

    await store.set_meta("scheduler_actual_state", "running")
    result = await scheduler.run_once()
    assert result["enqueued"] == 1
    assert "T-WATCH-1" in result["task_ids"]


@pytest.mark.asyncio
async def test_worker_pool_scale_to_respects_target_count(sqlite_store, workspace_manager):
    store = sqlite_store
    q = MemoryTaskQueue()
    dispatcher = MockSubagentDispatcher()
    pool = WorkerPool(store, q, dispatcher, workspace_manager, max_workers=1)

    await pool.start()
    assert len(pool._workers) == 1

    await pool.scale_to(3)
    assert len(pool._workers) == 3
    assert len([t for t in pool._tasks if not t.done()]) == 3

    await pool.scale_to(1)
    assert len(pool._workers) == 1

    await pool.stop()
    assert len(pool._workers) == 0


@pytest.mark.asyncio
async def test_worker_pool_scale_to_zero_stops_all(sqlite_store, workspace_manager):
    store = sqlite_store
    q = MemoryTaskQueue()
    dispatcher = MockSubagentDispatcher()
    pool = WorkerPool(store, q, dispatcher, workspace_manager, max_workers=2)

    await pool.start()
    assert len(pool._workers) == 2

    await pool.scale_to(0)
    assert len(pool._workers) == 0
    # Give stopped workers time to exit their run loop
    await asyncio.sleep(0.5)
    done = {t for t in pool._tasks if t.done()}
    assert len(done) == 2

    await pool.stop()
