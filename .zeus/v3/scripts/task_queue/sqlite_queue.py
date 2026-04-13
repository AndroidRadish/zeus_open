"""
SQLite-backed persistent task queue.

Useful when Redis is unavailable but persistence is still required.
"""
from __future__ import annotations

import json
from typing import Any

import aiosqlite

from task_queue.base import TaskQueue


class SqliteTaskQueue(TaskQueue):
    """Persistent queue backed by SQLite."""

    def __init__(self, db_path: str = "./zeus_v3_queue.sqlite", table_name: str = "task_queue") -> None:
        self._db_path = db_path
        self._table = table_name
        self._db: aiosqlite.Connection | None = None

    async def _ensure_db(self) -> aiosqlite.Connection:
        if self._db is None:
            self._db = await aiosqlite.connect(self._db_path)
            await self._db.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await self._db.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table}_dead (
                    task_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await self._db.commit()
        return self._db

    async def enqueue(self, task: dict[str, Any]) -> None:
        db = await self._ensure_db()
        await db.execute(
            f"INSERT OR REPLACE INTO {self._table} (task_id, payload, status) VALUES (?, ?, ?)",
            (task["id"], json.dumps(task), "pending"),
        )
        await db.commit()

    async def dequeue(self) -> dict[str, Any] | None:
        db = await self._ensure_db()
        async with db.execute(
            f"SELECT id, task_id, payload FROM {self._table} WHERE status = 'pending' ORDER BY id LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        row_id, task_id, payload = row
        await db.execute(
            f"UPDATE {self._table} SET status = 'inflight' WHERE id = ?",
            (row_id,),
        )
        await db.commit()
        return json.loads(payload)

    async def ack(self, task_id: str) -> None:
        db = await self._ensure_db()
        await db.execute(f"DELETE FROM {self._table} WHERE task_id = ?", (task_id,))
        await db.commit()

    async def nack(self, task_id: str, reason: str) -> None:
        db = await self._ensure_db()
        async with db.execute(
            f"SELECT retry_count, payload FROM {self._table} WHERE task_id = ?", (task_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return
        retry_count, payload = row
        retry_count = (retry_count or 0) + 1
        if retry_count > 3:
            await db.execute(
                f"INSERT OR REPLACE INTO {self._table}_dead (task_id, payload, reason) VALUES (?, ?, ?)",
                (task_id, payload, reason),
            )
            await db.execute(f"DELETE FROM {self._table} WHERE task_id = ?", (task_id,))
        else:
            await db.execute(
                f"UPDATE {self._table} SET status = 'pending', retry_count = ? WHERE task_id = ?",
                (retry_count, task_id),
            )
        await db.commit()

    async def size(self) -> int:
        db = await self._ensure_db()
        async with db.execute(f"SELECT COUNT(*) FROM {self._table} WHERE status = 'pending'") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None
