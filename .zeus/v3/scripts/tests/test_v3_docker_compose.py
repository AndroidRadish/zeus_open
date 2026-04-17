"""
Docker Compose multi-container integration validation.

Tests that the zeus-api / zeus-scheduler / zeus-worker split
builds, starts, and passes health checks together.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

COMPOSE_FILE = Path(__file__).resolve().parent.parent.parent / "docker-compose.yml"
PROJECT_NAME = "zeus-open-test"
API_URL = "http://127.0.0.1:8000"


def _docker_available() -> bool:
    try:
        subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except Exception:
        return False


def _compose_cmd(*args):
    return ["docker", "compose", "-f", str(COMPOSE_FILE), "-p", PROJECT_NAME, *args]


def _http_get(url: str, timeout: int = 5) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


@pytest.mark.skipif(not _docker_available(), reason="Docker not available")
def test_compose_config_valid():
    result = subprocess.run(
        _compose_cmd("config"),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    # Verify services exist
    assert "zeus-api" in result.stdout
    assert "zeus-scheduler" in result.stdout
    assert "zeus-worker" in result.stdout
    assert "redis" in result.stdout


@pytest.mark.skipif(not _docker_available(), reason="Docker not available")
def test_compose_build():
    result = subprocess.run(
        _compose_cmd("build"),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(not _docker_available(), reason="Docker not available")
def test_compose_stack_health():
    # Ensure clean state
    subprocess.run(
        _compose_cmd("down", "-v"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    up = subprocess.run(
        _compose_cmd("up", "-d"),
        capture_output=True,
        text=True,
    )
    assert up.returncode == 0, up.stderr

    try:
        # Wait for API health
        deadline = time.monotonic() + 60
        last_error = None
        while time.monotonic() < deadline:
            try:
                data = _http_get(f"{API_URL}/health")
                if data.get("status") == "ok":
                    break
            except (urllib.error.URLError, json.JSONDecodeError) as exc:
                last_error = exc
                time.sleep(1)
        else:
            raise RuntimeError(f"API health check timed out: {last_error}")

        # Verify root endpoint
        root = _http_get(f"{API_URL}/")
        assert "ZeusOpen v3 API" in root.get("message", "")

        # Verify control plane status endpoint works
        status = _http_get(f"{API_URL}/control/status")
        assert "scheduler" in status
        assert "workers" in status

        # Cold-start import and run so scheduler+worker have work
        subprocess.run(
            _compose_cmd("exec", "-T", "zeus-api", "python", "/app/.zeus/v3/scripts/run.py", "--project-root=/app", "--status"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    finally:
        # Collect logs for debugging if needed
        logs = subprocess.run(
            _compose_cmd("logs", "--no-color"),
            capture_output=True,
            text=True,
        )
        # Stop and clean up
        down = subprocess.run(
            _compose_cmd("down", "-v"),
            capture_output=True,
            text=True,
        )
        assert down.returncode == 0, down.stderr
