"""
Redis-backed task queue tests using fakeredis.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Patch redis.asyncio before importing our module
import fakeredis.aioredis
import redis.asyncio as redis_mod

redis_mod.from_url = lambda url, **kwargs: fakeredis.aioredis.FakeRedis()

from task_queue.redis_queue import RedisTaskQueue


@pytest.mark.asyncio
async def test_redis_queue_enqueue_dequeue():
    q = RedisTaskQueue()
    await q.enqueue({"id": "T-R1", "payload": 1})
    assert await q.size() == 1

    task = await q.dequeue()
    assert task is not None
    assert task["id"] == "T-R1"
    assert await q.size() == 0


@pytest.mark.asyncio
async def test_redis_queue_ack():
    q = RedisTaskQueue()
    await q.enqueue({"id": "T-R2", "payload": 2})
    task = await q.dequeue()
    assert task is not None
    await q.ack("T-R2")
    # No exception means success; inflight entry removed


@pytest.mark.asyncio
async def test_redis_queue_nack_retry_and_dead_letter():
    q = RedisTaskQueue()
    await q.enqueue({"id": "T-R3", "payload": 3})
    task = await q.dequeue()
    assert task is not None

    # Nack 4 times -> should land in dead letter after 3 retries
    for _ in range(4):
        await q.nack("T-R3", reason="fail")
        if await q.size() == 1:
            task = await q.dequeue()

    # After exceeding retries, queue should be empty
    assert await q.size() == 0


@pytest.mark.asyncio
async def test_redis_queue_close():
    q = RedisTaskQueue()
    await q.close()
