import json
import threading
import tempfile
from pathlib import Path

import pytest

from store import LocalStore


def test_local_store_read_write_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(base_dir=tmpdir)
        store.write_json("test.json", {"foo": "bar", "num": 42})
        result = store.read_json("test.json")
        assert result == {"foo": "bar", "num": 42}


def test_local_store_append_line():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(base_dir=tmpdir)
        store.append_line("log.txt", "first line")
        store.append_line("log.txt", "second line")
        path = Path(tmpdir) / "log.txt"
        content = path.read_text(encoding="utf-8")
        assert content == "first line\nsecond line\n"


def test_local_store_lock_prevents_concurrent_write():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(base_dir=tmpdir)
        store.write_json("counter.json", {"count": 0})

        num_threads = 10
        increments_per_thread = 20
        errors = []

        def worker():
            try:
                for _ in range(increments_per_thread):
                    with store.lock("counter.json"):
                        data = store.read_json("counter.json")
                        data["count"] += 1
                        store.write_json("counter.json", data)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent write errors: {errors}"
        final = store.read_json("counter.json")
        assert final["count"] == num_threads * increments_per_thread


def test_local_store_update_json_fields():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(base_dir=tmpdir)
        store.write_json("tasks.json", {
            "meta": {"current_wave": 1},
            "tasks": [
                {"id": "T-001", "wave": 1, "passes": False},
                {"id": "T-002", "wave": 1, "passes": False},
                {"id": "T-003", "wave": 2, "passes": False},
            ]
        })

        store.update_json_fields(
            "tasks.json",
            list_key="tasks",
            id_field="id",
            updates=[
                {"id": "T-001", "scheduled_wave": 1, "original_wave": 1},
                {"id": "T-003", "scheduled_wave": 1, "rescheduled_from": 2},
            ],
        )

        result = store.read_json("tasks.json")
        tasks = {t["id"]: t for t in result["tasks"]}
        assert tasks["T-001"]["scheduled_wave"] == 1
        assert tasks["T-001"]["original_wave"] == 1
        assert tasks["T-003"]["scheduled_wave"] == 1
        assert tasks["T-003"]["rescheduled_from"] == 2
        assert "scheduled_wave" not in tasks["T-002"]  # unchanged


def test_local_store_update_json_fields_concurrent():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalStore(base_dir=tmpdir)
        store.write_json("tasks.json", {
            "tasks": [{"id": f"T-{i:03d}", "wave": 1} for i in range(20)]
        })

        num_threads = 5
        updates_per_thread = 4
        errors = []

        def worker(thread_idx):
            try:
                for i in range(updates_per_thread):
                    task_id = f"T-{thread_idx * updates_per_thread + i:03d}"
                    store.update_json_fields(
                        "tasks.json",
                        list_key="tasks",
                        id_field="id",
                        updates=[{"id": task_id, "scheduled_wave": thread_idx}],
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent update_json_fields errors: {errors}"
        result = store.read_json("tasks.json")
        tasks = {t["id"]: t for t in result["tasks"]}
        for thread_idx in range(num_threads):
            for i in range(updates_per_thread):
                task_id = f"T-{thread_idx * updates_per_thread + i:03d}"
                assert tasks[task_id]["scheduled_wave"] == thread_idx
