"""
API + SSE integration tests for ZeusOpen v3.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import AsyncClient, ASGITransport

from api.bus import EventBus
from api.server import create_app
from db.engine import make_async_engine
from db.models import Base
from store.sqlite_store import SQLiteStateStore


@pytest_asyncio.fixture
async def sqlite_store(tmp_path):
    db_path = tmp_path / "api.sqlite"
    store = SQLiteStateStore(f"sqlite+aiosqlite:///{db_path}")
    engine = make_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    yield store
    await store.close()


@pytest_asyncio.fixture
async def api_client(sqlite_store):
    bus = EventBus()
    app = create_app(sqlite_store, bus)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, bus


@pytest.mark.asyncio
async def test_health(api_client):
    client, _ = api_client
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["store"]["ok"] is True


@pytest.mark.asyncio
async def test_tasks_crud(api_client, sqlite_store):
    client, _ = api_client
    await sqlite_store.upsert_task({"id": "T-API-1", "status": "pending", "wave": 1, "depends_on": []})
    await sqlite_store.upsert_task({"id": "T-API-2", "status": "completed", "wave": 1, "depends_on": []})

    resp = await client.get("/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    resp = await client.get("/tasks?status=pending")
    assert len(resp.json()) == 1

    resp = await client.get("/tasks/T-API-1")
    assert resp.status_code == 200
    assert resp.json()["id"] == "T-API-1"

    resp = await client.get("/tasks/NOT-FOUND")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_events_query(api_client, sqlite_store):
    client, _ = api_client
    await sqlite_store.log_event("task.started", task_id="T-API-1", agent_id="w-0", payload={"x": 1})
    await sqlite_store.log_event("task.completed", task_id="T-API-1", agent_id="w-0", payload={"x": 2})

    resp = await client.get("/events?task_id=T-API-1&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # Descending order by id
    assert data[0]["event_type"] == "task.completed"


@pytest.mark.asyncio
async def test_metrics_summary(api_client, sqlite_store):
    client, _ = api_client
    await sqlite_store.upsert_task({"id": "T-M1", "status": "completed", "wave": 1, "passes": True})
    await sqlite_store.upsert_task({"id": "T-M2", "status": "failed", "wave": 1, "passes": False})
    await sqlite_store.upsert_task({"id": "T-M3", "status": "pending", "wave": 1})
    await sqlite_store.quarantine_task("T-M2", "err")

    resp = await client.get("/metrics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_tasks"] == 3
    assert data["completed"] == 1
    assert data["failed"] == 1
    assert data["pending"] == 1
    assert data["quarantined"] == 1
    assert data["pass_rate"] == 0.5


@pytest.mark.asyncio
async def test_sse_endpoint_registered(api_client):
    client, _ = api_client
    app = client._transport.app
    paths = [getattr(r, "path", None) for r in app.routes]
    assert "/events/stream" in paths
    for r in app.routes:
        if getattr(r, "path", None) == "/events/stream":
            assert "GET" in getattr(r, "methods", set())


@pytest.mark.asyncio
async def test_metrics_tasks(api_client, sqlite_store):
    client, _ = api_client
    await sqlite_store.upsert_task({"id": "T-MT-1", "status": "pending", "wave": 1})
    # Simulate events with explicit ISO timestamps
    await sqlite_store.log_event("task.started", task_id="T-MT-1", agent_id="w-0", payload={})
    await sqlite_store.log_event("task.completed", task_id="T-MT-1", agent_id="w-0", payload={})

    resp = await client.get("/metrics/tasks")
    assert resp.status_code == 200
    data = resp.json()
    mt1 = next((m for m in data if m["task_id"] == "T-MT-1"), None)
    assert mt1 is not None
    assert mt1["status"] == "pending"  # store state hasn't been updated in this test
    assert mt1["duration_ms"] is not None


@pytest.mark.asyncio
async def test_metrics_bottleneck(api_client, sqlite_store):
    client, _ = api_client
    from datetime import datetime, timezone, timedelta
    base = datetime(2026, 4, 13, 10, 0, 0, tzinfo=timezone.utc)
    for i in range(3):
        tid = f"T-BOT-{i}"
        await sqlite_store.upsert_task({"id": tid, "status": "completed", "wave": 1})
        await sqlite_store.log_event("task.started", task_id=tid, agent_id="w-0", payload={}, ts=base)
    # Different finish times; durations are (completed - started)
    durations = [1000, 3000, 5000]  # ms
    for i, dur_ms in enumerate(durations):
        tid = f"T-BOT-{i}"
        finished = base + timedelta(milliseconds=dur_ms)
        await sqlite_store.log_event("task.completed" if i != 1 else "task.failed", task_id=tid, agent_id="w-0", payload={}, ts=finished)

    resp = await client.get("/metrics/bottleneck?top_n=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) <= 2
    # Longest should be T-BOT-2 (5s)
    assert data[0]["task_id"] == "T-BOT-2"
    assert data[0]["duration_ms"] == 5000


@pytest.mark.asyncio
async def test_metrics_blocked(api_client, sqlite_store):
    client, _ = api_client
    # T-BLK-1 fails, blocking T-BLK-2 and T-BLK-3
    await sqlite_store.upsert_task({"id": "T-BLK-1", "status": "failed", "wave": 1, "depends_on": []})
    await sqlite_store.upsert_task({"id": "T-BLK-2", "status": "pending", "wave": 2, "depends_on": ["T-BLK-1"]})
    await sqlite_store.upsert_task({"id": "T-BLK-3", "status": "pending", "wave": 2, "depends_on": ["T-BLK-2"]})

    resp = await client.get("/metrics/blocked")
    assert resp.status_code == 200
    data = resp.json()
    chain = next((c for c in data if c["blocked_by"] == "T-BLK-1"), None)
    assert chain is not None
    assert chain["blocked_task_count"] == 2
    assert "T-BLK-2" in chain["blocked_task_ids"]
    assert "T-BLK-3" in chain["blocked_task_ids"]


@pytest.mark.asyncio
async def test_event_bus_subscribe():
    bus = EventBus()

    async def emitter():
        await asyncio.sleep(0.05)
        bus.emit("task.started", {"task_id": "T-BUS"})
        await asyncio.sleep(0.05)
        bus.emit("task.completed", {"task_id": "T-BUS"})

    task = asyncio.create_task(emitter())

    chunks = []
    try:
        async for chunk in bus.subscribe():
            chunks.append(chunk)
            if "task.completed" in chunk:
                break
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert any("task.started" in c for c in chunks)
    assert any("task.completed" in c for c in chunks)


@pytest.mark.asyncio
async def test_dashboard_serves_index(api_client):
    client, _ = api_client
    resp = await client.get("/dashboard/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "ZeusOpen v3 Dashboard" in resp.text


@pytest.mark.asyncio
async def test_root_redirects_info(api_client):
    client, _ = api_client
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "dashboard" in data
    assert data["dashboard"] == "/dashboard"
