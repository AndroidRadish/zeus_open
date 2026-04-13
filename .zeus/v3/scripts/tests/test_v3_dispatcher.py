"""
Tests for v3 dispatcher command construction and subprocess integration.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dispatcher.cli import KimiSubagentDispatcher, ClaudeSubagentDispatcher, build_dispatcher


def test_kimi_command_build():
    d = KimiSubagentDispatcher(timeout_seconds=300.0)
    cmd = d.build_command(
        {"id": "T-K01"},
        Path("/tmp/ws"),
        "do something",
    )
    assert cmd[0] == "kimi"
    assert "--yolo" in cmd
    assert "--work-dir" in cmd
    assert str(Path("/tmp/ws")) in cmd
    assert "do something" in cmd


def test_claude_command_build():
    d = ClaudeSubagentDispatcher(timeout_seconds=300.0)
    cmd = d.build_command(
        {"id": "T-C01"},
        Path("/tmp/ws"),
        "fix bug",
    )
    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "fix bug" in cmd
    assert "--allowedTools" in cmd
    assert "Read,Edit,Bash,Agent" in cmd


def test_build_dispatcher_mock():
    from dispatcher.mock import MockSubagentDispatcher
    d = build_dispatcher({"subagent": {"dispatcher": "mock"}})
    assert isinstance(d, MockSubagentDispatcher)


def test_build_dispatcher_kimi():
    d = build_dispatcher({"subagent": {"dispatcher": "kimi", "timeout_seconds": 120}})
    assert isinstance(d, KimiSubagentDispatcher)
