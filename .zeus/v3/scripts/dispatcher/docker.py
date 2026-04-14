"""
Docker-based sandbox dispatcher for ZeusOpen v3.

Executes the subagent inside a Docker container with read-only source mounts
and a writable workspace volume.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from dispatcher.base import SubagentDispatcher


class DockerSubagentDispatcher(SubagentDispatcher):
    """Run the subagent inside a Docker container."""

    def __init__(
        self,
        image: str = "python:3.13-slim",
        timeout_seconds: float = 600.0,
        memory_limit: str | None = None,
        cpu_limit: str | None = None,
        extra_volumes: list[str] | None = None,
    ) -> None:
        self.image = image
        self.timeout_seconds = timeout_seconds
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.extra_volumes = extra_volumes or []

    def _build_cmd(
        self,
        task: dict[str, Any],
        workspace: Path,
        prompt: str,
    ) -> list[str]:
        tid = task["id"]
        # We assume the workspace is prepared under project_root/.zeus/v3/agent-workspaces/...
        # Mount the workspace as writable, and the project root as read-only
        project_root = self._find_project_root(workspace)

        container_ws = f"/zeus/agent-workspaces/zeus-agent-{tid}"
        container_project = "/zeus/project"

        cmd = [
            "docker", "run", "--rm",
            "-v", f"{workspace}:{container_ws}",
            "-v", f"{project_root}:{container_project}:ro",
            "-w", str(container_ws),
        ]

        if self.memory_limit:
            cmd.extend(["-m", self.memory_limit])
        if self.cpu_limit:
            cmd.extend(["--cpus", self.cpu_limit])

        for vol in self.extra_volumes:
            cmd.extend(["-v", vol])

        # Write prompt to a temp file inside workspace so the container can read it
        workspace.mkdir(parents=True, exist_ok=True)
        prompt_file = workspace / ".docker-prompt.txt"
        prompt_file.write_text(prompt, encoding="utf-8")
        cmd.extend(["-e", f"ZEUS_PROMPT_FILE={container_ws}/.docker-prompt.txt"])

        # Build the inner command that writes zeus-result.json
        result_stub = {
            "status": "completed",
            "changed_files": [],
            "test_summary": {"passed": 0, "failed": 0, "skipped": 0},
            "commit_sha": "",
            "artifacts": {"note": "Docker dispatcher stub: implement real agent command"},
        }
        result_path = f"{container_ws}/zeus-result.json"
        inner_script = (
            f"import json; "
            f"json.dump({json.dumps(result_stub)}, open('{result_path}', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)"
        )

        cmd.append(self.image)
        cmd.extend(["python", "-c", inner_script])
        return cmd

    def _find_project_root(self, workspace: Path) -> Path:
        # Heuristic: walk up from workspace until we hit .git or .zeus/v3/config.json
        path = workspace
        for _ in range(10):
            if (path / ".git").exists() or (path / ".zeus" / "v3" / "config.json").exists():
                return path
            parent = path.parent
            if parent == path:
                break
            path = parent
        return path

    async def run(self, task: dict[str, Any], workspace: Path, prompt: str, bus=None) -> dict[str, Any]:
        tid = task["id"]
        if bus:
            bus.emit("task.started", {"task_id": tid, "agent_name": "docker"})
        cmd = self._build_cmd(task, workspace, prompt)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            if bus:
                bus.emit("task.failed", {"task_id": tid, "agent_name": "docker", "error": "docker dispatcher timeout"})
            return {"status": "failed", "error": "docker dispatcher timeout"}

        if proc.returncode != 0:
            if bus:
                bus.emit("task.failed", {"task_id": tid, "agent_name": "docker", "error": f"exit code {proc.returncode}"})
            return {
                "status": "failed",
                "exit_code": proc.returncode,
                "stderr": stderr.decode("utf-8", errors="replace")[:2000],
            }
        if bus:
            bus.emit("task.completed", {"task_id": tid, "agent_name": "docker"})
        return {"status": "completed"}
