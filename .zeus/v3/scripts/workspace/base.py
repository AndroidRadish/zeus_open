"""
Base workspace manager interface.
"""
from __future__ import annotations

import abc
import shutil
from pathlib import Path
from typing import Any

from config import ZeusConfig


class BaseWorkspaceManager(abc.ABC):
    """Abstract base for workspace isolation strategies."""

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

    @abc.abstractmethod
    async def prepare(self, task: dict[str, Any]) -> Path:
        """Ensure a clean workspace exists with source, bootstrap files, and prompt."""
        raise NotImplementedError

    async def _bootstrap(self, workspace: Path) -> None:
        files = self.config.bootstrap_files
        for filename in files:
            src = self.project_root / filename
            if src.exists():
                dst = workspace / filename
                await self._to_thread(shutil.copy2, str(src), str(dst))

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

### 0. 认知校准（Think Before Coding）
在动手写代码前，你必须：
- 阅读涉及文件，确认对任务描述的理解没有歧义
- 如果有任何假设、不确定的接口行为或业务逻辑，**先在工作区写入假设清单（如 `assumptions.md`）并向我提问，不要直接实现**

### 1. 代码质量铁律
- **简洁至上**：禁止引入未明确要求的新依赖；禁止为单一用例创建抽象基类、Protocol、复杂 Enum 组合；能用 50 行解决的不用 500 行
- **手术式修改**：只修改与当前 task 直接相关的代码；不修无关的注释、格式、类型提示、引号风格；你的修改导致的废弃 import/变量必须删除，但历史遗留死代码不动
- **匹配现有风格**：优先拷贝-修改现有代码模式，而不是"重构得更通用"

### 2. 验证循环（Goal-Driven Execution）
- **如果是修复类任务**：先写一个能复现问题的测试，确认它失败，再修复，最后确认测试通过
- **如果是功能类任务**：先写测试或最小可运行脚本，再实现功能，最后确认通过
- **多文件任务**：每改 1-2 个文件后就要运行相关测试，禁止一次性改完所有文件再统一验证
- 多步骤任务需在 ai-log 中按 `1. [步骤] → 验证：[检查点]` 格式记录计划

### 3. 工程规范
- 在隔离工作区中实现上述任务
- 如有 typecheck / lint / test 配置，运行并保证通过
- 在 `.zeus/{self.version}/ai-logs/` 目录写入 ai-log 文件（如 `{task_id}.md`）
- **完成后必须**在当前工作区根目录写入 `zeus-result.json`，格式如下：
  ```json
  {{
    "status": "completed",
    "changed_files": ["src/foo.py"],
    "test_summary": {{"passed": 5, "failed": 0, "skipped": 0}},
    "commit_sha": "abc1234",
    "artifacts": {{}}
  }}
  ```
- **不需要**在隔离工作区中执行 `git commit`，也**不需要**修改主项目的 `task.json`

### 4. 进度上报
在执行过程中，每完成一个重要里程碑，请向当前工作区根目录的 `progress.jsonl` 追加一行 JSON：
```json
{{"ts": "2026-04-13T15:30:00Z", "step": "planning", "message": "已完成架构分析"}}
```
建议的 step 值：`planning`（规划）、`reading`（阅读）、`writing`（编写）、`testing`（测试）、`reviewing`（审查）、`completed`（完成）。

你也可以通过 HTTP POST 主动上报进度：
```bash
curl -X POST http://127.0.0.1:8000/tasks/{task_id}/progress -H "Content-Type: application/json" -d '{{"step":"writing","message":"正在修改 api/server.py"}}'
```

完成后，请在 Kimi Code 主会话中报告执行结果。
"""

    async def _to_thread(self, func, *args, **kwargs):
        import asyncio
        return await asyncio.to_thread(func, *args, **kwargs)
