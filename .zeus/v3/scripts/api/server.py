"""
ZeusOpen v3 FastAPI server.

Provides REST + SSE endpoints for the v3 execution engine.
"""
from __future__ import annotations

import argparse
import os
from contextlib import asynccontextmanager
from typing import Any

import pathlib

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api.bus import EventBus
from api.control_plane import ControlPlane
from api.metrics import MetricsCollector
from db.engine import make_async_engine
from db.models import Base
from store.sqlite_store import SQLiteStateStore


class ScaleWorkersRequest(BaseModel):
    count: int


def create_app(
    store: SQLiteStateStore,
    bus: EventBus | None = None,
    control_plane: ControlPlane | None = None,
) -> FastAPI:
    bus = bus or EventBus()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await store.close()

    app = FastAPI(title="ZeusOpen v3 Server", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    static_dir = pathlib.Path(__file__).resolve().parent / "static"
    if static_dir.exists():
        app.mount("/dashboard", StaticFiles(directory=str(static_dir), html=True), name="dashboard")

    @app.get("/")
    async def root():
        return {"message": "ZeusOpen v3 API", "dashboard": "/dashboard"}

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "store": await store.health()}

    @app.get("/tasks")
    async def list_tasks(
        status: str | None = Query(None),
        wave: int | None = Query(None),
    ) -> list[dict[str, Any]]:
        return await store.list_tasks(status=status, wave=wave)

    @app.get("/tasks/{task_id}")
    async def get_task(task_id: str) -> dict[str, Any]:
        task = await store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    # ------------------------------------------------------------------
    # Task actions
    # ------------------------------------------------------------------
    @app.post("/tasks/{task_id}/retry")
    async def retry_task(task_id: str) -> dict[str, Any]:
        task = await store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await store.unquarantine_task(task_id)
        await store.update_task_status(task_id, "pending", passes=False, worker_id=None)
        await store.log_event(event_type="task.retried", task_id=task_id, agent_id="control-plane", payload={})
        bus.emit("task.retried", {"task_id": task_id})
        return {"success": True, "task_id": task_id}

    @app.post("/tasks/{task_id}/cancel")
    async def cancel_task(task_id: str) -> dict[str, Any]:
        task = await store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await store.update_task_status(task_id, "cancelled")
        await store.log_event(event_type="task.cancelled", task_id=task_id, agent_id="control-plane", payload={})
        bus.emit("task.cancelled", {"task_id": task_id})
        return {"success": True, "task_id": task_id}

    @app.post("/tasks/{task_id}/pause")
    async def pause_task(task_id: str) -> dict[str, Any]:
        task = await store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await store.update_task_status(task_id, "paused")
        await store.log_event(event_type="task.paused", task_id=task_id, agent_id="control-plane", payload={})
        bus.emit("task.paused", {"task_id": task_id})
        return {"success": True, "task_id": task_id}

    @app.post("/tasks/{task_id}/resume")
    async def resume_task(task_id: str) -> dict[str, Any]:
        task = await store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await store.update_task_status(task_id, "pending")
        await store.log_event(event_type="task.resumed", task_id=task_id, agent_id="control-plane", payload={})
        bus.emit("task.resumed", {"task_id": task_id})
        return {"success": True, "task_id": task_id}

    @app.post("/tasks/{task_id}/quarantine")
    async def quarantine_task(task_id: str) -> dict[str, Any]:
        task = await store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await store.quarantine_task(task_id, reason="manual quarantine")
        await store.update_task_status(task_id, "failed", passes=False)
        await store.log_event(event_type="task.quarantined", task_id=task_id, agent_id="control-plane", payload={})
        bus.emit("task.quarantined", {"task_id": task_id})
        return {"success": True, "task_id": task_id}

    @app.post("/tasks/{task_id}/unquarantine")
    async def unquarantine_task(task_id: str) -> dict[str, Any]:
        task = await store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await store.unquarantine_task(task_id)
        await store.update_task_status(task_id, "pending", passes=False)
        await store.log_event(event_type="task.unquarantined", task_id=task_id, agent_id="control-plane", payload={})
        bus.emit("task.unquarantined", {"task_id": task_id})
        return {"success": True, "task_id": task_id}

    @app.post("/tasks/{task_id}/progress")
    async def report_progress(task_id: str, body: dict[str, Any]) -> dict[str, Any]:
        task = await store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await store.log_event(
            event_type="task.progress",
            task_id=task_id,
            agent_id="external",
            payload={"source": "http", **body},
        )
        bus.emit("task.progress", {"task_id": task_id, "progress": body, "source": "http"})
        return {"success": True, "task_id": task_id}

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    @app.get("/events")
    async def list_events(
        event_type: str | None = Query(None),
        task_id: str | None = Query(None),
        agent_id: str | None = Query(None),
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ) -> list[dict[str, Any]]:
        return await store.query_events(
            event_type=event_type,
            task_id=task_id,
            agent_id=agent_id,
            limit=limit,
            offset=offset,
        )

    @app.get("/events/stream")
    async def events_stream() -> StreamingResponse:
        async def generator():
            async for chunk in bus.subscribe():
                yield chunk.encode("utf-8")

        return StreamingResponse(
            generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    @app.get("/metrics/summary")
    async def metrics_summary() -> dict[str, Any]:
        collector = MetricsCollector(store)
        return await collector.summary()

    @app.get("/metrics/tasks")
    async def metrics_tasks() -> list[dict[str, Any]]:
        collector = MetricsCollector(store)
        return await collector.task_metrics()

    @app.get("/metrics/bottleneck")
    async def metrics_bottleneck(top_n: int = Query(5, ge=1, le=100)) -> list[dict[str, Any]]:
        collector = MetricsCollector(store)
        return await collector.bottleneck_tasks(top_n=top_n)

    @app.get("/metrics/blocked")
    async def metrics_blocked() -> list[dict[str, Any]]:
        collector = MetricsCollector(store)
        return await collector.blocked_chains()

    # ------------------------------------------------------------------
    # Control plane
    # ------------------------------------------------------------------
    def _ensure_control_plane():
        if control_plane is None:
            raise HTTPException(status_code=503, detail="Control plane not enabled")

    @app.get("/control/status")
    async def control_status() -> dict[str, Any]:
        _ensure_control_plane()
        return await control_plane.status()

    @app.post("/control/scheduler/start")
    async def control_scheduler_start() -> dict[str, Any]:
        _ensure_control_plane()
        try:
            pid = await control_plane.spawn_scheduler()
            return {"success": True, "pid": pid}
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e))

    @app.post("/control/scheduler/stop")
    async def control_scheduler_stop() -> dict[str, Any]:
        _ensure_control_plane()
        await control_plane.stop_scheduler()
        return {"success": True}

    @app.post("/control/scheduler/tick")
    async def control_scheduler_tick() -> dict[str, Any]:
        _ensure_control_plane()
        result = await control_plane.tick_once()
        return {"success": True, "result": result}

    @app.post("/control/workers/scale")
    async def control_workers_scale(body: ScaleWorkersRequest) -> dict[str, Any]:
        _ensure_control_plane()
        pids = await control_plane.spawn_workers(body.count)
        return {"success": True, "pids": pids}

    @app.post("/control/workers/stop")
    async def control_workers_stop() -> dict[str, Any]:
        _ensure_control_plane()
        await control_plane.stop_workers()
        return {"success": True}

    @app.post("/control/import")
    async def control_import() -> dict[str, Any]:
        _ensure_control_plane()
        result = await control_plane.import_tasks()
        return {"success": True, "result": result}

    @app.post("/control/global/run")
    async def control_global_run() -> dict[str, Any]:
        _ensure_control_plane()
        result = await control_plane.global_run()
        return {"success": True, "result": result}

    return app


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ZeusOpen v3 API Server")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--version", default="v3")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args(argv)


