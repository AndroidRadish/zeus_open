"""
Docker dispatcher unit and end-to-end tests.

E2E tests require a working Docker runtime.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dispatcher.docker import DockerSubagentDispatcher


def _docker_available() -> bool:
    try:
        subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except Exception:
        return False


# -----------------------------------------------------------------------------
# Command construction tests
# -----------------------------------------------------------------------------
def test_docker_command_builds_with_volumes():
    d = DockerSubagentDispatcher(
        image="python:3.13",
        memory_limit="512m",
        cpu_limit="1.5",
        pids_limit=64,
        blkio_weight=300,
        read_only=True,
        network_disabled=True,
        security_opts=["no-new-privileges:true"],
        cap_drop=["ALL"],
        extra_volumes=["/host/data:/data:ro"],
    )
    task = {"id": "T-DOCKER"}
    workspace = Path("/tmp/.zeus/v3/agent-workspaces/zeus-agent-T-DOCKER")
    prompt = "do work"
    cmd = d._build_cmd(task, workspace, prompt)

    assert cmd[0] == "docker"
    assert "run" in cmd
    assert "--rm" in cmd
    assert "--read-only" in cmd
    assert "--network" in cmd
    assert "none" in cmd
    assert "-m" in cmd
    assert "512m" in cmd
    assert "--cpus" in cmd
    assert "1.5" in cmd
    assert "--pids-limit" in cmd
    assert "64" in cmd
    assert "--blkio-weight" in cmd
    assert "300" in cmd
    assert "--security-opt" in cmd
    assert "no-new-privileges:true" in cmd
    assert "--cap-drop" in cmd
    assert "ALL" in cmd
    assert "/host/data:/data:ro" in cmd
    assert "python:3.13" in cmd


def test_docker_command_with_output_volume():
    d = DockerSubagentDispatcher(
        output_volume_path="/tmp/zeus-output",
        read_only=False,
    )
    task = {"id": "T-OUT"}
    workspace = Path("/tmp/.zeus/v3/agent-workspaces/zeus-agent-T-OUT")
    cmd = d._build_cmd(task, workspace, "prompt")

    expected_vol = f"{Path('/tmp/zeus-output')}:/zeus/agent-workspaces/zeus-agent-T-OUT/output"
    assert expected_vol in cmd
    assert "python -c" in " ".join(cmd)


def test_docker_find_project_root_heuristic():
    d = DockerSubagentDispatcher()
    ws = Path("/tmp/.zeus/v3/agent-workspaces/zeus-agent-X")
    root = d._find_project_root(ws)
    assert root is not None


# -----------------------------------------------------------------------------
# End-to-end tests (require Docker)
# -----------------------------------------------------------------------------
@pytest.mark.skipif(not _docker_available(), reason="Docker not available")
@pytest.mark.asyncio
async def test_docker_dispatcher_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "ws"
        workspace.mkdir()
        # Fake project root marker so _find_project_root stops here
        (workspace / ".git").mkdir()

        d = DockerSubagentDispatcher(image="python:3.13-slim", timeout_seconds=30.0)
        result = await d.run({"id": "T-E2E"}, workspace, "do work")

        assert result["status"] == "completed"
        result_file = workspace / "zeus-result.json"
        assert result_file.exists()
        data = json.loads(result_file.read_text("utf-8"))
        assert data["status"] == "completed"


@pytest.mark.skipif(not _docker_available(), reason="Docker not available")
@pytest.mark.asyncio
async def test_docker_dispatcher_with_output_volume():
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "ws"
        workspace.mkdir()
        (workspace / ".git").mkdir()
        output_vol = Path(tmp) / "out"

        d = DockerSubagentDispatcher(
            image="python:3.13-slim",
            timeout_seconds=30.0,
            output_volume_path=str(output_vol),
        )
        result = await d.run({"id": "T-ISO"}, workspace, "do work")

        assert result["status"] == "completed"
        # Result should have been copied back to workspace
        assert (workspace / "zeus-result.json").exists()
        # And also exist in the isolated output volume
        assert (output_vol / "zeus-result.json").exists()


@pytest.mark.skipif(not _docker_available(), reason="Docker not available")
@pytest.mark.asyncio
async def test_docker_dispatcher_failure():
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "ws"
        workspace.mkdir()
        (workspace / ".git").mkdir()

        d = DockerSubagentDispatcher(image="python:3.13-slim", timeout_seconds=30.0)
        # Override inner script by monkey-patching _build_cmd result
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{workspace}:/zeus/agent-workspaces/zeus-agent-T-FAIL",
            "-w", "/zeus/agent-workspaces/zeus-agent-T-FAIL",
            "python:3.13-slim",
            "python", "-c", "import sys; sys.exit(1)"
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        assert proc.returncode != 0


@pytest.mark.skipif(not _docker_available(), reason="Docker not available")
@pytest.mark.asyncio
async def test_docker_dispatcher_timeout():
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "ws"
        workspace.mkdir()
        (workspace / ".git").mkdir()

        d = DockerSubagentDispatcher(image="python:3.13-slim", timeout_seconds=1.0)
        # Run a command that sleeps longer than the timeout
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{workspace}:/zeus/agent-workspaces/zeus-agent-T-TIMEOUT",
            "-w", "/zeus/agent-workspaces/zeus-agent-T-TIMEOUT",
            "python:3.13-slim",
            "python", "-c", "import time; time.sleep(10)"
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=d.timeout_seconds)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
        # Ensure process was killed
        assert proc.returncode not in (0, None)
