"""
Stress test for ZeusOpen v3 — 12 tasks with varying dependency chains,
mock dispatcher with artificial delay, and 4 concurrent workers.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
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


@pytest_asyncio.fixture
async def sqlite_store(tmp_path):
    db_path = tmp_path / "stress.sqlite"
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
        json.dumps({"project": {"name": "Stress"}, "metrics": {"north_star": "n"}, "subagent": {"dispatcher": "mock"}}),
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("#\n", encoding="utf-8")
    yield WorkspaceManager(tmp_path, "v3")


@pytest.mark.asyncio
async def test_stress_12_tasks_4_workers(sqlite_store, workspace_manager):
    store = sqlite_store
    q = MemoryTaskQueue()

    # Seed 12 tasks:
    # Wave 1: T-001 ~ T-004 (no deps)
    # Wave 2: T-005 ~ T-008 (depend on T-001 ~ T-004 respectively)
    # Wave 3: T-009 ~ T-012 (depend on T-005 ~ T-008 respectively)
    for i in range(1, 13):
        wave = ((i - 1) // 4) + 1
        dep = f"T-{i-4:03d}" if i > 4 else None
        await store.upsert_task({
            "id": f"T-{i:03d}",
            "status": "pending",
            "wave": wave,
            "depends_on": [dep] if dep else [],
        })

    # Slow mock dispatcher to expose concurrency bottlenecks
    original_run = MockSubagentDispatcher.run

    async def slow_run(self, task, workspace, prompt):
        await asyncio.sleep(0.15)
        return await original_run(self, task, workspace, prompt)

    import dispatcher.mock as dm
    dm.MockSubagentDispatcher.run = slow_run

    scheduler = ZeusScheduler(store, q)
    pool = WorkerPool(store, q, dm.MockSubagentDispatcher(), workspace_manager, max_workers=4)

    await pool.start()
    start_time = time.monotonic()

    enqueued_ids: set[str] = set()
    ticks = 0
    while True:
        ready = await scheduler.tick(enqueued_ids)
        ticks += 1
        qsize = await q.size()
        if not ready and qsize == 0:
            # Only query DB when queue is idle to decide if we are truly done
            pending = len(await store.list_tasks(status="pending"))
            running = len(await store.list_tasks(status="running"))
            if pending == 0 and running == 0:
                break
        await asyncio.sleep(0.05)

    elapsed = time.monotonic() - start_time
    await pool.stop()

    # Restore original speed
    dm.MockSubagentDispatcher.run = original_run

    # Verify all tasks completed
    for i in range(1, 13):
        t = await store.get_task(f"T-{i:03d}")
        assert t["status"] == "completed", f"T-{i:03d} should be completed"
        assert t["passes"] is True

    # With 4 workers and 0.15s per task, 12 tasks should take ~0.45s per wave * 3 waves = ~0.6-1.0s
    # Serial would be 1.8s; if elapsed > 2.5s something is wrong with parallelism.
    assert elapsed < 5.0, f"Expected <5.0s with 4 workers, got {elapsed:.2f}s"
    print(f"\n   Stress test completed in {elapsed:.2f}s over {ticks} scheduler ticks")


@pytest.mark.asyncio
async def test_stress_quarantine_unblocks_independent_branch(sqlite_store, workspace_manager):
    """
    T-101 fails and gets quarantined, blocking T-103.
    T-102 succeeds, allowing T-104 to proceed.
    """
    store = sqlite_store
    q = MemoryTaskQueue()

    await store.upsert_task({"id": "T-101", "status": "pending", "wave": 1, "depends_on": []})
    await store.upsert_task({"id": "T-102", "status": "pending", "wave": 1, "depends_on": []})
    await store.upsert_task({"id": "T-103", "status": "pending", "wave": 2, "depends_on": ["T-101"]})
    await store.upsert_task({"id": "T-104", "status": "pending", "wave": 2, "depends_on": ["T-102"]})

    import dispatcher.mock as dm
    original_run = dm.MockSubagentDispatcher.run

    async def flaky_run(self, task, workspace, prompt):
        if task["id"] == "T-101":
            raise RuntimeError("simulated failure")
        return await original_run(self, task, workspace, prompt)

    dm.MockSubagentDispatcher.run = flaky_run

    scheduler = ZeusScheduler(store, q)
    pool = WorkerPool(store, q, dm.MockSubagentDispatcher(), workspace_manager, max_workers=2)

    await pool.start()
    enqueued_ids: set[str] = set()
    for _ in range(200):
        ready = await scheduler.tick(enqueued_ids)
        qsize = await q.size()
        if not ready and qsize == 0:
            pending = len(await store.list_tasks(status="pending"))
            running = len(await store.list_tasks(status="running"))
            if pending == 0 and running == 0:
                break
        await asyncio.sleep(0.05)

    await pool.stop()
    dm.MockSubagentDispatcher.run = original_run

    assert await store.is_quarantined("T-101") is True

    t102 = await store.get_task("T-102")
    assert t102["status"] == "completed"

    t103 = await store.get_task("T-103")
    assert t103["status"] == "pending"  # blocked by quarantined T-101

    t104 = await store.get_task("T-104")
    assert t104["status"] == "completed"  # unblocked because T-102 succeeded
