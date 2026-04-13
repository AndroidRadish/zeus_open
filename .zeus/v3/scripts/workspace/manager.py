"""
Workspace isolation manager for ZeusOpen v3.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from config import ZeusConfig


class WorkspaceManager:
    """Prepare isolated agent workspaces before dispatch."""

    def __init__(self, project_root: Path, version: str = "v3") -> None:
        self.project_root = Path(project_root)
        self.version = version
        self.config = ZeusConfig(project_root, version)

    def workspace_path(self, task_id: str) -> Path:
        return self.project_root / ".zeus" / self.version / "agent-workspaces" / f"zeus-agent-{task_id}"

    def prompt_path(self, task_id: str) -> Path:
        return self.workspace_path(task_id) / "PROMPT.md"

    def result_path(self, task_id: str) -> Path:
        return self.workspace_path(task_id) / "zeus-result.json"

    async def prepare(self, task: dict[str, Any]) -> Path:
        """Ensure a clean workspace exists with source, bootstrap files, and prompt."""
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

    async def _bootstrap(self, workspace: Path) -> None:
        files = self.config.bootstrap_files
        injected: list[str] = []
        skipped: list[str] = []
        for filename in files:
            src = self.project_root / filename
            if src.exists():
                dst = workspace / filename
                await self._to_thread(shutil.copy2, str(src), str(dst))
                injected.append(filename)
            else:
                skipped.append(filename)

    async def _write_prompt(self, task: dict[str, Any], workspace: Path) -> None:
        prompt = self._build_prompt(task)
        await self._to_thread((workspace / "PROMPT.md").write_text, prompt, "utf-8")

    def _build_prompt(self, task: dict[str, Any]) -> str:
        task_id = task["id"]
        task_title = task.get("title", "")
        task_desc = task.get("description", "")
        task_type = task.get("type", "feat")
        task_files = ", ".join(task.get("files") or []) or "N/A"
        depends_on = ", ".join(task.get("depends_on") or []) or "none"
        wave = task.get("wave", "N/A")

        return f"""# ZeusOpen v3 Agent Task Prompt

## 项目信息
- 项目名称：{self.config.project_name}
- 北极星指标：{self.config.north_star}
- Zeus 版本：{self.version}

## 当前任务
- 任务 ID：{task_id}
- 所属 Wave：{wave}
- 类型：{task_type}
- 标题：{task_title}
- 描述：{task_desc}
- 涉及文件：{task_files}
- 依赖任务：{depends_on}

## 执行要求
1. 在隔离工作区中实现上述任务，遵循项目现有的代码风格和架构模式。
2. 如有 typecheck / lint / test 配置，运行并保证通过。
3. 在 `.zeus/{self.version}/ai-logs/` 目录写入 ai-log 文件（如 `{task_id}.md`）。
4. **完成后必须**在当前工作区根目录写入 `zeus-result.json`，格式如下：
   ```json
   {{
     "status": "completed",
     "changed_files": ["src/foo.py"],
     "test_summary": {{"passed": 5, "failed": 0, "skipped": 0}},
     "commit_sha": "abc1234",
     "artifacts": {{}}
   }}
   ```
5. **不需要**在隔离工作区中执行 `git commit`，也**不需要**修改主项目的 `task.json`。

完成后，请在 Kimi Code 主会话中报告执行结果。
"""

    async def _to_thread(self, func, *args, **kwargs):
        import asyncio
        return await asyncio.to_thread(func, *args, **kwargs)
