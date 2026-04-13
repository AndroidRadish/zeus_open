"""
End-to-end tests for ZeusOpen v3 Phase 1:
- AsyncStateStore (SQLite + Postgres skeleton)
- TaskQueue (Memory + SQLite)
- Scheduler + WorkerPool integration
- Agent Result Protocol
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.engine import make_async_engine
from db.models import Base
from task_queue.memory_queue import MemoryTaskQueue
from task_queue.sqlite_queue import SqliteTaskQueue
from schemas.zeus_result import ZeusResult
from core.scheduler import ZeusScheduler
from core.worker_pool import WorkerPool
from store.sqlite_store import SQLiteStateStore
from store.postgres_store import PostgresStateStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def sqlite_store(tmp_path):
    db_path = tmp_path / "test_v3.sqlite"
    store = SQLiteStateStore(f"sqlite+aiosqlite:///{db_path}")
    engine = make_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    yield store
    await store.close()


@pytest_asyncio.fixture
async def memory_queue():
    q = MemoryTaskQueue()
    yield q
    await q.close()


@pytest_asyncio.fixture
async def sqlite_queue(tmp_path):
    db_path = tmp_path / "test_queue.sqlite"
    q = SqliteTaskQueue(str(db_path))
    yield q
    await q.close()


# ---------------------------------------------------------------------------
# StateStore tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sqlite_store_task_lifecycle(sqlite_store):
    store = sqlite_store
    await store.upsert_task({
        "id": "T-101",
        "title": "Test task",
        "status": "pending",
        "passes": False,
        "wave": 1,
        "depends_on": [],
    })
    task = await store.get_task("T-101")
    assert task is not None
    assert task["status"] == "pending"

    await store.update_task_status("T-101", "running")
    task = await store.get_task("T-101")
    assert task["status"] == "running"

    await store.update_task_status("T-101", "completed", passes=True, commit_sha="abc123")
    task = await store.get_task("T-101")
    assert task["status"] == "completed"
    assert task["passes"] is True
    assert task["commit_sha"] == "abc123"

    tasks = await store.list_tasks(status="completed")
    assert len(tasks) == 1
    assert tasks[0]["id"] == "T-101"


@pytest.mark.asyncio
async def test_sqlite_store_quarantine(sqlite_store):
    store = sqlite_store
    await store.upsert_task({"id": "T-102", "status": "pending", "wave": 1, "depends_on": []})
    await store.quarantine_task("T-102", "simulated failure", workspace="/tmp/ws")
    assert await store.is_quarantined("T-102") is True

    qlist = await store.list_quarantine()
    assert len(qlist) == 1
    assert qlist[0]["reason"] == "simulated failure"

    await store.unquarantine_task("T-102")
    assert await store.is_quarantined("T-102") is False


@pytest.mark.asyncio
async def test_sqlite_store_meta_and_events(sqlite_store):
    store = sqlite_store
    await store.set_meta("current_wave", 3)
    assert await store.get_meta("current_wave") == 3

    eid = await store.log_event("task.started", task_id="T-103", agent_id="w-0", wave=1, payload={"x": 1})
    assert isinstance(eid, int)

    events = await store.query_events(task_id="T-103")
    assert len(events) == 1
    assert events[0]["event_type"] == "task.started"


@pytest.mark.asyncio
async def test_postgres_store_init_without_url():
    with pytest.raises(ValueError):
        PostgresStateStore()


# ---------------------------------------------------------------------------
# Queue tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_memory_queue_basic(memory_queue):
    q = memory_queue
    await q.enqueue({"id": "T-201", "wave": 1})
    assert await q.size() == 1
    task = await q.dequeue()
    assert task["id"] == "T-201"
    await q.ack("T-201")


@pytest.mark.asyncio
async def test_memory_queue_nack_retry(memory_queue):
    q = memory_queue
    await q.enqueue({"id": "T-202", "wave": 1})
    task = await q.dequeue()
    assert task["id"] == "T-202"
    await q.nack("T-202", "oops")
    # Should be re-enqueued
    task2 = await q.dequeue()
    assert task2["id"] == "T-202"
    assert task2["retry_count"] == 1


@pytest.mark.asyncio
async def test_sqlite_queue_persistence(sqlite_queue):
    q = sqlite_queue
    await q.enqueue({"id": "T-203", "wave": 2})
    assert await q.size() == 1
    task = await q.dequeue()
    assert task["id"] == "T-203"
    await q.ack("T-203")
    assert await q.size() == 0


# ---------------------------------------------------------------------------
# Scheduler + WorkerPool integration
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_scheduler_enqueues_ready_tasks(sqlite_store, memory_queue):
    store = sqlite_store
    q = memory_queue
    await store.upsert_task({"id": "T-301", "status": "pending", "wave": 1, "depends_on": []})
    await store.upsert_task({"id": "T-302", "status": "pending", "wave": 1, "depends_on": ["T-301"]})

    scheduler = ZeusScheduler(store, q)
    enqueued_ids: set[str] = set()
    ready = await scheduler.tick(enqueued_ids)
    assert len(ready) == 1
    assert ready[0]["id"] == "T-301"
    assert await q.size() == 1


@pytest.mark.asyncio
async def test_scheduler_respects_quarantine(sqlite_store, memory_queue):
    store = sqlite_store
    q = memory_queue
    await store.upsert_task({"id": "T-303", "status": "pending", "wave": 1, "depends_on": []})
    await store.upsert_task({"id": "T-304", "status": "pending", "wave": 1, "depends_on": ["T-303"]})
    await store.quarantine_task("T-303", "fail")

    scheduler = ZeusScheduler(store, q)
    enqueued_ids: set[str] = set()
    ready = await scheduler.tick(enqueued_ids)
    assert len(ready) == 0  # T-303 quarantined, T-304 blocked


@pytest.mark.asyncio
async def test_worker_executes_mock_dispatcher(sqlite_store, memory_queue):
    store = sqlite_store
    q = memory_queue
    await store.upsert_task({"id": "T-305", "status": "pending", "wave": 1, "depends_on": []})
    await q.enqueue({"id": "T-305", "wave": 1})

    pool = WorkerPool(store, q, max_workers=1)
    await pool.start()
    await asyncio.sleep(0.3)
    await pool.stop()

    task = await store.get_task("T-305")
    assert task["status"] == "completed"
    assert task["passes"] is True


@pytest.mark.asyncio
async def test_end_to_end_scheduler_worker_pool(sqlite_store, memory_queue):
    store = sqlite_store
    q = memory_queue
    # Seed tasks
    await store.upsert_task({"id": "T-401", "status": "pending", "wave": 1, "depends_on": []})
    await store.upsert_task({"id": "T-402", "status": "pending", "wave": 1, "depends_on": []})
    await store.upsert_task({"id": "T-403", "status": "pending", "wave": 2, "depends_on": ["T-401"]})

    scheduler = ZeusScheduler(store, q)
    pool = WorkerPool(store, q, max_workers=2)

    await pool.start()

    # Tick 1: T-401 and T-402 should be enqueued
    enqueued_ids: set[str] = set()
    ready1 = await scheduler.tick(enqueued_ids)
    assert {t["id"] for t in ready1} == {"T-401", "T-402"}

    await asyncio.sleep(0.3)

    # Tick 2: T-401 completed, T-403 now ready
    ready2 = await scheduler.tick(enqueued_ids)
    assert {t["id"] for t in ready2} == {"T-403"}

    await asyncio.sleep(0.3)
    await pool.stop()

    for tid in ("T-401", "T-402", "T-403"):
        t = await store.get_task(tid)
        assert t["status"] == "completed", f"{tid} should be completed"
        assert t["passes"] is True

    await scheduler.mark_global_completed()
    assert await store.get_meta("scheduler_active") is False


# ---------------------------------------------------------------------------
# ARP schema tests
# ---------------------------------------------------------------------------
def test_zeus_result_validates():
    result = ZeusResult(
        status="completed",
        changed_files=["src/foo.py"],
        test_summary={"passed": 5, "failed": 0, "skipped": 1},
        commit_sha="abc1234",
        artifacts={"coverage": "85%"},
    )
    assert result.status == "completed"
    assert result.test_summary.passed == 5


def test_zeus_result_invalid_status():
    with pytest.raises(Exception):
        ZeusResult(status="unknown")
