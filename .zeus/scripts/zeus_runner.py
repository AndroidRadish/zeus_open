#!/usr/bin/env python3
"""
zeus_runner.py — 通用 AI-CLI 版 Zeus 执行引擎
替代 zeus-runner.sh，适用于任何不具备 claude CLI 的 AI 编程助手
（Kimi、GLM、DeepSeek、GPT/Codex、Gemini 等）
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Fix Windows console encoding for emoji/unicode output
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")


class ZeusRunner:
    def __init__(self, version: str = "main"):
        self.version = version
        self.base_dir = Path(f".zeus/{version}")
        self.task_file = self.base_dir / "task.json"
        self.config_file = self.base_dir / "config.json"
        self.log_dir = self.base_dir / "ai-logs"
        self.progress_file = self.base_dir / "progress.txt"

    def _load_json(self, path: Path) -> dict:
        if not path.exists():
            print(f"❌ 文件不存在: {path}")
            sys.exit(1)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_json(self, path: Path, data: dict) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_tasks(self) -> dict:
        return self._load_json(self.task_file)

    def load_config(self) -> dict:
        return self._load_json(self.config_file)

    def get_pending_tasks(self, wave: int | None = None, task_id: str | None = None) -> list[dict]:
        data = self.load_tasks()
        tasks = data.get("tasks", [])
        pending = [t for t in tasks if not t.get("passes", False)]
        if task_id:
            pending = [t for t in pending if t.get("id") == task_id]
        if wave is not None:
            pending = [t for t in pending if t.get("wave") == wave]
        return pending

    def get_current_wave(self) -> int | None:
        pending = self.get_pending_tasks()
        waves = [t.get("wave", 999) for t in pending if t.get("wave") is not None]
        if not waves:
            return None
        return min(waves)

    def status(self) -> None:
        print(f"\n🚀 Zeus Status (version: {self.version})\n")

        config = self.load_config()
        data = self.load_tasks()
        tasks = data.get("tasks", [])

        total = len(tasks)
        passed = sum(1 for t in tasks if t.get("passes"))
        pending = total - passed
        current_wave = self.get_current_wave()

        print(f"Project : {config.get('project', {}).get('name', 'N/A')}")
        print(f"North Star: {config.get('metrics', {}).get('north_star', 'N/A')}")
        print(f"Tasks   : {passed}/{total} completed ({pending} pending)")
        if current_wave is not None:
            print(f"Next Wave: {current_wave}")
        else:
            print("Next Wave: (all done)")

        # Recent completed
        recent = [t for t in tasks if t.get("passes")][-5:]
        if recent:
            print("\nRecent completed:")
            for t in recent:
                sha = t.get("commit_sha", "N/A")[:7] if t.get("commit_sha") else "N/A"
                print(f"  ✅ {t['id']}: {t['title']} → {sha}")

        # Next pending
        next_pending = self.get_pending_tasks(wave=current_wave)[:5]
        if next_pending:
            print("\nNext up:")
            for t in next_pending:
                print(f"  ⏳ {t['id']}: {t['title']} (wave {t.get('wave', 'N/A')})")

        # Recommendation
        print("\n📋 Recommendation:")
        if pending == 0:
            print("  All tasks complete. Consider /zeus:feedback or /zeus:evolve.")
        elif current_wave is None:
            print("  Some tasks have no wave assigned. Run zeus:plan first.")
        else:
            print(f"  Run: python .zeus/scripts/zeus_runner.py --wave {current_wave}")
        print()

    def plan(self) -> None:
        print(f"\n📋 Execution Plan (version: {self.version})\n")
        pending = self.get_pending_tasks()
        if not pending:
            print("✅ No pending tasks.")
            return

        # Group by wave
        waves: dict[int, list[dict]] = {}
        for t in pending:
            w = t.get("wave", 999)
            waves.setdefault(w, []).append(t)

        for w in sorted(waves.keys()):
            tasks = waves[w]
            print(f"Wave {w} — {len(tasks)} task(s):")
            for t in tasks:
                deps = ", ".join(t.get("depends_on", [])) or "none"
                print(f"  {t['id']}: {t['title']} [depends_on: {deps}]")
            print()

    def _build_prompt(self, task: dict) -> str:
        config = self.load_config()
        north_star = config.get("metrics", {}).get("north_star", "conversion")
        task_type = task.get("type", "feat")
        task_id = task["id"]
        task_title = task["title"]
        task_desc = task.get("description", "")
        task_files = ", ".join(task.get("files", []))

        prompt = f"""你是 Zeus 执行代理，负责完成以下单个任务。

## 当前任务

任务 ID：{task_id}
类型：{task_type}
标题：{task_title}
描述：{task_desc}
涉及文件：{task_files or "N/A"}
北极星指标：{ north_star }

## 执行要求

