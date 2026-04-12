"""
Tests for subagent_dispatcher.py
"""

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_bus import AgentBus
from store import LocalStore
from subagent_dispatcher import (
    AutoSubagentDispatcher,
    ClaudeSubagentDispatcher,
    KimiSubagentDispatcher,
    MockSubagentDispatcher,
    build_dispatcher,
)


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_bus():
    bus = MagicMock(spec=AgentBus)
    bus.emit = MagicMock()
    bus.post = MagicMock()
    return bus


# -----------------------------------------------------------------------------
# MockSubagentDispatcher
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_mock_dispatcher_writes_marker_and_emits_events(temp_workspace, mock_bus):
    task = {"id": "T-001"}
    dispatcher = MockSubagentDispatcher()
    result = await dispatcher.run(task, temp_workspace, "do something", mock_bus)

    assert result["status"] == "completed"
    assert result["exit_code"] == 0
    assert result["task_id"] == "T-001"
    assert (temp_workspace / ".mock_done").exists()

    mock_bus.emit.assert_any_call("task.started", "T-001", "mock-agent", {"message": "Mock dispatching T-001"})
    mock_bus.emit.assert_any_call("task.completed", "T-001", "mock-agent", {"workspace": str(temp_workspace)})


# -----------------------------------------------------------------------------
# KimiSubagentDispatcher command construction
# -----------------------------------------------------------------------------
def test_kimi_build_command(temp_workspace):
    dispatcher = KimiSubagentDispatcher()
    cmd = dispatcher.build_command({"id": "T-002"}, temp_workspace, "hello world")
    assert cmd[0] == "kimi"
    assert "--print" in cmd
    assert "--prompt" in cmd
    assert "hello world" in cmd
    assert "--work-dir" in cmd
    assert str(temp_workspace) in cmd
    assert "--output-format" in cmd
    assert "text" in cmd


# -----------------------------------------------------------------------------
# ClaudeSubagentDispatcher command construction
# -----------------------------------------------------------------------------
def test_claude_build_command(temp_workspace):
    dispatcher = ClaudeSubagentDispatcher()
    cmd = dispatcher.build_command({"id": "T-003"}, temp_workspace, "fix bug")
    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "fix bug" in cmd
    assert "--allowedTools" in cmd
    assert "Read,Edit,Bash,Agent" in cmd
    assert "--cwd" in cmd
    assert str(temp_workspace) in cmd


# -----------------------------------------------------------------------------
# AutoSubagentDispatcher selection
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_auto_selects_kimi_when_available(temp_workspace, mock_bus):
    with patch.object(shutil, "which", side_effect=lambda name: name == "kimi"):
        auto = AutoSubagentDispatcher()
        # Patch KimiSubagentDispatcher.run to avoid real subprocess
        with patch.object(KimiSubagentDispatcher, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {"status": "completed"}
            result = await auto.run({"id": "T-004"}, temp_workspace, "prompt", mock_bus)
            assert result["status"] == "completed"
            mock_run.assert_awaited_once()


@pytest.mark.asyncio
async def test_auto_selects_claude_when_kimi_missing(temp_workspace, mock_bus):
    with patch.object(shutil, "which", side_effect=lambda name: name == "claude"):
        auto = AutoSubagentDispatcher()
        with patch.object(ClaudeSubagentDispatcher, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {"status": "completed"}
            result = await auto.run({"id": "T-005"}, temp_workspace, "prompt", mock_bus)
            assert result["status"] == "completed"
            mock_run.assert_awaited_once()


@pytest.mark.asyncio
async def test_auto_falls_back_to_mock_when_no_cli(temp_workspace, mock_bus):
    with patch.object(shutil, "which", return_value=None):
        auto = AutoSubagentDispatcher()
        result = await auto.run({"id": "T-006"}, temp_workspace, "prompt", mock_bus)
        assert result["status"] == "completed"
        assert (temp_workspace / ".mock_done").exists()


# -----------------------------------------------------------------------------
# build_dispatcher factory
# -----------------------------------------------------------------------------
def test_build_dispatcher_kimi():
    d = build_dispatcher({"subagent": {"dispatcher": "kimi"}})
    assert isinstance(d, KimiSubagentDispatcher)


def test_build_dispatcher_claude():
    d = build_dispatcher({"subagent": {"dispatcher": "claude"}})
    assert isinstance(d, ClaudeSubagentDispatcher)


def test_build_dispatcher_mock():
    d = build_dispatcher({"subagent": {"dispatcher": "mock"}})
    assert isinstance(d, MockSubagentDispatcher)


def test_build_dispatcher_auto_by_default():
    d = build_dispatcher()
    assert isinstance(d, AutoSubagentDispatcher)


def test_build_dispatcher_respects_timeout():
    d = build_dispatcher({"subagent": {"dispatcher": "kimi", "timeout_seconds": 120.0}})
    assert isinstance(d, KimiSubagentDispatcher)
    assert d.timeout_seconds == 120.0


# -----------------------------------------------------------------------------
# _CliDispatcher stdout capture and timeout
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cli_dispatcher_captures_stdout(temp_workspace, mock_bus):
    dispatcher = KimiSubagentDispatcher(timeout_seconds=5.0)

    async def fake_run(*args, **kwargs):
        # Manually simulate a successful subprocess that prints something
        proc = await asyncio.create_subprocess_exec(
            "python", "-c", "print('hello from subagent')",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(temp_workspace),
        )
        return await dispatcher.run({"id": "T-007"}, temp_workspace, "dummy prompt", mock_bus)

    # We can't easily mock create_subprocess_exec inline, so let's just run a real tiny process
    result = await dispatcher.run({"id": "T-007"}, temp_workspace, "dummy prompt", mock_bus)

    # Since 'kimi' may not exist on this machine, the subprocess will fail with FileNotFoundError
    # which gets caught as a generic exception in our run() method... wait, no.
    # Actually create_subprocess_exec will raise FileNotFoundError if 'kimi' is not found.
    # So this will fail unless we patch build_command.

    # Let's patch build_command to use a real command
    with patch.object(dispatcher, "build_command", return_value=["python", "-c", "print('hello')"]):
        result = await dispatcher.run({"id": "T-007"}, temp_workspace, "dummy prompt", mock_bus)

    assert result["status"] == "completed"
    assert result["exit_code"] == 0
    stdout_path = Path(result["stdout_path"])
    assert stdout_path.exists()
    assert "hello" in stdout_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_cli_dispatcher_timeout(temp_workspace, mock_bus):
    dispatcher = KimiSubagentDispatcher(timeout_seconds=0.1)

    with patch.object(dispatcher, "build_command", return_value=["python", "-c", "import time; time.sleep(10)"]):
        result = await dispatcher.run({"id": "T-008"}, temp_workspace, "dummy prompt", mock_bus)

    assert result["status"] == "failed"
    assert result["exit_code"] == -1
    mock_bus.emit.assert_any_call(
        "task.failed",
        "T-008",
        "kimi-cli",
        {"error": "subagent timeout", "stdout_path": str(temp_workspace / "T-008-stdout.txt")},
    )
