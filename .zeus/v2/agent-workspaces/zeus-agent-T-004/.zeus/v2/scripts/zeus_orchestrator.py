"""
zeus_orchestrator.py — ZeusOpen v2 核心异步调度器

替代 v1 zeus_runner.py 的手动 copy-paste 模式，实现同一 wave 内多 Agent 并发执行。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_bus import AgentBus
from store import LocalStore


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ZeusOrchestrator:
    def __init__(self, version: str = "v2", project_root: str | None = None, max_parallel: int = 3):
        self.version = version
        if project_root is None:
            # 当前脚本位于 .zeus/v2/scripts/，项目根目录向上三级
            self.project_root = Path(__file__).resolve().parent.parent.parent.parent
        else:
            self.project_root = Path(project_root)
        self.max_parallel = max_parallel
        self._task_json_path = f".zeus/{version}/task.json"
        self._config_json_path = f".zeus/{version}/config.json"
        self._semaphore = asyncio.Semaphore(max_parallel)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    def _store(self) -> LocalStore:
        """Factory for a fresh LocalStore instance wired to project_root."""
        return LocalStore(base_dir=str(self.project_root))

    def _load_task_json(self, store: LocalStore) -> dict:
        target = store._resolve(self._task_json_path)
        with open(target, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    def _load_config_json(self, store: LocalStore) -> dict:
        try:
            target = store._resolve(self._config_json_path)
            with open(target, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            return {}

    def _build_prompt(self, task: dict, store: LocalStore) -> str:
        config = self._load_config_json(store)
        north_star = config.get("metrics", {}).get("north_star", "N/A")
        project_name = config.get("project", {}).get("name", "ZeusOpen Project")
        task_id = task["id"]
        task_title = task["title"]
        task_desc = task.get("description", "")
        task_type = task.get("type", "feat")
        task_files = ", ".join(task.get("files", [])) or "N/A"
        depends_on = ", ".join(task.get("depends_on", [])) or "none"
        wave = task.get("wave", "N/A")

        prompt = f"""# ZeusOpen v2 Agent Task Prompt

## 项目信息
- 项目名称：{project_name}
- 北极星指标：{north_star}
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
3. 完成后立即进行原子 git commit，格式建议：
   ```
   {self._suggest_commit_type(task_type)}({task_id}): {task_title}
   ```
4. 更新 `.zeus/{self.version}/task.json` 中此任务的 `passes` 为 `true`，并填写 `commit_sha`。
5. 在 `.zeus/{self.version}/ai-logs/` 目录写入 ai-log 文件（如 `{task_id}.md`），包含以下内容：
   - **Decision Rationale**：关键技术选择及原因
   - **Execution Summary**：修改了哪些文件，新增了什么，commit SHA
   - **Target Impact**：此 task 如何贡献北极星指标 `{north_star}`，尽量量化

## 注意事项
- 本 Prompt 所在目录即为你的隔离工作区，项目源码已复制至此。
- 请勿直接修改原始项目目录中的文件；所有改动应在此工作区完成，随后由主会话合并。
- 若遇到设计疑问，优先保持简单（KISS 原则），并在 ai-log 中记录决策。

