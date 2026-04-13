"""
Git worktree workspace manager tests.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workspace.git_worktree import GitWorktreeWorkspaceManager


@pytest_asyncio.fixture
async def git_project(tmp_path):
    """Initialize a minimal git repo for worktree tests."""
    (tmp_path / ".zeus" / "v3" / "config.json").parent.mkdir(parents=True)
    (tmp_path / ".zeus" / "v3" / "config.json").write_text(
        json.dumps({"project": {"name": "Git"}, "metrics": {"north_star": "n"}, "subagent": {"dispatcher": "mock"}}),
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("# main\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("# agents\n", encoding="utf-8")

    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True, check=True)

    yield tmp_path


@pytest.mark.asyncio
async def test_git_worktree_prepares_workspace(git_project):
    manager = GitWorktreeWorkspaceManager(git_project, "v3")
    task = {"id": "T-GIT-1", "title": "Test", "description": "D", "type": "feat", "files": [], "depends_on": [], "wave": 1}
    ws = await manager.prepare(task)

    assert ws.exists()
    assert (ws / "src" / "main.py").exists()
    assert (ws / "PROMPT.md").exists()
    assert (ws / "AGENTS.md").exists()

    # Verify it's a real git worktree
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=str(git_project),
        capture_output=True,
        text=True,
        check=True,
    )
    assert ws.as_posix() in result.stdout.replace("/", "\\") or ws.as_posix() in result.stdout


@pytest.mark.asyncio
async def test_git_worktree_reprepare_cleans_old(git_project):
    manager = GitWorktreeWorkspaceManager(git_project, "v3")
    task = {"id": "T-GIT-2", "title": "Test", "description": "D", "type": "feat", "files": [], "depends_on": [], "wave": 1}
    ws1 = await manager.prepare(task)
    marker = ws1 / "marker.txt"
    marker.write_text("old", encoding="utf-8")

    ws2 = await manager.prepare(task)
    assert ws1 == ws2
    assert not marker.exists()
    assert (ws2 / "PROMPT.md").exists()
