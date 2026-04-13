#!/usr/bin/env python3
"""
ZeusOpen v3 CLI entrypoint.

One-shot execution:
  1. Import task.json into the database state store
  2. Start the worker pool
  3. Run the scheduler loop until all tasks are done
  4. Print a summary report

Usage:
  python run.py --project-root . --max-workers 3
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from api.bus import EventBus
from api.server import create_app
from config import ZeusConfig
from core.scheduler import ZeusScheduler
from core.tracing import init_tracing
from core.worker_pool import WorkerPool
from db.engine import make_async_engine
from db.models import Base
from dispatcher.cli import build_dispatcher
from importer import import_tasks_from_json
from store.sqlite_store import SQLiteStateStore
from task_queue.memory_queue import MemoryTaskQueue
from task_queue.sqlite_queue import SqliteTaskQueue
from workspace import build_workspace_manager


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ZeusOpen v3 Runner")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    parser.add_argument("--version", default="v3", help="Zeus version folder")
    parser.add_argument("--max-workers", type=int, default=3, help="Max concurrent workers")
    parser.add_argument("--database-url", default=None, help="SQLAlchemy async DB URL")
    parser.add_argument("--queue-backend", default="memory", choices=["memory", "sqlite"], help="Task queue backend")
    parser.add_argument("--dispatcher", default=None, choices=["mock", "kimi", "claude", "auto"], help="Override dispatcher mode")
    parser.add_argument("--import-only", action="store_true", help="Only import task.json and exit")
    parser.add_argument("--serve", action="store_true", help="Start the API server instead of running the scheduler")
    parser.add_argument("--host", default="127.0.0.1", help="API server host")
    parser.add_argument("--port", type=int, default=8000, help="API server port")
    parser.add_argument("--trace", action="store_true", help="Enable OpenTelemetry console trace output")
    return parser.parse_args(argv)


async def ensure_schema(database_url: str) -> None:
    engine = make_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = Path(args.project_root).resolve()
    version = args.version

    task_json_path = project_root / ".zeus" / version / "task.json"
    if not task_json_path.exists():
        print(f"❌ task.json not found: {task_json_path}")
        return 1

    database_url = args.database_url or f"sqlite+aiosqlite:///{project_root / '.zeus' / version / 'state.db'}"
    tracer = init_tracing(export_to_console=args.trace)
    print(f"🚀 ZeusOpen v3 Runner")
    print(f"   Project : {project_root}")
    print(f"   Version : {version}")
    print(f"   DB      : {database_url}")
    print(f"   Workers : {args.max_workers}")
    print(f"   Queue   : {args.queue_backend}")

    # 1. Ensure schema
    await ensure_schema(database_url)

    # 2. Import tasks
    store = SQLiteStateStore(database_url)
    import_result = await import_tasks_from_json(store, task_json_path)
    print(f"📥 Imported {import_result['imported_tasks']} tasks, "
          f"{import_result['quarantine_count']} quarantined, "
          f"meta keys: {import_result['meta_keys']}")

    if args.import_only:
        await store.close()
        print("✅ Import complete.")
        return 0

    # 3. API server mode
    if args.serve:
        bus = EventBus()
        app = create_app(store, bus)
        import uvicorn
        print(f"🌐 Starting API server at http://{args.host}:{args.port}")
        config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
        return 0

    # 4. Runner mode: prepare queue, dispatcher, workspace manager
    if args.queue_backend == "sqlite":
        queue = SqliteTaskQueue(str(project_root / ".zeus" / version / "queue.sqlite"))
    else:
        queue = MemoryTaskQueue()

    config = ZeusConfig(project_root, version)
    dispatcher_cfg = config.raw()
    if args.dispatcher:
        dispatcher_cfg.setdefault("subagent", {})["dispatcher"] = args.dispatcher
    dispatcher = build_dispatcher(dispatcher_cfg)

    bus = EventBus()
    workspace_manager = build_workspace_manager(project_root, version)
    scheduler = ZeusScheduler(store, queue, bus)
    pool = WorkerPool(store, queue, dispatcher, workspace_manager, max_workers=args.max_workers, bus=bus)

    # 5. Start workers and scheduling loop
    await pool.start()
    print("▶ Scheduler started")

    enqueued_ids: set[str] = set()
    ticks = 0
    idle_count = 0
    max_idle_ticks = 10  # If scheduler is idle and queue is empty for 10 ticks, we are done

    with tracer.start_as_current_span("scheduler-run") as span:
        span.set_attribute("max_workers", args.max_workers)
        span.set_attribute("database_url", database_url)
        try:
            while True:
                with tracer.start_as_current_span("scheduler-tick") as tick_span:
                    ready = await scheduler.tick(enqueued_ids)
                    ticks += 1
                    tick_span.set_attribute("tick", ticks)
                    tick_span.set_attribute("enqueued_count", len(ready))
                    if ready:
                        idle_count = 0
                        print(f"   Tick {ticks}: enqueued {len(ready)} task(s) — {', '.join(t['id'] for t in ready)}")
                    else:
                        idle_count += 1
                        qsize = await queue.size()
                        if qsize == 0 and idle_count >= max_idle_ticks:
                            pending = len(await store.list_tasks(status="pending"))
                            running = len(await store.list_tasks(status="running"))
                            tick_span.set_attribute("pending", pending)
                            tick_span.set_attribute("running", running)
                            if pending == 0 and running == 0:
                                break
                        await asyncio.sleep(0.2)
        except KeyboardInterrupt:
            print("\n⏹ Interrupted by user")
        finally:
            await pool.stop()
            await scheduler.mark_global_completed()
            await store.close()
            await queue.close()

    # 6. Report
    print("\n🏁 Run complete")
    print(f"   Total ticks : {ticks}")
    print(f"   Enqueued    : {len(enqueued_ids)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n⏹ Aborted")
        sys.exit(130)
