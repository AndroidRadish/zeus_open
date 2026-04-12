"""
Tests for scheduler_state.py
"""

import json
import threading
import tempfile
from pathlib import Path

import pytest

from scheduler_state import SchedulerStateDB


@pytest.fixture
def temp_db():
    """Provide a SchedulerStateDB backed by a temporary SQLite file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "scheduler_state.db"
        yield SchedulerStateDB(db_path=db_path)


def test_load_empty_db(temp_db: SchedulerStateDB):
    """Loading a freshly-initialised DB should return empty structures."""
    snapshot = temp_db.load()
    assert snapshot["meta"] == {}
    assert snapshot["active_tasks"] == []
    assert snapshot["mailbox"] == []


def test_save_and_load_round_trip(temp_db: SchedulerStateDB):
    meta = {"current_wave": 12, "phase": "P-003", "scheduling_mode": "adaptive"}
    active_tasks = [
        {
            "task_id": "T-036-A",
            "agent_id": "zeus-agent-T-036-A",
            "status": "running",
            "started_at": "2026-04-13T01:00:00Z",
            "wave": 12,
        },
        {
            "task_id": "T-035",
            "agent_id": "zeus-agent-T-035",
            "status": "completed",
            "started_at": "2026-04-12T20:00:00Z",
            "wave": 12,
        },
    ]
    mailbox = [
        {
            "to_agent_id": "zeus-agent-T-036-A",
            "from_agent_id": "scheduler",
            "message": "start task",
            "ts": "2026-04-13T01:05:00Z",
            "read": False,
        },
        {
            "to_agent_id": "scheduler",
            "from_agent_id": "zeus-agent-T-036-A",
            "message": "task complete",
            "ts": "2026-04-13T01:06:00Z",
            "read": True,
        },
    ]

    temp_db.save(meta=meta, active_tasks=active_tasks, mailbox=mailbox)
    snapshot = temp_db.load()

    assert snapshot["meta"] == meta
    assert snapshot["active_tasks"] == active_tasks
    assert snapshot["mailbox"] == mailbox


def test_save_overwrites_previous_data(temp_db: SchedulerStateDB):
    temp_db.save(meta={"wave": 1}, active_tasks=[{"task_id": "T-001"}], mailbox=[])
    temp_db.save(meta={"wave": 2}, active_tasks=[{"task_id": "T-002"}], mailbox=[])

    snapshot = temp_db.load()
    assert snapshot["meta"] == {"wave": 2}
    assert len(snapshot["active_tasks"]) == 1
    assert snapshot["active_tasks"][0]["task_id"] == "T-002"


def test_meta_json_round_trip(temp_db: SchedulerStateDB):
    """Meta values that are complex objects must round-trip through JSON."""
    complex_value = {"nested": {"list": [1, 2, 3], "bool": True, "null": None}}
    temp_db.set_meta("config", complex_value)
    assert temp_db.get_meta("config") == complex_value

    temp_db.set_meta("number", 42)
    assert temp_db.get_meta("number") == 42

    temp_db.set_meta("boolean", False)
    assert temp_db.get_meta("boolean") is False


def test_get_meta_missing_returns_default(temp_db: SchedulerStateDB):
    assert temp_db.get_meta("nonexistent") is None
    assert temp_db.get_meta("nonexistent", "default") == "default"


def test_clear_removes_all_data(temp_db: SchedulerStateDB):
    temp_db.save(
        meta={"wave": 1},
        active_tasks=[{"task_id": "T-001"}],
        mailbox=[{"to_agent_id": "a", "from_agent_id": "b", "message": "hi"}],
    )
    temp_db.clear()
    snapshot = temp_db.load()
    assert snapshot["meta"] == {}
    assert snapshot["active_tasks"] == []
    assert snapshot["mailbox"] == []


def test_save_without_mailbox_defaults_to_empty(temp_db: SchedulerStateDB):
    temp_db.save(meta={"wave": 1}, active_tasks=[])
    snapshot = temp_db.load()
    assert snapshot["mailbox"] == []


def test_mailbox_read_boolean_conversion(temp_db: SchedulerStateDB):
    """Ensure SQLite INTEGER 0/1 is correctly converted back to Python bool."""
    temp_db.save(
        meta={},
        active_tasks=[],
        mailbox=[
            {"to_agent_id": "a", "from_agent_id": "b", "message": "unread", "read": False},
            {"to_agent_id": "a", "from_agent_id": "b", "message": "read", "read": True},
        ],
    )
    snapshot = temp_db.load()
    assert snapshot["mailbox"][0]["read"] is False
    assert snapshot["mailbox"][1]["read"] is True


def test_active_tasks_defaults(temp_db: SchedulerStateDB):
    """Partial active task dicts should receive sensible defaults."""
    temp_db.save(
        meta={},
        active_tasks=[{"task_id": "T-999"}],
    )
    task = temp_db.load()["active_tasks"][0]
    assert task["task_id"] == "T-999"
    assert task["agent_id"] == ""
    assert task["status"] == "running"
    assert task["wave"] == 1
    assert "started_at" in task


def test_concurrent_saves_do_not_corrupt_db(temp_db: SchedulerStateDB):
    """Multiple threads saving simultaneously should not corrupt SQLite."""
    errors = []

    def worker(thread_idx: int):
        try:
            for i in range(20):
                temp_db.save(
                    meta={"thread": thread_idx, "iteration": i},
                    active_tasks=[{"task_id": f"T-{thread_idx}-{i}"}],
                    mailbox=[],
                )
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent save errors: {errors}"
    # After all saves, the DB should still be readable
    snapshot = temp_db.load()
    assert snapshot["meta"]["thread"] in range(5)
    assert len(snapshot["active_tasks"]) == 1


def test_db_path_directory_created_automatically():
    """If the parent directory for the DB does not exist, it should be created."""
    with tempfile.TemporaryDirectory() as tmpdir:
        nested = Path(tmpdir) / "deep" / "nested" / "state.db"
        assert not nested.parent.exists()
        db = SchedulerStateDB(db_path=nested)
        db.save(meta={"ok": True}, active_tasks=[])
        assert nested.exists()
