"""
Integration tests for PostgresStateStore.

Requires Docker to run a temporary PostgreSQL container.
Skipped automatically if docker is unavailable.
"""
from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine

from api.metrics import MetricsCollector
from db.models import Base
from store.postgres_store import PostgresStateStore


DOCKER_IMAGE = "postgres:16-alpine"
POSTGRES_PASSWORD = "testpass"
POSTGRES_USER = "postgres"
POSTGRES_DB = "postgres"
CONTAINER_NAME_PREFIX = "zeus-open-test-pg-"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _docker_available() -> bool:
    try:
        subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except Exception:
        return False


def _wait_for_pg(host: str, port: int, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"PostgreSQL did not become ready at {host}:{port}")


def _pg_ready(container_name: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["docker", "exec", container_name, "pg_isready", "-U", POSTGRES_USER],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError("PostgreSQL pg_isready timed out")


@pytest.fixture(scope="module")
def pg_container():
    if not _docker_available():
        pytest.skip("Docker not available")

    port = _find_free_port()
    container_name = f"{CONTAINER_NAME_PREFIX}{port}"

    run_cmd = [
        "docker", "run", "--rm", "-d",
        "-e", f"POSTGRES_PASSWORD={POSTGRES_PASSWORD}",
        "-e", f"POSTGRES_USER={POSTGRES_USER}",
        "-e", f"POSTGRES_DB={POSTGRES_DB}",
        "-p", f"{port}:5432",
        "--name", container_name,
        DOCKER_IMAGE,
    ]
    subprocess.run(run_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    try:
        _wait_for_pg("127.0.0.1", port)
        _pg_ready(container_name)
        database_url = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@127.0.0.1:{port}/{POSTGRES_DB}"
        yield {"host": "127.0.0.1", "port": port, "database_url": database_url, "container_name": container_name}
    finally:
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


@pytest_asyncio.fixture
async def pg_store(pg_container):
    database_url = pg_container["database_url"]
    # Create tables
    engine = create_async_engine(database_url, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

    store = PostgresStateStore(database_url)
    yield store
    await store.close()


# -----------------------------------------------------------------------------
# Task lifecycle
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_postgres_store_task_lifecycle(pg_store):
    store = pg_store
    await store.upsert_task({
        "id": "T-PG-301",
        "title": "PG Test task",
        "status": "pending",
        "passes": False,
        "wave": 1,
        "depends_on": [],
    })
    task = await store.get_task("T-PG-301")
    assert task is not None
    assert task["status"] == "pending"
    assert task["title"] == "PG Test task"

    await store.update_task_status("T-PG-301", "running")
    task = await store.get_task("T-PG-301")
    assert task["status"] == "running"

    await store.update_task_status("T-PG-301", "completed", passes=True, commit_sha="abc123")
    task = await store.get_task("T-PG-301")
    assert task["status"] == "completed"
    assert task["passes"] is True
    assert task["commit_sha"] == "abc123"

    tasks = await store.list_tasks(status="completed")
    assert len(tasks) == 1
    assert tasks[0]["id"] == "T-PG-301"

    await store.delete_task("T-PG-301")
    assert await store.get_task("T-PG-301") is None


# -----------------------------------------------------------------------------
# Quarantine
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_postgres_store_quarantine(pg_store):
    store = pg_store
    await store.upsert_task({"id": "T-PG-302", "status": "pending", "wave": 1, "depends_on": []})
    await store.quarantine_task("T-PG-302", "simulated failure", workspace="/tmp/ws")
    assert await store.is_quarantined("T-PG-302") is True

    qlist = await store.list_quarantine()
    assert len(qlist) == 1
    assert qlist[0]["reason"] == "simulated failure"

    await store.unquarantine_task("T-PG-302")
    assert await store.is_quarantined("T-PG-302") is False


# -----------------------------------------------------------------------------
# Meta + Events
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_postgres_store_meta_and_events(pg_store):
    store = pg_store
    await store.set_meta("current_wave", 3)
    assert await store.get_meta("current_wave") == 3
    assert await store.get_meta("missing_key", "default") == "default"

    await store.delete_meta("current_wave")
    assert await store.get_meta("current_wave") is None

    eid = await store.log_event("task.started", task_id="T-PG-303", agent_id="w-0", wave=1, payload={"x": 1})
    assert isinstance(eid, int)

    events = await store.query_events(task_id="T-PG-303")
    assert len(events) == 1
    assert events[0]["event_type"] == "task.started"
    assert events[0]["payload"]["x"] == 1


# -----------------------------------------------------------------------------
# Phase + Milestone
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_postgres_store_phase_milestone(pg_store):
    store = pg_store
    await store.upsert_task({"id": "T-PG-401", "title": "Milestone Task", "status": "completed", "wave": 1, "milestone_id": "M-PG-1", "depends_on": []})

    await store.upsert_phase({
        "id": "P-PG-1",
        "title": "Phase 1",
        "title_en": "Phase 1",
        "title_zh": "阶段 1",
        "status": "completed",
        "progress_percent": 100,
        "milestone_ids": ["M-PG-1"],
    })
    await store.upsert_milestone({
        "id": "M-PG-1",
        "title": "Milestone 1",
        "task_ids": ["T-PG-401"],
        "status": "completed",
        "progress_percent": 100,
    })

    p = await store.get_phase("P-PG-1")
    assert p["title_zh"] == "阶段 1"
    assert p["milestone_ids"] == ["M-PG-1"]
    # enriched from tasks
    assert p["progress_percent"] == 100
    assert p["status"] == "completed"

    m = await store.get_milestone("M-PG-1")
    assert m["title"] == "Milestone 1"
    assert m["progress_percent"] == 100

    phases = await store.list_phases()
    assert any(x["id"] == "P-PG-1" for x in phases)

    milestones = await store.list_milestones()
    assert any(x["id"] == "M-PG-1" for x in milestones)

    tasks = await store.list_tasks_by_milestone("M-PG-1")
    assert len(tasks) == 1
    assert tasks[0]["id"] == "T-PG-401"

    await store.delete_milestone("M-PG-1")
    assert await store.get_milestone("M-PG-1") is None

    await store.delete_phase("P-PG-1")
    assert await store.get_phase("P-PG-1") is None


# -----------------------------------------------------------------------------
# Mailbox
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_postgres_store_mailbox(pg_store):
    store = pg_store
    mid = await store.send_message({
        "task_id": "T-PG-501",
        "from_agent": "alice",
        "to_agent": "bob",
        "message": "hello",
        "read": False,
    })
    assert isinstance(mid, int)

    unread = await store.list_messages(to_agent="bob", read=False)
    assert len(unread) == 1
    assert unread[0]["message"] == "hello"

    await store.mark_message_read(mid, read=True)
    read_msgs = await store.list_messages(to_agent="bob", read=True)
    assert len(read_msgs) == 1


# -----------------------------------------------------------------------------
# Metrics via MetricsCollector
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_postgres_store_metrics(pg_store):
    store = pg_store
    await store.upsert_task({"id": "T-PG-601", "status": "completed", "passes": True, "wave": 1, "depends_on": []})
    await store.upsert_task({"id": "T-PG-602", "status": "failed", "passes": False, "wave": 1, "depends_on": ["T-PG-601"]})
    await store.upsert_task({"id": "T-PG-603", "status": "pending", "passes": False, "wave": 1, "depends_on": ["T-PG-602"]})
    await store.quarantine_task("T-PG-602", "boom")

    await store.log_event("task.started", task_id="T-PG-601", ts=datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc))
    await store.log_event("task.completed", task_id="T-PG-601", ts=datetime(2026, 1, 1, 10, 0, 5, tzinfo=timezone.utc))

    collector = MetricsCollector(store)
    summary = await collector.summary()
    assert summary["total_tasks"] == 3
    assert summary["completed"] == 1
    assert summary["failed"] == 1
    assert summary["pending"] == 1
    assert summary["quarantined"] == 1

    tm = await collector.task_metrics()
    assert len(tm) == 3
    task_601 = next(m for m in tm if m["task_id"] == "T-PG-601")
    assert task_601["duration_ms"] == 5000

    bottlenecks = await collector.bottleneck_tasks(top_n=5)
    assert len(bottlenecks) == 1
    assert bottlenecks[0]["task_id"] == "T-PG-601"

    chains = await collector.blocked_chains()
    assert len(chains) == 1
    assert chains[0]["blocked_by"] == "T-PG-602"
    assert "T-PG-603" in chains[0]["blocked_task_ids"]


# -----------------------------------------------------------------------------
# Isolation: concurrent tasks do not interfere
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_postgres_store_isolation(pg_store):
    store = pg_store

    async def worker(prefix: str, count: int):
        for i in range(count):
            tid = f"{prefix}-{i}"
            await store.upsert_task({"id": tid, "status": "pending", "wave": 1, "depends_on": []})
            await store.update_task_status(tid, "completed", passes=True)

    await asyncio.gather(worker("A", 10), worker("B", 10))

    a_tasks = [t for t in await store.list_tasks() if t["id"].startswith("A-")]
    b_tasks = [t for t in await store.list_tasks() if t["id"].startswith("B-")]
    assert len(a_tasks) == 10
    assert len(b_tasks) == 10
    assert all(t["status"] == "completed" for t in a_tasks)
    assert all(t["status"] == "completed" for t in b_tasks)
