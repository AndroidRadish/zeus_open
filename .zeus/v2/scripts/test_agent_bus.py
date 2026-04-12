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


@pytest.fixture
def temp_agent_bus():
    """Provide an AgentBus with agent_id wired to a temporary .zeus directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            store = LocalStore(base_dir=tmpdir)
            bus = AgentBus(version="v2", wave=1, store=store, agent_id="zeus-agent-T-001")
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


# ---------------------------------------------------------------------------
# Agent-centric logs (T-032)
# ---------------------------------------------------------------------------
def test_agent_specific_events_and_activity(temp_agent_bus: AgentBus):
    bus = temp_agent_bus

    bus.emit("task.started", "T-001", "zeus-agent-T-001", {"step": 1})
    bus.post("T-001", "zeus-agent-T-001", "Working on task.")

    # Legacy wave logs should exist
    assert len(bus.get_events()) == 1
    assert "Working on task." in bus.get_discussion()

    # Agent-specific logs should exist
    agent_events = bus.get_agent_events()
    assert len(agent_events) == 1
    assert agent_events[0]["type"] == "task.started"

    activity = bus.get_activity()
    assert activity.startswith("# Agent zeus-agent-T-001 Activity Log")
    assert "Working on task." in activity


def test_both_legacy_and_agent_logs_exist(temp_agent_bus: AgentBus):
    bus = temp_agent_bus

    bus.emit("task.completed", "T-001", "zeus-agent-T-001", {})
    bus.post("T-001", "zeus-agent-T-001", "Done.")

    base = Path(".zeus/v2/agent-logs")
    assert (base / "wave-1-events.jsonl").exists()
    assert (base / "wave-1-discussion.md").exists()
    assert (base / "zeus-agent-T-001" / "reasoning.jsonl").exists()
    assert (base / "zeus-agent-T-001" / "activity.md").exists()


# ---------------------------------------------------------------------------
# Mailbox (T-031)
# ---------------------------------------------------------------------------
def test_send_and_receive_mailbox(temp_bus: AgentBus):
    bus = temp_bus
    bus.agent_id = "agent-a"

    msg = bus.send("agent-b", "Hello from A")
    assert msg["from"] == "agent-a"
    assert msg["to"] == "agent-b"
    assert msg["message"] == "Hello from A"
    assert msg["read"] is False

    # Receive as agent-b without marking read
    inbox = bus.receive("agent-b")
    assert len(inbox) == 1
    assert inbox[0]["message"] == "Hello from A"
    assert inbox[0]["read"] is False

    # Receive again and mark read
    inbox = bus.receive("agent-b", mark_read=True)
    assert len(inbox) == 1
    assert inbox[0]["read"] is True

    # Third receive should show read=True because file was updated
    inbox = bus.receive("agent-b")
    assert len(inbox) == 1
    assert inbox[0]["read"] is True


def test_receive_empty_mailbox(temp_bus: AgentBus):
    assert temp_bus.receive("nonexistent-agent") == []
