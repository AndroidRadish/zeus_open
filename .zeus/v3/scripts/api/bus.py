"""
In-memory event bus for real-time SSE broadcasting.

This is intentionally lightweight (single-process). For multi-node deployments,
swap this out for a Redis Pub/Sub backed bus.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any


class EventBus:
    """Async event bus that maintains a list of subscriber queues.

    Also provides AgentBus-style point-to-point messaging via an
    optional backing store (e.g. SQLiteStateStore mailbox).
    """

    def __init__(self, store=None) -> None:
        self._queues: set[asyncio.Queue[dict[str, Any]]] = set()
        self._store = store

    def emit(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        """Broadcast an event to all active subscribers (fire-and-forget)."""
        payload = payload or {}
        message = {
            "event": event_type,
            "data": payload,
        }
        for q in list(self._queues):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                pass

    async def post(
        self,
        task_id: str | None,
        agent_id: str | None,
        message: str,
        to_agent: str | None = None,
    ) -> int | None:
        """Persist a point-to-point message to the mailbox store.

        Returns the generated message id, or None if no store is attached.
        """
        if self._store is None:
            return None
        return await self._store.send_message({
            "task_id": task_id,
            "from_agent": agent_id,
            "to_agent": to_agent,
            "message": message,
            "read": False,
        })

    async def recv(
        self,
        agent_id: str,
        *,
        timeout: float | None = None,
        mark_read: bool = True,
    ) -> dict[str, Any] | None:
        """Poll the mailbox for the next unread message addressed to *agent_id*.

        If *timeout* is given, polls repeatedly until a message arrives or the
        timeout expires.  When *mark_read* is True (the default), the message
        is marked as read before being returned.
        """
        if self._store is None:
            return None

        deadline = None if timeout is None else asyncio.get_event_loop().time() + timeout
        while True:
            msgs = await self._store.list_messages(to_agent=agent_id, read=False, limit=1)
            if msgs:
                msg = msgs[0]
                if mark_read:
                    await self._store.mark_message_read(msg["id"], read=True)
                return msg
            if deadline is not None:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    return None
                await asyncio.sleep(min(0.5, remaining))
            else:
                await asyncio.sleep(0.5)

    async def subscribe(self):
        """Yield SSE-formatted messages as an async generator.

        Usage:
            async for msg in bus.subscribe():
                yield msg
        """
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        self._queues.add(q)
        try:
            while True:
                msg = await q.get()
                yield f"data: {json.dumps(msg)}\n\n"
        finally:
            self._queues.discard(q)
