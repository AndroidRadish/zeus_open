"""
zeus_orchestrator.py — ZeusOpen v2 核心异步调度器

替代 v1 zeus_runner.py 的手动 copy-paste 模式，实现同一 wave 内多 Agent 并发执行。
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_bus import AgentBus
from store import LocalStore
from subagent_dispatcher import build_dispatcher


def _fix_windows_stdio():
    """Fix Windows console encoding for emoji/unicode output."""
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


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
    @staticmethod
    def _task_effective_wave(task: dict) -> int | None:
        """Return the runtime wave (scheduled_wave falls back to wave)."""
        return task.get("scheduled_wave", task.get("wave"))

    @staticmethod
    def _task_original_wave(task: dict) -> int | None:
        """Return the originally planned wave."""
        return task.get("original_wave", task.get("wave"))

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

    @staticmethod
    def _localize(task: dict, field: str, lang: str = "zh") -> str:
        """Return localized task field if available, else fall back to base field."""
        localized = task.get(f"{field}_{lang}")
        if localized:
            return localized
        return task.get(field, "")

    @staticmethod
    def _build_dependency_graph(tasks: list[dict]) -> dict[str, list[str]]:
        """Build a task-id -> list of direct dependency ids graph."""
        return {t["id"]: t.get("depends_on", []) for t in tasks if t.get("id")}

    @staticmethod
    def _get_transitive_deps(task_id: str, graph: dict[str, list[str]], _cache: dict[str, set[str]] | None = None) -> set[str]:
        """Return all transitive dependency ids for a given task."""
        if _cache is None:
            _cache = {}
        if task_id in _cache:
            return _cache[task_id]
        deps: set[str] = set()
        for d in graph.get(task_id, []):
            deps.add(d)
            deps.update(ZeusOrchestrator._get_transitive_deps(d, graph, _cache))
        _cache[task_id] = deps
        return deps

    def _build_prompt(self, task: dict, store: LocalStore) -> str:
        config = self._load_config_json(store)
        north_star = config.get("metrics", {}).get("north_star", "N/A")
        project_name = config.get("project", {}).get("name", "ZeusOpen Project")
        task_id = task["id"]
        task_title = self._localize(task, "title", "zh")
        task_desc = self._localize(task, "description", "zh")
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
            if self._task_effective_wave(t) == wave_number and not t.get("passes", False)
        ]
        return pending

    def _get_ready_tasks(
        self,
        current_wave: int,
        dispatched_ids: set[str],
        store: LocalStore,
    ) -> list[dict]:
        """Return all tasks that are ready to run, sorted by (original_wave, id)."""
        data = self._load_task_json(store)
        tasks = data.get("tasks", [])
        meta = data.get("meta", {})

        scheduling_mode = meta.get("scheduling_mode", "legacy")
        lookahead = meta.get("lookahead_waves", 1 if scheduling_mode == "adaptive" else 0)

        pass_map = {t["id"]: t.get("passes", False) for t in tasks}

        ready = []
        for t in tasks:
            tid = t["id"]
            if tid in dispatched_ids:
                continue
            if pass_map.get(tid, False):
                continue

            eff_wave = self._task_effective_wave(t) or 0
            orig_wave = self._task_original_wave(t) or 0

            if scheduling_mode != "adaptive" or lookahead == 0:
                if eff_wave != current_wave:
                    continue
            else:
                if eff_wave > current_wave + lookahead:
                    continue
                if eff_wave < current_wave:
                    # Allow only if explicitly rescheduled into current wave
                    if orig_wave != current_wave and eff_wave != current_wave:
                        continue

            deps = t.get("depends_on", [])
            if not all(pass_map.get(d, False) for d in deps):
                continue

            ready.append(t)

        ready.sort(key=lambda t: (self._task_original_wave(t) or 0, t["id"]))
        return ready

    def _reschedule_task(
        self,
        task: dict,
        new_wave: int,
        store: LocalStore,
        bus: AgentBus,
    ) -> None:
        """Move a task to a new wave and persist the change atomically."""
        tid = task["id"]
        old_wave = self._task_effective_wave(task)
        orig_wave = self._task_original_wave(task)

        if old_wave == new_wave:
            return

        updates = {
            "scheduled_wave": new_wave,
            "wave": new_wave,
            "rescheduled_from": old_wave,
        }
        task.update(updates)

        store.update_json_fields(
            self._task_json_path,
            list_key="tasks",
            id_field="id",
            updates=[{"id": tid, **updates}],
        )

        bus.emit(
            "task.rescheduled",
            tid,
            "zeus-orchestrator",
            {
                "original_wave": orig_wave,
                "new_wave": new_wave,
                "previous_wave": old_wave,
                "reason": "slot_available_while_wave_blocked",
            },
        )

    async def _run_and_capture(self, task: dict, bus: AgentBus, store: LocalStore) -> tuple[str, Any]:
        """Wrapper that preserves task_id for result/error correlation."""
        try:
            result = await self._dispatch_with_semaphore(task, bus, store)
            return task["id"], result
        except Exception as exc:
            return task["id"], exc

    def _quarantine_task(
        self,
        task: dict,
        reason: str,
        store: LocalStore,
        bus: AgentBus,
        workspace: str | None = None,
    ) -> None:
        """Move a failed task into the quarantine zone and persist atomically."""
        tid = task["id"]

        with store.lock(self._task_json_path):
            data = store.read_json(self._task_json_path)
            quarantine = data.setdefault("quarantine", [])
            # Idempotent: remove existing entry if present
            quarantine = [q for q in quarantine if q.get("task_id") != tid]
            quarantine.append(
                {
                    "task_id": tid,
                    "reason": reason,
                    "quarantined_at": _now_iso(),
                    "workspace": workspace or "",
                }
            )
            data["quarantine"] = quarantine
            store.write_json(self._task_json_path, data)

        bus.emit(
            "task.quarantined",
            tid,
            "zeus-orchestrator",
            {"reason": reason, "workspace": workspace or ""},
        )
        bus.post(tid, "zeus-orchestrator", f"任务 **{tid}** 已被隔离：{reason}")

    def _get_global_ready_tasks(
        self,
        tasks: list[dict],
        pass_map: dict[str, bool],
        dispatched_ids: set[str],
        quarantined_ids: set[str],
    ) -> list[dict]:
        """Return globally ready tasks sorted by (original_wave, id)."""
        graph = self._build_dependency_graph(tasks)

        ready: list[dict] = []
        for t in tasks:
            tid = t["id"]
            if tid in dispatched_ids:
                continue
            if pass_map.get(tid, False):
                continue
            if tid in quarantined_ids:
                continue

            deps = t.get("depends_on", [])
            # All direct deps must have passed and must not be quarantined
            if not all(pass_map.get(d, False) for d in deps):
                continue
            if any(d in quarantined_ids for d in deps):
                continue

            ready.append(t)

        ready.sort(key=lambda t: (self._task_original_wave(t) or 0, t["id"]))
        return ready

    async def run_global(self) -> dict:
        """
        Global scheduler entry point.

        Dispatches tasks across all waves based purely on dependency readiness.
        Failed tasks are quarantined so they do not block unrelated downstream work.
        Wave numbers remain untouched and serve only as planning/observation fields.
        """
        store = self._store()
        bus = AgentBus(version=self.version, wave=-1, store=store)

        dispatched_ids: set[str] = set()
        dispatched_count = 0
        failed_count = 0
        running_tasks: set[asyncio.Task] = set()

        while True:
            # Refresh state from disk each iteration
            data = self._load_task_json(store)
            tasks = data.get("tasks", [])
            pass_map = {t["id"]: t.get("passes", False) for t in tasks}
            quarantined_ids = {q["task_id"] for q in data.get("quarantine", []) if q.get("task_id")}

            free_slots = self.max_parallel - len(running_tasks)
            if free_slots > 0:
                ready = self._get_global_ready_tasks(
                    tasks, pass_map, dispatched_ids, quarantined_ids
                )
                for task in ready[:free_slots]:
                    tid = task["id"]
                    dispatched_ids.add(tid)
                    coro = self._run_and_capture(task, bus, store)
                    aio_task = asyncio.create_task(coro)
                    running_tasks.add(aio_task)
                    dispatched_count += 1

            if not running_tasks:
                break

            done, running_tasks = await asyncio.wait(
                running_tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                tid, outcome = await task
                workspace_path = str(
                    store._resolve(f".zeus/{self.version}/agent-workspaces/zeus-agent-{tid}")
                )
                if isinstance(outcome, Exception):
                    failed_count += 1
                    self._quarantine_task(
                        {"id": tid},
                        reason=f"exception: {outcome}",
                        store=store,
                        bus=bus,
                        workspace=workspace_path,
                    )
                elif isinstance(outcome, dict) and outcome.get("status") == "failed":
                    failed_count += 1
                    self._quarantine_task(
                        {"id": tid},
                        reason=outcome.get("error", "dispatcher_failed"),
                        store=store,
                        bus=bus,
                        workspace=workspace_path,
                    )
                # Dispatcher mock/claude/kimi already emits task.completed / task.failed;
                # we additionally emit task.quarantined for global tracking.

        bus.emit("global.completed", "global", "zeus-orchestrator", {})

        return {
            "mode": "global",
            "dispatched": dispatched_count,
            "failed": failed_count,
        }

    def _build_dispatcher(self, store: LocalStore):
        """Factory for the subagent dispatcher based on project config."""
        config = self._load_config_json(store)
        return build_dispatcher(config)

    def _bootstrap_workspace(self, workspace_path: Path, bus: AgentBus, store: LocalStore) -> None:
        """Copy identity/context files into the agent workspace before dispatch."""
        config = self._load_config_json(store)
        subagent_cfg = config.get("subagent", {})
        bootstrap_cfg = subagent_cfg.get("bootstrap", {})

        default_files = ["AGENTS.md", "USER.md", "IDENTITY.md", "SOUL.md"]
        file_list = bootstrap_cfg.get("files", default_files)

        injected: list[str] = []
        skipped: list[str] = []

        for filename in file_list:
            src = self.project_root / filename
            if src.exists():
                dst = workspace_path / filename
                shutil.copy2(str(src), str(dst))
                injected.append(filename)
            else:
                skipped.append(filename)

        bus.emit(
            "task.bootstrapped",
            "workspace",
            "zeus-orchestrator",
            {
                "workspace": str(workspace_path),
                "injected": injected,
                "skipped": skipped,
            },
        )

    async def dispatch_task(self, task: dict, bus: AgentBus, store: LocalStore) -> dict:
        task_id = task["id"]
        agent_id = f"zeus-agent"
        wave = task.get("wave", 1)

        # Workspace path: .zeus/v2/agent-workspaces/{agent_id}-{task_id}/
        workspace_rel = f".zeus/{self.version}/agent-workspaces/{agent_id}-{task_id}"
        workspace_path = store._resolve(workspace_rel)
        prompt_path = workspace_path / "PROMPT.md"

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

        # Bootstrap identity/context files into workspace
        await asyncio.to_thread(self._bootstrap_workspace, workspace_path, bus, store)

        # Write PROMPT.md
        prompt = self._build_prompt(task, store)
        await asyncio.to_thread(prompt_path.write_text, prompt, "utf-8")

        # Delegate to the platform-specific subagent dispatcher
        dispatcher = self._build_dispatcher(store)
        return await dispatcher.run(task, workspace_path, prompt, bus)

    async def _dispatch_with_semaphore(self, task: dict, bus: AgentBus, store: LocalStore) -> dict:
        async with self._semaphore:
            return await self.dispatch_task(task, bus, store)

    async def await_wave_completion(self, wave_number: int) -> dict:
        store = self._store()
        bus = AgentBus(version=self.version, wave=wave_number, store=store)

        dispatched_ids: set[str] = set()
        dispatched_count = 0
        failed_count = 0
        running_tasks: set[asyncio.Task] = set()

        while True:
            free_slots = self.max_parallel - len(running_tasks)
            if free_slots > 0:
                ready = self._get_ready_tasks(wave_number, dispatched_ids, store)
                for task in ready[:free_slots]:
                    tid = task["id"]
                    orig_wave = self._task_original_wave(task) or wave_number

                    if orig_wave > wave_number:
                        self._reschedule_task(task, wave_number, store, bus)

                    dispatched_ids.add(tid)
                    coro = self._run_and_capture(task, bus, store)
                    aio_task = asyncio.create_task(coro)
                    running_tasks.add(aio_task)
                    dispatched_count += 1

            if not running_tasks:
                break

            done, running_tasks = await asyncio.wait(
                running_tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                tid, outcome = await task
                if isinstance(outcome, Exception):
                    failed_count += 1
                    bus.emit("task.failed", tid, "zeus-agent", {"error": str(outcome)})
                    bus.post(tid, "zeus-agent", f"任务 **{tid}** 执行失败：{outcome}")
                elif isinstance(outcome, dict) and outcome.get("status") == "failed":
                    failed_count += 1
                    # Dispatcher already emitted task.failed inside its run() method

        bus.emit("wave.completed", "wave", "zeus-orchestrator", {"wave": wave_number})

        return {
            "wave": wave_number,
            "total": dispatched_count,
            "dispatched": dispatched_count,
            "failed": failed_count,
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

        # Approval gate is based on original_wave so rescheduled tasks still count
        wave_tasks = [t for t in tasks if self._task_original_wave(t) == current_wave]
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

        wave_pending = [t for t in pending_tasks if self._task_effective_wave(t) == current_wave]
        print(f"\nPending in current wave ({current_wave}): {len(wave_pending)}")
        for t in wave_pending[:5]:
            orig = self._task_original_wave(t)
            suffix = f" [原 Wave {orig}]" if orig and orig != current_wave else ""
            print(f"  ⏳ {t['id']}: {t['title']}{suffix}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    _fix_windows_stdio()
    parser = argparse.ArgumentParser(description="ZeusOpen v2 Orchestrator")
    parser.add_argument("--version", default="v2", help="目标版本文件夹名 (默认: v2)")
    parser.add_argument("--wave", type=int, default=None, help="执行指定 wave")
    parser.add_argument("--run-global", action="store_true", dest="run_global", help="全局调度模式（跨 wave 依赖就绪即执行）")
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
    elif args.run_global:
        summary = asyncio.run(orch.run_global())
        print(json.dumps(summary, indent=2))
    elif args.wave is not None:
        summary = asyncio.run(orch.await_wave_completion(args.wave))
        print(json.dumps(summary, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
