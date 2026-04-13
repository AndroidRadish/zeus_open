"""
Redis-backed task queue using RPUSH / BLPOP.
"""
from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis

from task_queue.base import TaskQueue


class RedisTaskQueue(TaskQueue):
    """Redis list-based task queue."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0", queue_name: str = "zeus_v3_tasks") -> None:
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._queue = queue_name
        self._inflight = f"{queue_name}:inflight"
        self._dead = f"{queue_name}:dead"

    async def enqueue(self, task: dict[str, Any]) -> None:
        await self._client.rpush(self._queue, json.dumps(task))

    async def dequeue(self) -> dict[str, Any] | None:
        result = await self._client.blpop(self._queue, timeout=1)
        if result is None:
            return None
        _, raw = result
        task = json.loads(raw)
        await self._client.hset(self._inflight, task["id"], raw)
        return task

    async def ack(self, task_id: str) -> None:
        await self._client.hdel(self._inflight, task_id)

    async def nack(self, task_id: str, reason: str) -> None:
        raw = await self._client.hget(self._inflight, task_id)
        if raw:
            task = json.loads(raw)
            task.setdefault("retry_count", 0)
            task["retry_count"] += 1
            task["last_failure_reason"] = reason
            if task["retry_count"] > 3:
                await self._client.hset(self._dead, task_id, json.dumps(task))
            else:
                await self._client.rpush(self._queue, json.dumps(task))
            await self._client.hdel(self._inflight, task_id)

    async def size(self) -> int:
        return await self._client.llen(self._queue)

    async def close(self) -> None:
        await self._client.close()
