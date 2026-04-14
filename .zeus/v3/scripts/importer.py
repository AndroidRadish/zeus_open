"""
Import static task plans from v2 task.json into the v3 database state store.

This is a one-way migration: task.json becomes the read-only plan source,
and the database becomes the mutable runtime state source.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from store.base import AsyncStateStore


async def import_tasks_from_json(store: AsyncStateStore, task_json_path: Path | str) -> dict[str, Any]:
    """Read a v2-format task.json and upsert all tasks into the state store."""
    path = Path(task_json_path)
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    tasks = data.get("tasks", [])
    quarantine = data.get("quarantine", [])
    meta = data.get("meta", {})

    imported = 0
    for t in tasks:
        passes = t.get("passes", False)
        # Infer completion from passes: a passed task is considered completed
        status = t.get("status", "completed" if passes else "pending")
        task_state = {
            "id": t["id"],
            "story_id": t.get("story_id"),
            "title": t.get("title", ""),
            "description": t.get("description"),
            "status": status,
            "passes": passes,
            "wave": t.get("wave", 1),
            "original_wave": t.get("original_wave"),
            "scheduled_wave": t.get("scheduled_wave"),
            "rescheduled_from": t.get("rescheduled_from"),
            "depends_on": t.get("depends_on", []),
            "commit_sha": t.get("commit_sha"),
            "ai_log_ref": t.get("ai_log_ref"),
            "files": t.get("files"),
            "extra": {k: v for k, v in t.items() if k not in {
                "id", "story_id", "title", "description", "status", "passes",
                "wave", "original_wave", "scheduled_wave", "rescheduled_from",
                "depends_on", "commit_sha", "ai_log_ref", "files",
            }},
        }
        await store.upsert_task(task_state)
        imported += 1

    for q in quarantine:
        await store.quarantine_task(
            task_id=q["task_id"],
            reason=q.get("reason", ""),
            workspace=q.get("workspace"),
            extra={k: v for k, v in q.items() if k not in {"task_id", "reason", "workspace", "quarantined_at"}},
        )

    for key, value in meta.items():
        await store.set_meta(key, value)

    return {
        "imported_tasks": imported,
        "quarantine_count": len(quarantine),
        "meta_keys": list(meta.keys()),
    }
