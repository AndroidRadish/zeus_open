"""
并发实验脚本 — 验证 Global Scheduler + Agent Mailbox + Agent Logs 协同工作。

用法:
  1. 确保 server 已启动: python .zeus/v2/scripts/zeus_server.py --port 8234
  2. 运行: python .zeus/v2/scripts/experiment_concurrency.py
  3. 打开浏览器 http://localhost:8234/web
     - 切换到 "全局执行" 观察跨 wave 并发和隔离区
     - 切换到 "Agent 协作" 输入 agent_id (如 zeus-agent-T-EXP-001) 查看消息流
     - 切换到 "Agent 日志" 选择 agent 查看 activity / reasoning
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

# Allow imports from the scripts directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_bus import AgentBus
from store import LocalStore
from zeus_orchestrator import ZeusOrchestrator
import subagent_dispatcher as sd


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
TASK_JSON_PATH = PROJECT_ROOT / ".zeus" / "v2" / "task.json"
CONFIG_JSON_PATH = PROJECT_ROOT / ".zeus" / "v2" / "config.json"
BACKUP_SUFFIX = ".experiment-backup"

EXP_TASKS = [
    {
        "id": "T-EXP-001",
        "passes": False,
        "story_id": "EXP",
        "title": "Experiment task 1 (slow)",
        "description": "Sleeps 8s to simulate long-running agent.",
        "depends_on": [],
        "wave": 99,
        "original_wave": 99,
        "scheduled_wave": 99,
        "type": "feat",
    },
    {
        "id": "T-EXP-002",
        "passes": False,
        "story_id": "EXP",
        "title": "Experiment task 2 (slow)",
        "description": "Sleeps 6s to simulate long-running agent.",
        "depends_on": [],
        "wave": 99,
        "original_wave": 99,
        "scheduled_wave": 99,
        "type": "feat",
    },
    {
        "id": "T-EXP-003",
        "passes": False,
        "story_id": "EXP",
        "title": "Experiment task 3 (medium)",
        "description": "Sleeps 4s.",
        "depends_on": [],
        "wave": 99,
        "original_wave": 99,
        "scheduled_wave": 99,
        "type": "feat",
    },
    {
        "id": "T-EXP-004",
        "passes": False,
        "story_id": "EXP",
        "title": "Experiment task 4 (fast)",
        "description": "Sleeps 2s.",
        "depends_on": [],
        "wave": 99,
        "original_wave": 99,
        "scheduled_wave": 99,
        "type": "feat",
    },
]


def _backup(path: Path) -> Path:
    backup = path.with_suffix(path.suffix + BACKUP_SUFFIX)
    shutil.copy2(str(path), str(backup))
    return backup


def _restore(backup: Path, original: Path) -> None:
    shutil.copy2(str(backup), str(original))
    backup.unlink()


def _inject_tasks() -> None:
    store = LocalStore(base_dir=str(PROJECT_ROOT))
    data = store.read_json(".zeus/v2/task.json")
    # Remove any previous exp tasks
    data["tasks"] = [t for t in data["tasks"] if not t["id"].startswith("T-EXP-")]
    # Remove from quarantine if present
    data["quarantine"] = [q for q in data.get("quarantine", []) if not q["task_id"].startswith("T-EXP-")]
    data["tasks"].extend(EXP_TASKS)
    store.write_json(".zeus/v2/task.json", data)
    print(f"[{_now()}] Injected {len(EXP_TASKS)} experiment tasks into task.json")


def _ensure_mock_dispatcher() -> None:
    store = LocalStore(base_dir=str(PROJECT_ROOT))
    cfg = store.read_json(".zeus/v2/config.json")
    cfg.setdefault("subagent", {})["dispatcher"] = "mock"
    store.write_json(".zeus/v2/config.json", cfg)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


async def _mailbox_spammer(orch: ZeusOrchestrator) -> None:
    """Coroutine that sends mailbox messages to running agents periodically."""
    store = orch._store()
    bus = AgentBus(version="v2", wave=-1, store=store)
    spam_count = 0
    while True:
        await asyncio.sleep(3)
        # Discover currently running agents by reading latest wave events
        # We use wave-99-events.jsonl since our exp tasks are wave 99
        events_path = store._resolve(".zeus/v2/agent-logs/wave-99-events.jsonl")
        running_ids: set[str] = set()
        if events_path.exists():
            for line in events_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if evt.get("type") == "task.started":
                    running_ids.add(f"zeus-agent-{evt['task_id']}")
                elif evt.get("type") in ("task.completed", "task.failed", "task.quarantined"):
                    running_ids.discard(f"zeus-agent-{evt['task_id']}")

        if not running_ids:
            # Maybe all done or not started yet
            continue

        for agent_id in running_ids:
            msg = f"Spam #{spam_count + 1} to {agent_id} at {_now()}"
            bus.send(agent_id, msg)
            print(f"[{_now()}] [MAIL]  -> {agent_id}: {msg}")
        spam_count += 1

        if spam_count >= 10:
            break


async def main() -> None:
    print("=" * 60)
    print("ZeusOpen v2 Concurrency Experiment")
    print("=" * 60)

    if not TASK_JSON_PATH.exists():
        print("Error: task.json not found at", TASK_JSON_PATH)
        sys.exit(1)

    task_backup = _backup(TASK_JSON_PATH)
    config_backup = _backup(CONFIG_JSON_PATH) if CONFIG_JSON_PATH.exists() else None

    try:
        _inject_tasks()
        _ensure_mock_dispatcher()

        orch = ZeusOrchestrator(version="v2", project_root=str(PROJECT_ROOT), max_parallel=3)
        original_mock_run = sd.MockSubagentDispatcher.run

        async def patched_mock_run(self, task, workspace, prompt, bus):
            tid = task["id"]
            sleep_map = {"T-EXP-001": 8, "T-EXP-002": 6, "T-EXP-003": 4, "T-EXP-004": 2}
            delay = sleep_map.get(tid, 3)
            print(f"[{_now()}] [START] {tid} started (will sleep {delay}s)")
            await asyncio.sleep(delay)
            result = await original_mock_run(self, task, workspace, prompt, bus)
            print(f"[{_now()}] [DONE]  {tid} completed")
            # Mark as passed so downstream deps could proceed if they existed
            orch.update_task_state(tid, {"passes": True, "commit_sha": "exp"})
            return result

        with patch.object(sd.MockSubagentDispatcher, "run", patched_mock_run):
            print(f"[{_now()}] Starting run_global (max_parallel=3) ...")
            print("[{_now()}] Tip: Open http://localhost:8234/web and switch to '全局执行' / 'Agent 协作' / 'Agent 日志' tabs\n")

            # Race run_global against mailbox spammer
            summary = await asyncio.wait_for(
                asyncio.gather(
                    orch.run_global(),
                    _mailbox_spammer(orch),
                ),
                timeout=60,
            )

            global_summary = summary[0]
            print(f"\n[{_now()}] run_global finished: {json.dumps(global_summary, indent=2)}")

    except asyncio.TimeoutError:
        print(f"\n[{_now()}] Experiment timed out (>60s). Check if server is running.")
    finally:
        _restore(task_backup, TASK_JSON_PATH)
        if config_backup:
            _restore(config_backup, CONFIG_JSON_PATH)
        print(f"[{_now()}] Restored task.json and config.json")


if __name__ == "__main__":
    asyncio.run(main())