def _auto_detect_project_root(fallback: pathlib.Path, version: str = "v3") -> pathlib.Path:
    """If server.py is inside .zeus/<version>/scripts/api/, detect project root."""
    this_file = pathlib.Path(__file__).resolve()
    if (
        this_file.name == "server.py"
        and this_file.parent.name == "api"
        and this_file.parent.parent.name == "scripts"
    ):
        candidate = this_file.parent.parent.parent.parent
        if (candidate / ".zeus" / version / "task.json").exists():
            return candidate
    return fallback


async def ensure_schema(database_url: str) -> None:
    engine = make_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


def main(argv: list[str] | None = None) -> FastAPI:
    args = parse_args(argv)
    project_root = pathlib.Path(args.project_root).resolve()
    version = args.version

    if not (project_root / ".zeus" / version / "task.json").exists():
        project_root = _auto_detect_project_root(project_root, version)

    if not args.database_url:
        db_file = project_root / ".zeus" / version / "state.db"
        db_file.parent.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite+aiosqlite:///{db_file}"
    else:
        database_url = args.database_url

    import asyncio
    asyncio.run(ensure_schema(database_url))

    store = SQLiteStateStore(database_url)
    bus = EventBus()

    control_plane = None
    if os.environ.get("ZEUS_CONTROL_PLANE_ENABLED", "true").lower() != "false":
        control_plane = ControlPlane(store, bus, project_root, database_url)

    app = create_app(store, bus, control_plane)
    return app


# Expose default app for direct uvicorn usage: uvicorn api.server:app
# Use empty argv so import-time creation does not accidentally consume pytest args.
app = main([])


if __name__ == "__main__":
    import uvicorn
    args = parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
