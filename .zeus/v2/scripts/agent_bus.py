"""
Agent Bus for ZeusOpen v2.

Maintains machine-readable JSONL event stream and human-readable Markdown discussion log.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from store import LocalStore


class AgentBus:
    """
    Communication bus for agents in a given wave.

    Parameters
    ----------
    version: str
        Zeus version string, e.g. ``"v2"``.
    wave: int
        Current wave number.
    store: LocalStore
        Storage backend (typically ``LocalStore`` from ``store.py``).
    """

    SUPPORTED_EVENTS = frozenset(
        {
            "task.started",
            "task.progress",
            "task.completed",
            "task.failed",
            "task.rescheduled",
            "task.bootstrapped",
            "agent.message",
            "wave.completed",
        }
    )

    def __init__(self, version: str, wave: int, store: Any) -> None:
        self.version = version
        self.wave = wave
        self.store = store
        self._base_dir = Path(".zeus") / version / "agent-logs"
        self._events_file = self._base_dir / f"wave-{wave}-events.jsonl"
        self._discussion_file = self._base_dir / f"wave-{wave}-discussion.md"

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _iso_ts(self, dt: datetime | None = None) -> str:
        return (dt or self._now()).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _time_str(self, dt: datetime | None = None) -> str:
        return (dt or self._now()).strftime("%H:%M:%S")

    def _ensure_discussion_header(self) -> None:
        """Write the header if the discussion file is empty / missing."""
        with self.store.lock(str(self._discussion_file)):
            resolved = self.store._resolve(str(self._discussion_file))
            if not resolved.exists() or not resolved.read_text(encoding="utf-8").strip():
                resolved.parent.mkdir(parents=True, exist_ok=True)
                resolved.write_text(
                    f"# Wave {self.wave} Discussion Log\n\n",
                    encoding="utf-8",
                )

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------
    def emit(
        self,
        event_type: str,
        task_id: str,
        agent_id: str,
        payload: dict | None = None,
    ) -> dict:
        """
        Append an event to the JSONL stream.

        Returns
        -------
        dict
            The event that was written.
        """
        if event_type not in self.SUPPORTED_EVENTS:
            raise ValueError(f"Unsupported event type: {event_type!r}")

        event = {
            "ts": self._iso_ts(),
            "type": event_type,
            "wave": self.wave,
            "task_id": task_id,
            "agent_id": agent_id,
            "payload": payload or {},
        }
        self.store.append_line(str(self._events_file), json.dumps(event, ensure_ascii=False))
        return event

    def post(self, task_id: str, agent_id: str, message: str) -> str:
        """
        Append a message to the Markdown discussion log.

        Returns
        -------
        str
            The rendered block that was appended.
        """
        self._ensure_discussion_header()
        block = (
            f"## {self._time_str()} — {agent_id} ({task_id})\n"
            f"{message}\n"
            f"\n"
        )
        self.store.append_line(str(self._discussion_file), block.rstrip("\n"))
        return block

    def get_events(
        self,
        event_type: str | None = None,
        task_id: str | None = None,
    ) -> list[dict]:
        """
        Read and optionally filter events from the JSONL stream.
        """
        resolved = self.store._resolve(str(self._events_file))
        if not resolved.exists():
            return []
        raw = resolved.read_text(encoding="utf-8")
        events: list[dict] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event_type is not None and evt.get("type") != event_type:
                continue
            if task_id is not None and evt.get("task_id") != task_id:
                continue
            events.append(evt)
        return events

    def get_discussion(self) -> str:
        """Return the full Markdown discussion content."""
        resolved = self.store._resolve(str(self._discussion_file))
        if not resolved.exists():
            return ""
        return resolved.read_text(encoding="utf-8")
