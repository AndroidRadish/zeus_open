"""
CLI-based subagent dispatchers for Kimi and Claude.

Key v3 improvement: after the subprocess exits, we FIRST read zeus-result.json
from the workspace. Only if it is missing do we fall back to exit_code.
"""
from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

from dispatcher.base import SubagentDispatcher


class _BaseCliDispatcher(SubagentDispatcher):
    def __init__(self, timeout_seconds: float = 600.0):
        self.timeout_seconds = timeout_seconds

    def agent_name(self) -> str:
        raise NotImplementedError

    def build_command(self, task: dict[str, Any], workspace: Path, prompt: str) -> list[str]:
        raise NotImplementedError

    async def _stream_stdout(self, proc: asyncio.subprocess.Process, stdout_path: Path) -> None:
        with open(stdout_path, "w", encoding="utf-8") as f:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                f.write(line.decode("utf-8", errors="replace"))
                f.flush()

    def _is_stdout_crash_only(self, stdout_path: Path) -> bool:
        if not stdout_path.exists():
            return False
        try:
            text = stdout_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return False
        patterns = [
            "'gbk' codec can't encode character",
            "'cp936' codec can't encode character",
            "'ascii' codec can't encode character",
        ]
        return any(p in text for p in patterns)

    def _read_zeus_result(self, workspace: Path) -> dict[str, Any] | None:
        path = workspace / "zeus-result.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    async def run(self, task: dict[str, Any], workspace: Path, prompt: str, bus=None) -> dict[str, Any]:
        tid = task["id"]
        stdout_path = workspace / f"{tid}-stdout.txt"
        cmd = self.build_command(task, workspace, prompt)

        if bus:
            bus.emit("task.started", {"task_id": tid, "agent_name": self.agent_name(), "command": cmd})

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(workspace),
        )

        try:
            await asyncio.wait_for(self._stream_stdout(proc, stdout_path), timeout=self.timeout_seconds)
            exit_code = await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            result = {
                "status": "failed",
                "changed_files": [],
                "test_summary": {"passed": 0, "failed": 0, "skipped": 0},
                "commit_sha": None,
                "artifacts": {"error": "subagent timeout", "stdout_path": str(stdout_path)},
            }
            if bus:
                bus.emit("task.failed", {"task_id": tid, "agent_name": self.agent_name(), "error": "subagent timeout"})
            return result

        # v3 PRIMARY check: read zeus-result.json
        zeus_result = self._read_zeus_result(workspace)
        if zeus_result is not None:
            if bus:
                if zeus_result.get("status") == "completed":
                    bus.emit("task.completed", {"task_id": tid, "agent_name": self.agent_name(), "commit_sha": zeus_result.get("commit_sha")})
                else:
                    bus.emit("task.failed", {"task_id": tid, "agent_name": self.agent_name(), "error": zeus_result.get("artifacts", {}).get("error", "dispatcher_failed")})
            return zeus_result

        # Fallback: exit_code (with stdout-crash tolerance)
        if exit_code != 0 and self._is_stdout_crash_only(stdout_path):
            result = {
                "status": "completed",
                "changed_files": [],
                "test_summary": {"passed": 0, "failed": 0, "skipped": 0},
                "commit_sha": None,
                "artifacts": {
                    "warning": "stdout encoding crash",
                    "exit_code": exit_code,
                    "stdout_path": str(stdout_path),
                },
            }
            if bus:
                bus.emit("task.completed", {"task_id": tid, "agent_name": self.agent_name(), "warning": "stdout encoding crash"})
            return result

        if exit_code != 0:
            result = {
                "status": "failed",
                "changed_files": [],
                "test_summary": {"passed": 0, "failed": 0, "skipped": 0},
                "commit_sha": None,
                "artifacts": {
                    "error": f"non-zero exit code {exit_code}",
                    "stdout_path": str(stdout_path),
                },
            }
            if bus:
                bus.emit("task.failed", {"task_id": tid, "agent_name": self.agent_name(), "error": f"non-zero exit code {exit_code}"})
            return result

        # Exit code 0 but no zeus-result.json -> treat as completed with empty result
        result = {
            "status": "completed",
            "changed_files": [],
            "test_summary": {"passed": 0, "failed": 0, "skipped": 0},
            "commit_sha": None,
            "artifacts": {"warning": "no zeus-result.json found"},
        }
        if bus:
            bus.emit("task.completed", {"task_id": tid, "agent_name": self.agent_name(), "warning": "no zeus-result.json found"})
        return result


class KimiSubagentDispatcher(_BaseCliDispatcher):
    def agent_name(self) -> str:
        return "kimi-cli"

    def build_command(self, task: dict[str, Any], workspace: Path, prompt: str) -> list[str]:
        return [
            "kimi",
            "--print",
            "--yolo",
            "--prompt", prompt,
            "--work-dir", str(workspace),
            "--output-format", "text",
        ]


class ClaudeSubagentDispatcher(_BaseCliDispatcher):
    def agent_name(self) -> str:
        return "claude-cli"

    def build_command(self, task: dict[str, Any], workspace: Path, prompt: str) -> list[str]:
        return [
            "claude",
            "-p", prompt,
            "--allowedTools", "Read,Edit,Bash,Agent",
            "--cwd", str(workspace),
        ]


class AutoSubagentDispatcher(SubagentDispatcher):
    """Auto-detect available CLI and delegate."""

    def __init__(self, timeout_seconds: float = 600.0):
        self.timeout_seconds = timeout_seconds

    async def run(self, task: dict[str, Any], workspace: Path, prompt: str, bus=None) -> dict[str, Any]:
        if shutil.which("kimi"):
            dispatcher = KimiSubagentDispatcher(timeout_seconds=self.timeout_seconds)
        elif shutil.which("claude"):
            dispatcher = ClaudeSubagentDispatcher(timeout_seconds=self.timeout_seconds)
        else:
            dispatcher = __import__("dispatcher.mock", fromlist=["MockSubagentDispatcher"]).MockSubagentDispatcher()
        return await dispatcher.run(task, workspace, prompt, bus=bus)


def build_dispatcher(config: dict[str, Any] | None = None) -> SubagentDispatcher:
    cfg = config or {}
    subagent_cfg = cfg.get("subagent", {})
    mode = subagent_cfg.get("dispatcher", "auto")
    timeout = float(subagent_cfg.get("timeout_seconds", 600.0))

    if mode == "kimi":
        return KimiSubagentDispatcher(timeout_seconds=timeout)
    if mode == "claude":
        return ClaudeSubagentDispatcher(timeout_seconds=timeout)
    if mode == "docker":
        from dispatcher.docker import DockerSubagentDispatcher
        docker_cfg = subagent_cfg.get("docker", {})
        return DockerSubagentDispatcher(
            image=docker_cfg.get("image", "python:3.13-slim"),
            timeout_seconds=timeout,
            memory_limit=docker_cfg.get("memory_limit"),
            cpu_limit=docker_cfg.get("cpu_limit"),
            extra_volumes=docker_cfg.get("extra_volumes"),
        )
    if mode == "mock":
        from dispatcher.mock import MockSubagentDispatcher
        return MockSubagentDispatcher()
    return AutoSubagentDispatcher(timeout_seconds=timeout)
