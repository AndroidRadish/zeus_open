import json
import pytest
from fastapi.testclient import TestClient

from store import LocalStore
from zeus_server import app


@pytest.fixture
def client(tmp_path):
    test_store = LocalStore(base_dir=str(tmp_path))

    task_data = {
        "meta": {
            "current_wave": 1,
            "wave_approval_required": True,
            "max_parallel_agents": 2,
        },
        "tasks": [
            {"id": "T-001", "title": "Task 1", "passes": True, "depends_on": [], "wave": 1},
            {"id": "T-002", "title": "Task 2", "passes": False, "depends_on": [], "wave": 1},
            {"id": "T-003", "title": "Task 3", "passes": True, "depends_on": [], "wave": 2},
        ],
    }
    task_dir = tmp_path / ".zeus" / "v2"
    task_dir.mkdir(parents=True)
    (task_dir / "task.json").write_text(json.dumps(task_data), encoding="utf-8")

    events = [
        {
            "ts": "2026-04-10T07:00:00Z",
            "type": "task.started",
            "wave": 1,
            "task_id": "T-002",
            "agent_id": "coder-0",
            "payload": {},
        },
        {
            "ts": "2026-04-10T07:05:00Z",
            "type": "task.progress",
            "wave": 1,
            "task_id": "T-002",
            "agent_id": "coder-0",
            "payload": {},
        },
    ]
    logs_dir = task_dir / "agent-logs"
    logs_dir.mkdir()
    with open(logs_dir / "wave-1-events.jsonl", "w", encoding="utf-8") as f:
        for evt in events:
            f.write(json.dumps(evt) + "\n")

    import zeus_server as zs

    original_store = zs.store
    zs.store = test_store
    yield TestClient(app)
    zs.store = original_store


def test_status_endpoint(client):
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "v2"
    assert data["project_name"] == "zeus-open"
    assert data["current_wave"] == 1
    assert data["pending_tasks"] == 1
    assert data["completed_tasks"] == 2
    assert data["validation"] == "pass"


def test_wave_endpoint(client):
    response = client.get("/wave/1")
    assert response.status_code == 200
    data = response.json()
    assert data["wave"] == 1
    assert len(data["tasks"]) == 2
    ids = {t["id"] for t in data["tasks"]}
    assert ids == {"T-001", "T-002"}
    for t in data["tasks"]:
        assert "id" in t
        assert "title" in t
        assert "passes" in t
        assert "depends_on" in t


def test_graph_mermaid_endpoint(client):
    response = client.get("/graph/mermaid")
    assert response.status_code == 200
    text = response.text
    assert "flowchart TD" in text
    assert "T001" in text or "T002" in text


def test_approve_endpoint_valid_wave(client, tmp_path):
    task_path = tmp_path / ".zeus" / "v2" / "task.json"
    task_data = json.loads(task_path.read_text(encoding="utf-8"))
    for t in task_data["tasks"]:
        if t.get("wave") == 1:
            t["passes"] = True
    task_path.write_text(json.dumps(task_data), encoding="utf-8")

    response = client.post("/wave/1/approve")
    assert response.status_code == 200
    data = response.json()
    assert data["approved"] is True
    assert data["next_wave"] == 2

    updated = json.loads(task_path.read_text(encoding="utf-8"))
    assert updated["meta"]["current_wave"] == 2


def test_approve_endpoint_invalid_wave(client):
    response = client.post("/wave/1/approve")
    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "Wave 1 has pending tasks"
