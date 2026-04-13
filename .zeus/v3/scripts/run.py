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
    parser.add_argument("--queue-backend", default="memory", choices=["memory", "sqlite", "redis"], help="Task queue backend")
    parser.add_argument("--redis-url", default=None, help="Redis URL (required if queue-backend=redis)")
    parser.add_argument("--dispatcher", default=None, choices=["mock", "kimi", "claude", "auto"], help="Override dispatcher mode")
    parser.add_argument("--import-only", action="store_true", help="Only import task.json and exit")
    parser.add_argument("--mode", default="combined", choices=["combined", "scheduler", "worker", "serve"], help="Execution mode")
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
        # Auto-detect project root when run.py is executed from .zeus/<version>/scripts/
        run_py = Path(__file__).resolve()
        if run_py.name == "run.py" and run_py.parent.name == "scripts":
            candidate = run_py.parent.parent.parent.parent
            candidate_task_json = candidate / ".zeus" / version / "task.json"
            if candidate_task_json.exists():
                project_root = candidate
                task_json_path = candidate_task_json
    if not task_json_path.exists():
        print(f"[ERROR] task.json not found: {task_json_path}")
        return 1

    database_url = args.database_url or f"sqlite+aiosqlite:///{project_root / '.zeus' / version / 'state.db'}"
    tracer = init_tracing(export_to_console=args.trace)
    print(">> ZeusOpen v3 Runner")
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
    print(f"[IMPORT] Imported {import_result['imported_tasks']} tasks, "
          f"{import_result['quarantine_count']} quarantined, "
          f"meta keys: {import_result['meta_keys']}")

    if args.import_only:
        await store.close()
        print("[OK] Import complete.")
        return 0

    # 3. API server mode
    if args.mode == "serve":
        bus = EventBus()
        app = create_app(store, bus)
        import uvicorn
        print(f"[SERVE] Starting API server at http://{args.host}:{args.port}")
        config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
        return 0

    # 4. Runner mode: prepare queue, dispatcher, workspace manager
    if args.queue_backend == "sqlite":
        queue = SqliteTaskQueue(str(project_root / ".zeus" / version / "queue.sqlite"))
    elif args.queue_backend == "redis":
        redis_url = args.redis_url or config.raw().get("queue", {}).get("redis_url", "redis://localhost:6379/0")
        queue = RedisTaskQueue(redis_url)
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

    # 5. Start workers and/or scheduling loop based on mode
    ticks = 0
    idle_count = 0
    max_idle_ticks = 10
    enqueued_ids: set[str] = set()

    if args.mode in ("combined", "worker"):
        await pool.start()
        print(">> Workers started")

    if args.mode in ("combined", "scheduler"):
        print(">> Scheduler started")
        with tracer.start_as_current_span("scheduler-run") as span:
            span.set_attribute("max_workers", args.max_workers)
            span.set_attribute("database_url", database_url)
            span.set_attribute("mode", args.mode)
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
                print("\n[STOP] Interrupted by user")

    if args.mode == "worker":
        # In worker-only mode, run indefinitely until interrupted
        print(">> Workers running (Ctrl+C to stop)")
        try:
            while True:
                await asyncio.sleep(1)
                # Health check: if queue is idle and all tasks are terminal, exit gracefully
                qsize = await queue.size()
                pending = len(await store.list_tasks(status="pending"))
                running = len(await store.list_tasks(status="running"))
                if qsize == 0 and pending == 0 and running == 0:
                    break
        except KeyboardInterrupt:
            print("\n[STOP] Interrupted by user")

    if args.mode in ("combined", "worker"):
        await pool.stop()
    if args.mode in ("combined", "scheduler"):
        await scheduler.mark_global_completed()
    await store.close()
    await queue.close()

    # 6. Report
    if args.mode in ("combined", "scheduler"):
        print("\n[DONE] Run complete")
        print(f"   Total ticks : {ticks}")
        print(f"   Enqueued    : {len(enqueued_ids)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n[STOP] Aborted")
        sys.exit(130)