完成后，请在 Kimi Code 主会话中报告执行结果。
"""
        return prompt

    @staticmethod
    def _suggest_commit_type(task_type: str) -> str:
        mapping = {
            "api": "feat",
            "frontend": "feat",
            "infra": "chore",
            "docs": "docs",
            "test": "test",
            "fix": "fix",
        }
        return mapping.get(task_type, "feat")

    # -----------------------------------------------------------------------
    # Core API
    # -----------------------------------------------------------------------
    def load_wave(self, wave_number: int) -> list[dict]:
        store = self._store()
        data = self._load_task_json(store)
        tasks = data.get("tasks", [])
        pending = [
            t for t in tasks
            if t.get("wave") == wave_number and not t.get("passes", False)
        ]
        return pending

    async def dispatch_task(self, task: dict, bus: AgentBus, store: LocalStore) -> dict:
        task_id = task["id"]
        agent_id = f"zeus-agent"
        wave = task.get("wave", 1)

        # Workspace path: .zeus/v2/agent-workspaces/{agent_id}-{task_id}/
        workspace_rel = f".zeus/{self.version}/agent-workspaces/{agent_id}-{task_id}"
        workspace_path = store._resolve(workspace_rel)
        prompt_path = workspace_path / "PROMPT.md"

        # Emit start event
        bus.emit("task.started", task_id, agent_id, {"message": f"Dispatching {task_id}"})

        # Ensure clean workspace
        if workspace_path.exists():
            await asyncio.to_thread(shutil.rmtree, workspace_path)

        # Copy project source into workspace (read-only clone), excluding .git and agent-workspaces
        def _do_copy():
            workspace_path.mkdir(parents=True, exist_ok=True)
            # Copy contents of project_root into workspace_path, excluding specified patterns
            ignore = shutil.ignore_patterns(".git", "agent-workspaces", "__pycache__", "*.pyc")
            shutil.copytree(
                self.project_root,
                workspace_path,
                dirs_exist_ok=True,
                ignore=ignore,
            )

        await asyncio.to_thread(_do_copy)

        # Write PROMPT.md
        prompt = self._build_prompt(task, store)
        await asyncio.to_thread(prompt_path.write_text, prompt, "utf-8")

        # Emit completion event
        bus.emit("task.completed", task_id, agent_id, {"workspace": str(workspace_path)})

        return {
            "task_id": task_id,
            "status": "dispatched",
            "workspace": str(workspace_path),
            "prompt_path": str(prompt_path),
        }

    async def _dispatch_with_semaphore(self, task: dict, bus: AgentBus, store: LocalStore) -> dict:
        async with self._semaphore:
            return await self.dispatch_task(task, bus, store)

    async def await_wave_completion(self, wave_number: int) -> dict:
        store = self._store()
        bus = AgentBus(version=self.version, wave=wave_number, store=store)
        tasks = self.load_wave(wave_number)

        if not tasks:
            return {
                "wave": wave_number,
                "total": 0,
                "dispatched": 0,
                "failed": 0,
            }

        coros = [self._dispatch_with_semaphore(t, bus, store) for t in tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)

        dispatched = 0
        failed = 0
        for res in results:
            if isinstance(res, Exception):
                failed += 1
                # Emit failure via bus for the first task (best-effort logging)
                bus.emit("task.failed", tasks[results.index(res)]["id"], "zeus-agent", {"error": str(res)})
            else:
                dispatched += 1

        bus.emit("wave.completed", "wave", "zeus-orchestrator", {"wave": wave_number})

        return {
            "wave": wave_number,
            "total": len(tasks),
            "dispatched": dispatched,
            "failed": failed,
        }

    def update_task_state(self, task_id: str, updates: dict) -> None:
        store = self._store()
        with store.lock(self._task_json_path):
            data = store.read_json(self._task_json_path)
            tasks = data.get("tasks", [])
            for t in tasks:
                if t.get("id") == task_id:
                    t.update(updates)
                    break
            store.write_json(self._task_json_path, data)

    def transition_to_next_wave(self, current_wave: int, auto: bool = False) -> bool:
        store = self._store()
        data = self._load_task_json(store)
        tasks = data.get("tasks", [])

        wave_tasks = [t for t in tasks if t.get("wave") == current_wave]
        all_passed = all(t.get("passes", False) for t in wave_tasks)

        if not all_passed:
            print(f"⚠️ Wave {current_wave} 尚未全部完成，无法进入下一 wave。")
            return False

        if not auto:
            print("=" * 40)
            print(f"Wave {current_wave} completed.")
            print(f"Please approve to proceed to Wave {current_wave + 1}.")
            print("=" * 40)
            return False

        # Auto-approve: update meta.current_wave
        meta = data.get("meta", {})
        meta["current_wave"] = current_wave + 1
        data["meta"] = meta
        store.write_json(self._task_json_path, data)
        print(f"✅ 已自动批准：进入 Wave {current_wave + 1}")
        return True

    def print_status(self) -> None:
        store = self._store()
        data = self._load_task_json(store)
        config = self._load_config_json(store)
        tasks = data.get("tasks", [])
        meta = data.get("meta", {})
        current_wave = meta.get("current_wave", 1)

        total = len(tasks)
        passed = sum(1 for t in tasks if t.get("passes"))
        pending = total - passed
        recent_completed = [t for t in tasks if t.get("passes")][-5:]
        pending_tasks = [t for t in tasks if not t.get("passes", False)]

        print(f"\n🚀 ZeusOpen v2 Status (version: {self.version})\n")
        print(f"Project : {config.get('project', {}).get('name', 'N/A')}")
        print(f"North Star: {config.get('metrics', {}).get('north_star', 'N/A')}")
        print(f"Current Wave: {current_wave}")
        print(f"Tasks   : {passed}/{total} completed ({pending} pending)")

        if recent_completed:
            print(f"\nRecent completed:")
            for t in recent_completed:
                sha = t.get("commit_sha", "N/A")
                sha_short = sha[:7] if sha else "N/A"
                print(f"  ✅ {t['id']}: {t['title']} → {sha_short}")

        wave_pending = [t for t in pending_tasks if t.get("wave") == current_wave]
        print(f"\nPending in current wave ({current_wave}): {len(wave_pending)}")
        for t in wave_pending[:5]:
            print(f"  ⏳ {t['id']}: {t['title']}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="ZeusOpen v2 Orchestrator")
    parser.add_argument("--version", default="v2", help="目标版本文件夹名 (默认: v2)")
    parser.add_argument("--wave", type=int, default=None, help="执行指定 wave")
    parser.add_argument("--status", action="store_true", help="打印 v2 项目状态")
    parser.add_argument("--approve-next", action="store_true", help="人类批准后进入下一 wave")

    args = parser.parse_args()
    orch = ZeusOrchestrator(version=args.version)

    if args.status:
        orch.print_status()
    elif args.approve_next:
        store = orch._store()
        data = orch._load_task_json(store)
        current_wave = data.get("meta", {}).get("current_wave", 1)
        orch.transition_to_next_wave(current_wave, auto=True)
    elif args.wave is not None:
        summary = asyncio.run(orch.await_wave_completion(args.wave))
        print(json.dumps(summary, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
