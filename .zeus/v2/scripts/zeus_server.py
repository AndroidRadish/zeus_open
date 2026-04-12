"""
ZeusOpen v2 FastAPI unified backend.

Provides REST APIs for the PyQt GUI and Web frontend.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from store import LocalStore
from workflow_graph import WorkflowGraph

app = FastAPI(title="ZeusOpen v2 Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global store instance (project root by default)
store = LocalStore()

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _task_json_path(version: str) -> str:
    return f".zeus/{version}/task.json"


def _agent_logs_dir(version: str) -> str:
    return f".zeus/{version}/agent-logs"


def _resolve(path: str) -> str:
    """Return absolute path via the current store."""
    return str(store._resolve(path))


def _read_task_json(version: str) -> dict[str, Any]:
    return store.read_json(_task_json_path(version))


def _validate_task_json(data: dict[str, Any]) -> str:
    """Simplified validation consistent with v1 runner logic."""
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        return "fail"

    task_ids: set[str] = set()
    for t in tasks:
        tid = t.get("id")
        if not tid:
            return "fail"
        if tid in task_ids:
            return "fail"
        task_ids.add(tid)

        wave = t.get("wave")
        if wave is not None and (not isinstance(wave, int) or wave < 1):
            return "fail"

        deps = t.get("depends_on", [])
        if not isinstance(deps, list):
            return "fail"
        for dep in deps:
            if dep and dep not in task_ids:
                return "fail"

    # Detect circular dependencies (simple DFS)
    graph = {t["id"]: t.get("depends_on", []) for t in tasks if t.get("id")}

    def _has_cycle(node: str, visited: set[str], stack: set[str]) -> bool:
        visited.add(node)
        stack.add(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if _has_cycle(neighbor, visited, stack):
                    return True
            elif neighbor in stack:
                return True
        stack.remove(node)
        return False

    visited: set[str] = set()
    for node in graph:
        if node not in visited:
            if _has_cycle(node, visited, set()):
                return "fail"

    return "pass"


def _load_events(wave: int, version: str) -> list[dict[str, Any]]:
    path = os.path.join(_agent_logs_dir(version), f"wave-{wave}-events.jsonl")
    resolved = store._resolve(path)
    events: list[dict[str, Any]] = []
    if not resolved.exists():
        return events
    for line in resolved.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _discover_versions() -> list[dict[str, str]]:
    """Scan .zeus/ for available version folders with task.json."""
    zeus_dir = store._resolve(".zeus")
    versions = []
    if zeus_dir.exists():
        for entry in sorted(zeus_dir.iterdir()):
            if entry.is_dir() and (entry / "task.json").exists():
                versions.append({"id": entry.name, "label": entry.name})
    # Ensure v2 is first if present
    versions.sort(key=lambda v: (v["id"] != "v2", v["id"]))
    return versions


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------

@app.get("/status")
def get_status(version: str = Query("v2")) -> dict[str, Any]:
    data = _read_task_json(version)
    meta = data.get("meta", {})
    tasks = data.get("tasks", [])
    current_wave = meta.get("current_wave", 0)

    pending = sum(1 for t in tasks if not t.get("passes"))
    completed = sum(1 for t in tasks if t.get("passes"))

    config = store.read_json(f".zeus/{version}/config.json") if store._resolve(f".zeus/{version}/config.json").exists() else {}
    project_name = config.get("project", {}).get("name", "zeus-open")

    return {
        "version": version,
        "project_name": project_name,
        "current_wave": current_wave,
        "pending_tasks": pending,
        "completed_tasks": completed,
        "validation": _validate_task_json(data),
        "project_dir": str(store.base_dir),
    }


@app.get("/wave/{n}")
def get_wave(n: int, version: str = Query("v2")) -> dict[str, Any]:
    data = _read_task_json(version)
    tasks = data.get("tasks", [])
    wave_tasks = [
        {
            "id": t["id"],
            "title": t.get("title", ""),
            "title_en": t.get("title_en"),
            "title_zh": t.get("title_zh"),
            "description": t.get("description", ""),
            "description_en": t.get("description_en"),
            "description_zh": t.get("description_zh"),
            "passes": t.get("passes", False),
            "depends_on": t.get("depends_on", []),
            "wave": t.get("wave"),
            "original_wave": t.get("original_wave", t.get("wave")),
            "scheduled_wave": t.get("scheduled_wave", t.get("wave")),
            "rescheduled_from": t.get("rescheduled_from"),
        }
        for t in tasks
        if t.get("wave") == n
    ]
    return {"wave": n, "tasks": wave_tasks}


@app.get("/milestones")
def get_milestones(version: str = Query("v2")) -> dict[str, Any]:
    roadmap_path = f".zeus/{version}/roadmap.json"
    roadmap_data = store.read_json(roadmap_path) if store._resolve(roadmap_path).exists() else {"milestones": []}
    task_data = _read_task_json(version)
    tasks = {t["id"]: t for t in task_data.get("tasks", [])}

    result: list[dict[str, Any]] = []
    for ms in roadmap_data.get("milestones", []):
        ms_tasks: list[dict[str, Any]] = []
        for tid in ms.get("task_ids", []):
            if tid in tasks:
                t = tasks[tid]
                ms_tasks.append({
                    "id": t["id"],
                    "title": t.get("title", ""),
                    "title_en": t.get("title_en"),
                    "title_zh": t.get("title_zh"),
                    "passes": t.get("passes", False),
                    "wave": t.get("wave"),
                    "original_wave": t.get("original_wave", t.get("wave")),
                    "scheduled_wave": t.get("scheduled_wave", t.get("wave")),
                })
        total = len(ms_tasks)
        done = sum(1 for mt in ms_tasks if mt["passes"])
        if total == 0:
            status = "pending"
        elif done == total:
            status = "completed"
        else:
            status = "in_progress"
        progress = round((done / total) * 100) if total else 0
        result.append({
            "id": ms.get("id"),
            "title": ms.get("title", ""),
            "status": status,
            "progress_percent": progress,
            "tasks": ms_tasks,
        })
    return {"milestones": result}


@app.get("/agents")
def get_agents(version: str = Query("v2")) -> dict[str, Any]:
    data = _read_task_json(version)
    current_wave = data.get("meta", {}).get("current_wave", 1)
    events = _load_events(current_wave, version)

    state: dict[str, str] = {}
    latest_start: dict[str, dict[str, Any]] = {}
    latest_end: dict[str, dict[str, Any]] = {}

    for evt in events:
        tid = evt.get("task_id")
        typ = evt.get("type")
        if typ == "task.started":
            latest_start[tid] = evt
            state[tid] = "running"
        elif typ == "task.completed":
            state[tid] = "completed"
            latest_end[tid] = evt
        elif typ == "task.failed":
            state[tid] = "failed"
            latest_end[tid] = evt

    running: list[dict[str, Any]] = []
    recent: list[dict[str, Any]] = []

    for tid, evt in latest_start.items():
        agent = {
            "agent_id": evt.get("agent_id", ""),
            "task_id": tid,
            "started_at": evt.get("ts", ""),
            "status": state.get(tid, "running"),
        }
        if latest_end.get(tid):
            agent["finished_at"] = latest_end[tid].get("ts", "")
        if state.get(tid) == "running":
            running.append(agent)
        else:
            recent.append(agent)

    # Sort recent by finished_at descending, keep top 10
    recent.sort(key=lambda a: a.get("finished_at", ""), reverse=True)
    recent = recent[:10]

    return {"running": running, "recent": recent}


@app.get("/events")
def get_events(wave: int = Query(...), limit: int = Query(50), version: str = Query("v2")) -> list[dict[str, Any]]:
    events = _load_events(wave, version)
    return events[-limit:]


@app.get("/discussion")
def get_discussion(wave: int = Query(...), version: str = Query("v2")) -> Response:
    path = os.path.join(_agent_logs_dir(version), f"wave-{wave}-discussion.md")
    resolved = store._resolve(path)
    if resolved.exists():
        content = resolved.read_text(encoding="utf-8")
    else:
        content = ""
    return Response(content=content, media_type="text/plain; charset=utf-8")


@app.get("/graph/mermaid")
def graph_mermaid(version: str = Query("v2")) -> Response:
    path = _resolve(_task_json_path(version))
    graph = WorkflowGraph(path)
    return Response(content=graph.to_mermaid(), media_type="text/plain; charset=utf-8")


@app.get("/graph/echarts")
def graph_echarts(version: str = Query("v2")) -> dict[str, Any]:
    path = _resolve(_task_json_path(version))
    graph = WorkflowGraph(path)
    return graph.to_echarts()


@app.get("/graph/svg")
def graph_svg(version: str = Query("v2")) -> Response:
    path = _resolve(_task_json_path(version))
    graph = WorkflowGraph(path)

    if shutil.which("dot") is not None:
        dot_src = graph.to_graphviz()
        with tempfile.TemporaryDirectory() as tmpdir:
            dot_path = os.path.join(tmpdir, "graph.dot")
            svg_path = os.path.join(tmpdir, "graph.svg")
            with open(dot_path, "w", encoding="utf-8") as f:
                f.write(dot_src)
            result = subprocess.run(
                ["dot", "-Tsvg", dot_path, "-o", svg_path],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                err = result.stderr.strip() or "unknown error"
                raise HTTPException(status_code=503, detail=f"dot command failed: {err}")
            with open(svg_path, "r", encoding="utf-8") as f:
                svg_content = f.read()
        return Response(content=svg_content, media_type="image/svg+xml")

    # Fallback: pure-Python native SVG renderer (no Graphviz required)
    svg_content = graph.to_svg_native()
    return Response(content=svg_content, media_type="image/svg+xml")


@app.post("/wave/{n}/approve")
def approve_wave(n: int, version: str = Query("v2")) -> dict[str, Any]:
    task_path = _task_json_path(version)
    with store.lock(task_path):
        data = store.read_json(task_path)
        tasks = data.get("tasks", [])
        # Approval gate uses original_wave so rescheduled tasks still count toward their home wave
        wave_tasks = [t for t in tasks if t.get("original_wave", t.get("wave")) == n]
        if not wave_tasks:
            raise HTTPException(status_code=400, detail=f"No tasks found for wave {n}")
        pending = [t for t in wave_tasks if not t.get("passes")]
        if pending:
            raise HTTPException(
                status_code=400,
                detail=f"Wave {n} has pending tasks",
            )
        data["meta"]["current_wave"] = n + 1
        store.write_json(task_path, data)

    return {"approved": True, "next_wave": n + 1}


class OpenProjectBody(BaseModel):
    project_dir: str


def _is_valid_zeus_project(project_dir: Path) -> bool:
    """Check if *project_dir* contains a .zeus/ folder with at least one task.json."""
    if not project_dir.is_dir():
        return False
    zeus_dir = project_dir / ".zeus"
    if not zeus_dir.is_dir():
        return False
    for entry in zeus_dir.iterdir():
        if entry.is_dir() and (entry / "task.json").exists():
            return True
    return False


@app.post("/project/open")
def open_project(body: OpenProjectBody) -> dict[str, Any]:
    target = Path(body.project_dir).expanduser().resolve()
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="project_dir must be a directory")
    if not _is_valid_zeus_project(target):
        raise HTTPException(
            status_code=400,
            detail="Not a valid Zeus project: .zeus directory missing or no task.json found",
        )
    global store
    store = LocalStore(base_dir=str(target))
    return {
        "success": True,
        "project_dir": str(store.base_dir),
        "status": get_status(version="v2"),
    }


@app.get("/versions")
def get_versions() -> dict[str, Any]:
    return {"versions": _discover_versions()}


# ----------------------------------------------------------------------
# Static web frontend
# ----------------------------------------------------------------------
web_dir = os.path.join(os.path.dirname(__file__), "..", "web")
if os.path.isdir(web_dir):
    app.mount("/web", StaticFiles(directory=web_dir, html=True), name="web")


# ----------------------------------------------------------------------
# CLI entrypoint
# ----------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="ZeusOpen v2 Server")
    parser.add_argument("--port", type=int, default=8234)
    parser.add_argument("--project-dir", type=str, default=None, help="Zeus project root directory")
    args = parser.parse_args()

    if args.project_dir:
        global store
        store = LocalStore(base_dir=args.project_dir)

    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
