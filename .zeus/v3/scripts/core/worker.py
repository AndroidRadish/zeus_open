"""
ZeusOpen v3 worker.

Consumes tasks from a queue, prepares workspace, executes via dispatcher,
reads the Agent Result Protocol (ARP), and updates the state store.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Awaitable, Callable

from dispatcher.base import SubagentDispatcher
from schemas.zeus_result import ZeusResult
from store.base import AsyncStateStore
from task_queue.base import TaskQueue
from workspace.manager import WorkspaceManager

Dispatcher = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class ZeusWorker:
    """Single worker that loops over the queue until told to stop."""

    def __init__(
        self,
        worker_id: str,
        store: AsyncStateStore,
        queue: TaskQueue,
        dispatcher: SubagentDispatcher,
        workspace_manager: WorkspaceManager,
        bus=None,
    ) -> None:
        self.worker_id = worker_id
        self.store = store
        self.queue = queue
        self.dispatcher = dispatcher
        self.workspace_manager = workspace_manager
        self.bus = bus
        self._stop = False

    async def run(self) -> None:
        while not self._stop:
            task = await self.queue.dequeue()
            if task is None:
                import asyncio
                await asyncio.sleep(0.1)
                continue
            await self._execute(task)

    def stop(self) -> None:
        self._stop = True

    async def _execute(self, task: dict[str, Any]) -> None:
        tid = task["id"]
        await self.store.update_task_heartbeat(tid, self.worker_id)
        await self.store.log_event(
            event_type="task.started",
            task_id=tid,
            agent_id=self.worker_id,
            wave=task.get("wave"),
            payload={},
        )
        if self.bus:
            self.bus.emit("task.started", {"task_id": tid, "worker_id": self.worker_id, "wave": task.get("wave")})

        workspace: Path | None = None
        heartbeat_task = None
        try:
            workspace = await self.workspace_manager.prepare(task)
            prompt = self.workspace_manager.prompt_path(tid).read_text("utf-8")

            async def _heartbeat_loop():
                while True:
                    await asyncio.sleep(10)
                    await self.store.update_task_heartbeat(tid, self.worker_id)

            heartbeat_task = asyncio.create_task(_heartbeat_loop())
            raw_result = await self.dispatcher.run(task, workspace, prompt)
        except Exception as exc:
            await self.store.log_event(
                event_type="task.failed",
                task_id=tid,
                agent_id=self.worker_id,
                payload={"error": str(exc)},
            )
            if self.bus:
                self.bus.emit("task.failed", {"task_id": tid, "worker_id": self.worker_id, "error": str(exc)})
            await self.store.update_task_status(tid, "failed", passes=False, worker_id=None)
            if workspace:
                await self.store.quarantine_task(tid, str(exc), workspace=str(workspace))
            await self.queue.nack(tid, reason=str(exc))
            return
        finally:
            if heartbeat_task:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

        # Primary source of truth: zeus-result.json in workspace
        zeus_result = self._read_zeus_result(workspace)
        if zeus_result is None:
            zeus_result = raw_result

        try:
            validated = ZeusResult.model_validate(zeus_result)
        except Exception as exc:
            await self.store.log_event(
                event_type="task.failed",
                task_id=tid,
                agent_id=self.worker_id,
                payload={"error": f"invalid zeus-result.json: {exc}", "raw": zeus_result},
            )
            if self.bus:
                self.bus.emit("task.failed", {"task_id": tid, "worker_id": self.worker_id, "error": f"invalid zeus-result.json: {exc}"})
            await self.store.update_task_status(tid, "failed", passes=False, worker_id=None)
            if workspace:
                await self.store.quarantine_task(tid, f"invalid zeus-result.json: {exc}", workspace=str(workspace))
            await self.queue.nack(tid, reason=f"invalid zeus-result.json: {exc}")
            return

        if validated.status == "completed":
            await self.store.update_task_status(
                tid,
                "completed",
                passes=True,
                commit_sha=validated.commit_sha,
                worker_id=None,
            )
            await self.store.log_event(
                event_type="task.completed",
                task_id=tid,
                agent_id=self.worker_id,
                payload={
                    "changed_files": validated.changed_files,
                    "test_summary": validated.test_summary.model_dump(),
                },
            )
            if self.bus:
                self.bus.emit("task.completed", {"task_id": tid, "worker_id": self.worker_id, "commit_sha": validated.commit_sha})
            await self.queue.ack(tid)
        else:
            await self.store.update_task_status(tid, "failed", passes=False)
            await self.store.update_task_status(tid, "failed", passes=False, worker_id=None)
            await self.store.log_event(
                event_type="task.failed",
                task_id=tid,
                agent_id=self.worker_id,
                payload={"status": validated.status, "artifacts": validated.artifacts},
            )
            if self.bus:
                self.bus.emit("task.failed", {"task_id": tid, "worker_id": self.worker_id, "status": validated.status})
            if workspace:
                await self.store.quarantine_task(tid, validated.artifacts.get("error", "partial_or_failed"), workspace=str(workspace))
            await self.queue.nack(tid, reason=validated.artifacts.get("error", "partial_or_failed"))

    def _read_zeus_result(self, workspace: Path | None) -> dict[str, Any] | None:
        if workspace is None:
            return None
        path = workspace / "zeus-result.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
