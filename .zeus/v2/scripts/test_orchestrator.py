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
from scheduler_state import SchedulerStateDB
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

    # Verify events were emitted (bootstrap + started + completed)
    events = bus.get_events()
    assert len(events) == 3
    assert events[0]["type"] == "task.bootstrapped"
    assert events[1]["type"] == "task.started"
    assert events[2]["type"] == "task.completed"


@pytest.mark.asyncio
async def test_dispatch_task_bootstraps_identity_files(orchestrator, temp_project):
    """Existing identity files should be copied into the workspace; missing ones skipped."""
    store = LocalStore(base_dir=str(temp_project))
    bus = AgentBus(version="v2", wave=1, store=store)

    # Seed AGENTS.md and USER.md in project root
    (temp_project / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    (temp_project / "USER.md").write_text("# USER\n", encoding="utf-8")
    # IDENTITY.md and SOUL.md are intentionally missing

    task = {
        "id": "T-002",
        "passes": False,
        "story_id": "US-001",
        "title": "Bootstrap test task",
        "depends_on": [],
        "wave": 1,
        "type": "feat",
    }

    result = await orchestrator.dispatch_task(task, bus, store)
    workspace = Path(result["workspace"])

    assert (workspace / "AGENTS.md").exists()
    assert (workspace / "USER.md").exists()
    assert not (workspace / "IDENTITY.md").exists()
    assert not (workspace / "SOUL.md").exists()

    # Verify task.bootstrapped event
    events = bus.get_events()
    bootstrap_events = [e for e in events if e["type"] == "task.bootstrapped"]
    assert len(bootstrap_events) == 1
    assert "AGENTS.md" in bootstrap_events[0]["payload"]["injected"]
    assert "USER.md" in bootstrap_events[0]["payload"]["injected"]
    assert "IDENTITY.md" in bootstrap_events[0]["payload"]["skipped"]
    assert "SOUL.md" in bootstrap_events[0]["payload"]["skipped"]


@pytest.mark.asyncio
async def test_dispatch_task_bootstrap_respects_config_override(temp_project):
    """config.subagent.bootstrap.files should override the default list entirely."""
    store = LocalStore(base_dir=str(temp_project))
    bus = AgentBus(version="v2", wave=1, store=store)

    # Update config with custom bootstrap file list
    config = store.read_json(".zeus/v2/config.json")
    config["subagent"]["bootstrap"] = {"files": ["CUSTOM.md"]}
    store.write_json(".zeus/v2/config.json", config)

    (temp_project / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    (temp_project / "CUSTOM.md").write_text("# CUSTOM\n", encoding="utf-8")

    orch = ZeusOrchestrator(version="v2", project_root=str(temp_project), max_parallel=2)

    task = {
        "id": "T-002",
        "passes": False,
        "story_id": "US-001",
        "title": "Config override test",
        "depends_on": [],
        "wave": 1,
        "type": "feat",
    }

    result = await orch.dispatch_task(task, bus, store)
    workspace = Path(result["workspace"])

    # Because the whole project tree is copied, AGENTS.md may already be present;
    # the important thing is that bootstrap only reports CUSTOM.md as injected.
    assert (workspace / "CUSTOM.md").exists()

    events = bus.get_events()
    bootstrap_events = [e for e in events if e["type"] == "task.bootstrapped"]
    assert bootstrap_events[0]["payload"]["injected"] == ["CUSTOM.md"]
    assert bootstrap_events[0]["payload"]["skipped"] == []


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


# ---------------------------------------------------------------------------
# Global Scheduler & Quarantine
# ---------------------------------------------------------------------------
@pytest.fixture
def global_project():
    """Provide a project with tasks across multiple waves for global scheduling tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
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
                    "passes": False,
                    "story_id": "US-001",
                    "title": "Task wave 1",
                    "depends_on": [],
                    "wave": 1,
                    "original_wave": 1,
                    "scheduled_wave": 1,
                },
                {
                    "id": "T-002",
                    "passes": False,
                    "story_id": "US-001",
                    "title": "Task wave 1 b",
                    "depends_on": [],
                    "wave": 1,
                    "original_wave": 1,
                    "scheduled_wave": 1,
                },
                {
                    "id": "T-003",
                    "passes": False,
                    "story_id": "US-002",
                    "title": "Task wave 2 depends on T-001",
                    "depends_on": ["T-001"],
                    "wave": 2,
                    "original_wave": 2,
                    "scheduled_wave": 2,
                },
                {
                    "id": "T-004",
                    "passes": False,
                    "story_id": "US-002",
                    "title": "Task wave 2 no deps",
                    "depends_on": [],
                    "wave": 2,
                    "original_wave": 2,
                    "scheduled_wave": 2,
                },
                {
                    "id": "T-005",
                    "passes": False,
                    "story_id": "US-003",
                    "title": "Task wave 3 depends on T-004",
                    "depends_on": ["T-004"],
                    "wave": 3,
                    "original_wave": 3,
                    "scheduled_wave": 3,
                },
            ],
        }
        (zeus_dir / "task.json").write_text(json.dumps(task_data), encoding="utf-8")

        config_data = {
            "project": {"name": "Global Test Project"},
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
async def test_run_global_dispatches_cross_wave(global_project):
    """Global scheduler should dispatch T-003/T-004/T-005 as soon as their deps are ready, ignoring wave boundaries."""
    orch = ZeusOrchestrator(version="v2", project_root=str(global_project), max_parallel=2)

    dispatch_order: list[str] = []

    async def fake_dispatch(task, bus, store):
        await asyncio.sleep(0.01)
        dispatch_order.append(task["id"])
        # Simulate subagent updating passes in task.json
        orch.update_task_state(task["id"], {"passes": True, "commit_sha": "abc123"})
        bus.emit("task.completed", task["id"], "mock-agent", {})
        return {"task_id": task["id"], "status": "completed"}

    with patch.object(orch, "dispatch_task", side_effect=fake_dispatch):
        summary = await orch.run_global()

    assert summary["mode"] == "global"
    assert summary["dispatched"] == 5
    assert summary["failed"] == 0

    # T-001 and T-002 should start first (only two slots)
    first_batch = set(dispatch_order[:2])
    assert first_batch == {"T-001", "T-002"}

    # After T-001 and T-002 finish, T-003 (depends T-001), T-004 (no deps) should go next
    second_batch = set(dispatch_order[2:4])
    assert second_batch == {"T-003", "T-004"}

    # Finally T-005 depends on T-004
    assert dispatch_order[4] == "T-005"


@pytest.mark.asyncio
async def test_quarantine_unblocks_unrelated_tasks(global_project):
    """When T-001 fails, T-004 and T-005 (which do not depend on T-001) should still proceed."""
    orch = ZeusOrchestrator(version="v2", project_root=str(global_project), max_parallel=2)
    store = LocalStore(base_dir=str(global_project))

    async def fake_dispatch(task, bus, store):
        await asyncio.sleep(0.01)
        if task["id"] == "T-001":
            raise RuntimeError("simulated failure")
        orch.update_task_state(task["id"], {"passes": True, "commit_sha": "abc123"})
        bus.emit("task.completed", task["id"], "mock-agent", {})
        return {"task_id": task["id"], "status": "completed"}

    with patch.object(orch, "dispatch_task", side_effect=fake_dispatch):
        summary = await orch.run_global()

    # T-001 fails; T-002, T-004, T-005 succeed; T-003 is never dispatched because T-001 is quarantined
    assert summary["dispatched"] == 4
    assert summary["failed"] == 1

    # T-001 should be quarantined
    data = store.read_json(".zeus/v2/task.json")
    quarantine_ids = {q["task_id"] for q in data.get("quarantine", [])}
    assert "T-001" in quarantine_ids

    # T-003, which depends on T-001, should NOT have been dispatched and should not have passed
    t003 = next(t for t in data["tasks"] if t["id"] == "T-003")
    assert t003.get("passes") is False

    # T-004 and T-005 should have completed successfully
    t004 = next(t for t in data["tasks"] if t["id"] == "T-004")
    t005 = next(t for t in data["tasks"] if t["id"] == "T-005")
    assert t004.get("passes") is True
    assert t005.get("passes") is True

    # Verify bus events
    bus = AgentBus(version="v2", wave=-1, store=store)
    events = bus.get_events()
    quarantine_events = [e for e in events if e["type"] == "task.quarantined"]
    assert len(quarantine_events) == 1
    assert quarantine_events[0]["task_id"] == "T-001"


@pytest.mark.asyncio
async def test_quarantine_blocks_dependent_tasks(global_project):
    """T-003 depends on T-001; if T-001 is quarantined, T-003 must never be dispatched."""
    orch = ZeusOrchestrator(version="v2", project_root=str(global_project), max_parallel=2)

    dispatched: list[str] = []

    async def fake_dispatch(task, bus, store):
        await asyncio.sleep(0.01)
        dispatched.append(task["id"])
        if task["id"] == "T-001":
            raise RuntimeError("simulated failure")
        orch.update_task_state(task["id"], {"passes": True, "commit_sha": "abc123"})
        bus.emit("task.completed", task["id"], "mock-agent", {})
        return {"task_id": task["id"], "status": "completed"}

    with patch.object(orch, "dispatch_task", side_effect=fake_dispatch):
        await orch.run_global()

    # T-003 should never have been dispatched because T-001 failed and was quarantined
    assert "T-003" not in dispatched


@pytest.mark.asyncio
async def test_run_global_respects_max_parallel(global_project):
    """Only max_parallel tasks should run concurrently."""
    orch = ZeusOrchestrator(version="v2", project_root=str(global_project), max_parallel=2)

    concurrent = 0
    max_concurrent = 0
    block_event = asyncio.Event()

    async def fake_dispatch(task, bus, store):
        nonlocal concurrent, max_concurrent
        concurrent += 1
        max_concurrent = max(max_concurrent, concurrent)
        await block_event.wait()
        concurrent -= 1
        orch.update_task_state(task["id"], {"passes": True, "commit_sha": "abc123"})
        bus.emit("task.completed", task["id"], "mock-agent", {})
        return {"task_id": task["id"], "status": "completed"}

    async def unblock():
        await asyncio.sleep(0.1)
        block_event.set()

    with patch.object(orch, "dispatch_task", side_effect=fake_dispatch):
        asyncio.create_task(unblock())
        await orch.run_global()

    assert max_concurrent <= 2


@pytest.mark.asyncio
async def test_dispatch_task_creates_agent_specific_and_legacy_logs(orchestrator, temp_project):
    """T-032: dispatch_task should write both agent-specific and legacy wave logs."""
    store = LocalStore(base_dir=str(temp_project))
    bus = AgentBus(version="v2", wave=1, store=store)
    task = {
        "id": "T-002",
        "passes": False,
        "story_id": "US-001",
        "title": "Log test task",
        "depends_on": [],
        "wave": 1,
        "type": "feat",
    }

    result = await orchestrator.dispatch_task(task, bus, store)
    assert result["task_id"] == "T-002"

    agent_id = "zeus-agent-T-002"
    base = temp_project / ".zeus" / "v2" / "agent-logs"

    # Legacy wave logs
    assert (base / "wave-1-events.jsonl").exists()
    assert (base / "wave-1-discussion.md").exists()

    # Agent-specific logs
    assert (base / agent_id / "reasoning.jsonl").exists()
    assert (base / agent_id / "activity.md").exists()

    # Verify agent reasoning content
    agent_bus = AgentBus(version="v2", wave=1, store=store, agent_id=agent_id)
    agent_events = agent_bus.get_agent_events()
    assert any(e["type"] == "task.started" for e in agent_events)
    assert any(e["type"] == "task.completed" for e in agent_events)

    # Verify legacy content via original bus
    legacy_events = bus.get_events()
    assert any(e["type"] == "task.started" for e in legacy_events)
    assert any(e["type"] == "task.completed" for e in legacy_events)


@pytest.mark.asyncio
async def test_stop_global_scheduler_persists_state(temp_project):
    """T-036-B: stop_global_scheduler persists running tasks to SQLite."""
    store = LocalStore(base_dir=str(temp_project))
    task_json = {
        "meta": {"current_wave": 1, "max_parallel_agents": 2},
        "tasks": [
            {"id": "T-001", "title": "Task 1", "passes": False, "status": "running", "depends_on": [], "wave": 1},
        ],
    }
    task_path = temp_project / ".zeus" / "v2" / "task.json"
    task_path.write_text(json.dumps(task_json), encoding="utf-8")

    orch = ZeusOrchestrator(version="v2", project_root=str(temp_project), max_parallel=2)
    orch._running_task_ids = {"T-001"}
    orch._bus = AgentBus(version="v2", wave=-1, store=store)

    orch.stop_global_scheduler()
    assert orch._shutdown is True

    db_path = temp_project / ".zeus" / "v2" / "scheduler_state.db"
    db = SchedulerStateDB(str(db_path))
    snapshot = db.load()
    assert snapshot["meta"]["scheduler_active"] is True
    assert any(at["task_id"] == "T-001" for at in snapshot["active_tasks"])


def test_resume_from_state_updates_task_json(temp_project):
    """T-036-C: resume_from_state restores task.json statuses from SQLite."""
    task_path = temp_project / ".zeus" / "v2" / "task.json"
    task_json = {
        "meta": {"current_wave": 1, "max_parallel_agents": 2},
        "tasks": [
            {"id": "T-001", "title": "Task 1", "passes": False, "status": "pending", "depends_on": [], "wave": 1},
            {"id": "T-002", "title": "Task 2", "passes": True, "status": "completed", "depends_on": [], "wave": 1},
        ],
    }
    task_path.write_text(json.dumps(task_json), encoding="utf-8")

    orch = ZeusOrchestrator(version="v2", project_root=str(temp_project), max_parallel=2)
    orch._running_task_ids = {"T-001"}
    orch._persist_scheduler_state()

    # Reset to pending to prove resume actually writes
    task_json["tasks"][0]["status"] = "failed"
    task_path.write_text(json.dumps(task_json), encoding="utf-8")

    recovered = orch.resume_from_state()
    assert "T-001" in recovered
    assert "T-002" not in recovered  # completed task should not be recovered

    updated = json.loads(task_path.read_text(encoding="utf-8"))
    assert next(t for t in updated["tasks"] if t["id"] == "T-001")["status"] == "running"


def test_scheduler_active_from_state(temp_project):
    """T-036-C: scheduler_active_from_state reads scheduler_active from SQLite."""
    orch = ZeusOrchestrator(version="v2", project_root=str(temp_project), max_parallel=2)
    assert orch.scheduler_active_from_state() is False

    orch._running_task_ids = {"T-001"}
    orch.stop_global_scheduler()
    assert orch.scheduler_active_from_state() is True

    orch._clear_scheduler_state()
    assert orch.scheduler_active_from_state() is False
