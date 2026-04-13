"""
ZeusOpen v3 FastAPI server.

Provides REST + SSE endpoints for the v3 execution engine.
"""
from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.bus import EventBus
from api.metrics import MetricsCollector
from db.engine import make_async_engine
from db.models import Base
from store.sqlite_store import SQLiteStateStore


def create_app(store: SQLiteStateStore, bus: EventBus | None = None) -> FastAPI:
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

    return app


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ZeusOpen v3 API Server")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--version", default="v3")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args(argv)


async def ensure_schema(database_url: str) -> None:
    engine = make_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


def main(argv: list[str] | None = None) -> FastAPI:
    args = parse_args(argv)
    import pathlib
    project_root = pathlib.Path(args.project_root).resolve()
    database_url = args.database_url or f"sqlite+aiosqlite:///{project_root / '.zeus' / args.version / 'state.db'}"

    import asyncio
    asyncio.run(ensure_schema(database_url))

    store = SQLiteStateStore(database_url)
    bus = EventBus()
    app = create_app(store, bus)
    return app


if __name__ == "__main__":
    import uvicorn
    args = parse_args()
    app = main()
    uvicorn.run(app, host=args.host, port=args.port)