1. 实现上述任务，遵循项目现有的代码风格和架构模式
2. 如有 typecheck/lint/test 配置，运行并保证通过
3. 完成后立即进行原子 git commit，格式建议：
   {self._suggest_commit_type(task_type)}({task_id}): {task_title}
4. 将 task.json 中此任务的 passes 字段更新为 true，填写 commit_sha
5. 在 {self.log_dir}/ 目录写入三段式 ai-log 文件，文件名格式：
   {now_compact()}-{task_id}.md

   三段式内容：
   ## Decision Rationale
   （实现时的关键技术选择，为什么这样做）

   ## Execution Summary
   （改了哪些文件，新增了什么，commit SHA）

   ## Target Impact
   （此 task 如何贡献北极星指标 {north_star}，尽量量化）

完成后，请在 Kimi Code 中直接执行上述步骤。
"""
        return prompt

    def _suggest_commit_type(self, task_type: str) -> str:
        mapping = {
            "api": "feat",
            "frontend": "feat",
            "infra": "chore",
            "docs": "docs",
        }
        return mapping.get(task_type, "feat")

    def _mark_done(self, task_id: str, commit_sha: str, log_ref: str) -> None:
        data = self.load_tasks()
        for t in data.get("tasks", []):
            if t.get("id") == task_id:
                t["passes"] = True
                t["commit_sha"] = commit_sha
                t["ai_log_ref"] = log_ref
                t["completed_at"] = now_iso()
                break
        self._save_json(self.task_file, data)

    def _append_progress(self, task_id: str, title: str, note: str = "") -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        line = f"[{now_iso()}] {task_id} 完成：{title}"
        if note:
            line += f"。学到：{note}"
        with open(self.progress_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _create_ai_log_template(self, task_id: str) -> Path:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{now_compact()}-{task_id}.md"
        path = self.log_dir / filename
        content = f"""## Decision Rationale

## Execution Summary

## Target Impact
"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def _get_latest_commit_sha(self) -> str:
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-1", "--format=%H"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except Exception:
            return "unknown"

    def run_wave(self, wave: int | None = None, task_id: str | None = None, auto: bool = False) -> None:
        pending = self.get_pending_tasks(wave=wave, task_id=task_id)
        if not pending:
            print("✅ 没有待执行的任务。")
            return

        if task_id:
            print(f"\n▶ 执行任务: {task_id}\n")
        elif wave is not None:
            print(f"\n▶ Wave {wave} — {len(pending)} 个任务\n")
        else:
            print(f"\n▶ 全部待执行任务 — {len(pending)} 个\n")

        for task in pending:
            tid = task["id"]
            title = task["title"]
            print(f"\n{'='*60}")
            print(f"任务: {tid} — {title}")
            print(f"{'='*60}\n")

            if not auto:
                confirm = input("执行此任务? [y/n/q]: ").strip().lower()
                if confirm == "q":
                    print("⏹️ 已中止。")
                    break
                if confirm != "y":
                    print("⏭️ 跳过。")
                    continue

            prompt = self._build_prompt(task)
            print(prompt)

            # Create AI log template for user
            log_path = self._create_ai_log_template(tid)
            print(f"\n📝 AI log 模板已创建: {log_path}")

            # Wait for user to finish execution in Kimi Code
            done = input("\n任务是否已在你的 AI 会话中完成? [y/n]: ").strip().lower()
            if done != "y":
                print("⏭️ 标记为未完成，继续下一个。")
                continue

            commit_sha = self._get_latest_commit_sha()
            log_ref = f"{tid}.md"
            self._mark_done(tid, commit_sha, log_ref)
            self._append_progress(tid, title, note="通过 AI 会话完成")
            print(f"✅ {tid} 已完成并记录 (commit: {commit_sha[:7]})")

        print("\n🏁 本轮执行结束。")
        self.status()


def main() -> None:
    parser = argparse.ArgumentParser(description="Kimi-CLI 版 Zeus Runner")
    parser.add_argument("--version", default="main", help="Zeus 版本 (默认: main)")
    parser.add_argument("--wave", type=int, default=None, help="仅执行指定 wave")
    parser.add_argument("--task", default=None, help="仅执行指定 task ID")
    parser.add_argument("--status", action="store_true", help="显示全局状态")
    parser.add_argument("--plan", action="store_true", help="显示执行计划")
    parser.add_argument("--auto", action="store_true", help="自动模式（对 Kimi 版不推荐）")

    args = parser.parse_args()
    runner = ZeusRunner(version=args.version)

    if args.status:
        runner.status()
    elif args.plan:
        runner.plan()
    elif args.wave is not None or args.task is not None:
        runner.run_wave(wave=args.wave, task_id=args.task, auto=args.auto)
    else:
        # Default: run current wave interactively
        current = runner.get_current_wave()
        if current is None:
            runner.status()
        else:
            runner.run_wave(wave=current, auto=args.auto)


if __name__ == "__main__":
    main()
