"""
Workspace isolation manager for ZeusOpen v3 (copytree backend).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from workspace.base import BaseWorkspaceManager


class WorkspaceManager(BaseWorkspaceManager):
    """Prepare isolated agent workspaces using shutil.copytree."""

    async def prepare(self, task: dict[str, Any]) -> Path:
        tid = task["id"]
        ws = self.workspace_path(tid)

        if ws.exists():
            await self._to_thread(shutil.rmtree, ws)

        await self._copy_project(ws)
        await self._bootstrap(ws)
        await self._write_prompt(task, ws)
        return ws

    async def _copy_project(self, workspace: Path) -> None:
        def _do_copy():
            workspace.mkdir(parents=True, exist_ok=True)
            ignore = shutil.ignore_patterns(
                ".git", "agent-workspaces", "__pycache__", "*.pyc", "*.tmp", "*.lock"
            )
            shutil.copytree(self.project_root, workspace, dirs_exist_ok=True, ignore=ignore)
            subprocess.run(
                ["git", "init"],
                cwd=str(workspace),
                capture_output=True,
                check=False,
            )

        await self._to_thread(_do_copy)
