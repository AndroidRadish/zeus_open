"""
End-to-end tests for ZeusOpen v3 Phase 1:
- AsyncStateStore (SQLite + Postgres skeleton)
- TaskQueue (Memory + SQLite)
- Scheduler + WorkerPool integration
- Agent Result Protocol
- Importer (task.json -> DB)
- Workspace + Dispatcher integration
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

import sys
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.engine import make_async_engine
from db.models import Base
from dispatcher.mock import MockSubagentDispatcher
from importer import import_tasks_from_json
from task_queue.memory_queue import MemoryTaskQueue
from task_queue.sqlite_queue import SqliteTaskQueue
from schemas.zeus_result import ZeusResult
from core.scheduler import ZeusScheduler
from core.worker_pool import WorkerPool
from store.sqlite_store import SQLiteStateStore
from store.postgres_store import PostgresStateStore
from workspace.manager import WorkspaceManager


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


@pytest_asyncio.fixture
async def workspace_manager(tmp_path):
    # Create a minimal fake project tree
    (tmp_path / ".zeus" / "v3" / "config.json").parent.mkdir(parents=True)
    (tmp_path / ".zeus" / "v3" / "config.json").write_text(
        json.dumps({
            "project": {"name": "TestProj"},
            "metrics": {"north_star": "test-coverage"},
            "subagent": {"dispatcher": "mock"},
        }),
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("# main\n", encoding="utf-8")
    yield WorkspaceManager(tmp_path, version="v3")


# ---------------------------------------------------------------------------
# Importer tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_import_tasks_from_json(sqlite_store, tmp_path):
    store = sqlite_store
    task_json = {
        "meta": {"current_wave": 3, "max_parallel_agents": 2},
        "tasks": [
            {"id": "T-101", "title": "Task 1", "status": "pending", "passes": False, "wave": 1, "depends_on": [], "type": "feat"},
            {"id": "T-102", "title": "Task 2", "status": "running", "passes": False, "wave": 1, "depends_on": ["T-101"]},
        ],
        "quarantine": [
            {"task_id": "T-103", "reason": "fail", "workspace": "/tmp"},
        ],
    }
    path = tmp_path / "task.json"
    path.write_text(json.dumps(task_json), encoding="utf-8")

    result = await import_tasks_from_json(store, path)
    assert result["imported_tasks"] == 2
    assert result["quarantine_count"] == 1

    t1 = await store.get_task("T-101")
    assert t1["title"] == "Task 1"
    assert t1["wave"] == 1

    t2 = await store.get_task("T-102")
    assert t2["depends_on"] == ["T-101"]

    q = await store.list_quarantine()
    assert any(x["task_id"] == "T-103" for x in q)
    assert await store.get_meta("current_wave") == 3


@pytest.mark.asyncio
async def test_import_preserves_extra_fields(sqlite_store, tmp_path):
    store = sqlite_store
    task_json = {
        "meta": {},
        "tasks": [
            {"id": "T-104", "title": "Task", "custom_flag": True, "status": "pending", "wave": 1, "depends_on": []},
        ],
        "quarantine": [],
    }
    path = tmp_path / "task.json"
    path.write_text(json.dumps(task_json), encoding="utf-8")
    await import_tasks_from_json(store, path)
    t = await store.get_task("T-104")
    assert t["extra"]["custom_flag"] is True


@pytest.mark.asyncio
async def test_import_phases_and_milestones(sqlite_store, tmp_path):
    store = sqlite_store
    task_json = {
        "meta": {},
        "tasks": [
            {"id": "T-201", "title": "Task 1", "status": "pending", "wave": 1, "milestone_id": "M-1"},
        ],
        "phases": [
            {"id": "P-1", "title": "Phase 1", "title_en": "Phase 1", "title_zh": "阶段 1", "status": "completed", "progress_percent": 100, "milestone_ids": ["M-1"]},
        ],
        "milestones": [
            {"id": "M-1", "title": "Milestone 1", "task_ids": ["T-201"], "status": "completed", "progress_percent": 100},
        ],
    }
    path = tmp_path / "task.json"
    path.write_text(json.dumps(task_json), encoding="utf-8")
    result = await import_tasks_from_json(store, path)
    assert result["imported_phases"] == 1
    assert result["imported_milestones"] == 1

    t = await store.get_task("T-201")
    assert t["milestone_id"] == "M-1"

    p = await store.get_phase("P-1")
    assert p["title"] == "Phase 1"
    assert p["title_zh"] == "阶段 1"
    assert p["milestone_ids"] == ["M-1"]

    m = await store.get_milestone("M-1")
    assert m["title"] == "Milestone 1"
    assert m["task_ids"] == ["T-201"]


@pytest.mark.asyncio
async def test_import_preserves_runtime_state(sqlite_store, tmp_path):
    """Importer must never overwrite status, passes, commit_sha from task.json."""
    store = sqlite_store
    # Pre-seed DB with a completed task
    await store.upsert_task({
        "id": "T-RUNTIME",
        "title": "DB Title",
        "status": "completed",
        "passes": True,
        "commit_sha": "abc1234",
        "wave": 5,
        "depends_on": [],
    })

    # task.json tries to change runtime fields back to pending/false
    task_json = {
        "meta": {},
        "tasks": [
            {"id": "T-RUNTIME", "title": "JSON Title", "status": "pending", "passes": False, "wave": 1, "depends_on": []},
        ],
        "quarantine": [],
    }
    path = tmp_path / "task.json"
    path.write_text(json.dumps(task_json), encoding="utf-8")
    await import_tasks_from_json(store, path)

    t = await store.get_task("T-RUNTIME")
    # Static fields should be updated
    assert t["title"] == "JSON Title"
    assert t["wave"] == 1
    # Runtime fields must be preserved from DB
    assert t["status"] == "completed"
    assert t["passes"] is True
    assert t["commit_sha"] == "abc1234"


# ---------------------------------------------------------------------------
# Workspace tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_workspace_prepare_cleans_and_copies(workspace_manager):
    tid = "T-201"
    ws = await workspace_manager.prepare({"id": tid, "title": "Test", "wave": 1, "depends_on": []})
    assert ws.exists()
    assert (ws / "src" / "main.py").exists()
    assert (ws / ".git").exists() or (ws / ".git" / "config").exists()
    assert (ws / "PROMPT.md").exists()
    # Should contain task-specific content
    prompt = (ws / "PROMPT.md").read_text("utf-8")
    assert "T-201" in prompt
    assert "TestProj" in prompt


@pytest.mark.asyncio
async def test_workspace_prepare_ignores_heavy_dirs(tmp_path):
    """Heavy directories like node_modules should be excluded to keep prepare fast."""
    (tmp_path / ".zeus" / "v3" / "config.json").parent.mkdir(parents=True)
    (tmp_path / ".zeus" / "v3" / "config.json").write_text(
        json.dumps({"project": {"name": "HeavyProj"}, "metrics": {"north_star": "n"}, "subagent": {"dispatcher": "mock"}}),
        encoding="utf-8",
    )
    (tmp_path / "src" / "main.py").parent.mkdir(parents=True)
    (tmp_path / "src" / "main.py").write_text("# main\n", encoding="utf-8")

    # Create heavy directories that should be ignored
    for heavy in ["node_modules", "__pycache__", ".pytest_cache", "venv"]:
        (tmp_path / heavy / "foo" / "bar").mkdir(parents=True)
        for i in range(50):
            (tmp_path / heavy / f"file{i}.txt").write_text("x" * 100, encoding="utf-8")

    wm = WorkspaceManager(tmp_path, version="v3")
    import time
    start = time.monotonic()
    ws = await wm.prepare({"id": "T-201", "title": "Test", "wave": 1, "depends_on": []})
    elapsed = time.monotonic() - start

    assert ws.exists()
    assert (ws / "src" / "main.py").exists()
    assert not (ws / "node_modules").exists()
    assert not (ws / "__pycache__").exists()
    assert not (ws / ".pytest_cache").exists()
    assert not (ws / "venv").exists()
    assert elapsed < 1.0, f"prepare took {elapsed:.2f}s, expected <1.0s"


# ---------------------------------------------------------------------------
# StateStore tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sqlite_store_task_lifecycle(sqlite_store):
    store = sqlite_store
    await store.upsert_task({
        "id": "T-301",
        "title": "Test task",
        "status": "pending",
        "passes": False,
        "wave": 1,
        "depends_on": [],
    })
    task = await store.get_task("T-301")
    assert task is not None
    assert task["status"] == "pending"

    await store.update_task_status("T-301", "running")
    task = await store.get_task("T-301")
    assert task["status"] == "running"

    await store.update_task_status("T-301", "completed", passes=True, commit_sha="abc123")
    task = await store.get_task("T-301")
    assert task["status"] == "completed"
    assert task["passes"] is True
    assert task["commit_sha"] == "abc123"

    tasks = await store.list_tasks(status="completed")
    assert len(tasks) == 1
    assert tasks[0]["id"] == "T-301"


@pytest.mark.asyncio
async def test_sqlite_store_quarantine(sqlite_store):
    store = sqlite_store
    await store.upsert_task({"id": "T-302", "status": "pending", "wave": 1, "depends_on": []})
    await store.quarantine_task("T-302", "simulated failure", workspace="/tmp/ws")
    assert await store.is_quarantined("T-302") is True

    qlist = await store.list_quarantine()
    assert len(qlist) == 1
    assert qlist[0]["reason"] == "simulated failure"

    await store.unquarantine_task("T-302")
    assert await store.is_quarantined("T-302") is False


@pytest.mark.asyncio
async def test_sqlite_store_meta_and_events(sqlite_store):
    store = sqlite_store
    await store.set_meta("current_wave", 3)
    assert await store.get_meta("current_wave") == 3

    eid = await store.log_event("task.started", task_id="T-303", agent_id="w-0", wave=1, payload={"x": 1})
    assert isinstance(eid, int)

    events = await store.query_events(task_id="T-303")
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
    await q.enqueue({"id": "T-401", "wave": 1})
    assert await q.size() == 1
    task = await q.dequeue()
    assert task["id"] == "T-401"
    await q.ack("T-401")


@pytest.mark.asyncio
async def test_memory_queue_nack_retry(memory_queue):
    q = memory_queue
    await q.enqueue({"id": "T-402", "wave": 1})
    task = await q.dequeue()
    assert task["id"] == "T-402"
    await q.nack("T-402", "oops")
    # Should be re-enqueued
    task2 = await q.dequeue()
    assert task2["id"] == "T-402"
    assert task2["retry_count"] == 1


@pytest.mark.asyncio
async def test_sqlite_queue_persistence(sqlite_queue):
    q = sqlite_queue
    await q.enqueue({"id": "T-403", "wave": 2})
    assert await q.size() == 1
    task = await q.dequeue()
    assert task["id"] == "T-403"
    await q.ack("T-403")
    assert await q.size() == 0


@pytest.mark.asyncio
async def test_sqlite_queue_dead_letter_after_retries(sqlite_queue):
    q = sqlite_queue
    await q.enqueue({"id": "T-404", "wave": 1})
    for _ in range(4):
        task = await q.dequeue()
        assert task["id"] == "T-404"
        await q.nack("T-404", "fail")
    # After 3 retries it should go to dead letter; queue should be empty
    assert await q.size() == 0


# ---------------------------------------------------------------------------
# Scheduler + WorkerPool integration
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_scheduler_enqueues_ready_tasks(sqlite_store, memory_queue):
    store = sqlite_store
    q = memory_queue
    await store.upsert_task({"id": "T-501", "status": "pending", "wave": 1, "depends_on": []})
    await store.upsert_task({"id": "T-502", "status": "pending", "wave": 1, "depends_on": ["T-501"]})

    scheduler = ZeusScheduler(store, q)
    enqueued_ids: set[str] = set()
    ready = await scheduler.tick(enqueued_ids)
    assert len(ready) == 1
    assert ready[0]["id"] == "T-501"
    assert await q.size() == 1


@pytest.mark.asyncio
async def test_scheduler_respects_quarantine(sqlite_store, memory_queue):
    store = sqlite_store
    q = memory_queue
    await store.upsert_task({"id": "T-503", "status": "pending", "wave": 1, "depends_on": []})
    await store.upsert_task({"id": "T-504", "status": "pending", "wave": 1, "depends_on": ["T-503"]})
    await store.quarantine_task("T-503", "fail")

    scheduler = ZeusScheduler(store, q)
    enqueued_ids: set[str] = set()
    ready = await scheduler.tick(enqueued_ids)
    assert len(ready) == 0  # T-503 quarantined, T-504 blocked


@pytest.mark.asyncio
async def test_scheduler_wave_filter_only_enqueues_matching_wave(sqlite_store, memory_queue):
    store = sqlite_store
    q = memory_queue
    await store.upsert_task({"id": "T-505", "status": "pending", "wave": 1, "depends_on": []})
    await store.upsert_task({"id": "T-506", "status": "pending", "wave": 2, "depends_on": []})
    await store.upsert_task({"id": "T-507", "status": "pending", "wave": 2, "depends_on": []})

    scheduler = ZeusScheduler(store, q)
    enqueued_ids: set[str] = set()
    ready = await scheduler.tick(enqueued_ids, wave_filter=2)
    assert len(ready) == 2
    assert {t["id"] for t in ready} == {"T-506", "T-507"}
    assert await q.size() == 2

    # T-505 should still be pending
    t505 = await store.get_task("T-505")
    assert t505["status"] == "pending"


@pytest.mark.asyncio
async def test_worker_executes_mock_dispatcher(sqlite_store, memory_queue, workspace_manager):
    store = sqlite_store
    q = memory_queue
    await store.upsert_task({"id": "T-505", "status": "pending", "wave": 1, "depends_on": []})
    await q.enqueue({"id": "T-505", "wave": 1})

    dispatcher = MockSubagentDispatcher()
    pool = WorkerPool(store, q, dispatcher, workspace_manager, max_workers=1)
    await pool.start()
    await asyncio.sleep(0.5)
    await pool.stop()

    task = await store.get_task("T-505")
    assert task["status"] == "completed"
    assert task["passes"] is True


@pytest.mark.asyncio
async def test_worker_reads_zeus_result_json(sqlite_store, memory_queue, workspace_manager):
    """Simulate a sub-agent that writes zeus-result.json before exiting."""
    store = sqlite_store
    q = memory_queue
    await store.upsert_task({"id": "T-506", "status": "pending", "wave": 1, "depends_on": []})
    await q.enqueue({"id": "T-506", "wave": 1})

    class FakeDispatcher:
        async def run(self, task, workspace, prompt, bus=None):
            # Sub-agent writes its own result
            result = {
                "status": "completed",
                "changed_files": ["src/foo.py"],
                "test_summary": {"passed": 5, "failed": 0, "skipped": 0},
                "commit_sha": "deadbeef",
                "artifacts": {},
            }
            (workspace / "zeus-result.json").write_text(json.dumps(result), encoding="utf-8")
            return {"status": "failed", "artifacts": {"error": "dispatcher says failed but result file says ok"}}

    pool = WorkerPool(store, q, FakeDispatcher(), workspace_manager, max_workers=1)
    await pool.start()
    await asyncio.sleep(0.5)
    await pool.stop()

    task = await store.get_task("T-506")
    assert task["status"] == "completed"
    assert task["passes"] is True
    assert task["commit_sha"] == "deadbeef"


@pytest.mark.asyncio
async def test_worker_retries_and_eventually_fails(sqlite_store, memory_queue, workspace_manager):
    """Dispatcher always fails and never writes zeus-result.json -> nack each time."""
    store = sqlite_store
    q = memory_queue
    await store.upsert_task({"id": "T-507", "status": "pending", "wave": 1, "depends_on": []})
    await q.enqueue({"id": "T-507", "wave": 1})

    class AlwaysFailDispatcher:
        async def run(self, task, workspace, prompt, bus=None):
            raise RuntimeError("always fails")

    pool = WorkerPool(store, q, AlwaysFailDispatcher(), workspace_manager, max_workers=1)
    await pool.start()
    await asyncio.sleep(2.0)  # enough time for a few retries
    await pool.stop()

    # After retries the task should be failed in DB (queue may have dead-lettered it)
    task = await store.get_task("T-507")
    assert task["status"] == "failed"


@pytest.mark.asyncio
async def test_end_to_end_scheduler_worker_pool(sqlite_store, memory_queue, workspace_manager):
    store = sqlite_store
    q = memory_queue
    # Seed tasks
    await store.upsert_task({"id": "T-601", "status": "pending", "wave": 1, "depends_on": []})
    await store.upsert_task({"id": "T-602", "status": "pending", "wave": 1, "depends_on": []})
    await store.upsert_task({"id": "T-603", "status": "pending", "wave": 2, "depends_on": ["T-601"]})

    scheduler = ZeusScheduler(store, q)
    dispatcher = MockSubagentDispatcher()
    pool = WorkerPool(store, q, dispatcher, workspace_manager, max_workers=2)

    await pool.start()

    # Tick 1: T-601 and T-602 should be enqueued
    enqueued_ids: set[str] = set()
    ready1 = await scheduler.tick(enqueued_ids)
    assert {t["id"] for t in ready1} == {"T-601", "T-602"}

    # Poll until T-601 completes (workspace copy may take >0.5s on Windows)
    for _ in range(50):
        await asyncio.sleep(0.1)
        t601 = await store.get_task("T-601")
        if t601["status"] == "completed":
            break

    # Tick 2: T-601 completed, T-603 now ready
    ready2 = await scheduler.tick(enqueued_ids)
    assert {t["id"] for t in ready2} == {"T-603"}

    # Poll until all tasks complete
    for _ in range(50):
        await asyncio.sleep(0.1)
        pending = len(await store.list_tasks(status="pending"))
        running = len(await store.list_tasks(status="running"))
        if pending == 0 and running == 0:
            break
    await pool.stop()

    for tid in ("T-601", "T-602", "T-603"):
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


@pytest.mark.asyncio
async def test_worker_heartbeat_scans_progress_jsonl(sqlite_store, memory_queue, workspace_manager):
    """Worker heartbeat loop should scan progress.jsonl, deduplicate, and log events."""
    store = sqlite_store
    q = memory_queue
    await store.upsert_task({"id": "T-PROG", "status": "pending", "wave": 1, "depends_on": []})
    await q.enqueue({"id": "T-PROG", "wave": 1})

    real_sleep = asyncio.sleep

    class SlowDispatcher:
        async def run(self, task, workspace, prompt, bus=None):
            progress_path = workspace / "progress.jsonl"
            # Write first line
            progress_path.write_text(
                json.dumps({"step": "planning", "message": "m1"}) + "\n", encoding="utf-8"
            )
            await real_sleep(0.5)  # use real sleep so heartbeat has time to run
            # Append second line
            with open(progress_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"step": "writing", "message": "m2"}) + "\n")
            await real_sleep(0.5)
            # Write result
            result = {
                "status": "completed",
                "changed_files": [],
                "test_summary": {"passed": 1, "failed": 0, "skipped": 0},
                "commit_sha": "prog-test",
                "artifacts": {},
            }
            (workspace / "zeus-result.json").write_text(json.dumps(result), encoding="utf-8")
            return result

    async def fast_sleep(delay):
        return await real_sleep(0.01)

    import core.worker as cw
    pool = WorkerPool(store, q, SlowDispatcher(), workspace_manager, max_workers=1)
    with patch.object(cw.asyncio, "sleep", fast_sleep):
        await pool.start()
        for _ in range(300):
            await real_sleep(0.05)
            t = await store.get_task("T-PROG")
            if t["status"] == "completed":
                break
        else:
            print("Task did not complete in time")
        await pool.stop()

    task = await store.get_task("T-PROG")
    assert task["status"] == "completed"
    events = await store.query_events(task_id="T-PROG", event_type="task.progress")
    assert len(events) == 2
    # query_events returns descending order by id
    steps = [e["payload"]["step"] for e in reversed(events)]
    assert steps == ["planning", "writing"]
    assert all(e["payload"]["source"] == "file" for e in events)
