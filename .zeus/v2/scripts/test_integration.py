"""
Integration tests for ZeusOpen v2.

- End-to-end 2-wave execution via ZeusOrchestrator
- API smoke tests against a live uvicorn server
"""

from __future__ import annotations

import asyncio
import json
import shutil
import socket
import threading
import time
from pathlib import Path

import pytest
import requests
import uvicorn

from agent_bus import AgentBus
from store import LocalStore
from zeus_orchestrator import ZeusOrchestrator

import zeus_server as zs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _write_minimal_project(root: Path) -> None:
    """Create a minimal zeus-open v2 tree under *root*."""
    zeus_dir = root / ".zeus" / "v2"
    zeus_dir.mkdir(parents=True, exist_ok=True)

    task_data = {
        "meta": {
            "current_wave": 1,
            "wave_approval_required": True,
            "max_parallel_agents": 2,
        },
        "tasks": [
            {
                "id": "T-001",
                "title": "Task 1 wave 1",
                "passes": False,
                "depends_on": [],
                "wave": 1,
                "type": "feat",
            },
            {
                "id": "T-002",
                "title": "Task 2 wave 1",
                "passes": False,
                "depends_on": [],
                "wave": 1,
                "type": "feat",
            },
            {
                "id": "T-003",
                "title": "Task 3 wave 2",
                "passes": False,
                "depends_on": ["T-001"],
                "wave": 2,
                "type": "feat",
            },
        ],
    }
    (zeus_dir / "task.json").write_text(json.dumps(task_data), encoding="utf-8")

    config_data = {
        "project": {"name": "Integration Test Project"},
        "metrics": {"north_star": "integration-coverage"},
    }
    (zeus_dir / "config.json").write_text(json.dumps(config_data), encoding="utf-8")

    src_dir = root / "src"
    src_dir.mkdir(exist_ok=True)
    (src_dir / "main.py").write_text("# dummy source\n", encoding="utf-8")


