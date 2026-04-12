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
            {"id": "T-001", "title": "Task 1", "passes": True, "status": "completed", "depends_on": [], "wave": 1},
            {"id": "T-002", "title": "Task 2", "passes": False, "status": "pending", "depends_on": [], "wave": 1},
            {"id": "T-003", "title": "Task 3", "passes": True, "status": "completed", "depends_on": [], "wave": 2},
        ],
    }
    task_dir = tmp_path / ".zeus" / "v2"
    task_dir.mkdir(parents=True)
    (task_dir / "task.json").write_text(json.dumps(task_data), encoding="utf-8")

    roadmap_data = {
        "version": "v2",
        "phases": [
            {
                "id": "P-001",
                "title": "Foundation",
                "milestone_ids": ["M-001"],
                "wave_start": 1,
                "wave_end": 1,
            },
            {
                "id": "P-002",
                "title": "Ship",
                "milestone_ids": ["M-002"],
                "wave_start": 2,
                "wave_end": 2,
            },
        ],
        "milestones": [
            {
                "id": "M-001",
                "title": "Infra",
                "status": "in_progress",
                "task_ids": ["T-001", "T-002"],
                "story_ids": ["US-001"],
            },
            {
                "id": "M-002",
                "title": "Future",
                "status": "pending",
                "task_ids": ["T-003"],
                "story_ids": ["US-002"],
            },
        ],
    }
    (task_dir / "roadmap.json").write_text(json.dumps(roadmap_data), encoding="utf-8")

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


def test_status_endpoint(client, tmp_path):
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "v2"
    assert data["project_name"] == "zeus-open"
    assert data["current_wave"] == 1
    assert data["pending_tasks"] == 1
    assert data["completed_tasks"] == 2
    assert data["validation"] == "pass"
    assert "project_dir" in data
    assert str(tmp_path) in data["project_dir"]


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
        assert "original_wave" in t
        assert "scheduled_wave" in t
        assert "rescheduled_from" in t


def test_approve_endpoint_uses_original_wave(client, tmp_path):
    """Approval gate should count tasks by original_wave, not scheduled wave."""
    task_path = tmp_path / ".zeus" / "v2" / "task.json"
    task_data = {
        "meta": {"current_wave": 1, "wave_approval_required": True, "max_parallel_agents": 2},
        "tasks": [
            {"id": "T-001", "title": "Task 1", "passes": True, "depends_on": [], "wave": 1, "original_wave": 1},
            {"id": "T-002", "title": "Task 2", "passes": False, "depends_on": [], "wave": 1, "original_wave": 2, "scheduled_wave": 1, "rescheduled_from": 2},
        ],
    }
    task_path.write_text(json.dumps(task_data), encoding="utf-8")

    # T-001 (original_wave=1) is done; T-002 (original_wave=2) is pending.
    # Wave 1 approval should succeed because all original_wave==1 tasks are passed.
    response = client.post("/wave/1/approve")
    assert response.status_code == 200
    data = response.json()
    assert data["approved"] is True
    assert data["next_wave"] == 2

    updated = json.loads(task_path.read_text(encoding="utf-8"))
    assert updated["meta"]["current_wave"] == 2


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


def test_versions_endpoint(client, tmp_path):
    response = client.get("/versions")
    assert response.status_code == 200
    data = response.json()
    assert "versions" in data
    ids = {v["id"] for v in data["versions"]}
    assert "v2" in ids


def test_status_with_version_query(client, tmp_path):
    # Also create a main version to switch to
    main_dir = tmp_path / ".zeus" / "main"
    main_dir.mkdir(parents=True)
    main_task = {
        "meta": {"current_wave": 3, "wave_approval_required": True, "max_parallel_agents": 2},
        "tasks": [
            {"id": "M-001", "title": "Main task", "passes": True, "depends_on": [], "wave": 1},
        ],
    }
    (main_dir / "task.json").write_text(json.dumps(main_task), encoding="utf-8")
    main_config = {"project": {"name": "main-project"}}
    (main_dir / "config.json").write_text(json.dumps(main_config), encoding="utf-8")

    response = client.get("/status?version=main")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "main"
    assert data["project_name"] == "main-project"
    assert data["current_wave"] == 3

    response = client.get("/wave/1?version=main")
    assert response.status_code == 200
    wave_data = response.json()
    assert wave_data["wave"] == 1
    assert any(t["id"] == "M-001" for t in wave_data["tasks"])


def test_graph_mermaid_with_version(client, tmp_path):
    main_dir = tmp_path / ".zeus" / "main"
    main_dir.mkdir(parents=True)
    main_task = {
        "meta": {"current_wave": 1},
        "tasks": [
            {"id": "M-001", "title": "Main task", "passes": True, "depends_on": [], "wave": 1},
        ],
    }
    (main_dir / "task.json").write_text(json.dumps(main_task), encoding="utf-8")

    response = client.get("/graph/mermaid?version=main")
    assert response.status_code == 200
    text = response.text
    assert "flowchart TD" in text
    assert "M001" in text


