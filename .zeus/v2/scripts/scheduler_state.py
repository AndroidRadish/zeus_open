"""
scheduler_state.py — SQLite-based scheduler state persistence for ZeusOpen v2.

Persists global scheduler state, active tasks, and mailbox across server restarts.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SchedulerStateDB:
    """SQLite backend for scheduler state snapshots."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _iso_now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        try:
            yield conn
        finally:
            conn.close()

    def _ensure_tables(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS active_tasks (
                    task_id TEXT PRIMARY KEY,
                    agent_id TEXT,
                    status TEXT,
                    started_at TEXT,
                    wave INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mailbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    to_agent_id TEXT,
                    from_agent_id TEXT,
                    message TEXT,
                    ts TEXT,
                    read INTEGER DEFAULT 0
                )
                """
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Save / Load helpers
    # ------------------------------------------------------------------
    def save(
        self,
        meta: dict[str, Any],
        active_tasks: list[dict[str, Any]],
        mailbox: list[dict[str, Any]] | None = None,
    ) -> None:
        """Atomically replace the current snapshot."""
        mailbox = mailbox or []
        with self._connect() as conn:
            conn.execute("DELETE FROM meta")
            conn.execute("DELETE FROM active_tasks")
            conn.execute("DELETE FROM mailbox")
            for k, v in meta.items():
                conn.execute("INSERT INTO meta (key, value) VALUES (?, ?)", (k, json.dumps(v)))
            for t in active_tasks:
                conn.execute(
                    "INSERT INTO active_tasks (task_id, agent_id, status, started_at, wave) VALUES (?, ?, ?, ?, ?)",
                    (
                        t["task_id"],
                        t.get("agent_id", ""),
                        t.get("status", "running"),
                        t.get("started_at", self._iso_now()),
                        t.get("wave", 1),
                    ),
                )
            for m in mailbox:
                conn.execute(
                    "INSERT INTO mailbox (to_agent_id, from_agent_id, message, ts, read) VALUES (?, ?, ?, ?, ?)",
                    (
                        m.get("to", m.get("to_agent_id", "")),
                        m.get("from", m.get("from_agent_id", "")),
                        m.get("message", ""),
                        m.get("ts", self._iso_now()),
                        1 if m.get("read", False) else 0,
                    ),
                )
            conn.commit()

    def load(self) -> dict[str, Any]:
        """Return the latest snapshot as a dict."""
        with self._connect() as conn:
            meta_rows = conn.execute("SELECT key, value FROM meta").fetchall()
            task_rows = conn.execute(
                "SELECT task_id, agent_id, status, started_at, wave FROM active_tasks"
            ).fetchall()
            mail_rows = conn.execute(
                "SELECT to_agent_id, from_agent_id, message, ts, read FROM mailbox"
            ).fetchall()

        meta = {k: json.loads(v) for k, v in meta_rows}
        active_tasks = [
            {
                "task_id": row[0],
                "agent_id": row[1],
                "status": row[2],
                "started_at": row[3],
                "wave": row[4],
            }
            for row in task_rows
        ]
        mailbox = [
            {
                "to_agent_id": row[0],
                "from_agent_id": row[1],
                "message": row[2],
                "ts": row[3],
                "read": bool(row[4]),
            }
            for row in mail_rows
        ]
        return {
            "meta": meta,
            "active_tasks": active_tasks,
            "mailbox": mailbox,
        }

    def clear(self) -> None:
        """Drop all persisted state."""
        with self._connect() as conn:
            conn.execute("DELETE FROM meta")
            conn.execute("DELETE FROM active_tasks")
            conn.execute("DELETE FROM mailbox")
            conn.commit()

    def set_meta(self, key: str, value: Any) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value)),
            )
            conn.commit()

    def get_meta(self, key: str, default: Any = None) -> Any:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        return json.loads(row[0])