def _free_port() -> int:
    """Return an ephemeral TCP port on 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# 1. End-to-end 2-wave execution
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_end_to_end_two_wave_execution(tmp_path: Path) -> None:
    """Run wave 1 and wave 2 through the orchestrator and verify artifacts."""
    _write_minimal_project(tmp_path)

    orch = ZeusOrchestrator(version="v2", project_root=str(tmp_path), max_parallel=2)

    # --- Wave 1 -----------------------------------------------------------
    summary1 = await orch.await_wave_completion(1)
    assert summary1["wave"] == 1
    assert summary1["total"] == 2
    assert summary1["dispatched"] == 2
    assert summary1["failed"] == 0

    # Mark wave-1 tasks as passed
    orch.update_task_state("T-001", {"passes": True, "commit_sha": "abc123"})
    orch.update_task_state("T-002", {"passes": True, "commit_sha": "def456"})

    # Advance meta to wave 2
    store = orch._store()
    with store.lock(".zeus/v2/task.json"):
        data = store.read_json(".zeus/v2/task.json")
        data["meta"]["current_wave"] = 2
        store.write_json(".zeus/v2/task.json", data)

    # --- Wave 2 -----------------------------------------------------------
    summary2 = await orch.await_wave_completion(2)
    assert summary2["wave"] == 2
    assert summary2["total"] == 1
    assert summary2["dispatched"] == 1
    assert summary2["failed"] == 0

    # task.json still valid JSON
    final_data = store.read_json(".zeus/v2/task.json")
    assert "tasks" in final_data
    assert "meta" in final_data
    assert final_data["meta"]["current_wave"] == 2

    # Agent workspaces created
    workspaces = tmp_path / ".zeus" / "v2" / "agent-workspaces"
    assert (workspaces / "zeus-agent-T-001").exists()
    assert (workspaces / "zeus-agent-T-002").exists()
    assert (workspaces / "zeus-agent-T-003").exists()

    # Wave-1 event log exists and contains expected events
    logs_dir = tmp_path / ".zeus" / "v2" / "agent-logs"
    events_path = logs_dir / "wave-1-events.jsonl"
    assert events_path.exists()
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    types = [e["type"] for e in events]
    assert types.count("task.started") == 2
    assert types.count("task.completed") == 2
    assert types.count("wave.completed") == 1

    # Simulate a discussion post so the Markdown log exists
    bus = AgentBus(version="v2", wave=1, store=store)
    bus.post("T-001", "zeus-agent", "Wave 1 integration test complete")

    discussion_path = logs_dir / "wave-1-discussion.md"
    assert discussion_path.exists()
    discussion = discussion_path.read_text(encoding="utf-8")
    assert "Wave 1 Discussion Log" in discussion
    assert "Wave 1 integration test complete" in discussion

    # Dependency sequencing respected: T-003 depends on T-001 and lives in wave 2
    t003 = next(t for t in final_data["tasks"] if t["id"] == "T-003")
    assert t003["depends_on"] == ["T-001"]
    assert t003["wave"] == 2


# ---------------------------------------------------------------------------
# 2. API smoke full lifecycle
# ---------------------------------------------------------------------------
def test_api_smoke_full_lifecycle(tmp_path: Path) -> None:
    """Start the real FastAPI app and exercise the full REST surface."""
    _write_minimal_project(tmp_path)

    # Prepare store and monkey-patch the server global
    test_store = LocalStore(base_dir=str(tmp_path))
    original_store = zs.store
    zs.store = test_store

    port = _free_port()
    host = "127.0.0.1"
    base_url = f"http://{host}:{port}"

    config = uvicorn.Config(zs.app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    srv_thread = threading.Thread(target=server.run, daemon=True)
    srv_thread.start()

    try:
        # Wait for server readiness
        for _ in range(50):
            try:
                requests.get(f"{base_url}/status", timeout=0.1)
                break
            except Exception:
                time.sleep(0.1)
        else:
            pytest.fail("Uvicorn server did not start in time")

        # GET /status
        r = requests.get(f"{base_url}/status")
        assert r.status_code == 200
        status = r.json()
        assert status["version"] == "v2"
        assert status["current_wave"] == 1
        assert status["pending_tasks"] == 3
        assert status["completed_tasks"] == 0
        assert status["validation"] == "pass"

        # GET /wave/1
        r = requests.get(f"{base_url}/wave/1")
        assert r.status_code == 200
        wave_data = r.json()
        assert wave_data["wave"] == 1
        ids = {t["id"] for t in wave_data["tasks"]}
        assert ids == {"T-001", "T-002"}

        # Inject a running-agent event for /agents
        logs_dir = tmp_path / ".zeus" / "v2" / "agent-logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        started_event = {
            "ts": "2026-04-10T07:00:00Z",
            "type": "task.started",
            "wave": 1,
            "task_id": "T-002",
            "agent_id": "coder-0",
            "payload": {},
        }
        with open(logs_dir / "wave-1-events.jsonl", "w", encoding="utf-8") as f:
            f.write(json.dumps(started_event) + "\n")

        # GET /agents
        r = requests.get(f"{base_url}/agents")
        assert r.status_code == 200
        agents_data = r.json()
        agents = agents_data["agents"]
        assert any(a["task_id"] == "T-002" and a["status"] == "running" for a in agents)

        # GET /events?wave=1
        r = requests.get(f"{base_url}/events", params={"wave": 1})
        assert r.status_code == 200
        events = r.json()
        assert any(e["type"] == "task.started" and e["task_id"] == "T-002" for e in events)

        # Seed discussion log and GET /discussion?wave=1
        bus = AgentBus(version="v2", wave=1, store=test_store)
        bus.post("T-002", "coder-0", "Smoke test discussion entry")
        r = requests.get(f"{base_url}/discussion", params={"wave": 1})
        assert r.status_code == 200
        assert "Smoke test discussion entry" in r.text

        # GET /graph/mermaid
        r = requests.get(f"{base_url}/graph/mermaid")
        assert r.status_code == 200
        assert "flowchart TD" in r.text

        # GET /graph/svg — tolerate 503 when Graphviz is missing
        r = requests.get(f"{base_url}/graph/svg")
        if shutil.which("dot"):
            assert r.status_code == 200
            assert "svg" in r.text.lower()
        else:
            assert r.status_code == 503

        # POST /wave/1/approve (need all wave-1 tasks passed)
        task_path = tmp_path / ".zeus" / "v2" / "task.json"
        task_data = json.loads(task_path.read_text(encoding="utf-8"))
        for t in task_data["tasks"]:
            if t.get("wave") == 1:
                t["passes"] = True
        task_path.write_text(json.dumps(task_data), encoding="utf-8")

        r = requests.post(f"{base_url}/wave/1/approve")
        assert r.status_code == 200
        approve_data = r.json()
        assert approve_data["approved"] is True
        assert approve_data["next_wave"] == 2

        updated = json.loads(task_path.read_text(encoding="utf-8"))
        assert updated["meta"]["current_wave"] == 2

    finally:
        server.should_exit = True
        srv_thread.join(timeout=5)
        zs.store = original_store
