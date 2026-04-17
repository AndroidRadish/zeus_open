"""
Docker-based sandbox dispatcher for ZeusOpen v3.

Executes the subagent inside a Docker container with read-only source mounts,
resource cgroup limits, and optional output volume isolation.
"""
from __future__ import annotations

import asyncio
import json
import shutil
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
        pids_limit: int | None = None,
        blkio_weight: int | None = None,
        read_only: bool = True,
        network_disabled: bool = True,
        security_opts: list[str] | None = None,
        cap_drop: list[str] | None = None,
        extra_volumes: list[str] | None = None,
        output_volume_path: str | None = None,
    ) -> None:
        self.image = image
        self.timeout_seconds = timeout_seconds
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.pids_limit = pids_limit
        self.blkio_weight = blkio_weight
        self.read_only = read_only
        self.network_disabled = network_disabled
        self.security_opts = security_opts or []
        self.cap_drop = cap_drop or ["ALL"]
        self.extra_volumes = extra_volumes or []
        self.output_volume_path = output_volume_path

    def _build_cmd(
        self,
        task: dict[str, Any],
        workspace: Path,
        prompt: str,
    ) -> list[str]:
        tid = task["id"]
        project_root = self._find_project_root(workspace)

        container_ws = f"/zeus/agent-workspaces/zeus-agent-{tid}"
        container_project = "/zeus/project"
        container_output = f"{container_ws}/output"

        cmd = [
            "docker", "run", "--rm",
            "-v", f"{workspace}:{container_ws}",
            "-v", f"{project_root}:{container_project}:ro",
            "-w", str(container_ws),
        ]

        if self.read_only:
            cmd.append("--read-only")

        if self.memory_limit:
            cmd.extend(["-m", self.memory_limit])
        if self.cpu_limit:
            cmd.extend(["--cpus", self.cpu_limit])
        if self.pids_limit is not None:
            cmd.extend(["--pids-limit", str(self.pids_limit)])
        if self.blkio_weight is not None:
            cmd.extend(["--blkio-weight", str(self.blkio_weight)])

        if self.network_disabled:
            cmd.extend(["--network", "none"])

        for opt in self.security_opts:
            cmd.extend(["--security-opt", opt])

        for cap in self.cap_drop:
            cmd.extend(["--cap-drop", cap])

        for vol in self.extra_volumes:
            cmd.extend(["-v", vol])

        # Write prompt to a temp file inside workspace so the container can read it
        workspace.mkdir(parents=True, exist_ok=True)
        prompt_file = workspace / ".docker-prompt.txt"
        prompt_file.write_text(prompt, encoding="utf-8")
        cmd.extend(["-e", f"ZEUS_PROMPT_FILE={container_ws}/.docker-prompt.txt"])

        # Determine where to write zeus-result.json
        if self.output_volume_path:
            out_host = Path(self.output_volume_path)
            out_host.mkdir(parents=True, exist_ok=True)
            cmd.extend(["-v", f"{out_host}:{container_output}"])
            result_path = f"{container_output}/zeus-result.json"
        else:
            result_path = f"{container_ws}/zeus-result.json"

        # Build the inner command that writes zeus-result.json
        result_stub = {
            "status": "completed",
            "changed_files": [],
            "test_summary": {"passed": 0, "failed": 0, "skipped": 0},
            "commit_sha": "",
            "artifacts": {"note": "Docker dispatcher stub: implement real agent command"},
        }
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

        # If output volume isolation was used, copy zeus-result.json back to workspace
        if self.output_volume_path:
            src = Path(self.output_volume_path) / "zeus-result.json"
            dst = workspace / "zeus-result.json"
            if src.exists():
                shutil.copy2(str(src), str(dst))

        if bus:
            bus.emit("task.completed", {"task_id": tid, "agent_name": "docker"})
        return {"status": "completed"}
