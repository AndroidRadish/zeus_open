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
        tid = task["id"]
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