def test_open_project_success(client, tmp_path):
    import zeus_server as zs

    # Create a second zeus project directory
    other = tmp_path / "other-project"
    other.mkdir()
    zeus_dir = other / ".zeus" / "v2"
    zeus_dir.mkdir(parents=True)
    task_data = {
        "meta": {"current_wave": 2, "wave_approval_required": True, "max_parallel_agents": 2},
        "tasks": [
            {"id": "O-001", "title": "Other task", "passes": True, "depends_on": [], "wave": 1},
        ],
    }
    (zeus_dir / "task.json").write_text(json.dumps(task_data), encoding="utf-8")
    (zeus_dir / "config.json").write_text(json.dumps({"project": {"name": "other"}}), encoding="utf-8")

    response = client.post("/project/open", json={"project_dir": str(other)})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert str(other) in data["project_dir"]
    assert data["status"]["project_name"] == "other"
    assert data["status"]["current_wave"] == 2

    # Verify /versions now scans the new project
    response = client.get("/versions")
    assert response.status_code == 200
    versions_data = response.json()
    ids = {v["id"] for v in versions_data["versions"]}
    assert "v2" in ids

    # Restore store so other tests in the same session are not affected
    zs.store = LocalStore(base_dir=str(tmp_path))


def test_open_project_invalid_dir(client):
    response = client.post("/project/open", json={"project_dir": "D:\\nonexistent-zeus-project-xyz"})
    assert response.status_code == 400
    assert "project_dir must be a directory" in response.json()["detail"]


def test_open_project_not_zeus(client, tmp_path):
    plain_dir = tmp_path / "plain-folder"
    plain_dir.mkdir()
    response = client.post("/project/open", json={"project_dir": str(plain_dir)})
    assert response.status_code == 400
    assert "Not a valid Zeus project" in response.json()["detail"]


def test_milestones_endpoint(client):
    response = client.get("/milestones")
    assert response.status_code == 200
    data = response.json()
    assert "milestones" in data
    assert len(data["milestones"]) == 2

    m1 = next(m for m in data["milestones"] if m["id"] == "M-001")
    assert m1["title"] == "Infra"
    assert m1["status"] == "in_progress"
    assert m1["progress_percent"] == 50
    assert len(m1["tasks"]) == 2
    assert any(t["id"] == "T-001" and t["passes"] is True for t in m1["tasks"])
    assert any(t["id"] == "T-002" and t["passes"] is False for t in m1["tasks"])

    m2 = next(m for m in data["milestones"] if m["id"] == "M-002")
    assert m2["title"] == "Future"
    assert m2["status"] == "completed"
    assert m2["progress_percent"] == 100
    assert len(m2["tasks"]) == 1


def test_phases_endpoint(client):
    response = client.get("/phases")
    assert response.status_code == 200
    data = response.json()
    assert "phases" in data
    assert len(data["phases"]) == 2

    p1 = next(p for p in data["phases"] if p["id"] == "P-001")
    assert p1["title"] == "Foundation"
    assert p1["status"] == "in_progress"
    assert p1["progress_percent"] == 50
    assert len(p1["milestones"]) == 1
    assert p1["milestones"][0]["id"] == "M-001"

    p2 = next(p for p in data["phases"] if p["id"] == "P-002")
    assert p2["title"] == "Ship"
    assert p2["status"] == "completed"
    assert p2["progress_percent"] == 100
    assert len(p2["milestones"]) == 1
    assert p2["milestones"][0]["id"] == "M-002"


def test_status_includes_current_phase(client):
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["current_phase"] == "P-001"


