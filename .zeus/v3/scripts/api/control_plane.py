"""
Control plane for ZeusOpen v3 Dashboard.

Manages scheduler and worker subprocesses, plus in-process operations
like tick_once and task import.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.bus import EventBus
from core.scheduler import ZeusScheduler
from importer import import_tasks_from_json
from store.sqlite_store import SQLiteStateStore
from task_queue.memory_queue import MemoryTaskQueue


class ControlPlane:
    """Manages scheduler/worker lifecycle and one-shot operations."""

    def __init__(
        self,
        store: SQLiteStateStore,
        bus: EventBus,
        project_root: Path,
        database_url: str,
    ) -> None:
        self.store = store
        self.bus = bus
        self.project_root = project_root
        self.database_url = database_url
        self._scheduler_proc: subprocess.Popen | None = None
        self._worker_procs: list[subprocess.Popen] = []

    def _run_py_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "run.py"

    def spawn_scheduler(self) -> int:
        if self._scheduler_proc is not None and self._scheduler_proc.poll() is None:
            raise RuntimeError("Scheduler already running")
        cmd = [
            sys.executable,
            str(self._run_py_path()),
            "--project-root",
            str(self.project_root),
            "--database-url",
            self.database_url,
            "--mode",
            "scheduler",
        ]
        self._scheduler_proc = subprocess.Popen(cmd)
        return self._scheduler_proc.pid

    def stop_scheduler(self) -> None:
        if self._scheduler_proc is not None and self._scheduler_proc.poll() is None:
            self._scheduler_proc.terminate()
            try:
                self._scheduler_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._scheduler_proc.kill()
        self._scheduler_proc = None

    def spawn_workers(self, count: int) -> list[int]:
        self.stop_workers()
        run_py = self._run_py_path()
        pids: list[int] = []
        for _ in range(count):
            cmd = [
                sys.executable,
                str(run_py),
                "--project-root",
                str(self.project_root),
                "--database-url",
                self.database_url,
                "--mode",
                "worker",
            ]
            proc = subprocess.Popen(cmd)
            self._worker_procs.append(proc)
            pids.append(proc.pid)
        return pids

    def stop_workers(self) -> None:
        for proc in self._worker_procs:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        self._worker_procs.clear()

    async def tick_once(self) -> dict[str, Any]:
        queue = MemoryTaskQueue()
        scheduler = ZeusScheduler(self.store, queue, self.bus)
        result = await scheduler.run_once()
        return result

    async def import_tasks(self) -> dict[str, Any]:
        task_json_path = self.project_root / ".zeus" / "v3" / "task.json"
        result = await import_tasks_from_json(self.store, task_json_path)
        await self.store.set_meta(
            "last_import_at", datetime.now(timezone.utc).isoformat()
        )
        return result

    async def global_run(self) -> dict[str, Any]:
        import_result = await self.import_tasks()
        scheduler_pid = self.spawn_scheduler()
        worker_pids = self.spawn_workers(3)
        return {
            "imported_tasks": import_result["imported_tasks"],
            "scheduler_pid": scheduler_pid,
            "worker_pids": worker_pids,
        }

    async def status(self) -> dict[str, Any]:
        scheduler_running = (
            self._scheduler_proc is not None and self._scheduler_proc.poll() is None
        )
        scheduler_pid = self._scheduler_proc.pid if scheduler_running else None
        alive_workers = [p for p in self._worker_procs if p.poll() is None]
        worker_pids = [p.pid for p in alive_workers]
        queue_size = await self.store.get_meta("queue_size", 0)
        last_import_at = await self.store.get_meta("last_import_at", None)
        return {
            "scheduler": {"running": scheduler_running, "pid": scheduler_pid},
            "workers": {"count": len(worker_pids), "pids": worker_pids},
            "queue_size": queue_size,
            "last_import_at": last_import_at,
        }
