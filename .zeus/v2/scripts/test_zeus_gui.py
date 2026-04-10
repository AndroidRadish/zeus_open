"""
Smoke tests for zeus_gui.py

These tests verify that the PyQt GUI components can be instantiated
and updated without crashing. A real QApplication is required.
"""

import json
import tempfile
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

from agent_bus import AgentBus
from store import LocalStore
from zeus_gui import (
    AgentsTab,
    ApprovalDialog,
    DashboardTab,
    DiscussionTab,
    GraphTab,
    MainWindow,
    ZeusApiClient,
)


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication exists for the test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def sample_status():
    return {
        "version": "v2",
        "project_name": "test",
        "current_wave": 1,
        "pending_tasks": 1,
        "completed_tasks": 2,
        "validation": "pass",
    }


@pytest.fixture
def sample_wave_data():
    return {
        "wave": 1,
        "tasks": [
            {"id": "T-001", "title": "Task 1", "passes": True, "depends_on": []},
            {"id": "T-002", "title": "Task 2", "passes": False, "depends_on": ["T-001"]},
        ],
    }


# ---------------------------------------------------------------------------
# Component smoke tests
# ---------------------------------------------------------------------------
def test_dashboard_tab_smoke(qapp, sample_status, sample_wave_data):
    tab = DashboardTab()
    tab.update_data(sample_status, sample_wave_data)
    assert tab.tasks_table.rowCount() == 2


def test_agents_tab_smoke(qapp):
    tab = AgentsTab()
    tab.update_data(
        [
            {
                "agent_id": "coder-0",
                "task_id": "T-001",
                "started_at": "2026-04-10T12:00:00Z",
                "status": "running",
            }
        ]
    )
    assert tab.list_layout.count() == 1


def test_agents_tab_empty(qapp):
    tab = AgentsTab()
    tab.update_data([])
    assert tab.list_layout.count() == 1


def test_discussion_tab_smoke(qapp):
    tab = DiscussionTab()
    md = "# Wave 1\n\n## 12:00:00 — coder-0 (T-001)\nHello world"
    tab.set_content(md)
    html = tab.text_browser.toHtml()
    assert "Wave 1" in html
    assert "Hello world" in html


def test_graph_tab_smoke(qapp):
    tab = GraphTab()
    svg = b"""<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <rect width="100" height="100" fill="red"/>
</svg>
"""
    tab.set_svg(svg)
    assert tab.svg_widget is not None


def test_approval_dialog_smoke(qapp):
    dlg = ApprovalDialog(1)
    assert dlg.windowTitle() == "Wave 1 Complete"
    assert dlg.selected_action == "pause"


# ---------------------------------------------------------------------------
# API Client (offline)
# ---------------------------------------------------------------------------
def test_api_client_base_url():
    client = ZeusApiClient("http://localhost:9999")
    assert client.base_url == "http://localhost:9999"


# ---------------------------------------------------------------------------
# MainWindow smoke test with mocked client
# ---------------------------------------------------------------------------
def test_main_window_smoke(qapp, monkeypatch, tmp_path):
    # Prepare a temporary project so the server can serve it
    zeus_dir = tmp_path / ".zeus" / "v2"
    zeus_dir.mkdir(parents=True)
    task_data = {
        "meta": {"current_wave": 1, "wave_approval_required": True, "max_parallel_agents": 2},
        "tasks": [
            {"id": "T-001", "title": "Task 1", "passes": True, "depends_on": [], "wave": 1},
            {"id": "T-002", "title": "Task 2", "passes": False, "depends_on": [], "wave": 1},
        ],
    }
    (zeus_dir / "task.json").write_text(json.dumps(task_data), encoding="utf-8")

    # Monkeypatch store in zeus_server to point to tmp_path
    import zeus_server as zs

    test_store = LocalStore(base_dir=str(tmp_path))
    original_store = zs.store
    zs.store = test_store

    # Start server in background thread
    import threading
    import uvicorn

    server = uvicorn.Server(uvicorn.Config(zs.app, host="127.0.0.1", port=18234, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    import time

    time.sleep(1.5)

    try:
        window = MainWindow(api_base="http://127.0.0.1:18234")
        assert window.tabs.count() == 4
        window.refresh()
        assert window.dashboard_tab.tasks_table.rowCount() == 2
    finally:
        server.should_exit = True
        thread.join(timeout=3)
        zs.store = original_store
