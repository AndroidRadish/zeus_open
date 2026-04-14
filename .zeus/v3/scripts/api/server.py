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

from fastapi import FastAPI, HTTPException, Query, Request as FastAPIRequest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api.bus import EventBus
from api.control_plane import ControlPlane
from api.metrics import MetricsCollector
from api.workflow_graph import WorkflowGraph
from core.recovery import recover_running_tasks
from db.engine import make_async_engine
from db.models import Base
from store.sqlite_store import SQLiteStateStore


class ScaleWorkersRequest(BaseModel):
    count: int


def create_app(
    store: SQLiteStateStore,
    bus: EventBus | None = None,
    control_plane: ControlPlane | None = None,
    embedded_runner: dict[str, Any] | None = None,
) -> FastAPI:
    bus = bus or EventBus()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        scheduler_task = None
        worker_watch_task = None
        pool = None
        queue = None

        # Recover any tasks stuck in 'running' from a previous scheduler crash
        recovered = await recover_running_tasks(app.state.store)
        if recovered:
            await app.state.store.log_event(
                event_type="scheduler.recovered",
                task_id="global",
                agent_id="api-server",
                payload={"recovered_count": len(recovered), "task_ids": recovered},
            )

        if embedded_runner:
            import asyncio
            from core.scheduler import ZeusScheduler
            from core.worker_pool import WorkerPool
            from config import ZeusConfig
            from dispatcher.cli import build_dispatcher
            from workspace import build_workspace_manager
            from task_queue.memory_queue import MemoryTaskQueue
            from task_queue.sqlite_queue import SqliteTaskQueue

            project_root = pathlib.Path(embedded_runner["project_root"]).resolve()
            version = embedded_runner.get("version", "v3")
            max_workers = embedded_runner.get("max_workers", 3)
            queue_backend = embedded_runner.get("queue_backend", "memory")
            redis_url = embedded_runner.get("redis_url")
            dispatcher_cfg = embedded_runner.get("config", ZeusConfig(project_root, version).raw())

            if queue_backend == "sqlite":
                queue = SqliteTaskQueue(str(project_root / ".zeus" / version / "queue.sqlite"))
            elif queue_backend == "redis" and redis_url:
                from task_queue.redis_queue import RedisTaskQueue
                queue = RedisTaskQueue(redis_url)
            else:
                queue = MemoryTaskQueue()

            dispatcher = build_dispatcher(dispatcher_cfg)
            workspace_manager = build_workspace_manager(project_root, version)
            scheduler = ZeusScheduler(app.state.store, queue, bus)
            pool = WorkerPool(app.state.store, queue, dispatcher, workspace_manager, max_workers=max_workers, bus=bus)

            await pool.start()
            await app.state.store.set_meta("worker_target_count", max_workers)
            await app.state.store.set_meta("worker_actual_count", len(pool._workers))
            await app.state.store.set_meta("scheduler_target_state", "running")
            await app.state.store.set_meta("scheduler_actual_state", "running")
            await app.state.store.set_meta("scheduler_active", True)

            enqueued_ids: set[str] = set()
            async def _scheduler_loop():
                idle_count = 0
                max_idle = 10
                try:
                    while True:
                        target = await app.state.store.get_meta("scheduler_target_state", "running")
                        if target != "running":
                            await app.state.store.set_meta("scheduler_actual_state", "stopped")
                            await app.state.store.set_meta("scheduler_active", False)
                            break
                        await app.state.store.set_meta("scheduler_actual_state", "running")
                        await app.state.store.set_meta("scheduler_active", True)
                        ready = await scheduler.tick(enqueued_ids)
                        if ready:
                            idle_count = 0
                        else:
                            idle_count += 1
                            qsize = await queue.size()
                            if qsize == 0 and idle_count >= max_idle:
                                pending = len(await app.state.store.list_tasks(status="pending"))
                                running = len(await app.state.store.list_tasks(status="running"))
                                if pending == 0 and running == 0:
                                    await scheduler.mark_global_completed()
                                    break
                            await asyncio.sleep(0.2)
                except asyncio.CancelledError:
                    pass

            async def _worker_watch():
                try:
                    while True:
                        await asyncio.sleep(2)
                        target = await app.state.store.get_meta("worker_target_count", max_workers)
                        actual = len(pool._workers)
                        if target != actual:
                            await pool.scale_to(target)
                            await app.state.store.set_meta("worker_actual_count", len(pool._workers))
                except asyncio.CancelledError:
                    pass

            scheduler_task = asyncio.create_task(_scheduler_loop())
            worker_watch_task = asyncio.create_task(_worker_watch())
            await app.state.store.log_event(
                event_type="embedded.scheduler.started",
                task_id="global",
                agent_id="api-server",
                payload={"max_workers": max_workers},
            )

        try:
            yield
        finally:
            if scheduler_task:
                scheduler_task.cancel()
                try:
                    await scheduler_task
                except asyncio.CancelledError:
                    pass
            if worker_watch_task:
                worker_watch_task.cancel()
                try:
                    await worker_watch_task
                except asyncio.CancelledError:
                    pass
            if pool:
                await pool.stop()
                await app.state.store.set_meta("worker_actual_count", 0)
            if queue:
                await queue.close()
            await app.state.store.set_meta("scheduler_actual_state", "stopped")
            await app.state.store.set_meta("scheduler_active", False)
            await app.state.store.close()

    app = FastAPI(title="ZeusOpen v3 Server", lifespan=lifespan)
    app.state.store = store
    app.state.bus = bus
    app.state.control_plane = control_plane

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
    async def health(request: FastAPIRequest) -> dict[str, Any]:
        return {"status": "ok", "store": await request.app.state.store.health()}

    @app.get("/tasks")
    async def list_tasks(
        request: FastAPIRequest,
        status: str | None = Query(None),
        wave: int | None = Query(None),
    ) -> list[dict[str, Any]]:
        return await request.app.state.store.list_tasks(status=status, wave=wave)

    @app.get("/tasks/{task_id}")
    async def get_task(request: FastAPIRequest, task_id: str) -> dict[str, Any]:
        task = await request.app.state.store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    # ------------------------------------------------------------------
    # Task actions
    # ------------------------------------------------------------------
    @app.post("/tasks/{task_id}/retry")
    async def retry_task(request: FastAPIRequest, task_id: str) -> dict[str, Any]:
        store = request.app.state.store
        task = await store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await store.unquarantine_task(task_id)
        await store.update_task_status(task_id, "pending", passes=False, worker_id=None)
        await store.log_event(event_type="task.retried", task_id=task_id, agent_id="control-plane", payload={})
        request.app.state.bus.emit("task.retried", {"task_id": task_id})
        return {"success": True, "task_id": task_id}

    @app.post("/tasks/{task_id}/cancel")
    async def cancel_task(request: FastAPIRequest, task_id: str) -> dict[str, Any]:
        store = request.app.state.store
        task = await store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await store.update_task_status(task_id, "cancelled")
        await store.log_event(event_type="task.cancelled", task_id=task_id, agent_id="control-plane", payload={})
        request.app.state.bus.emit("task.cancelled", {"task_id": task_id})
        return {"success": True, "task_id": task_id}

    @app.post("/tasks/{task_id}/pause")
    async def pause_task(request: FastAPIRequest, task_id: str) -> dict[str, Any]:
        store = request.app.state.store
        task = await store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await store.update_task_status(task_id, "paused")
        await store.log_event(event_type="task.paused", task_id=task_id, agent_id="control-plane", payload={})
        request.app.state.bus.emit("task.paused", {"task_id": task_id})
        return {"success": True, "task_id": task_id}

    @app.post("/tasks/{task_id}/resume")
    async def resume_task(request: FastAPIRequest, task_id: str) -> dict[str, Any]:
        store = request.app.state.store
        task = await store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await store.update_task_status(task_id, "pending", passes=False, worker_id=None)
        await store.log_event(event_type="task.resumed", task_id=task_id, agent_id="control-plane", payload={})
        request.app.state.bus.emit("task.resumed", {"task_id": task_id})
        return {"success": True, "task_id": task_id}

    @app.post("/tasks/{task_id}/quarantine")
    async def quarantine_task(request: FastAPIRequest, task_id: str) -> dict[str, Any]:
        store = request.app.state.store
        task = await store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await store.quarantine_task(task_id, reason="manual quarantine")
        await store.update_task_status(task_id, "failed", passes=False)
        await store.log_event(event_type="task.quarantined", task_id=task_id, agent_id="control-plane", payload={})
        request.app.state.bus.emit("task.quarantined", {"task_id": task_id})
        return {"success": True, "task_id": task_id}

    @app.post("/tasks/{task_id}/unquarantine")
    async def unquarantine_task(request: FastAPIRequest, task_id: str) -> dict[str, Any]:
        store = request.app.state.store
        task = await store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await store.unquarantine_task(task_id)
        await store.update_task_status(task_id, "pending", passes=False)
        await store.log_event(event_type="task.unquarantined", task_id=task_id, agent_id="control-plane", payload={})
        request.app.state.bus.emit("task.unquarantined", {"task_id": task_id})
        return {"success": True, "task_id": task_id}

    @app.post("/tasks/{task_id}/progress")
    async def report_progress(request: FastAPIRequest, task_id: str, body: dict[str, Any]) -> dict[str, Any]:
        store = request.app.state.store
        task = await store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await store.log_event(
            event_type="task.progress",
            task_id=task_id,
            agent_id="external",
            payload={"source": "http", **body},
        )
        request.app.state.bus.emit("task.progress", {"task_id": task_id, "progress": body, "source": "http"})
        return {"success": True, "task_id": task_id}

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    @app.get("/events")
    async def list_events(
        request: FastAPIRequest,
        event_type: str | None = Query(None),
        task_id: str | None = Query(None),
        agent_id: str | None = Query(None),
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ) -> list[dict[str, Any]]:
        return await request.app.state.store.query_events(
            event_type=event_type,
            task_id=task_id,
            agent_id=agent_id,
            limit=limit,
            offset=offset,
        )

    @app.get("/events/stream")
    async def events_stream(request: FastAPIRequest) -> StreamingResponse:
        bus = request.app.state.bus
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
    async def metrics_summary(request: FastAPIRequest) -> dict[str, Any]:
        collector = MetricsCollector(request.app.state.store)
        return await collector.summary()

    @app.get("/metrics/tasks")
    async def metrics_tasks(request: FastAPIRequest) -> list[dict[str, Any]]:
        collector = MetricsCollector(request.app.state.store)
        return await collector.task_metrics()

    @app.get("/metrics/bottleneck")
    async def metrics_bottleneck(request: FastAPIRequest, top_n: int = Query(5, ge=1, le=100)) -> list[dict[str, Any]]:
        collector = MetricsCollector(request.app.state.store)
        return await collector.bottleneck_tasks(top_n=top_n)

    @app.get("/metrics/blocked")
    async def metrics_blocked(request: FastAPIRequest) -> list[dict[str, Any]]:
        collector = MetricsCollector(request.app.state.store)
        return await collector.blocked_chains()

    # ------------------------------------------------------------------
    # Workflow graph
    # ------------------------------------------------------------------
    @app.get("/workflow/graph")
    async def workflow_graph(request: FastAPIRequest, format: str = Query("echarts")) -> Any:
        tasks = await request.app.state.store.list_tasks()
        graph = WorkflowGraph(tasks)
        if format == "mermaid":
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse(content=graph.to_mermaid(), media_type="text/plain; charset=utf-8")
        if format == "graphviz":
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse(content=graph.to_graphviz(), media_type="text/plain; charset=utf-8")
        if format == "svg":
            from fastapi.responses import Response
            return Response(content=graph.to_svg_native(), media_type="image/svg+xml")
        return graph.to_echarts()

    # ------------------------------------------------------------------
    # Agent logs
    # ------------------------------------------------------------------
    @app.get("/agents/{agent_id}/logs")
    async def agent_logs(request: FastAPIRequest, agent_id: str) -> dict[str, Any]:
        store = request.app.state.store
        task_id = agent_id.replace("zeus-agent-", "")
        workspace_path = None
        task = await store.get_task(task_id)
        if task and task.get("extra"):
            workspace_path = task.get("extra", {}).get("workspace")
        if workspace_path:
            wp = pathlib.Path(workspace_path)
            activity_path = wp / "activity.md"
            if activity_path.exists():
                activity = activity_path.read_text("utf-8")
            else:
                activity = ""
            reasoning_path = wp / "reasoning.jsonl"
            reasoning: list[dict[str, Any]] = []
            if reasoning_path.exists():
                for line in reasoning_path.read_text("utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        reasoning.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            return {"agent_id": agent_id, "activity": activity, "reasoning": reasoning, "source": "workspace"}

        events = await store.query_events(task_id=task_id, limit=500)
        lines = [f"# Agent {agent_id} Activity Log\n"]
        for ev in events:
            ts = ev.get("ts", "")
            et = ev.get("event_type", "")
            payload = ev.get("payload", {})
            lines.append(f"## {ts} — {et}")
            lines.append(json.dumps(payload, ensure_ascii=False, indent=2))
            lines.append("")
        activity = "\n".join(lines)
        return {"agent_id": agent_id, "activity": activity, "reasoning": events, "source": "eventlog"}

    # ------------------------------------------------------------------
    # Phase & Milestone
    # ------------------------------------------------------------------
    @app.get("/phases")
    async def list_phases(request: FastAPIRequest) -> list[dict[str, Any]]:
        return await request.app.state.store.list_phases()

    @app.get("/phases/{phase_id}")
    async def get_phase(request: FastAPIRequest, phase_id: str) -> dict[str, Any]:
        phase = await request.app.state.store.get_phase(phase_id)
        if not phase:
            raise HTTPException(status_code=404, detail="Phase not found")
        milestones = await request.app.state.store.list_milestones()
        phase_milestone_ids = set(phase.get("milestone_ids") or [])
        phase["milestones"] = [m for m in milestones if m["id"] in phase_milestone_ids]
        return phase

    @app.post("/phases")
    async def create_phase(request: FastAPIRequest, body: dict[str, Any]) -> dict[str, Any]:
        pid = body.get("id")
        if not pid:
            raise HTTPException(status_code=400, detail="id is required")
        await request.app.state.store.upsert_phase(body)
        return {"success": True, "id": pid}

    @app.put("/phases/{phase_id}")
    async def update_phase(request: FastAPIRequest, phase_id: str, body: dict[str, Any]) -> dict[str, Any]:
        body["id"] = phase_id
        await request.app.state.store.upsert_phase(body)
        return {"success": True, "id": phase_id}

    @app.delete("/phases/{phase_id}")
    async def delete_phase(request: FastAPIRequest, phase_id: str) -> dict[str, Any]:
        await request.app.state.store.delete_phase(phase_id)
        return {"success": True, "id": phase_id}

    @app.get("/milestones")
    async def list_milestones(request: FastAPIRequest) -> list[dict[str, Any]]:
        return await request.app.state.store.list_milestones()

    @app.get("/milestones/{milestone_id}")
    async def get_milestone(request: FastAPIRequest, milestone_id: str) -> dict[str, Any]:
        ms = await request.app.state.store.get_milestone(milestone_id)
        if not ms:
            raise HTTPException(status_code=404, detail="Milestone not found")
        ms["tasks"] = await request.app.state.store.list_tasks_by_milestone(milestone_id)
        return ms

    @app.post("/milestones")
    async def create_milestone(request: FastAPIRequest, body: dict[str, Any]) -> dict[str, Any]:
        mid = body.get("id")
        if not mid:
            raise HTTPException(status_code=400, detail="id is required")
        await request.app.state.store.upsert_milestone(body)
        return {"success": True, "id": mid}

    @app.put("/milestones/{milestone_id}")
    async def update_milestone(request: FastAPIRequest, milestone_id: str, body: dict[str, Any]) -> dict[str, Any]:
        body["id"] = milestone_id
        await request.app.state.store.upsert_milestone(body)
        return {"success": True, "id": milestone_id}

    @app.delete("/milestones/{milestone_id}")
    async def delete_milestone(request: FastAPIRequest, milestone_id: str) -> dict[str, Any]:
        await request.app.state.store.delete_milestone(milestone_id)
        return {"success": True, "id": milestone_id}

    # ------------------------------------------------------------------
    # Mailbox
    # ------------------------------------------------------------------
    @app.get("/mailbox")
    async def list_messages(
        request: FastAPIRequest,
        to_agent: str | None = Query(None),
        read: bool | None = Query(None),
        limit: int = Query(100, ge=1, le=1000),
    ) -> list[dict[str, Any]]:
        return await request.app.state.store.list_messages(to_agent=to_agent, read=read, limit=limit)

    @app.post("/mailbox")
    async def send_message(request: FastAPIRequest, body: dict[str, Any]) -> dict[str, Any]:
        mid = await request.app.state.store.send_message(body)
        request.app.state.bus.emit("mailbox.message_sent", {"id": mid, "to_agent": body.get("to_agent")})
        return {"success": True, "id": mid}

    @app.post("/mailbox/{message_id}/read")
    async def mark_message_read(request: FastAPIRequest, message_id: int) -> dict[str, Any]:
        await request.app.state.store.mark_message_read(message_id, read=True)
        return {"success": True, "id": message_id}

    # ------------------------------------------------------------------
    # Control plane
    # ------------------------------------------------------------------
    def _ensure_control_plane(request: FastAPIRequest):
        if request.app.state.control_plane is None:
            raise HTTPException(status_code=503, detail="Control plane not enabled")

    @app.get("/control/status")
    async def control_status(request: FastAPIRequest) -> dict[str, Any]:
        _ensure_control_plane(request)
        return await request.app.state.control_plane.status()

    @app.post("/control/scheduler/start")
    async def control_scheduler_start(request: FastAPIRequest) -> dict[str, Any]:
        _ensure_control_plane(request)
        try:
            pid = await request.app.state.control_plane.spawn_scheduler()
            return {"success": True, "pid": pid}
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e))

    @app.post("/control/scheduler/stop")
    async def control_scheduler_stop(request: FastAPIRequest) -> dict[str, Any]:
        _ensure_control_plane(request)
        await request.app.state.control_plane.stop_scheduler()
        return {"success": True}

    @app.post("/control/scheduler/tick")
    async def control_scheduler_tick(request: FastAPIRequest) -> dict[str, Any]:
        _ensure_control_plane(request)
        result = await request.app.state.control_plane.tick_once()
        return {"success": True, "result": result}

    @app.post("/control/workers/scale")
    async def control_workers_scale(request: FastAPIRequest, body: ScaleWorkersRequest) -> dict[str, Any]:
        _ensure_control_plane(request)
        pids = await request.app.state.control_plane.spawn_workers(body.count)
        return {"success": True, "pids": pids}

    @app.post("/control/workers/stop")
    async def control_workers_stop(request: FastAPIRequest) -> dict[str, Any]:
        _ensure_control_plane(request)
        await request.app.state.control_plane.stop_workers()
        return {"success": True}

    @app.post("/control/import")
    async def control_import(request: FastAPIRequest) -> dict[str, Any]:
        _ensure_control_plane(request)
        result = await request.app.state.control_plane.import_tasks()
        return {"success": True, "result": result}

    @app.post("/control/global/run")
    async def control_global_run(request: FastAPIRequest) -> dict[str, Any]:
        _ensure_control_plane(request)
        result = await request.app.state.control_plane.global_run()
        return {"success": True, "result": result}

    @app.post("/control/project/switch")
    async def control_project_switch(request: FastAPIRequest, body: dict[str, Any]) -> dict[str, Any]:
        _ensure_control_plane(request)
        from importer import import_tasks_from_json
        from store.sqlite_store import SQLiteStateStore
        new_root = pathlib.Path(body.get("project_root", ".")).resolve()
        version = body.get("version", "v3")
        task_json = new_root / ".zeus" / version / "task.json"
        if not task_json.exists():
            raise HTTPException(status_code=400, detail="task.json not found in target project")
        new_db = f"sqlite+aiosqlite:///{new_root / '.zeus' / version / 'state.db'}"
        await ensure_schema(new_db)
        new_store = SQLiteStateStore(new_db)
        import_result = await import_tasks_from_json(new_store, task_json)
        old_store = request.app.state.store
        request.app.state.store = new_store
        request.app.state.control_plane.store = new_store
        await old_store.close()
        return {
            "success": True,
            "project_root": str(new_root),
            "imported_tasks": import_result["imported_tasks"],
        }

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
        from api.control_plane import ControlPlane
        control_plane = ControlPlane(store, bus, project_root, database_url)

    embedded_runner = None
    if os.environ.get("ZEUS_EMBEDDED_SCHEDULER", "true").lower() != "false":
        embedded_runner = {
            "project_root": str(project_root),
            "version": version,
            "max_workers": int(os.environ.get("ZEUS_EMBEDDED_WORKERS", "3")),
            "queue_backend": os.environ.get("ZEUS_EMBEDDED_QUEUE", "memory"),
            "redis_url": os.environ.get("ZEUS_EMBEDDED_REDIS_URL"),
        }

    app = create_app(store, bus, control_plane, embedded_runner)
    return app


# Expose default app for direct uvicorn usage: uvicorn api.server:app
# Use empty argv so import-time creation does not accidentally consume pytest args.
app = main([])


if __name__ == "__main__":
    import uvicorn
    args = parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