def test_mailbox_endpoint(client, tmp_path):
    # Seed a mailbox message for agent-x
    logs_dir = tmp_path / ".zeus" / "v2" / "agent-logs" / "mailbox"
    logs_dir.mkdir(parents=True)
    msg = {"ts": "2026-04-12T10:00:00Z", "from": "agent-a", "to": "agent-x", "message": "hello", "read": False}
    with open(logs_dir / "agent-x.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps(msg) + "\n")

    response = client.get("/mailbox/agent-x")
    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == "agent-x"
    assert len(data["messages"]) == 1
    assert data["messages"][0]["message"] == "hello"
    assert data["messages"][0]["read"] is False

    # Mark read
    response = client.get("/mailbox/agent-x?mark_read=true")
    assert response.status_code == 200
    data = response.json()
    assert data["messages"][0]["read"] is True

    # Verify persistence
    response = client.get("/mailbox/agent-x")
    assert response.json()["messages"][0]["read"] is True


def test_mailbox_endpoint_empty(client):
    response = client.get("/mailbox/no-one")
    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == "no-one"
    assert data["messages"] == []


def test_global_status_includes_status_map(client):
    response = client.get("/global/status")
    assert response.status_code == 200
    data = response.json()
    assert "status_map" in data
    assert data["status_map"].get("T-001") == "completed"
    assert data["status_map"].get("T-002") == "pending"


def test_cancel_task_endpoint(client, tmp_path):
    task_path = tmp_path / ".zeus" / "v2" / "task.json"
    task_data = json.loads(task_path.read_text(encoding="utf-8"))
    for t in task_data["tasks"]:
        if t["id"] == "T-002":
            t["status"] = "pending"
            t["passes"] = False
    task_path.write_text(json.dumps(task_data), encoding="utf-8")

    response = client.post("/tasks/T-002/cancel")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["status"] == "cancelled"

    updated = json.loads(task_path.read_text(encoding="utf-8"))
    t2 = next(t for t in updated["tasks"] if t["id"] == "T-002")
    assert t2["status"] == "cancelled"
    assert t2["passes"] is False


def test_pause_task_endpoint(client, tmp_path):
    task_path = tmp_path / ".zeus" / "v2" / "task.json"
    task_data = json.loads(task_path.read_text(encoding="utf-8"))
    for t in task_data["tasks"]:
        if t["id"] == "T-002":
            t["status"] = "running"
            t["passes"] = False
    task_path.write_text(json.dumps(task_data), encoding="utf-8")

    response = client.post("/tasks/T-002/pause")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["status"] == "paused"

    updated = json.loads(task_path.read_text(encoding="utf-8"))
    t2 = next(t for t in updated["tasks"] if t["id"] == "T-002")
    assert t2["status"] == "paused"


def test_retry_task_endpoint(client, tmp_path):
    task_path = tmp_path / ".zeus" / "v2" / "task.json"
    task_data = json.loads(task_path.read_text(encoding="utf-8"))
    for t in task_data["tasks"]:
        if t["id"] == "T-002":
            t["status"] = "failed"
            t["passes"] = False
            t["commit_sha"] = "abc1234"
    task_data.setdefault("quarantine", []).append({"task_id": "T-002", "reason": "test"})
    task_path.write_text(json.dumps(task_data), encoding="utf-8")

    response = client.post("/tasks/T-002/retry")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["status"] == "pending"

    updated = json.loads(task_path.read_text(encoding="utf-8"))
    t2 = next(t for t in updated["tasks"] if t["id"] == "T-002")
    assert t2["status"] == "pending"
    assert t2["passes"] is False
    assert "commit_sha" not in t2
    assert all(q["task_id"] != "T-002" for q in updated.get("quarantine", []))


def test_cancel_invalid_status_returns_400(client, tmp_path):
    task_path = tmp_path / ".zeus" / "v2" / "task.json"
    task_data = json.loads(task_path.read_text(encoding="utf-8"))
    for t in task_data["tasks"]:
        if t["id"] == "T-002":
            t["status"] = "completed"
            t["passes"] = True
    task_path.write_text(json.dumps(task_data), encoding="utf-8")

    response = client.post("/tasks/T-002/cancel")
    assert response.status_code == 400


def test_pause_invalid_status_returns_400(client, tmp_path):
    task_path = tmp_path / ".zeus" / "v2" / "task.json"
    task_data = json.loads(task_path.read_text(encoding="utf-8"))
    for t in task_data["tasks"]:
        if t["id"] == "T-002":
            t["status"] = "pending"
    task_path.write_text(json.dumps(task_data), encoding="utf-8")

    response = client.post("/tasks/T-002/pause")
    assert response.status_code == 400


def test_retry_invalid_status_returns_400(client, tmp_path):
    task_path = tmp_path / ".zeus" / "v2" / "task.json"
    task_data = json.loads(task_path.read_text(encoding="utf-8"))
    for t in task_data["tasks"]:
        if t["id"] == "T-002":
            t["status"] = "running"
    task_path.write_text(json.dumps(task_data), encoding="utf-8")

    response = client.post("/tasks/T-002/retry")
    assert response.status_code == 400


def test_agent_ids_endpoint(client, tmp_path):
    # Seed agent-specific log directories
    logs_dir = tmp_path / ".zeus" / "v2" / "agent-logs"
    (logs_dir / "zeus-agent-A").mkdir(parents=True)
    (logs_dir / "zeus-agent-B").mkdir(parents=True)
    # mailbox directory should be ignored
    (logs_dir / "mailbox").mkdir(parents=True)

    response = client.get("/agent-ids")
    assert response.status_code == 200
    data = response.json()
    assert sorted(data["agent_ids"]) == ["zeus-agent-A", "zeus-agent-B"]


def test_run_global_endpoint_success(client):
    from unittest.mock import patch, AsyncMock
    import zeus_server as zs

    original = zs._active_global_runs.copy()
    zs._active_global_runs.clear()
    mock_run = AsyncMock()
    with patch.object(zs, "ZeusOrchestrator") as MockOrch:
        MockOrch.return_value.run_global = mock_run
        response = client.post("/global/run")
        assert response.status_code == 200
        assert response.json()["started"] is True
    zs._active_global_runs.clear()
    zs._active_global_runs.update(original)


def test_run_global_endpoint_conflict(client):
    import zeus_server as zs

    original = zs._active_global_runs.copy()
    zs._active_global_runs.add("v2")
    try:
        response = client.post("/global/run")
        assert response.status_code == 409
        assert "already running" in response.json()["detail"]
    finally:
        zs._active_global_runs.clear()
        zs._active_global_runs.update(original)
