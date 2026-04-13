# v3 Redis Queue Backend — Multi-node Ready

## Decision Rationale

One of the core architectural promises of v3 is Queue-Worker separation, which enables horizontal scaling. Until now, only in-memory (`asyncio.Queue`) and SQLite-backed queues were available—both single-process. Adding a Redis-backed queue makes it possible to run the scheduler and workers on different machines or containers, unlocking true multi-node deployments.

## Execution Summary

### Modified files
- `.zeus/v3/scripts/run.py` — extended `--queue-backend` choices to include `redis`
  - Added `--redis-url` CLI argument
  - Falls back to `config.json` `queue.redis_url` or default `redis://localhost:6379/0`
- `.zeus/v3/scripts/task_queue/redis_queue.py` — fixed `close()` deprecation warning
  - Uses `aclose()` when available (redis-py 5.0.1+), falling back to `close()` for older versions
- `.zeus/v3/scripts/tests/test_v3_redis_queue.py` — new test suite
  - Patches `redis.asyncio.from_url` with `fakeredis.aioredis.FakeRedis` so tests run without a real Redis server
  - Covers enqueue/dequeue, ack, nack/retry/dead-letter, and close

### Design notes
- **No breaking changes**: existing `memory` and `sqlite` backends remain the default
- **Config-driven**: Redis URL can be supplied via CLI (`--redis-url`), `config.json`, or environment convention (future enhancement)
- **Dead-letter support**: `RedisTaskQueue.nack()` already implements retry counting (max 3) before moving tasks to a dead-letter hash

### Verification
- `45/45` v3 tests passed (including 4 new Redis queue tests)
- `python .zeus/scripts/zeus_runner.py --status` reports v2 validation pass

## Target Impact

- **multi_agent_efficiency** ↑↑↑ — Scheduler and workers can now run on separate processes/machines
- **scalability** ↑↑↑ — Redis queue is the foundation for M-008 multi-container deployment
- **reliability** ↑↑ — Dead-letter handling prevents infinite retry loops on persistent failures
