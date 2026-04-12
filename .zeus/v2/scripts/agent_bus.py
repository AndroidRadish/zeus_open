"""
Agent Bus for ZeusOpen v2.

Maintains machine-readable JSONL event stream and human-readable Markdown discussion log.
Supports agent-centric logs and cross-agent mailbox messaging.
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
    agent_id: str | None
        Optional agent identifier. When provided, events and discussion are
        also written to agent-specific paths.
    """

    SUPPORTED_EVENTS = frozenset(
        {
            "task.started",
            "task.progress",
            "task.completed",
            "task.failed",
            "task.rescheduled",
            "task.bootstrapped",
            "task.quarantined",
            "agent.message",
            "wave.completed",
            "global.completed",
            "global.stopped",
            "global.completed",
        }
    )

    def __init__(
        self,
        version: str,
        wave: int,
        store: Any,
        agent_id: str | None = None,
    ) -> None:
        self.version = version
        self.wave = wave
        self.store = store
        self.agent_id = agent_id
        self._base_dir = Path(".zeus") / version / "agent-logs"
        self._events_file = self._base_dir / f"wave-{wave}-events.jsonl"
        self._discussion_file = self._base_dir / f"wave-{wave}-discussion.md"

        if agent_id:
            self._agent_dir = self._base_dir / agent_id
            self._activity_file = self._agent_dir / "activity.md"
            self._reasoning_file = self._agent_dir / "reasoning.jsonl"
        else:
            self._agent_dir = None
            self._activity_file = None
            self._reasoning_file = None

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _iso_ts(self, dt: datetime | None = None) -> str:
        return (dt or self._now()).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _time_str(self, dt: datetime | None = None) -> str:
        return (dt or self._now()).strftime("%H:%M:%S")

    def _ensure_discussion_header(self, path: Path) -> None:
        """Write the header if the discussion file is empty / missing."""
        with self.store.lock(str(path)):
            resolved = self.store._resolve(str(path))
            if not resolved.exists() or not resolved.read_text(encoding="utf-8").strip():
                resolved.parent.mkdir(parents=True, exist_ok=True)
                resolved.write_text(
                    f"# Wave {self.wave} Discussion Log\n\n",
                    encoding="utf-8",
                )

    def _ensure_activity_header(self, path: Path) -> None:
        """Write the header if the agent activity file is empty / missing."""
        with self.store.lock(str(path)):
            resolved = self.store._resolve(str(path))
            if not resolved.exists() or not resolved.read_text(encoding="utf-8").strip():
                resolved.parent.mkdir(parents=True, exist_ok=True)
                resolved.write_text(
                    f"# Agent {self.agent_id} Activity Log\n\n",
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
        line = json.dumps(event, ensure_ascii=False)
        # Legacy aggregated log
        self.store.append_line(str(self._events_file), line)
        # Agent-specific reasoning log
        if self._reasoning_file is not None:
            self.store.append_line(str(self._reasoning_file), line)
        return event

    def post(self, task_id: str, agent_id: str, message: str) -> str:
        """
        Append a message to the Markdown discussion log.

        Returns
        -------
        str
            The rendered block that was appended.
        """
        self._ensure_discussion_header(self._discussion_file)
        block = (
            f"## {self._time_str()} — {agent_id} ({task_id})\n"
            f"{message}\n"
            f"\n"
        )
        self.store.append_line(str(self._discussion_file), block.rstrip("\n"))

        if self._activity_file is not None:
            self._ensure_activity_header(self._activity_file)
            self.store.append_line(str(self._activity_file), block.rstrip("\n"))

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

    def get_agent_events(self) -> list[dict]:
        """Read events from the agent-specific reasoning JSONL stream."""
        if self._reasoning_file is None:
            return []
        resolved = self.store._resolve(str(self._reasoning_file))
        if not resolved.exists():
            return []
        events: list[dict] = []
        for line in resolved.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events

    def get_activity(self) -> str:
        """Return the full agent-specific Markdown activity content."""
        if self._activity_file is None:
            return ""
        resolved = self.store._resolve(str(self._activity_file))
        if not resolved.exists():
            return ""
        return resolved.read_text(encoding="utf-8")

    # -----------------------------------------------------------------------
    # Mailbox API
    # -----------------------------------------------------------------------
    def send(self, to_agent_id: str, message: str) -> dict:
        """
        Send a message to another agent's mailbox.

        Messages are persisted as JSONL in
        ``.zeus/{version}/agent-logs/mailbox/{to_agent_id}.jsonl``.
        """
        mailbox_file = self._base_dir / "mailbox" / f"{to_agent_id}.jsonl"
        entry = {
            "ts": self._iso_ts(),
            "from": self.agent_id or "unknown",
            "to": to_agent_id,
            "message": message,
            "read": False,
        }
        self.store.append_line(str(mailbox_file), json.dumps(entry, ensure_ascii=False))
        return entry

    def receive(self, agent_id: str, mark_read: bool = False) -> list[dict]:
        """
        Retrieve messages for *agent_id* from its mailbox.

        If *mark_read* is True, unread messages are marked as read in place.
        """
        mailbox_file = self._base_dir / "mailbox" / f"{agent_id}.jsonl"
        resolved = self.store._resolve(str(mailbox_file))
        if not resolved.exists():
            return []

        raw = resolved.read_text(encoding="utf-8")
        messages: list[dict] = []
        lines: list[str] = []
        changed = False
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("to") == agent_id:
                messages.append(msg)
                if mark_read and not msg.get("read", False):
                    msg["read"] = True
                    changed = True
            lines.append(json.dumps(msg, ensure_ascii=False))

        if mark_read and changed:
            resolved.write_text("\n".join(lines) + "\n", encoding="utf-8")

        return messages
