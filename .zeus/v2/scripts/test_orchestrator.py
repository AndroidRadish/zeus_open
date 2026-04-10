"""
Tests for zeus_orchestrator.py
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_bus import AgentBus
from store import LocalStore
from zeus_orchestrator import ZeusOrchestrator


@pytest.fixture
def temp_project():
    """Provide a minimal temporary project tree with task.json and config.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        zeus_dir = root / ".zeus" / "v2"
        zeus_dir.mkdir(parents=True, exist_ok=True)

        task_data = {
            "meta": {"current_wave": 1, "wave_approval_required": True, "max_parallel_agents": 3},
            "tasks": [
                {
                    "id": "T-001",
                    "passes": True,
                    "story_id": "US-001",
                    "title": "Done task",
                    "depends_on": [],
                    "wave": 1,
                },
                {
                    "id": "T-002",
                    "passes": False,
                    "story_id": "US-001",
                    "title": "Pending task wave 1",
                    "depends_on": [],
                    "wave": 1,
                },
                {
                    "id": "T-003",
                    "passes": False,
                    "story_id": "US-002",
                    "title": "Pending task wave 2",
                    "depends_on": ["T-001"],
                    "wave": 2,
                },
            ],
        }
        (zeus_dir / "task.json").write_text(json.dumps(task_data), encoding="utf-8")

        config_data = {
            "project": {"name": "Test Project"},
            "metrics": {"north_star": "test-coverage"},
        }
        (zeus_dir / "config.json").write_text(json.dumps(config_data), encoding="utf-8")

        # Create a small dummy source file so copytree has something to copy
        (root / "src").mkdir()
        (root / "src" / "main.py").write_text("# hello\n", encoding="utf-8")

        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            yield root
        finally:
            os.chdir(old_cwd)


@pytest.fixture
def orchestrator(temp_project):
    return ZeusOrchestrator(version="v2", project_root=str(temp_project), max_parallel=2)


# ---------------------------------------------------------------------------
# load_wave
# ---------------------------------------------------------------------------
def test_load_wave_returns_pending_tasks(orchestrator):
    pending_wave1 = orchestrator.load_wave(1)
    assert len(pending_wave1) == 1
    assert pending_wave1[0]["id"] == "T-002"

    pending_wave2 = orchestrator.load_wave(2)
    assert len(pending_wave2) == 1
    assert pending_wave2[0]["id"] == "T-003"

    pending_wave3 = orchestrator.load_wave(3)
    assert pending_wave3 == []


# ---------------------------------------------------------------------------
# dispatch_task
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dispatch_task_creates_workspace_and_prompt(orchestrator, temp_project):
    store = LocalStore(base_dir=str(temp_project))
    bus = AgentBus(version="v2", wave=1, store=store)
    task = {
        "id": "T-002",
        "passes": False,
        "story_id": "US-001",
        "title": "Pending task wave 1",
        "depends_on": [],
        "wave": 1,
        "type": "feat",
    }

    result = await orchestrator.dispatch_task(task, bus, store)

    assert result["task_id"] == "T-002"
    assert result["status"] == "dispatched"

    workspace = Path(result["workspace"])
    prompt_path = Path(result["prompt_path"])

    assert workspace.exists()
    assert workspace.name == "zeus-agent-T-002"
    assert prompt_path.exists()

    prompt_text = prompt_path.read_text(encoding="utf-8")
    assert "T-002" in prompt_text
    assert "Pending task wave 1" in prompt_text
    assert "Test Project" in prompt_text

    # Verify source was copied
    assert (workspace / "src" / "main.py").exists()

    # Verify events were emitted
    events = bus.get_events()
    assert len(events) == 2
    assert events[0]["type"] == "task.started"
    assert events[1]["type"] == "task.completed"


# ---------------------------------------------------------------------------
# await_wave_completion + semaphore
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_await_wave_completion_respects_max_parallel(orchestrator, temp_project):
    store = LocalStore(base_dir=str(temp_project))

    acquire_calls = []
    release_calls = []

    class TrackedSemaphore(asyncio.Semaphore):
        async def acquire(self):
            acquire_calls.append(1)
            return await super().acquire()

        def release(self):
            release_calls.append(1)
            super().release()

    orchestrator._semaphore = TrackedSemaphore(orchestrator.max_parallel)

    summary = await orchestrator.await_wave_completion(1)

    assert summary["wave"] == 1
    assert summary["total"] == 1
    assert summary["dispatched"] == 1
    assert summary["failed"] == 0

    # One acquire and one release for the single pending task
    assert len(acquire_calls) == 1
    assert len(release_calls) == 1


# ---------------------------------------------------------------------------
# update_task_state
# ---------------------------------------------------------------------------
def test_update_task_state_with_lock(orchestrator, temp_project):
    orchestrator.update_task_state(
        "T-002",
        {"passes": True, "commit_sha": "deadbeef", "finished_at": "2026-04-10T12:00:00Z"},
    )

    store = LocalStore(base_dir=str(temp_project))
    data = store.read_json(".zeus/v2/task.json")
    t002 = next(t for t in data["tasks"] if t["id"] == "T-002")
    assert t002["passes"] is True
    assert t002["commit_sha"] == "deadbeef"
    assert t002["finished_at"] == "2026-04-10T12:00:00Z"


# ---------------------------------------------------------------------------
# transition_to_next_wave
# ---------------------------------------------------------------------------
def test_transition_requires_approval_when_auto_false(orchestrator, temp_project, capsys):
    # First mark all wave-1 tasks as done so transition is eligible
    orchestrator.update_task_state("T-002", {"passes": True, "commit_sha": "abc123"})

    result = orchestrator.transition_to_next_wave(1, auto=False)
    assert result is False

    captured = capsys.readouterr()
    assert "Wave 1 completed." in captured.out
    assert "Please approve to proceed to Wave 2." in captured.out

    # Ensure meta was NOT updated
    store = LocalStore(base_dir=str(temp_project))
    data = store.read_json(".zeus/v2/task.json")
    assert data["meta"]["current_wave"] == 1
