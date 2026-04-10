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
