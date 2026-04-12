"""
subagent_dispatcher.py — ZeusOpen v2 子 Agent 调度器抽象层

支持平台：
- Mock（向后兼容，仅写标记文件）
- Kimi CLI（kimi --print）
- Claude Code（claude -p）
- Auto（自动检测可用 CLI）
"""

from __future__ import annotations

import abc
import asyncio
import shutil
from pathlib import Path
from typing import Any

from agent_bus import AgentBus


class SubagentDispatcher(abc.ABC):
    """
    子 Agent 调度器抽象基类。

    负责在隔离 workspace 中真正执行任务，并通过 AgentBus 上报生命周期事件。
    """

    @abc.abstractmethod
    async def run(
        self,
        task: dict[str, Any],
        workspace: Path,
        prompt: str,
        bus: AgentBus,
    ) -> dict[str, Any]:
        """
        在 *workspace* 中执行任务并返回结果。

        必须向 bus 发送 task.started 和 task.completed / task.failed 事件。
        """
        raise NotImplementedError


class MockSubagentDispatcher(SubagentDispatcher):
    """模拟调度器：立即返回，用于测试和向后兼容。"""

    async def run(
        self,
        task: dict[str, Any],
        workspace: Path,
        prompt: str,
        bus: AgentBus,
    ) -> dict[str, Any]:
        tid = task["id"]
        bus.emit("task.started", tid, "mock-agent", {"message": f"Mock dispatching {tid}"})
        bus.post(tid, "mock-agent", f"模拟执行 **{tid}** 完成（无外部 CLI）")
        (workspace / ".mock_done").write_text("done", encoding="utf-8")
        bus.emit("task.completed", tid, "mock-agent", {"workspace": str(workspace)})
        return {
            "task_id": tid,
            "status": "completed",
            "exit_code": 0,
            "stdout_path": None,
            "workspace": str(workspace),
        }


class _CliDispatcher(SubagentDispatcher):
    """CLI 调度器公共基类，处理 stdout 捕获、超时和统一事件上报。"""

    def __init__(self, timeout_seconds: float = 600.0):
        self.timeout_seconds = timeout_seconds

    @abc.abstractmethod
    def agent_name(self) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def build_command(self, task: dict[str, Any], workspace: Path, prompt: str) -> list[str]:
        """构造子进程命令行参数列表。"""
        raise NotImplementedError

    async def _stream_stdout(
        self,
        proc: asyncio.subprocess.Process,
        stdout_path: Path,
    ) -> None:
        """将子进程 stdout 实时写入文件。"""
        with open(stdout_path, "w", encoding="utf-8") as f:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                f.write(line.decode("utf-8", errors="replace"))
                f.flush()

    async def run(
        self,
        task: dict[str, Any],
        workspace: Path,
        prompt: str,
        bus: AgentBus,
    ) -> dict[str, Any]:
        tid = task["id"]
        stdout_path = workspace / f"{tid}-stdout.txt"
        cmd = self.build_command(task, workspace, prompt)

        bus.emit("task.started", tid, self.agent_name(), {"command": " ".join(cmd)})
        bus.post(tid, self.agent_name(), f"启动外部 Agent: `{' '.join(cmd)}`")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(workspace),
        )

        try:
            await asyncio.wait_for(
                self._stream_stdout(proc, stdout_path),
                timeout=self.timeout_seconds,
            )
            exit_code = await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            bus.emit(
                "task.failed",
                tid,
                self.agent_name(),
                {"error": "subagent timeout", "stdout_path": str(stdout_path)},
            )
            bus.post(tid, self.agent_name(), f"任务 **{tid}** 执行超时（>{self.timeout_seconds}s）")
            return {
                "task_id": tid,
                "status": "failed",
                "exit_code": -1,
                "stdout_path": str(stdout_path),
                "workspace": str(workspace),
            }

        if exit_code != 0:
            bus.emit(
                "task.failed",
                tid,
                self.agent_name(),
                {"exit_code": exit_code, "stdout_path": str(stdout_path)},
            )
            bus.post(tid, self.agent_name(), f"任务 **{tid}** 外部 Agent 返回非零退出码 `{exit_code}`")
            return {
                "task_id": tid,
                "status": "failed",
                "exit_code": exit_code,
                "stdout_path": str(stdout_path),
                "workspace": str(workspace),
            }

        bus.emit(
            "task.completed",
            tid,
            self.agent_name(),
            {"exit_code": exit_code, "stdout_path": str(stdout_path)},
        )
        bus.post(tid, self.agent_name(), f"任务 **{tid}** 外部 Agent 执行完成（exit code {exit_code}）")
        return {
            "task_id": tid,
            "status": "completed",
            "exit_code": exit_code,
            "stdout_path": str(stdout_path),
            "workspace": str(workspace),
        }


class KimiSubagentDispatcher(_CliDispatcher):
    """通过 Kimi CLI（kimi --print）执行任务的调度器。"""

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


class ClaudeSubagentDispatcher(_CliDispatcher):
    """通过 Claude Code CLI（claude -p）执行任务的调度器。"""

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
    """
    自动检测环境并选择可用调度器：
    1. Kimi CLI
    2. Claude CLI
    3. Mock fallback
    """

    def __init__(self, timeout_seconds: float = 600.0):
        self.timeout_seconds = timeout_seconds

    async def run(
        self,
        task: dict[str, Any],
        workspace: Path,
        prompt: str,
        bus: AgentBus,
    ) -> dict[str, Any]:
        if shutil.which("kimi"):
            dispatcher: SubagentDispatcher = KimiSubagentDispatcher(timeout_seconds=self.timeout_seconds)
        elif shutil.which("claude"):
            dispatcher = ClaudeSubagentDispatcher(timeout_seconds=self.timeout_seconds)
        else:
            dispatcher = MockSubagentDispatcher()
        return await dispatcher.run(task, workspace, prompt, bus)


def build_dispatcher(config: dict[str, Any] | None = None) -> SubagentDispatcher:
    """
    根据配置构造调度器实例。

    支持的 config.subagent.dispatcher 值：
    - "auto"（默认）
    - "kimi"
    - "claude"
    - "mock"
    """
    cfg = config or {}
    subagent_cfg = cfg.get("subagent", {})
    mode = subagent_cfg.get("dispatcher", "auto")
    timeout = subagent_cfg.get("timeout_seconds", 600.0)

    if mode == "kimi":
        return KimiSubagentDispatcher(timeout_seconds=timeout)
    if mode == "claude":
        return ClaudeSubagentDispatcher(timeout_seconds=timeout)
    if mode == "mock":
        return MockSubagentDispatcher()
    return AutoSubagentDispatcher(timeout_seconds=timeout)
