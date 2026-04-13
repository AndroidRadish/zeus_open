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

    async def run(self, task: dict[str, Any], workspace: Path, prompt: str) -> dict[str, Any]:
        tid = task["id"]
        stdout_path = workspace / f"{tid}-stdout.txt"
        cmd = self.build_command(task, workspace, prompt)

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
            return {
                "status": "failed",
                "changed_files": [],
                "test_summary": {"passed": 0, "failed": 0, "skipped": 0},
                "commit_sha": None,
                "artifacts": {"error": "subagent timeout", "stdout_path": str(stdout_path)},
            }

        # v3 PRIMARY check: read zeus-result.json
        zeus_result = self._read_zeus_result(workspace)
        if zeus_result is not None:
            return zeus_result

        # Fallback: exit_code (with stdout-crash tolerance)
        if exit_code != 0 and self._is_stdout_crash_only(stdout_path):
            return {
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

        if exit_code != 0:
            return {
                "status": "failed",
                "changed_files": [],
                "test_summary": {"passed": 0, "failed": 0, "skipped": 0},
                "commit_sha": None,
                "artifacts": {
                    "error": f"non-zero exit code {exit_code}",
                    "stdout_path": str(stdout_path),
                },
            }

        # Exit code 0 but no zeus-result.json -> treat as completed with empty result
        return {
            "status": "completed",
            "changed_files": [],
            "test_summary": {"passed": 0, "failed": 0, "skipped": 0},
            "commit_sha": None,
            "artifacts": {"warning": "no zeus-result.json found"},
        }


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

    async def run(self, task: dict[str, Any], workspace: Path, prompt: str) -> dict[str, Any]:
        if shutil.which("kimi"):
            dispatcher = KimiSubagentDispatcher(timeout_seconds=self.timeout_seconds)
        elif shutil.which("claude"):
            dispatcher = ClaudeSubagentDispatcher(timeout_seconds=self.timeout_seconds)
        else:
            dispatcher = __import__("dispatcher.mock", fromlist=["MockSubagentDispatcher"]).MockSubagentDispatcher()
        return await dispatcher.run(task, workspace, prompt)


def build_dispatcher(config: dict[str, Any] | None = None) -> SubagentDispatcher:
    cfg = config or {}
    subagent_cfg = cfg.get("subagent", {})
    mode = subagent_cfg.get("dispatcher", "auto")
    timeout = float(subagent_cfg.get("timeout_seconds", 600.0))

    if mode == "kimi":
        return KimiSubagentDispatcher(timeout_seconds=timeout)
    if mode == "claude":
        return ClaudeSubagentDispatcher(timeout_seconds=timeout)
    if mode == "mock":
        from dispatcher.mock import MockSubagentDispatcher
        return MockSubagentDispatcher()
    return AutoSubagentDispatcher(timeout_seconds=timeout)
