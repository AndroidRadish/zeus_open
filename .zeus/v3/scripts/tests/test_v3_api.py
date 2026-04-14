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
    # Vite-built SPA: check for root mount point and asset references
    assert '<div id="app"></div>' in resp.text or "ZeusOpen v3 Dashboard" in resp.text


@pytest.mark.asyncio
async def test_root_redirects_info(api_client):
    client, _ = api_client
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "dashboard" in data
    assert data["dashboard"] == "/dashboard"


# ---------------------------------------------------------------------
# Task action endpoints
# ---------------------------------------------------------------------

def _capture_emit(bus):
    """Monkey-patch bus.emit to record calls."""
    emitted = []
    original = bus.emit

    def _emit(event_type, payload=None):
        emitted.append((event_type, payload or {}))
        original(event_type, payload)

    bus.emit = _emit
    return emitted


@pytest.mark.asyncio
async def test_task_retry(api_client, sqlite_store):
    client, bus = api_client
    await sqlite_store.upsert_task({"id": "T-ACT-1", "status": "failed", "wave": 1, "passes": False, "worker_id": "w-1"})
    await sqlite_store.quarantine_task("T-ACT-1", "err")

    emitted = _capture_emit(bus)
    resp = await client.post("/tasks/T-ACT-1/retry")
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "task_id": "T-ACT-1"}

    task = await sqlite_store.get_task("T-ACT-1")
    assert task["status"] == "pending"
    assert task["passes"] is False
    assert task["worker_id"] is None
    assert await sqlite_store.is_quarantined("T-ACT-1") is False

    events = await sqlite_store.query_events(task_id="T-ACT-1", event_type="task.retried")
    assert len(events) == 1
    assert any(e == "task.retried" and p.get("task_id") == "T-ACT-1" for e, p in emitted)


@pytest.mark.asyncio
async def test_task_cancel(api_client, sqlite_store):
    client, bus = api_client
    await sqlite_store.upsert_task({"id": "T-ACT-2", "status": "pending", "wave": 1})

    emitted = _capture_emit(bus)
    resp = await client.post("/tasks/T-ACT-2/cancel")
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "task_id": "T-ACT-2"}

    task = await sqlite_store.get_task("T-ACT-2")
    assert task["status"] == "cancelled"

    events = await sqlite_store.query_events(task_id="T-ACT-2", event_type="task.cancelled")
    assert len(events) == 1
    assert any(e == "task.cancelled" and p.get("task_id") == "T-ACT-2" for e, p in emitted)


@pytest.mark.asyncio
async def test_task_pause(api_client, sqlite_store):
    client, bus = api_client
    await sqlite_store.upsert_task({"id": "T-ACT-3", "status": "pending", "wave": 1})

    emitted = _capture_emit(bus)
    resp = await client.post("/tasks/T-ACT-3/pause")
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "task_id": "T-ACT-3"}

    task = await sqlite_store.get_task("T-ACT-3")
    assert task["status"] == "paused"

    events = await sqlite_store.query_events(task_id="T-ACT-3", event_type="task.paused")
    assert len(events) == 1
    assert any(e == "task.paused" and p.get("task_id") == "T-ACT-3" for e, p in emitted)


@pytest.mark.asyncio
async def test_task_resume(api_client, sqlite_store):
    client, bus = api_client
    await sqlite_store.upsert_task({"id": "T-ACT-4", "status": "paused", "wave": 1})

    emitted = _capture_emit(bus)
    resp = await client.post("/tasks/T-ACT-4/resume")
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "task_id": "T-ACT-4"}

    task = await sqlite_store.get_task("T-ACT-4")
    assert task["status"] == "pending"

    events = await sqlite_store.query_events(task_id="T-ACT-4", event_type="task.resumed")
    assert len(events) == 1
    assert any(e == "task.resumed" and p.get("task_id") == "T-ACT-4" for e, p in emitted)


@pytest.mark.asyncio
async def test_task_quarantine(api_client, sqlite_store):
    client, bus = api_client
    await sqlite_store.upsert_task({"id": "T-ACT-5", "status": "pending", "wave": 1})

    emitted = _capture_emit(bus)
    resp = await client.post("/tasks/T-ACT-5/quarantine")
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "task_id": "T-ACT-5"}

    task = await sqlite_store.get_task("T-ACT-5")
    assert task["status"] == "failed"
    assert task["passes"] is False
    assert await sqlite_store.is_quarantined("T-ACT-5") is True

    events = await sqlite_store.query_events(task_id="T-ACT-5", event_type="task.quarantined")
    assert len(events) == 1
    assert any(e == "task.quarantined" and p.get("task_id") == "T-ACT-5" for e, p in emitted)


@pytest.mark.asyncio
async def test_task_unquarantine(api_client, sqlite_store):
    client, bus = api_client
    await sqlite_store.upsert_task({"id": "T-ACT-6", "status": "failed", "wave": 1, "passes": False})
    await sqlite_store.quarantine_task("T-ACT-6", "err")

    emitted = _capture_emit(bus)
    resp = await client.post("/tasks/T-ACT-6/unquarantine")
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "task_id": "T-ACT-6"}

    task = await sqlite_store.get_task("T-ACT-6")
    assert task["status"] == "pending"
    assert task["passes"] is False
    assert await sqlite_store.is_quarantined("T-ACT-6") is False

    events = await sqlite_store.query_events(task_id="T-ACT-6", event_type="task.unquarantined")
    assert len(events) == 1
    assert any(e == "task.unquarantined" and p.get("task_id") == "T-ACT-6" for e, p in emitted)


