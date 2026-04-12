"""
ZeusOpen v2 FastAPI unified backend.

Provides REST APIs for the PyQt GUI and Web frontend.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from scheduler_state import SchedulerStateDB
from store import LocalStore
from workflow_graph import WorkflowGraph
from zeus_orchestrator import ZeusOrchestrator

app = FastAPI(title="ZeusOpen v2 Server")

# Track active global scheduler runs to avoid duplicates
_active_global_runs: set[str] = set()

# Reference to active orchestrators for graceful shutdown
_global_orchs: dict[str, ZeusOrchestrator] = {}
_shutdown_called = False


def _stop_schedulers() -> None:
    global _shutdown_called
    if _shutdown_called:
        return
    _shutdown_called = True
    for version, orch in list(_global_orchs.items()):
        try:
            orch.stop_global_scheduler()
        except Exception:
            pass


@app.on_event("startup")
async def on_startup() -> None:
    version = "v2"
    db_path = _scheduler_db_path(version)
    if os.path.exists(db_path):
        try:
            db = SchedulerStateDB(db_path)
            snapshot = db.load()
            if snapshot.get("meta", {}).get("scheduler_active"):
                orch = ZeusOrchestrator(version=version, project_root=str(store.base_dir), max_parallel=3)
                orch.resume_from_state()
        except Exception:
            pass


@app.on_event("shutdown")
async def on_shutdown() -> None:
    _stop_schedulers()

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


def _scheduler_db_path(version: str) -> str:
    return str(store._resolve(f".zeus/{version}/scheduler_state.db"))


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


def _read_roadmap_json(version: str) -> dict[str, Any]:
    path = f".zeus/{version}/roadmap.json"
    if store._resolve(path).exists():
        return store.read_json(path)
    return {"milestones": [], "phases": []}


def _compute_phase_status(phase: dict, milestone_statuses: dict[str, str]) -> str:
    ids = phase.get("milestone_ids", [])
    if not ids:
        return "pending"
    statuses = [milestone_statuses.get(mid, "pending") for mid in ids]
    if all(s == "completed" for s in statuses):
        return "completed"
    if any(s in ("completed", "in_progress") for s in statuses):
        return "in_progress"
    return "pending"


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

    # Determine current_phase from roadmap phases based on current_wave
    current_phase = None
    roadmap_data = _read_roadmap_json(version)
    for ph in roadmap_data.get("phases", []):
        ws = ph.get("wave_start")
        we = ph.get("wave_end")
        if ws is not None and current_wave >= ws:
            if we is None or current_wave <= we:
                current_phase = ph["id"]
                break

    return {
        "version": version,
        "project_name": project_name,
        "current_wave": current_wave,
        "current_phase": current_phase,
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


@app.get("/phases")
def get_phases(version: str = Query("v2")) -> dict[str, Any]:
    roadmap_data = _read_roadmap_json(version)
    task_data = _read_task_json(version)
    tasks_by_id = {t["id"]: t for t in task_data.get("tasks", [])}

    # Compute milestone statuses from task pass states
    milestone_statuses: dict[str, str] = {}
    milestone_progress: dict[str, int] = {}
    milestones = roadmap_data.get("milestones", [])
    for ms in milestones:
        ms_tasks = [tasks_by_id[tid] for tid in ms.get("task_ids", []) if tid in tasks_by_id]
        total = len(ms_tasks)
        done = sum(1 for mt in ms_tasks if mt.get("passes"))
        milestone_progress[ms["id"]] = round((done / total) * 100) if total else 0
        if total == 0:
            milestone_statuses[ms["id"]] = "pending"
        elif done == total:
            milestone_statuses[ms["id"]] = "completed"
        else:
            milestone_statuses[ms["id"]] = "in_progress"

    # Build phase payload with nested milestones
    phases = roadmap_data.get("phases", [])
    result: list[dict[str, Any]] = []
    for ph in phases:
        ph_milestones: list[dict[str, Any]] = []
        for mid in ph.get("milestone_ids", []):
            ms = next((m for m in milestones if m["id"] == mid), None)
            if ms:
                ph_milestones.append({
                    "id": ms["id"],
                    "title": ms.get("title", ""),
                    "status": milestone_statuses.get(mid, "pending"),
                    "progress_percent": milestone_progress.get(mid, 0),
                })
        total = len(ph_milestones)
        progress = round(sum(pm["progress_percent"] for pm in ph_milestones) / total) if total else 0
        result.append({
            "id": ph.get("id"),
            "title": ph.get("title", ""),
            "title_en": ph.get("title_en"),
            "title_zh": ph.get("title_zh"),
            "summary": ph.get("summary", ""),
            "summary_en": ph.get("summary_en"),
            "summary_zh": ph.get("summary_zh"),
            "wave_start": ph.get("wave_start"),
            "wave_end": ph.get("wave_end"),
            "status": _compute_phase_status(ph, milestone_statuses),
            "progress_percent": progress,
            "milestones": ph_milestones,
        })
    return {"phases": result}


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


@app.get("/mailbox/{agent_id}")
def get_mailbox(agent_id: str, version: str = Query("v2"), mark_read: bool = Query(False)) -> dict[str, Any]:
    from agent_bus import AgentBus
    bus = AgentBus(version=version, wave=-1, store=store)
    messages = bus.receive(agent_id, mark_read=mark_read)
    return {"agent_id": agent_id, "messages": messages}


@app.post("/tasks/{task_id}/retry")
def retry_task(task_id: str, version: str = Query("v2")) -> dict:
    orch = ZeusOrchestrator(version=version, project_root=str(store.base_dir), max_parallel=3)
    result = orch.retry_task(task_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Retry failed"))
    return result


@app.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str, version: str = Query("v2")) -> dict:
    orch = ZeusOrchestrator(version=version, project_root=str(store.base_dir), max_parallel=3)
    result = orch.cancel_task(task_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Cancel failed"))
    return result


@app.post("/tasks/{task_id}/pause")
def pause_task(task_id: str, version: str = Query("v2")) -> dict:
    orch = ZeusOrchestrator(version=version, project_root=str(store.base_dir), max_parallel=3)
    result = orch.pause_task(task_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Pause failed"))
    return result


@app.get("/global/status")
def get_global_status(version: str = Query("v2")) -> dict[str, Any]:
    data = _read_task_json(version)
    tasks = data.get("tasks", [])
    quarantine = data.get("quarantine", [])

    # Running agents from latest wave events
    current_wave = data.get("meta", {}).get("current_wave", 1)
    events = _load_events(current_wave, version)
    running_map: dict[str, dict[str, Any]] = {}
    for evt in events:
        tid = evt.get("task_id")
        if evt.get("type") == "task.started":
            running_map[tid] = {"agent_id": evt.get("agent_id", ""), "started_at": evt.get("ts", "")}
        elif evt.get("type") in ("task.completed", "task.failed", "task.quarantined"):
            running_map.pop(tid, None)

    pending = [t for t in tasks if not t.get("passes", False)]
    pending_by_wave: dict[int, list[dict[str, Any]]] = {}
    for t in pending:
        w = t.get("wave", 1)
        pending_by_wave.setdefault(w, []).append({
            "id": t["id"],
            "title": t.get("title", ""),
            "wave": w,
            "depends_on": t.get("depends_on", []),
        })

    running = []
    for tid, info in running_map.items():
        task = next((t for t in tasks if t["id"] == tid), None)
        running.append({
            "task_id": tid,
            "agent_id": info["agent_id"],
            "started_at": info["started_at"],
            "wave": task.get("wave", 1) if task else 1,
        })

    # Merge any active tasks recovered from SQLite scheduler state
    db_path = _scheduler_db_path(version)
    if os.path.exists(db_path):
        try:
            db = SchedulerStateDB(db_path)
            snapshot = db.load()
            for at in snapshot.get("active_tasks", []):
                tid = at.get("task_id")
                if tid and not any(r["task_id"] == tid for r in running):
                    task = next((t for t in tasks if t["id"] == tid), None)
                    running.append({
                        "task_id": tid,
                        "agent_id": at.get("agent_id", ""),
                        "started_at": at.get("started_at", ""),
                        "wave": at.get("wave", 1) if task is None else task.get("wave", 1),
                    })
        except Exception:
            pass  # SQLite may be locked or corrupt; fall back to event-only view

    status_map = {t["id"]: t.get("status", "pending") for t in tasks}
    for r in running:
        r["status"] = status_map.get(r["task_id"], "running")
    return {
        "running": running,
        "pending_by_wave": pending_by_wave,
        "quarantine": quarantine,
        "scheduler_active": version in _active_global_runs,
        "status_map": status_map,
    }


@app.get("/global/recovery")
def get_global_recovery(version: str = Query("v2")) -> dict[str, Any]:
    db_path = _scheduler_db_path(version)
    recovered = False
    recovered_at = None
    active_tasks_count = 0
    if os.path.exists(db_path):
        try:
            db = SchedulerStateDB(db_path)
            snapshot = db.load()
            active_tasks = snapshot.get("active_tasks", [])
            active_tasks_count = len(active_tasks)
            if active_tasks_count > 0:
                recovered = True
                recovered_at = db.get_meta("recovered_at")
        except Exception:
            pass
    return {
        "recovered": recovered,
        "recovered_at": recovered_at,
        "active_tasks_count": active_tasks_count,
    }


@app.post("/global/run")
async def run_global(version: str = Query("v2")) -> dict[str, Any]:
    if version in _active_global_runs:
        raise HTTPException(status_code=409, detail="Global scheduler already running for this version")

    async def _run() -> None:
        orch = ZeusOrchestrator(version=version, project_root=str(store.base_dir), max_parallel=3)
        _global_orchs[version] = orch
        try:
            await orch.run_global()
        finally:
            _active_global_runs.discard(version)
            _global_orchs.pop(version, None)

    _active_global_runs.add(version)
    asyncio.create_task(_run())
    return {"started": True, "version": version}


@app.get("/agent-ids")
def get_agent_ids(version: str = Query("v2")) -> dict[str, Any]:
    """Return all agent IDs discovered from the agent-logs directory."""
    logs_dir = store._resolve(f".zeus/{version}/agent-logs")
    ids: list[str] = []
    if logs_dir.exists() and logs_dir.is_dir():
        for entry in sorted(logs_dir.iterdir()):
            if entry.is_dir() and not entry.name.startswith("mailbox"):
                ids.append(entry.name)
    return {"agent_ids": ids}


@app.get("/agents/{agent_id}/logs")
def get_agent_logs(agent_id: str, version: str = Query("v2")) -> dict[str, Any]:
    base = store._resolve(f".zeus/{version}/agent-logs/{agent_id}")
    activity_path = base / "activity.md"
    reasoning_path = base / "reasoning.jsonl"

    activity = ""
    if activity_path.exists():
        activity = activity_path.read_text(encoding="utf-8")

    reasoning: list[dict[str, Any]] = []
    if reasoning_path.exists():
        for line in reasoning_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                reasoning.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return {
        "agent_id": agent_id,
        "activity": activity,
        "reasoning": reasoning,
    }


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
    def _signal_handler(signum: int, frame: Any) -> None:
        _stop_schedulers()
        if signum == signal.SIGINT:
            raise KeyboardInterrupt
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
    except Exception:
        pass

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
