"""
Subprocess integration test — verify that v3 Worker correctly invokes an external
process and reads zeus-result.json as the primary source of truth.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.engine import make_async_engine
from db.models import Base
from core.scheduler import ZeusScheduler
from core.worker_pool import WorkerPool
from store.sqlite_store import SQLiteStateStore
from task_queue.memory_queue import MemoryTaskQueue
from workspace.manager import WorkspaceManager
from dispatcher.base import SubagentDispatcher


class PythonSubagentDispatcher(SubagentDispatcher):
    """
    A 'real' dispatcher that spawns a Python subprocess.
    The subprocess writes zeus-result.json into the workspace and exits.
    """

    async def run(self, task: dict, workspace: Path, prompt: str, bus=None) -> dict:
        tid = task["id"]
        result = {
            "status": "completed",
            "changed_files": [f"src/{tid.lower()}.py"],
            "test_summary": {"passed": 3, "failed": 0, "skipped": 0},
            "commit_sha": f"sub-{tid}",
            "artifacts": {"note": "written by subprocess"},
        }
        out_path = workspace / "zeus-result.json"
        script = (
            f"import json; "
            f"json.dump({json.dumps(result)}, open({repr(str(out_path))}, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)"
        )
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", script,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return {}  # The worker should ignore this and read the file instead


@pytest_asyncio.fixture
async def sqlite_store(tmp_path):
    db_path = tmp_path / "test.sqlite"
    store = SQLiteStateStore(f"sqlite+aiosqlite:///{db_path}")
    engine = make_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    yield store
    await store.close()


@pytest_asyncio.fixture
async def workspace_manager(tmp_path):
    (tmp_path / ".zeus" / "v3" / "config.json").parent.mkdir(parents=True)
    (tmp_path / ".zeus" / "v3" / "config.json").write_text(
        json.dumps({"project": {"name": "Sub"}, "metrics": {"north_star": "n"}, "subagent": {"dispatcher": "mock"}}),
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("#\n", encoding="utf-8")
    yield WorkspaceManager(tmp_path, "v3")


@pytest.mark.asyncio
async def test_worker_with_real_subprocess(sqlite_store, workspace_manager):
    store = sqlite_store
    q = MemoryTaskQueue()
    await store.upsert_task({"id": "T-SUB", "status": "pending", "wave": 1, "depends_on": []})
    await q.enqueue({"id": "T-SUB", "wave": 1})

    dispatcher = PythonSubagentDispatcher()
    pool = WorkerPool(store, q, dispatcher, workspace_manager, max_workers=1)
    await pool.start()
    await asyncio.sleep(1.0)
    await pool.stop()

    task = await store.get_task("T-SUB")
    assert task["status"] == "completed"
    assert task["passes"] is True
    assert task["commit_sha"] == "sub-T-SUB"

    # Verify the workspace received the result file
    ws = workspace_manager.workspace_path("T-SUB")
    result_path = ws / "zeus-result.json"
    assert result_path.exists()
    data = json.loads(result_path.read_text("utf-8"))
    assert data["artifacts"]["note"] == "written by subprocess"