@pytest.mark.asyncio
async def test_task_progress_http(api_client, sqlite_store):
    client, bus = api_client
    await sqlite_store.upsert_task({"id": "T-ACT-7", "status": "running", "wave": 1})

    emitted = _capture_emit(bus)
    resp = await client.post("/tasks/T-ACT-7/progress", json={"step": "writing", "message": "hello"})
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "task_id": "T-ACT-7"}

    events = await sqlite_store.query_events(task_id="T-ACT-7", event_type="task.progress")
    assert len(events) == 1
    assert events[0]["payload"]["source"] == "http"
    assert events[0]["payload"]["step"] == "writing"
    assert events[0]["payload"]["message"] == "hello"
    assert any(e == "task.progress" and p.get("task_id") == "T-ACT-7" for e, p in emitted)


@pytest.mark.asyncio
async def test_task_progress_http_404(api_client):
    client, _ = api_client
    resp = await client.post("/tasks/NOT-FOUND/progress", json={"step": "test"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_task_action_404(api_client):
    client, _ = api_client
    for action in ("retry", "cancel", "pause", "resume", "quarantine", "unquarantine"):
        resp = await client.post(f"/tasks/NOT-FOUND/{action}")
        assert resp.status_code == 404, f"Action {action} should 404"


@pytest.mark.asyncio
async def test_phase_crud(api_client, sqlite_store):
    client, _ = api_client

    # create
    resp = await client.post("/phases", json={"id": "P-001", "title": "Foundation", "status": "pending", "progress_percent": 0})
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # list
    resp = await client.get("/phases")
    assert resp.status_code == 200
    phases = resp.json()
    assert any(p["id"] == "P-001" for p in phases)

    # get detail (with milestones hydrated)
    resp = await client.get("/phases/P-001")
    assert resp.status_code == 200
    phase = resp.json()
    assert phase["title"] == "Foundation"
    assert "milestones" in phase

    # update
    resp = await client.put("/phases/P-001", json={"title": "Foundation v2", "progress_percent": 50})
    assert resp.status_code == 200
    phase = await sqlite_store.get_phase("P-001")
    assert phase["title"] == "Foundation v2"
    assert phase["progress_percent"] == 50

    # delete
    resp = await client.delete("/phases/P-001")
    assert resp.status_code == 200
    assert await sqlite_store.get_phase("P-001") is None


@pytest.mark.asyncio
async def test_milestone_crud(api_client, sqlite_store):
    client, _ = api_client

    # create milestone
    resp = await client.post("/milestones", json={"id": "M-001", "title": "Setup", "status": "pending", "task_ids": ["T-1"]})
    assert resp.status_code == 200

    # list
    resp = await client.get("/milestones")
    assert resp.status_code == 200
    milestones = resp.json()
    assert any(m["id"] == "M-001" for m in milestones)

    # insert task with milestone_id
    await sqlite_store.upsert_task({"id": "T-1", "status": "pending", "wave": 1, "milestone_id": "M-001"})

    # get detail with tasks
    resp = await client.get("/milestones/M-001")
    assert resp.status_code == 200
    ms = resp.json()
    assert ms["title"] == "Setup"
    assert any(t["id"] == "T-1" for t in ms["tasks"])

    # update
    resp = await client.put("/milestones/M-001", json={"title": "Setup v2"})
    assert resp.status_code == 200
    ms = await sqlite_store.get_milestone("M-001")
    assert ms["title"] == "Setup v2"

    # delete
    resp = await client.delete("/milestones/M-001")
    assert resp.status_code == 200
    assert await sqlite_store.get_milestone("M-001") is None


@pytest.mark.asyncio
async def test_mailbox(api_client, sqlite_store):
    client, bus = api_client

    # send message
    resp = await client.post("/mailbox", json={"from_agent": "agent-a", "to_agent": "agent-b", "message": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    msg_id = data["id"]

    # list all
    resp = await client.get("/mailbox")
    assert resp.status_code == 200
    msgs = resp.json()
    assert any(m["id"] == msg_id for m in msgs)

    # filter by to_agent
    resp = await client.get("/mailbox?to_agent=agent-b")
    assert resp.status_code == 200
    msgs = resp.json()
    assert all(m["to_agent"] == "agent-b" for m in msgs)

    # filter unread
    resp = await client.get("/mailbox?read=false")
    assert resp.status_code == 200
    msgs = resp.json()
    assert any(m["id"] == msg_id for m in msgs)

    # mark read
    resp = await client.post(f"/mailbox/{msg_id}/read")
    assert resp.status_code == 200

    # verify read
    msgs = await sqlite_store.list_messages(read=True)
    assert any(m["id"] == msg_id for m in msgs)
