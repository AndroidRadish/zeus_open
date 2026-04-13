"""
Docker dispatcher unit tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dispatcher.docker import DockerSubagentDispatcher


def test_docker_command_builds_with_volumes():
    d = DockerSubagentDispatcher(image="python:3.13", memory_limit="512m", cpu_limit="1.5")
    task = {"id": "T-DOCKER"}
    workspace = Path("/tmp/.zeus/v3/agent-workspaces/zeus-agent-T-DOCKER")
    prompt = "do work"
    cmd = d._build_cmd(task, workspace, prompt)

    assert cmd[0] == "docker"
    assert "run" in cmd
    assert "--rm" in cmd
    assert "-m" in cmd
    assert "512m" in cmd
    assert "--cpus" in cmd
    assert "1.5" in cmd
    assert "python:3.13" in cmd


def test_docker_find_project_root_heuristic():
    d = DockerSubagentDispatcher()
    ws = Path("/tmp/.zeus/v3/agent-workspaces/zeus-agent-X")
    # Without real files, heuristic walks up and returns the first existing parent or the top
    root = d._find_project_root(ws)
    assert root is not None
