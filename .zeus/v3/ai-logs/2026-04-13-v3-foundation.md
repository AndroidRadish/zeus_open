# v3 Phase 1 Foundation — Database State Store, ARP, Queue-Worker Separation

## Decision Rationale

Following the "evolution permission" granted after v2 sunset, we immediately began building the v3 production multi-agent framework. The user's directive was aggressive: implement both SQLite and PostgreSQL backends from day one, and build the queue-worker architecture as completely as possible.

Key design decisions:
- **SQLAlchemy 2.0 async ORM** unifies SQLite (`aiosqlite`) and PostgreSQL (`asyncpg`) under one model layer. This avoids rewriting models when switching backends.
- **Alembic for migrations** ensures the schema can evolve safely as v3 develops.
- **State store replaces `task.json` mutation**: `TaskState`, `Quarantine`, `SchedulerMeta`, and `EventLog` tables provide indexed, concurrent-safe state without file locks.
- **Queue-Worker separation**: `ZeusScheduler` is now a pure decision engine that only enqueues ready tasks. `ZeusWorker` + `WorkerPool` handle actual execution. This enables horizontal scaling in the future.
- **Agent Result Protocol (ARP)**: defined a structured `ZeusResult` schema that sub-agents will write to `zeus-result.json`. The worker reads this file to determine success, treating exit code as secondary evidence.
- **Three queue backends**: `MemoryTaskQueue` for local dev/tests, `SqliteTaskQueue` for zero-dependency persistence, and `RedisTaskQueue` for production horizontal scaling.

Notable fix: the initial package name `queue` conflicted with Python's stdlib `queue` module (causing a circular import when `redis` tried to import `Empty`). It was renamed to `task_queue`.

## Execution Summary

### New directories and files
- `.zeus/v3/scripts/db/`
  - `models.py` — SQLAlchemy async models: `TaskState`, `Quarantine`, `SchedulerMeta`, `EventLog`
  - `engine.py` — `create_async_engine` + `async_sessionmaker` helpers
- `.zeus/v3/scripts/store/`
  - `base.py` — `AsyncStateStore` abstract interface
  - `sqlalchemy_base.py` — shared SQLAlchemy implementation
  - `sqlite_store.py` — `SQLiteStateStore`
  - `postgres_store.py` — `PostgresStateStore`
- `.zeus/v3/scripts/task_queue/`
  - `base.py` — `TaskQueue` abstraction
  - `memory_queue.py` — `asyncio.Queue` implementation
  - `sqlite_queue.py` — persistent SQLite queue with dead-letter table
  - `redis_queue.py` — Redis list-based queue with retry logic
- `.zeus/v3/scripts/core/`
  - `scheduler.py` — pure `ZeusScheduler` (dependency-aware enqueue only)
  - `worker.py` — `ZeusWorker` (consume queue, execute dispatcher, update store)
  - `worker_pool.py` — `WorkerPool` managing multiple workers
- `.zeus/v3/scripts/schemas/`
  - `zeus_result.py` — Pydantic `ZeusResult` + `TestSummary` models (ARP v1)
- `.zeus/v3/scripts/tests/`
  - `test_v3_core.py` — 13 integration tests covering state store, queues, scheduler, worker pool, and end-to-end flow
- `.zeus/v3/alembic.ini` + `.zeus/v3/alembic/`
  - Initial migration `fd166328014a_v3_initial_schema.py`
- `.zeus/v3/specs/2026-04-13-v3-production-multi-agent-framework.md` — long-term v3 roadmap

### Modified files
- `requirements.txt` — added `aiosqlite`, `sqlalchemy[asyncio]`, `alembic`, `asyncpg`, `redis`, `sse-starlette`, `pydantic-settings`

### Verification
- Alembic migration generated and applied successfully
- `13/13` v3 core tests passed
- SQLite state store + Memory queue + Scheduler + WorkerPool end-to-end confirmed working

## Target Impact

- **multi_agent_efficiency** ↑↑↑ — Queue-Worker separation removes the single-process bottleneck of v2.
- **developer_adoption_rate** ↑↑ — ARP gives sub-agents a structured contract instead of fragile stdout parsing.
- **observability** ↑↑ — `EventLog` table with indexes enables historical queries and metrics without linear file scanning.
- **deployment_readiness** ↑↑↑ — Three queue backends (memory/SQLite/Redis) let the same codebase run locally, in containers, or in distributed K8s clusters.
