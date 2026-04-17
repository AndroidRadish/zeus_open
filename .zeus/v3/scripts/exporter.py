"""
Export the current v3 plan from the database back to a JSON snapshot.

This is the inverse of importer: it produces a human-readable task.json-like
file for documentation, backup, or onboarding new contributors.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from store.base import AsyncStateStore


async def export_plan_to_json(store: AsyncStateStore, *, include_runtime: bool = False) -> dict[str, Any]:
    """Export the full plan (tasks, phases, milestones) from the database."""
    return await store.export_plan(include_runtime=include_runtime)


async def export_plan_to_file(
    store: AsyncStateStore,
    output_path: Path | str,
    *,
    include_runtime: bool = False,
) -> dict[str, Any]:
    """Export the plan and write it to a JSON file."""
    data = await export_plan_to_json(store, include_runtime=include_runtime)
    path = Path(output_path)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"output_path": str(path), "task_count": len(data.get("tasks", [])),
            "phase_count": len(data.get("phases", [])), "milestone_count": len(data.get("milestones", []))}
