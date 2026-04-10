"""
Tests for agent_bus.py
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from agent_bus import AgentBus
from store import LocalStore


@pytest.fixture
def temp_bus():
    """Provide an AgentBus wired to a temporary .zeus directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            store = LocalStore(base_dir=tmpdir)
            bus = AgentBus(version="v2", wave=1, store=store)
            yield bus
        finally:
            os.chdir(old_cwd)


def test_emit_and_read_events(temp_bus: AgentBus):
    bus = temp_bus

    evt = bus.emit(
        event_type="task.started",
        task_id="T-001",
        agent_id="coder-0",
        payload={"message": "hello"},
    )

    assert evt["type"] == "task.started"
    assert evt["wave"] == 1
    assert evt["task_id"] == "T-001"
    assert evt["agent_id"] == "coder-0"
    assert evt["payload"]["message"] == "hello"
    assert "ts" in evt

    events = bus.get_events()
    assert len(events) == 1
    assert events[0]["type"] == "task.started"

    # Filter by type
    assert len(bus.get_events(event_type="task.completed")) == 0
    assert len(bus.get_events(event_type="task.started")) == 1

    # Filter by task_id
    assert len(bus.get_events(task_id="T-999")) == 0
    assert len(bus.get_events(task_id="T-001")) == 1


def test_post_and_read_discussion(temp_bus: AgentBus):
    bus = temp_bus

    block = bus.post(
        task_id="T-001",
        agent_id="coder-0",
        message="Started working on `T-001`.\nPlan: create files.",
    )

    assert "coder-0 (T-001)" in block
    assert "Started working" in block

    md = bus.get_discussion()
    assert md.startswith("# Wave 1 Discussion Log")
    assert "coder-0 (T-001)" in md
    assert "Started working on `T-001`." in md


def test_multiple_tasks_in_same_wave(temp_bus: AgentBus):
    bus = temp_bus

    bus.emit("task.started", "T-001", "coder-0", {"step": 1})
    bus.emit("task.progress", "T-001", "coder-0", {"step": 2})
    bus.emit("task.started", "T-002", "coder-1", {"step": 1})
    bus.emit("task.completed", "T-001", "coder-0", {"step": 3})

    all_events = bus.get_events()
    assert len(all_events) == 4

    t001 = bus.get_events(task_id="T-001")
    assert len(t001) == 3
    assert [e["type"] for e in t001] == ["task.started", "task.progress", "task.completed"]

    t002 = bus.get_events(task_id="T-002")
    assert len(t002) == 1
    assert t002[0]["type"] == "task.started"

    started = bus.get_events(event_type="task.started")
    assert len(started) == 2

    # Discussion side
    bus.post("T-001", "coder-0", "Done with T-001.")
    bus.post("T-002", "coder-1", "Starting T-002.")

    md = bus.get_discussion()
    assert md.count("## ") == 2
    assert "Done with T-001." in md
    assert "Starting T-002." in md


def test_unsupported_event_type(temp_bus: AgentBus):
    with pytest.raises(ValueError, match="Unsupported event type"):
        temp_bus.emit("unknown.event", "T-001", "coder-0")
