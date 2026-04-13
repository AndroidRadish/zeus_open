"""
Git worktree based workspace isolation manager.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from workspace.base import BaseWorkspaceManager


class GitWorktreeWorkspaceManager(BaseWorkspaceManager):
    """Prepare isolated agent workspaces using git worktree.

    Requires the project_root to be inside a git repository.
    """

    async def prepare(self, task: dict[str, Any]) -> Path:
        tid = task["id"]
        ws = self.workspace_path(tid)

        # Remove existing workspace if present
        if ws.exists():
            await self._remove_worktree(ws)

        await self._add_worktree(ws)
        await self._bootstrap(ws)
        await self._write_prompt(task, ws)
        return ws

    async def _add_worktree(self, workspace: Path) -> None:
        def _do_add():
            workspace.parent.mkdir(parents=True, exist_ok=True)
            branch_name = f"zeus-agent-{workspace.name}"
            # Create orphan branch worktree (no history, clean slate)
            result = subprocess.run(
                [
                    "git", "worktree", "add", "--detach", str(workspace),
                ],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                # Fallback: try with force if worktree already existed previously
                result = subprocess.run(
                    [
                        "git", "worktree", "add", "--force", "--detach", str(workspace),
                    ],
                    cwd=str(self.project_root),
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    raise RuntimeError(f"git worktree add failed: {result.stderr}")

        await self._to_thread(_do_add)

    async def _remove_worktree(self, workspace: Path) -> None:
        def _do_remove():
            result = subprocess.run(
                ["git", "worktree", "remove", "--force", str(workspace)],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                # Fallback to manual removal + prune
                import shutil
                shutil.rmtree(workspace, ignore_errors=True)
                subprocess.run(
                    ["git", "worktree", "prune"],
                    cwd=str(self.project_root),
                    capture_output=True,
                    check=False,
                )

        await self._to_thread(_do_remove)
