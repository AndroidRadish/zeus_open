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
    """Async event bus that maintains a list of subscriber queues."""

    def __init__(self) -> None:
        self._queues: set[asyncio.Queue[dict[str, Any]]] = set()

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
