from pathlib import Path
from typing import Any

from workspace.base import BaseWorkspaceManager
from workspace.git_worktree import GitWorktreeWorkspaceManager
from workspace.manager import WorkspaceManager


__all__ = [
    "BaseWorkspaceManager",
    "WorkspaceManager",
    "GitWorktreeWorkspaceManager",
    "build_workspace_manager",
]


def build_workspace_manager(project_root: Path, version: str = "v3", backend: str | None = None) -> BaseWorkspaceManager:
    if backend is None:
        from config import ZeusConfig
        backend = ZeusConfig(project_root, version).workspace_backend

    if backend == "git_worktree":
        return GitWorktreeWorkspaceManager(project_root, version)
    return WorkspaceManager(project_root, version)
