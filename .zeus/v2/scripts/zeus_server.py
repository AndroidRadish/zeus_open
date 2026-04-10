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
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
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

TASK_JSON_PATH = ".zeus/v2/task.json"
AGENT_LOGS_DIR = ".zeus/v2/agent-logs"


def _resolve(path: str) -> str:
    """Return absolute path via the current store."""
    return str(store._resolve(path))


def _read_task_json() -> dict[str, Any]:
    return store.read_json(TASK_JSON_PATH)


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


def _load_events(wave: int) -> list[dict[str, Any]]:
    path = os.path.join(AGENT_LOGS_DIR, f"wave-{wave}-events.jsonl")
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


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------

@app.get("/status")
def get_status() -> dict[str, Any]:
    data = _read_task_json()
    meta = data.get("meta", {})
    tasks = data.get("tasks", [])
    current_wave = meta.get("current_wave", 0)

    pending = sum(1 for t in tasks if not t.get("passes"))
    completed = sum(1 for t in tasks if t.get("passes"))

    return {
        "version": "v2",
        "project_name": "zeus-open",
        "current_wave": current_wave,
        "pending_tasks": pending,
        "completed_tasks": completed,
        "validation": _validate_task_json(data),
    }


@app.get("/wave/{n}")
def get_wave(n: int) -> dict[str, Any]:
    data = _read_task_json()
    tasks = data.get("tasks", [])
    wave_tasks = [
        {
            "id": t["id"],
            "title": t.get("title", ""),
            "passes": t.get("passes", False),
            "depends_on": t.get("depends_on", []),
        }
        for t in tasks
        if t.get("wave") == n
    ]
    return {"wave": n, "tasks": wave_tasks}


@app.get("/agents")
def get_agents() -> dict[str, Any]:
    data = _read_task_json()
    current_wave = data.get("meta", {}).get("current_wave", 1)
    events = _load_events(current_wave)

    state: dict[str, str] = {}
    latest_start: dict[str, dict[str, Any]] = {}

    for evt in events:
        tid = evt.get("task_id")
        typ = evt.get("type")
        if typ == "task.started":
            latest_start[tid] = evt
            state[tid] = "running"
        elif typ in ("task.completed", "task.failed"):
            state[tid] = "done"

    agents = []
    for tid, evt in latest_start.items():
        if state.get(tid) == "running":
            agents.append(
                {
                    "agent_id": evt.get("agent_id", ""),
                    "task_id": tid,
                    "started_at": evt.get("ts", ""),
                    "status": "running",
                }
            )

    return {"agents": agents}


@app.get("/events")
def get_events(wave: int = Query(...), limit: int = Query(50)) -> list[dict[str, Any]]:
    events = _load_events(wave)
    return events[-limit:]


@app.get("/discussion")
def get_discussion(wave: int = Query(...)) -> Response:
    path = os.path.join(AGENT_LOGS_DIR, f"wave-{wave}-discussion.md")
    resolved = store._resolve(path)
    if resolved.exists():
        content = resolved.read_text(encoding="utf-8")
    else:
        content = ""
    return Response(content=content, media_type="text/plain; charset=utf-8")


@app.get("/graph/mermaid")
def graph_mermaid() -> Response:
    path = _resolve(TASK_JSON_PATH)
    graph = WorkflowGraph(path)
    return Response(content=graph.to_mermaid(), media_type="text/plain; charset=utf-8")


@app.get("/graph/echarts")
def graph_echarts() -> dict[str, Any]:
    path = _resolve(TASK_JSON_PATH)
    graph = WorkflowGraph(path)
    return graph.to_echarts()


@app.get("/graph/svg")
def graph_svg() -> Response:
    path = _resolve(TASK_JSON_PATH)
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
def approve_wave(n: int) -> dict[str, Any]:
    with store.lock(TASK_JSON_PATH):
        data = store.read_json(TASK_JSON_PATH)
        tasks = data.get("tasks", [])
        wave_tasks = [t for t in tasks if t.get("wave") == n]
        if not wave_tasks:
            raise HTTPException(status_code=400, detail=f"No tasks found for wave {n}")
        pending = [t for t in wave_tasks if not t.get("passes")]
        if pending:
            raise HTTPException(
                status_code=400,
                detail=f"Wave {n} has pending tasks",
            )
        data["meta"]["current_wave"] = n + 1
        store.write_json(TASK_JSON_PATH, data)

    return {"approved": True, "next_wave": n + 1}


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
    args = parser.parse_args()
    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
