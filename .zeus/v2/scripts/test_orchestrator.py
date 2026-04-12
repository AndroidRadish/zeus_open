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
            "subagent": {"dispatcher": "mock"},
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
    assert result["status"] == "completed"  # Mock dispatcher falls back when no CLI installed

    workspace = Path(result["workspace"])
    prompt_path = workspace / "PROMPT.md"

    assert workspace.exists()
    assert workspace.name == "zeus-agent-T-002"
    assert prompt_path.exists()

    prompt_text = prompt_path.read_text(encoding="utf-8")
    assert "T-002" in prompt_text
    assert "Pending task wave 1" in prompt_text
    assert "Test Project" in prompt_text

    # Verify source was copied
    assert (workspace / "src" / "main.py").exists()

    # Verify events were emitted by the mock dispatcher
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
# Adaptive wave rescheduling
# ---------------------------------------------------------------------------
@pytest.fixture
def adaptive_project():
    """Provide a project configured for adaptive scheduling with a blocking wave-1 task."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        zeus_dir = root / ".zeus" / "v2"
        zeus_dir.mkdir(parents=True, exist_ok=True)

        task_data = {
            "meta": {
                "current_wave": 1,
                "wave_approval_required": True,
                "max_parallel_agents": 2,
                "scheduling_mode": "adaptive",
            },
            "tasks": [
                {
                    "id": "T-001",
                    "passes": False,
                    "story_id": "US-001",
                    "title": "Blocking task wave 1",
                    "depends_on": [],
                    "wave": 1,
                    "original_wave": 1,
                    "scheduled_wave": 1,
                },
                {
                    "id": "T-002",
                    "passes": False,
                    "story_id": "US-001",
                    "title": "Quick task wave 1",
                    "depends_on": [],
                    "wave": 1,
                    "original_wave": 1,
                    "scheduled_wave": 1,
                },
                {
                    "id": "T-003",
                    "passes": False,
                    "story_id": "US-002",
                    "title": "Future wave 2 task",
                    "depends_on": [],
                    "wave": 2,
                    "original_wave": 2,
                    "scheduled_wave": 2,
                },
            ],
        }
        (zeus_dir / "task.json").write_text(json.dumps(task_data), encoding="utf-8")

        config_data = {
            "project": {"name": "Adaptive Test Project"},
            "metrics": {"north_star": "efficiency"},
            "subagent": {"dispatcher": "mock"},
        }
        (zeus_dir / "config.json").write_text(json.dumps(config_data), encoding="utf-8")

        (root / "src").mkdir(parents=True, exist_ok=True)
        (root / "src" / "main.py").write_text("# hello\n", encoding="utf-8")

        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            yield root
        finally:
            os.chdir(old_cwd)


@pytest.mark.asyncio
async def test_adaptive_rescheduling_fills_slots_from_future_wave(adaptive_project):
    """When a wave-1 slot frees up, a ready wave-2 task should be rescheduled and dispatched."""
    orch = ZeusOrchestrator(version="v2", project_root=str(adaptive_project), max_parallel=2)
    store = LocalStore(base_dir=str(adaptive_project))

    block_event = asyncio.Event()

    async def fake_dispatch(task, bus, store):
        if task["id"] == "T-001":
            await asyncio.wait_for(block_event.wait(), timeout=5)
        else:
            await asyncio.sleep(0.05)
        bus.emit("task.completed", task["id"], "mock-agent", {})
        return {"task_id": task["id"], "status": "dispatched"}

    async def unblock():
        await asyncio.sleep(0.2)
        block_event.set()

    with patch.object(orch, "dispatch_task", side_effect=fake_dispatch):
        asyncio.create_task(unblock())
        summary = await orch.await_wave_completion(1)

    # T-001, T-002, and T-003 should all have been dispatched
    assert summary["wave"] == 1
    assert summary["dispatched"] == 3
    assert summary["failed"] == 0

    # T-003 should have been rescheduled into wave 1
    data = store.read_json(".zeus/v2/task.json")
    t003 = next(t for t in data["tasks"] if t["id"] == "T-003")
    assert t003["scheduled_wave"] == 1
    assert t003["wave"] == 1
    assert t003["rescheduled_from"] == 2
    assert t003["original_wave"] == 2

    # Bus should contain a reschedule event for T-003
    bus = AgentBus(version="v2", wave=1, store=store)
    events = bus.get_events()
    reschedule_events = [e for e in events if e["type"] == "task.rescheduled" and e.get("task_id") == "T-003"]
    assert len(reschedule_events) == 1
    assert reschedule_events[0]["payload"]["new_wave"] == 1
    assert reschedule_events[0]["payload"]["previous_wave"] == 2


@pytest.mark.asyncio
async def test_no_rescheduling_when_lookahead_disabled(adaptive_project):
    """With scheduling_mode=legacy, wave-2 tasks must not be pulled into wave 1."""
    store = LocalStore(base_dir=str(adaptive_project))
    data = store.read_json(".zeus/v2/task.json")
    data["meta"]["scheduling_mode"] = "legacy"
    data["meta"]["lookahead_waves"] = 0
    store.write_json(".zeus/v2/task.json", data)

    orch = ZeusOrchestrator(version="v2", project_root=str(adaptive_project), max_parallel=2)
    block_event = asyncio.Event()

    async def fake_dispatch(task, bus, store):
        if task["id"] == "T-001":
            await asyncio.wait_for(block_event.wait(), timeout=5)
        else:
            await asyncio.sleep(0.05)
        bus.emit("task.completed", task["id"], "mock-agent", {})
        return {"task_id": task["id"], "status": "dispatched"}

    with patch.object(orch, "dispatch_task", side_effect=fake_dispatch):
        summary = await orch.await_wave_completion(1)

    # Only T-001 and T-002 should be dispatched
    assert summary["dispatched"] == 2

    # T-003 must remain untouched
    data = store.read_json(".zeus/v2/task.json")
    t003 = next(t for t in data["tasks"] if t["id"] == "T-003")
    assert t003.get("wave") == 2
    assert t003.get("scheduled_wave") == 2


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
