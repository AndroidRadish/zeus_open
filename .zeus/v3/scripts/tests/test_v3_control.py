"""
Control plane endpoint tests for ZeusOpen v3.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import AsyncClient, ASGITransport

from api.bus import EventBus
from api.control_plane import ControlPlane
from api.server import create_app
from db.engine import make_async_engine
from db.models import Base
from store.sqlite_store import SQLiteStateStore


class FakePopen:
    """Mock subprocess.Popen for scheduler/worker tests."""

    _pid_counter = 1000

    def __init__(self, cmd):
        self.cmd = cmd
        self.pid = FakePopen._pid_counter
        FakePopen._pid_counter += 1
        self._alive = True

    def poll(self):
        return None if self._alive else 0

    def terminate(self):
        self._alive = False

    def kill(self):
        self._alive = False

    def wait(self, timeout=None):
        self._alive = False


@pytest_asyncio.fixture
async def sqlite_store(tmp_path):
    db_path = tmp_path / "control.sqlite"
    store = SQLiteStateStore(f"sqlite+aiosqlite:///{db_path}")
    engine = make_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    yield store
    await store.close()


@pytest_asyncio.fixture
async def control_api_client(sqlite_store, tmp_path, monkeypatch):
    bus = EventBus()
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".zeus" / "v3").mkdir(parents=True)
    (project_root / ".zeus" / "v3" / "task.json").write_text(
        json.dumps({"version": "v3", "tasks": [], "quarantine": [], "meta": {}}),
        encoding="utf-8",
    )
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'control.sqlite'}"
    cp = ControlPlane(sqlite_store, bus, project_root, database_url)

    # Mock subprocess.Popen so we don't spawn real long-running processes
    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    app = create_app(sqlite_store, bus, cp)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, cp, sqlite_store


@pytest.mark.asyncio
async def test_control_status_empty(control_api_client):
    client, cp, _ = control_api_client
    resp = await client.get("/control/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scheduler"]["running"] is False
    assert data["scheduler"]["pid"] is None
    assert data["workers"]["count"] == 0
    assert data["workers"]["pids"] == []
    assert data["queue_size"] == 0
    assert data["last_import_at"] is None


@pytest.mark.asyncio
async def test_control_scheduler_start_stop(control_api_client):
    client, cp, _ = control_api_client

    resp = await client.post("/control/scheduler/start")
    assert resp.status_code == 200
    start_data = resp.json()
    assert start_data["success"] is True
    assert isinstance(start_data["pid"], int)

    # Double-start should conflict
    resp = await client.post("/control/scheduler/start")
    assert resp.status_code == 409

    resp = await client.post("/control/scheduler/stop")
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Verify status reflects stopped state
    resp = await client.get("/control/status")
    assert resp.json()["scheduler"]["running"] is False


@pytest.mark.asyncio
async def test_control_workers_scale_stop(control_api_client):
    client, cp, _ = control_api_client

    resp = await client.post("/control/workers/scale", json={"count": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["pids"]) == 2

    resp = await client.get("/control/status")
    status = resp.json()
    assert status["workers"]["count"] == 2
    assert len(status["workers"]["pids"]) == 2

    resp = await client.post("/control/workers/stop")
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    resp = await client.get("/control/status")
    assert resp.json()["workers"]["count"] == 0


@pytest.mark.asyncio
async def test_control_scheduler_tick(control_api_client, sqlite_store):
    client, cp, _ = control_api_client
    await sqlite_store.upsert_task({"id": "T-TICK", "status": "pending", "wave": 1, "depends_on": []})

    resp = await client.post("/control/scheduler/tick")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "result" in data
    assert data["result"]["enqueued"] == 1
    assert "T-TICK" in data["result"]["task_ids"]


@pytest.mark.asyncio
async def test_control_import(control_api_client, sqlite_store):
    client, cp, _ = control_api_client
    resp = await client.post("/control/import")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["result"]["imported_tasks"] == 0

    last_import = await sqlite_store.get_meta("last_import_at")
    assert last_import is not None


@pytest.mark.asyncio
async def test_control_global_run(control_api_client, sqlite_store):
    client, cp, _ = control_api_client
    resp = await client.post("/control/global/run")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "scheduler_pid" in data["result"]
    assert len(data["result"]["worker_pids"]) == 3

    last_import = await sqlite_store.get_meta("last_import_at")
    assert last_import is not None


@pytest.mark.asyncio
async def test_control_plane_disabled_returns_503(sqlite_store):
    bus = EventBus()
    app = create_app(sqlite_store, bus, control_plane=None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/control/status")
        assert resp.status_code == 503

        resp = await client.post("/control/scheduler/start")
        assert resp.status_code == 503

        resp = await client.post("/control/scheduler/stop")
        assert resp.status_code == 503

        resp = await client.post("/control/scheduler/tick")
        assert resp.status_code == 503

        resp = await client.post("/control/workers/scale", json={"count": 1})
        assert resp.status_code == 503

        resp = await client.post("/control/workers/stop")
        assert resp.status_code == 503

        resp = await client.post("/control/import")
        assert resp.status_code == 503

        resp = await client.post("/control/global/run")
        assert resp.status_code == 503
