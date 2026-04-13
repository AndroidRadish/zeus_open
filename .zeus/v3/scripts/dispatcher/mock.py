"""
Mock dispatcher for testing and backward compatibility.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dispatcher.base import SubagentDispatcher


class MockSubagentDispatcher(SubagentDispatcher):
    """Writes a mock zeus-result.json and returns immediately."""

    async def run(self, task: dict[str, Any], workspace: Path, prompt: str) -> dict[str, Any]:
        import asyncio
        tid = task["id"]
        progress_path = workspace / "progress.jsonl"
        steps = [
            {"ts": "2026-04-13T15:30:00Z", "step": "planning", "message": "mock planning"},
            {"ts": "2026-04-13T15:31:00Z", "step": "writing", "message": "mock writing"},
            {"ts": "2026-04-13T15:32:00Z", "step": "testing", "message": "mock testing"},
        ]
        for step in steps:
            await asyncio.sleep(0.05)
            with open(progress_path, "a", encoding="utf-8") as f:
                f.write(__import__("json").dumps(step, ensure_ascii=False) + "\n")
        result = {
            "status": "completed",
            "changed_files": [],
            "test_summary": {"passed": 1, "failed": 0, "skipped": 0},
            "commit_sha": "mock",
            "artifacts": {"message": f"Mock dispatching {tid}"},
        }
        (workspace / ".mock_done").write_text("done", encoding="utf-8")
        (workspace / "zeus-result.json").write_text(__import__("json").dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
