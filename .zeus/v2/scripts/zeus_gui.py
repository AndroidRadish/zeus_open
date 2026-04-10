"""
zeus_gui.py — ZeusOpen v2 PyQt Desktop Dashboard

Provides a desktop GUI for monitoring waves, agents, discussions,
and workflow graphs. Communicates with zeus_server.py via REST API.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import requests
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

DEFAULT_API_BASE = "http://localhost:8234"
POLL_INTERVAL_MS = 2000


# ---------------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------------
class ZeusApiClient:
    def __init__(self, base_url: str = DEFAULT_API_BASE):
        self.base_url = base_url.rstrip("/")

    def _get(self, path: str) -> Any:
        resp = requests.get(self.base_url + path, timeout=10)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            return resp.json()
        return resp.text

    def _post(self, path: str) -> Any:
        resp = requests.post(self.base_url + path, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_status(self) -> dict[str, Any]:
        return self._get("/status")

    def get_wave(self, n: int) -> dict[str, Any]:
        return self._get(f"/wave/{n}")

    def get_agents(self) -> dict[str, Any]:
        return self._get("/agents")

    def get_discussion(self, wave: int) -> str:
        return self._get(f"/discussion?wave={wave}")

    def get_graph_svg(self) -> bytes:
        resp = requests.get(self.base_url + "/graph/svg", timeout=30)
        resp.raise_for_status()
        return resp.content

    def approve_wave(self, n: int) -> dict[str, Any]:
        return self._post(f"/wave/{n}/approve")


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
class DashboardTab(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Stats cards
        stats_layout = QHBoxLayout()
        self.pending_card = self._create_stat_card("Pending Tasks", "0", "#3b82f6")
        self.completed_card = self._create_stat_card("Completed Tasks", "0", "#22c55e")
        self.failed_card = self._create_stat_card("Failed Tasks", "0", "#ef4444")
        stats_layout.addWidget(self.pending_card)
        stats_layout.addWidget(self.completed_card)
        stats_layout.addWidget(self.failed_card)
        layout.addLayout(stats_layout)

        # Progress bar
        progress_group = QGroupBox("Wave Progress")
        pg_layout = QVBoxLayout(progress_group)
        self.wave_progress = QProgressBar()
        self.wave_progress.setRange(0, 1)
        self.wave_progress.setValue(0)
        self.wave_progress.setFormat("%v / %m tasks")
        pg_layout.addWidget(self.wave_progress)
        layout.addWidget(progress_group)

        # Tasks table
        table_group = QGroupBox("Tasks")
        tg_layout = QVBoxLayout(table_group)
        self.tasks_table = QTableWidget()
        self.tasks_table.setColumnCount(4)
        self.tasks_table.setHorizontalHeaderLabels(["ID", "Title", "Status", "Depends On"])
        self.tasks_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tasks_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tasks_table.setAlternatingRowColors(True)
        tg_layout.addWidget(self.tasks_table)
        layout.addWidget(table_group)

        layout.addStretch()

    def _create_stat_card(self, label: str, value: str, color: str) -> QGroupBox:
        card = QGroupBox()
        card.setStyleSheet(f"QGroupBox {{ border-left: 4px solid {color}; }}")
        layout = QVBoxLayout(card)
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #6b7280; font-size: 12px;")
        val = QLabel(value)
        val.setStyleSheet("color: #111827; font-size: 24px; font-weight: bold;")
        val.setObjectName("value")
        layout.addWidget(lbl)
        layout.addWidget(val)
        return card

    def _set_card_value(self, card: QGroupBox, value: str) -> None:
        val_label = card.findChild(QLabel, "value")
        if val_label:
            val_label.setText(value)

    def update_data(self, status: dict[str, Any], wave_data: dict[str, Any]) -> None:
        pending = status.get("pending_tasks", 0)
        completed = status.get("completed_tasks", 0)
        tasks = wave_data.get("tasks", [])
        failed = sum(1 for t in tasks if t.get("passes") is False)
        total_wave = len(tasks)
        done_wave = sum(1 for t in tasks if t.get("passes") is True)

        self._set_card_value(self.pending_card, str(pending))
        self._set_card_value(self.completed_card, str(completed))
        self._set_card_value(self.failed_card, str(failed))

        self.wave_progress.setRange(0, max(total_wave, 1))
        self.wave_progress.setValue(done_wave)

        self.tasks_table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            self.tasks_table.setItem(row, 0, QTableWidgetItem(task.get("id", "")))
            self.tasks_table.setItem(row, 1, QTableWidgetItem(task.get("title", "")))
            status_text = self._task_status(task)
            self.tasks_table.setItem(row, 2, QTableWidgetItem(status_text))
            deps = ", ".join(task.get("depends_on", [])) or "—"
            self.tasks_table.setItem(row, 3, QTableWidgetItem(deps))

    @staticmethod
    def _task_status(task: dict[str, Any]) -> str:
        if task.get("passes") is True:
            return "done"
        if task.get("passes") is False:
            return "failed"
        return "pending"


class AgentsTab(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.list_layout = QVBoxLayout()
        self.list_layout.setSpacing(8)
        layout.addLayout(self.list_layout)
        layout.addStretch()

    def update_data(self, agents: list[dict[str, Any]]) -> None:
        # Clear existing widgets
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not agents:
            empty = QLabel("No agents currently running.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #6b7280; padding: 40px;")
            self.list_layout.addWidget(empty)
            return

        for agent in agents:
            card = QGroupBox()
            card.setStyleSheet("QGroupBox { border: 1px solid #e5e7eb; border-radius: 6px; }")
            hbox = QHBoxLayout(card)
            info = QVBoxLayout()
            info.addWidget(QLabel(f"<b>{agent.get('agent_id', 'unknown')}</b>"))
            info.addWidget(QLabel(f"Task: {agent.get('task_id', '—')}"))
            info.addWidget(QLabel(f"Started: {agent.get('started_at', '—')}"))
            hbox.addLayout(info)
            status = QLabel(agent.get("status", "idle").upper())
            status.setStyleSheet(
                "color: #15803d; background: #dcfce7; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;"
            )
            hbox.addWidget(status)
            self.list_layout.addWidget(card)


class DiscussionTab(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Wave:"))
        self.wave_input = QLineEdit("1")
        self.wave_input.setMaximumWidth(80)
        controls.addWidget(self.wave_input)
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self._on_load)
        controls.addWidget(load_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        layout.addWidget(self.text_browser)

    def _on_load(self) -> None:
        # Triggered by button; actual load is done via update_data
        pass

    def set_content(self, text: str) -> None:
        # Convert simple markdown headers to HTML for QTextBrowser
        html = self._markdown_to_html(text)
        self.text_browser.setHtml(html)

    @staticmethod
    def _markdown_to_html(md: str) -> str:
        lines = md.splitlines()
        out: list[str] = []
        in_pre = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                out.append(f"<h1>{stripped[2:]}</h1>")
            elif stripped.startswith("## "):
                out.append(f"<h2>{stripped[3:]}</h2>")
            elif stripped.startswith("```"):
                if not in_pre:
                    out.append("<pre><code>")
                    in_pre = True
                else:
                    out.append("</code></pre>")
                    in_pre = False
            else:
                escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                if in_pre:
                    out.append(escaped)
                else:
                    out.append(f"<p>{escaped}</p>")
        return "\n".join(out)


class GraphTab(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.svg_widget = QSvgWidget()
        self.svg_widget.setMinimumSize(400, 300)
        layout.addWidget(self.svg_widget)

    def set_svg(self, data: bytes) -> None:
        from PyQt6.QtCore import QByteArray

        self.svg_widget.load(QByteArray(data))


# ---------------------------------------------------------------------------
# Approval Dialog
# ---------------------------------------------------------------------------
class ApprovalDialog(QDialog):
    def __init__(self, wave: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"Wave {wave} Complete")
        self.setMinimumWidth(360)
        self.selected_action = "pause"
        self._setup_ui(wave)

    def _setup_ui(self, wave: int) -> None:
        layout = QVBoxLayout(self)
        msg = QLabel(
            f"<h2>Wave {wave} Completed</h2>"
            f"<p>All tasks in Wave {wave} have finished.</p>"
            f"<p>What would you like to do next?</p>"
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn_box = QDialogButtonBox()
        self.approve_btn = btn_box.addButton(
            f"Approve Wave {wave + 1}", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.retry_btn = btn_box.addButton("Retry Failed Tasks", QDialogButtonBox.ButtonRole.ResetRole)
        self.pause_btn = btn_box.addButton("Pause", QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(btn_box)

        btn_box.accepted.connect(self._on_approve)
        btn_box.rejected.connect(self._on_pause)
        # Handle ResetRole manually
        self.retry_btn.clicked.connect(self._on_retry)

    def _on_approve(self) -> None:
        self.selected_action = "approve"
        self.accept()

    def _on_pause(self) -> None:
        self.selected_action = "pause"
        self.reject()

    def _on_retry(self) -> None:
        self.selected_action = "retry"
        self.reject()


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self, api_base: str = DEFAULT_API_BASE):
        super().__init__()
        self.client = ZeusApiClient(api_base)
        self._approval_shown_for_wave: int | None = None
        self._setup_ui()
        self._setup_timer()
        self.refresh()

    def _setup_ui(self) -> None:
        self.setWindowTitle("ZeusOpen v2 Dashboard")
        self.setMinimumSize(900, 600)

        # Menu bar
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        refresh_action = QAction("Refresh", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.refresh)
        file_menu.addAction(refresh_action)
        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Central tabs
        self.tabs = QTabWidget()
        self.dashboard_tab = DashboardTab()
        self.agents_tab = AgentsTab()
        self.discussion_tab = DiscussionTab()
        self.graph_tab = GraphTab()

        self.tabs.addTab(self.dashboard_tab, "Dashboard")
        self.tabs.addTab(self.agents_tab, "Agents")
        self.tabs.addTab(self.discussion_tab, "Discussion")
        self.tabs.addTab(self.graph_tab, "Workflow Graph")
        self.setCentralWidget(self.tabs)

        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

        # Connect tab changes to lazy loading
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _setup_timer(self) -> None:
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(POLL_INTERVAL_MS)

    def _on_tab_changed(self, index: int) -> None:
        if index == 2:
            self._load_discussion()
        elif index == 3:
            self._load_graph()

    def refresh(self) -> None:
        try:
            status = self.client.get_status()
            current_wave = status.get("current_wave", 1)
            wave_data = self.client.get_wave(current_wave)
            agents_data = self.client.get_agents()
        except Exception as e:
            self.status_bar.showMessage(f"Connection error: {e}")
            return

        self.dashboard_tab.update_data(status, wave_data)
        self.agents_tab.update_data(agents_data.get("agents", []))

        if self.tabs.currentWidget() == self.discussion_tab:
            self._load_discussion()
        if self.tabs.currentWidget() == self.graph_tab:
            self._load_graph()

        self.status_bar.showMessage(
            f"Wave {current_wave} | Pending {status.get('pending_tasks', 0)} | Completed {status.get('completed_tasks', 0)}"
        )

        self._check_approval_gate(current_wave, wave_data)

    def _load_discussion(self) -> None:
        try:
            wave = int(self.discussion_tab.wave_input.text() or 1)
        except ValueError:
            wave = 1
        try:
            text = self.client.get_discussion(wave)
            self.discussion_tab.set_content(text)
        except Exception as e:
            self.discussion_tab.set_content(f"Error loading discussion: {e}")

    def _load_graph(self) -> None:
        try:
            svg_data = self.client.get_graph_svg()
            self.graph_tab.set_svg(svg_data)
        except Exception as e:
            self.graph_tab.set_svg(b"")
            self.status_bar.showMessage(f"Graph load error: {e}")

    def _check_approval_gate(self, current_wave: int, wave_data: dict[str, Any]) -> None:
        tasks = wave_data.get("tasks", [])
        if not tasks:
            return
        all_done = all(t.get("passes") is True for t in tasks)
        any_failed = any(t.get("passes") is False for t in tasks)

        if not all_done:
            return

        if self._approval_shown_for_wave == current_wave:
            return

        self._approval_shown_for_wave = current_wave
        dlg = ApprovalDialog(current_wave, parent=self)
        result = dlg.exec()

        if dlg.selected_action == "approve":
            try:
                resp = self.client.approve_wave(current_wave)
                next_wave = resp.get("next_wave", current_wave + 1)
                QMessageBox.information(self, "Approved", f"Proceeding to Wave {next_wave}")
                self._approval_shown_for_wave = None
            except Exception as e:
                QMessageBox.critical(self, "Approval Failed", str(e))
                self._approval_shown_for_wave = None
        elif dlg.selected_action == "retry":
            # Retry is a no-op in GUI; user handles retry via orchestrator or manually
            QMessageBox.information(self, "Retry", "Please retry failed tasks via the orchestrator CLI.")
            self._approval_shown_for_wave = None
        else:
            # Pause — do nothing, dialog will reappear on next poll unless user acts
            pass


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="ZeusOpen v2 PyQt Dashboard")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="Zeus server base URL")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("ZeusOpen v2")
    app.setStyle("Fusion")

    # Set a readable default font
    font = QFont("Segoe UI", 10)
    if not QFont(font).exactMatch():
        font = QFont("Microsoft YaHei", 10)
    app.setFont(font)

    window = MainWindow(api_base=args.api_base)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
