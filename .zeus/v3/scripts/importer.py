"""
Import static task plans from an optional task.json into the v3 database state store.

v3 design:
- task.json is an optional static plan source (id, title, description, depends_on, wave, files, phases, milestones).
- Runtime fields (status, passes, commit_sha, worker_id, heartbeat_at) live in the database ONLY.
- Importing never overwrites existing runtime state.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from store.base import AsyncStateStore


# Fields that belong to the static plan definition
_STATIC_TASK_FIELDS = {
    "id", "story_id", "title", "description", "wave", "original_wave",
    "scheduled_wave", "rescheduled_from", "depends_on", "ai_log_ref",
    "files", "milestone_id", "extra", "created_at",
}


async def import_tasks_from_json(store: AsyncStateStore, task_json_path: Path | str) -> dict[str, Any]:
    """Read a task.json and upsert static fields into the state store.

    Existing tasks are merged: static fields are updated from the JSON,
    but runtime fields (status, passes, commit_sha, worker_id, heartbeat_at)
    are always preserved from the database.
    """
    path = Path(task_json_path)
    if not path.exists():
        return {"imported_tasks": 0, "imported_phases": 0, "imported_milestones": 0, "quarantine_count": 0, "meta_keys": [], "skipped": True}

    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    tasks = data.get("tasks", [])
    quarantine = data.get("quarantine", [])
    meta = data.get("meta", {})

    imported = 0
    for t in tasks:
        tid = t["id"]
        existing = await store.get_task(tid)
        if existing:
            # Preserve scalar runtime fields from DB; overlay static fields from JSON
            # NOTE: heartbeat_at is a DateTime column and must not be passed as a string
            task_state: dict[str, Any] = {k: existing[k] for k in ("status", "passes", "commit_sha", "worker_id") if k in existing}
            extra: dict[str, Any] = {}
            for k, v in t.items():
                if k in _STATIC_TASK_FIELDS:
                    task_state[k] = v
                elif k not in ("status", "passes", "commit_sha", "worker_id", "heartbeat_at"):
                    extra[k] = v
            if extra:
                task_state["extra"] = extra
            task_state["id"] = tid
        else:
            # New task: default runtime state
            task_state = {
                "id": tid,
                "status": "pending",
                "passes": False,
                "commit_sha": None,
                "worker_id": None,
                "heartbeat_at": None,
            }
            extra = {}
            for k, v in t.items():
                if k in _STATIC_TASK_FIELDS:
                    task_state[k] = v
                elif k not in ("status", "passes", "commit_sha", "worker_id", "heartbeat_at"):
                    extra[k] = v
            if extra:
                task_state["extra"] = extra

        await store.upsert_task(task_state)
        imported += 1

    phases = data.get("phases", [])
    for p in phases:
        await store.upsert_phase(p)

    milestones = data.get("milestones", [])
    for m in milestones:
        await store.upsert_milestone(m)

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
        "imported_phases": len(phases),
        "imported_milestones": len(milestones),
        "quarantine_count": len(quarantine),
        "meta_keys": list(meta.keys()),
        "skipped": False,
    }
