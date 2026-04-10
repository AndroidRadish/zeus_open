"""
zeus_gui.py — ZeusOpen v2 PyQt Desktop Dashboard (Redesigned)

Redesign goals:
- Dark glassmorphism aesthetic matching the web UI
- All networking off the main thread via QThreadPool
- Smart caching, lazy loading, and reduced polling
- Reusable agent cards instead of delete/recreate on every poll
"""

from __future__ import annotations

import argparse
import io
import sys
from typing import Any

import requests
from PyQt6.QtCore import QByteArray, QObject, QRunnable, QThreadPool, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QKeySequence
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

DEFAULT_API_BASE = "http://localhost:8234"
POLL_INTERVAL_MS = 5000

# ---------------------------------------------------------------------------
# Dark theme QSS matching the web UI
# ---------------------------------------------------------------------------
DARK_THEME_QSS = """
QWidget {
    background: #0a0a0f;
    color: #e2e8f0;
    font-family: "DM Sans", "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 13px;
    outline: none;
}

QMainWindow {
    background: #0a0a0f;
}

/* Sidebar */
#sidebar {
    background: #0d0d12;
    border-right: 1px solid rgba(255,255,255,0.04);
}

#appTitle {
    color: #f8fafc;
    font-size: 18px;
    font-weight: 700;
}

#appSubtitle {
    color: #64748b;
    font-size: 11px;
    font-weight: 500;
}

NavButton {
    background: transparent;
    color: #94a3b8;
    border: none;
    border-radius: 8px;
    padding: 10px 14px;
    text-align: left;
    font-size: 13px;
    font-weight: 500;
}
NavButton:hover {
    background: rgba(255,255,255,0.05);
    color: #e2e8f0;
}
NavButton[active="true"] {
    background: rgba(6, 182, 212, 0.12);
    color: #22d3ee;
    border: 1px solid rgba(6, 182, 212, 0.25);
}

/* Header */
#headerFrame {
    background: #0d0d12;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}

#connectionIndicator {
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}
#connectionIndicator[online="true"] {
    color: #10b981;
    background: rgba(16, 185, 129, 0.12);
}
#connectionIndicator[online="false"] {
    color: #f43f5e;
    background: rgba(244, 63, 94, 0.12);
}

/* Cards */
#cardFrame {
    background: #111118;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
}

#statCard {
    background: #111118;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
}

#mutedLabel {
    color: #64748b;
}

/* Buttons */
QPushButton {
    background: #1e1e2a;
    color: #e2e8f0;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
}
QPushButton:hover {
    background: #252532;
    border: 1px solid rgba(255,255,255,0.12);
}
QPushButton:pressed {
    background: #15151c;
}
#primaryButton {
    background: #06b6d4;
    color: #0a0a0f;
    border: none;
    font-weight: 600;
}
#primaryButton:hover {
    background: #22d3ee;
}
#refreshButton {
    background: transparent;
    border: 1px solid rgba(255,255,255,0.08);
}
#refreshButton:hover {
    background: rgba(255,255,255,0.05);
}

/* Progress Bar */
QProgressBar {
    border: none;
    border-radius: 5px;
    background: #1e1e2a;
    text-align: center;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #06b6d4, stop:1 #6366f1);
    border-radius: 5px;
}

/* Table */
QTableWidget {
    background: #111118;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px;
    gridline-color: rgba(255,255,255,0.04);
    selection-background-color: rgba(6, 182, 212, 0.15);
}
QHeaderView::section {
    background: #16161f;
    color: #94a3b8;
    padding: 10px;
    border: none;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    font-weight: 600;
}
QTableWidget::item {
    padding: 10px;
    border: none;
}
QTableWidget::item:selected {
    background: rgba(6, 182, 212, 0.15);
    color: #e2e8f0;
}

/* Inputs */
QLineEdit {
    background: #111118;
    color: #e2e8f0;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px;
    padding: 6px 10px;
}
QLineEdit:focus {
    border: 1px solid #06b6d4;
}

/* Text Browser */
QTextBrowser {
    background: #111118;
    color: #e2e8f0;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px;
    padding: 12px;
}

/* Scrollbar */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: rgba(255,255,255,0.12);
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(255,255,255,0.20);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: rgba(255,255,255,0.12);
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Dialog */
QDialog {
    background: #0a0a0f;
}

/* Empty state */
#emptyState {
    color: #475569;
    font-size: 14px;
    padding: 40px;
}

/* Agent card */
#agentCard {
    background: #111118;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
}

#statusBadge {
    color: #22d3ee;
    background: rgba(6, 182, 212, 0.12);
    border: 1px solid rgba(6, 182, 212, 0.20);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}
"""


def _fix_windows_stdio() -> None:
    """Fix Windows console encoding for emoji/unicode output."""
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# API Layer
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


class WorkerSignals(QObject):
    result = pyqtSignal(object)
    error = pyqtSignal(str)


class ApiWorker(QRunnable):
    """Run a callable in QThreadPool and emit signals with the result or error."""

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))


# ---------------------------------------------------------------------------
# Custom widgets
# ---------------------------------------------------------------------------
class NavButton(QPushButton):
    """Sidebar navigation button with active state support."""

    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text, parent)

    def set_active(self, active: bool):
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
class DashboardTab(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(0, 0, 0, 0)

        # Stats row
        stats = QHBoxLayout()
        stats.setSpacing(16)
        self.pending_card = self._create_stat_card("待执行任务", "0", "#f59e0b")
        self.completed_card = self._create_stat_card("已完成任务", "0", "#10b981")
        self.validation_card = self._create_stat_card("验证状态", "-", "#06b6d4")
        stats.addWidget(self.pending_card)
        stats.addWidget(self.completed_card)
        stats.addWidget(self.validation_card)
        layout.addLayout(stats)

        # Progress
        progress_frame = QFrame()
        progress_frame.setObjectName("cardFrame")
        pf_layout = QVBoxLayout(progress_frame)
        pf_layout.setSpacing(10)
        pf_layout.setContentsMargins(16, 16, 16, 16)
        header = QHBoxLayout()
        title = QLabel("Wave 进度")
        title.setStyleSheet("font-weight: 600;")
        self.progress_label = QLabel("0 / 0")
        self.progress_label.setObjectName("mutedLabel")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.progress_label)
        pf_layout.addLayout(header)

        self.wave_progress = QProgressBar()
        self.wave_progress.setTextVisible(False)
        self.wave_progress.setFixedHeight(10)
        self.wave_progress.setRange(0, 1)
        self.wave_progress.setValue(0)
        pf_layout.addWidget(self.wave_progress)
        layout.addWidget(progress_frame)

        # Table
        table_frame = QFrame()
        table_frame.setObjectName("cardFrame")
        tf_layout = QVBoxLayout(table_frame)
        tf_layout.setSpacing(10)
        tf_layout.setContentsMargins(16, 16, 16, 16)
        table_title = QLabel("当前 Wave 任务")
        table_title.setStyleSheet("font-weight: 600;")
        tf_layout.addWidget(table_title)

        self.tasks_table = QTableWidget()
        self.tasks_table.setColumnCount(4)
        self.tasks_table.setHorizontalHeaderLabels(["ID", "标题", "状态", "依赖"])
        self.tasks_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tasks_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.tasks_table.horizontalHeader().resizeSection(2, 90)
        self.tasks_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.tasks_table.horizontalHeader().resizeSection(0, 90)
        self.tasks_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tasks_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tasks_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tasks_table.setAlternatingRowColors(False)
        self.tasks_table.verticalHeader().setVisible(False)
        self.tasks_table.setMinimumHeight(200)
        tf_layout.addWidget(self.tasks_table)
        layout.addWidget(table_frame, 1)

    def _create_stat_card(self, label: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setObjectName("statCard")
        # Accent line via inline style since QSS border-left on object name can be overridden
        card.setStyleSheet(f"""
            #statCard {{
                background: #111118;
                border: 1px solid rgba(255,255,255,0.06);
                border-left: 3px solid {color};
                border-radius: 12px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(4)
        layout.setContentsMargins(16, 16, 16, 16)
        lbl = QLabel(label)
        lbl.setObjectName("mutedLabel")
        val = QLabel(value)
        val.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: 700;")
        val.setObjectName("statValue")
        layout.addWidget(lbl)
        layout.addWidget(val)
        return card

    def _set_card_value(self, card: QFrame, value: str) -> None:
        val_label = card.findChild(QLabel, "statValue")
        if val_label:
            val_label.setText(value)

    def update_data(self, status: dict[str, Any], wave_data: dict[str, Any]) -> None:
        pending = status.get("pending_tasks", 0)
        completed = status.get("completed_tasks", 0)
        validation = status.get("validation", "fail")
        tasks = wave_data.get("tasks", [])
        failed = sum(1 for t in tasks if t.get("passes") is False)
        total_wave = len(tasks)
        done_wave = sum(1 for t in tasks if t.get("passes") is True)

        self._set_card_value(self.pending_card, str(pending))
        self._set_card_value(self.completed_card, str(completed))
        val_text = "通过" if validation == "pass" else "异常"
        self._set_card_value(self.validation_card, val_text)
        # Update validation accent color
        val_color = "#10b981" if validation == "pass" else "#f43f5e"
        self.validation_card.setStyleSheet(f"""
            #statCard {{
                background: #111118;
                border: 1px solid rgba(255,255,255,0.06);
                border-left: 3px solid {val_color};
                border-radius: 12px;
            }}
        """)
        val_label = self.validation_card.findChild(QLabel, "statValue")
        if val_label:
            val_label.setStyleSheet(f"color: {val_color}; font-size: 28px; font-weight: 700;")
            val_label.setText(val_text)

        self.wave_progress.setRange(0, max(total_wave, 1))
        self.wave_progress.setValue(done_wave)
        self.progress_label.setText(f"{done_wave} / {total_wave} 任务")

        self.tasks_table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            self.tasks_table.setItem(row, 0, QTableWidgetItem(task.get("id", "")))
            title_item = QTableWidgetItem(task.get("title", ""))
            title_item.setToolTip(task.get("title", ""))
            self.tasks_table.setItem(row, 1, title_item)

            status_text = self._task_status(task)
            status_color = {"done": "#10b981", "failed": "#f43f5e", "pending": "#94a3b8"}.get(status_text, "#94a3b8")
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(status_color))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tasks_table.setItem(row, 2, status_item)

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
        self._agent_cards: dict[str, QFrame] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setSpacing(12)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.container_layout.setContentsMargins(0, 0, 8, 0)

        self.empty_label = QLabel("当前没有运行中的 Agent")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setObjectName("emptyState")
        self.container_layout.addWidget(self.empty_label)

        scroll.setWidget(self.container)
        layout.addWidget(scroll)

    def _create_card(self, agent: dict[str, Any]) -> QFrame:
        card = QFrame()
        card.setObjectName("agentCard")
        card.setFixedHeight(80)
        hbox = QHBoxLayout(card)
        hbox.setContentsMargins(16, 12, 16, 12)
        hbox.setSpacing(12)

        avatar = QLabel(agent.get("agent_id", "A")[-1].upper())
        avatar.setFixedSize(40, 40)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            "background: rgba(6,182,212,0.10); color: #22d3ee; border-radius: 20px; font-weight: 700;"
        )
        hbox.addWidget(avatar)

        info = QVBoxLayout()
        info.setSpacing(2)
        self._name_label = QLabel(f"<b>{agent.get('agent_id', 'unknown')}</b>")
        self._name_label.setTextFormat(Qt.TextFormat.RichText)
        self._task_label = QLabel(f"任务: {agent.get('task_id', '—')}")
        self._task_label.setObjectName("mutedLabel")
        info.addWidget(self._name_label)
        info.addWidget(self._task_label)
        hbox.addLayout(info, 1)

        status = QLabel("运行中")
        status.setObjectName("statusBadge")
        hbox.addWidget(status)

        return card

    def _update_card(self, card: QFrame, agent: dict[str, Any]) -> None:
        # Card children are stable; we only need to update task label if needed
        labels = card.findChildren(QLabel)
        for lbl in labels:
            if lbl.objectName() == "mutedLabel":
                lbl.setText(f"任务: {agent.get('task_id', '—')}")

    def update_data(self, agents: list[dict[str, Any]]) -> None:
        current_ids = set()
        for agent in agents:
            aid = agent.get("agent_id") or agent.get("task_id", "unknown")
            current_ids.add(aid)

        # Remove old
        for aid in list(self._agent_cards.keys()):
            if aid not in current_ids:
                card = self._agent_cards.pop(aid)
                self.container_layout.removeWidget(card)
                card.deleteLater()

        has_agents = len(agents) > 0
        self.empty_label.setVisible(not has_agents)

        # Update or create
        for agent in agents:
            aid = agent.get("agent_id") or agent.get("task_id", "unknown")
            if aid in self._agent_cards:
                self._update_card(self._agent_cards[aid], agent)
            else:
                card = self._create_card(agent)
                self._agent_cards[aid] = card
                self.container_layout.addWidget(card)


class DiscussionTab(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        controls = QFrame()
        controls.setObjectName("cardFrame")
        c_layout = QHBoxLayout(controls)
        c_layout.setContentsMargins(12, 12, 12, 12)
        c_layout.addWidget(QLabel("Wave:"))
        self.wave_input = QLineEdit("1")
        self.wave_input.setMaximumWidth(80)
        c_layout.addWidget(self.wave_input)
        load_btn = QPushButton("加载")
        load_btn.clicked.connect(self._trigger_load)
        c_layout.addWidget(load_btn)
        c_layout.addStretch()
        layout.addWidget(controls)

        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        layout.addWidget(self.text_browser)

    def _trigger_load(self) -> None:
        # Actual load is handled by MainWindow calling load_discussion
        pass

    def set_content(self, text: str) -> None:
        html = self._markdown_to_html(text)
        self.text_browser.setHtml(html)

    def has_content(self) -> bool:
        return bool(self.text_browser.toPlainText().strip())

    @staticmethod
    def _markdown_to_html(md: str) -> str:
        lines = md.splitlines()
        out: list[str] = []
        in_pre = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                out.append(f'<h1 style="color:#f8fafc;font-size:20px;font-weight:700;margin:12px 0;">{stripped[2:]}</h1>')
            elif stripped.startswith("## "):
                out.append(f'<h2 style="color:#e2e8f0;font-size:16px;font-weight:600;margin:10px 0;border-bottom:1px solid rgba(255,255,255,0.06);padding-bottom:4px;">{stripped[3:]}</h2>')
            elif stripped.startswith("### "):
                out.append(f'<h3 style="color:#94a3b8;font-size:14px;font-weight:600;margin:8px 0;">{stripped[4:]}</h3>')
            elif stripped.startswith("```"):
                if not in_pre:
                    out.append('<pre style="background:#0a0a0f;border:1px solid rgba(255,255,255,0.06);border-radius:6px;padding:10px;overflow:auto;"><code style="color:#22d3ee;">')
                    in_pre = True
                else:
                    out.append("</code></pre>")
                    in_pre = False
            else:
                escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                if in_pre:
                    out.append(escaped)
                else:
                    out.append(f'<p style="color:#cbd5e1;line-height:1.6;margin:4px 0;">{escaped}</p>')
        return "\n".join(out)


class GraphTab(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        self.error_label = QLabel()
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setObjectName("mutedLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        self.svg_widget = QSvgWidget()
        self.svg_widget.setMinimumSize(400, 300)
        layout.addWidget(self.svg_widget)

    def set_svg(self, data: bytes) -> None:
        if not data:
            self.svg_widget.load(QByteArray())
            self.error_label.setText("无法加载图谱。请确保后端已启动且 Graphviz 已安装。")
            self.error_label.setVisible(True)
            return
        self.error_label.setVisible(False)
        self.svg_widget.load(QByteArray(data))


# ---------------------------------------------------------------------------
# Approval Dialog
# ---------------------------------------------------------------------------
class ApprovalDialog(QDialog):
    def __init__(self, wave: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Wave 完成")
        self.setMinimumWidth(380)
        self.selected_action = "pause"
        self._setup_ui(wave)

    def _setup_ui(self, wave: int) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel(f"Wave {wave} 已完成")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(title)

        msg = QLabel(f"Wave {wave} 中的所有任务都已结束。\n请选择下一步操作：")
        msg.setObjectName("mutedLabel")
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.approve_btn = QPushButton(f"批准进入 Wave {wave + 1}")
        self.approve_btn.setObjectName("primaryButton")
        self.approve_btn.clicked.connect(self._on_approve)
        btn_layout.addWidget(self.approve_btn)

        retry_btn = QPushButton("重试失败任务")
        retry_btn.clicked.connect(self._on_retry)
        btn_layout.addWidget(retry_btn)

        pause_btn = QPushButton("暂停")
        pause_btn.clicked.connect(self._on_pause)
        btn_layout.addWidget(pause_btn)

        layout.addLayout(btn_layout)

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
        self.thread_pool = QThreadPool.globalInstance()

        # Caches
        self._cached_status: dict[str, Any] | None = None
        self._cached_wave: dict[str, Any] | None = None
        self._cached_wave_num: int | None = None
        self._cached_agents: dict[str, Any] | None = None
        self._cached_svg_wave: int | None = None
        self._cached_svg_data: bytes | None = None
        self._approval_shown_for_wave: int | None = None

        self._setup_ui()
        self._setup_timer()
        self._setup_shortcuts()
        self._refresh_all()

    def _setup_ui(self) -> None:
        self.setWindowTitle("ZeusOpen v2 Dashboard")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setSpacing(0)
        root_layout.setContentsMargins(0, 0, 0, 0)

        # Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(180)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setSpacing(8)
        sb_layout.setContentsMargins(16, 20, 16, 20)

        brand = QVBoxLayout()
        title = QLabel("ZeusOpen")
        title.setObjectName("appTitle")
        subtitle = QLabel("v2 控制台")
        subtitle.setObjectName("appSubtitle")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        sb_layout.addLayout(brand)
        sb_layout.addSpacing(24)

        self.nav_buttons: list[NavButton] = []
        self.nav_dashboard = NavButton("  Dashboard")
        self.nav_agents = NavButton("  Agents")
        self.nav_discussion = NavButton("  Discussion")
        self.nav_graph = NavButton("  Graph")

        for btn, idx in [
            (self.nav_dashboard, 0),
            (self.nav_agents, 1),
            (self.nav_discussion, 2),
            (self.nav_graph, 3),
        ]:
            btn.clicked.connect(lambda checked, i=idx: self._set_page(i))
            sb_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sb_layout.addStretch()

        web_btn = QPushButton("打开 Web UI")
        web_btn.clicked.connect(self._open_web_ui)
        sb_layout.addWidget(web_btn)
        sb_layout.addSpacing(8)

        quit_btn = QPushButton("退出")
        quit_btn.clicked.connect(self.close)
        sb_layout.addWidget(quit_btn)

        root_layout.addWidget(sidebar)

        # Main content area
        content = QVBoxLayout()
        content.setSpacing(0)
        content.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QFrame()
        header.setObjectName("headerFrame")
        header.setFixedHeight(64)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(24, 0, 24, 0)
        hl.setSpacing(16)

        self.header_title = QLabel("Dashboard")
        self.header_title.setStyleSheet("font-size: 18px; font-weight: 700;")
        hl.addWidget(self.header_title)
        hl.addStretch()

        self.connection_indicator = QLabel("在线")
        self.connection_indicator.setObjectName("connectionIndicator")
        self.connection_indicator.setProperty("online", True)
        hl.addWidget(self.connection_indicator)

        refresh_btn = QPushButton("⟳ 刷新")
        refresh_btn.setObjectName("refreshButton")
        refresh_btn.setShortcut(QKeySequence("F5"))
        refresh_btn.clicked.connect(self._refresh_all)
        hl.addWidget(refresh_btn)

        content.addWidget(header)

        # Pages
        self.stack = QStackedWidget()
        self.stack.setContentsMargins(24, 24, 24, 24)

        # Wrap each page in a padded container
        self.dashboard_tab = DashboardTab()
        self.agents_tab = AgentsTab()
        self.discussion_tab = DiscussionTab()
        self.graph_tab = GraphTab()

        self.discussion_tab.findChild(QPushButton).clicked.connect(self._load_discussion)

        self.stack.addWidget(self._wrap_page(self.dashboard_tab))
        self.stack.addWidget(self._wrap_page(self.agents_tab))
        self.stack.addWidget(self._wrap_page(self.discussion_tab))
        self.stack.addWidget(self._wrap_page(self.graph_tab))

        self.stack.currentChanged.connect(self._on_page_changed)
        content.addWidget(self.stack, 1)

        root_layout.addLayout(content, 1)

        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("就绪")

        self._set_page(0)

    def _wrap_page(self, widget: QWidget) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setSpacing(0)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(widget)
        return wrapper

    def _setup_timer(self) -> None:
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_all)
        self.timer.start(POLL_INTERVAL_MS)

    def _setup_shortcuts(self) -> None:
        refresh_action = QAction("刷新", self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self._refresh_all)
        self.addAction(refresh_action)

    def _set_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        titles = ["Dashboard", "Agents", "Discussion", "Workflow Graph"]
        self.header_title.setText(titles[index])
        for i, btn in enumerate(self.nav_buttons):
            btn.set_active(i == index)
        self._on_page_changed(index)

    def _on_page_changed(self, index: int) -> None:
        if index == 2:
            if not self.discussion_tab.has_content():
                self._load_discussion()
        elif index == 3:
            self._maybe_load_graph()

    def _open_web_ui(self) -> None:
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl(self.client.base_url + "/web"))

    # -----------------------------------------------------------------------
    # Refresh & API workers
    # -----------------------------------------------------------------------
    def _refresh_all(self) -> None:
        self._fetch_status()
        self._fetch_agents()

    def _fetch_status(self) -> None:
        worker = ApiWorker(self.client.get_status)
        worker.signals.result.connect(self._on_status_fetched)
        worker.signals.error.connect(self._on_fetch_error)
        self.thread_pool.start(worker)

    def _on_status_fetched(self, status: dict[str, Any]) -> None:
        self._cached_status = status
        self.connection_indicator.setProperty("online", True)
        self.connection_indicator.setText("在线")
        self.connection_indicator.style().unpolish(self.connection_indicator)
        self.connection_indicator.style().polish(self.connection_indicator)

        current_wave = status.get("current_wave", 1)
        if self._cached_wave_num != current_wave:
            self._fetch_wave(current_wave)
        else:
            self._update_dashboard()
            self._check_approval_gate(status, self._cached_wave)

        self._update_status_bar(status)

    def _fetch_wave(self, wave: int) -> None:
        worker = ApiWorker(self.client.get_wave, wave)
        worker.signals.result.connect(lambda data, w=wave: self._on_wave_fetched(data, w))
        worker.signals.error.connect(self._on_fetch_error)
        self.thread_pool.start(worker)

    def _on_wave_fetched(self, data: dict[str, Any], wave: int) -> None:
        self._cached_wave = data
        self._cached_wave_num = wave
        self._update_dashboard()
        self._check_approval_gate(self._cached_status, data)
        # Graph cache is now stale
        if self._cached_svg_wave != wave:
            self._cached_svg_data = None
            if self.stack.currentIndex() == 3:
                self._maybe_load_graph()

    def _fetch_agents(self) -> None:
        worker = ApiWorker(self.client.get_agents)
        worker.signals.result.connect(self._on_agents_fetched)
        worker.signals.error.connect(self._on_fetch_error)
        self.thread_pool.start(worker)

    def _on_agents_fetched(self, data: dict[str, Any]) -> None:
        self._cached_agents = data
        self.agents_tab.update_data(data.get("agents", []))

    def _on_fetch_error(self, error: str) -> None:
        self.connection_indicator.setProperty("online", False)
        self.connection_indicator.setText("离线")
        self.connection_indicator.style().unpolish(self.connection_indicator)
        self.connection_indicator.style().polish(self.connection_indicator)
        self.status_bar.showMessage(f"连接错误: {error}")

    # -----------------------------------------------------------------------
    # UI updates
    # -----------------------------------------------------------------------
    def _update_dashboard(self) -> None:
        if self._cached_status and self._cached_wave:
            self.dashboard_tab.update_data(self._cached_status, self._cached_wave)

    def _update_status_bar(self, status: dict[str, Any]) -> None:
        cw = status.get("current_wave", 0)
        pending = status.get("pending_tasks", 0)
        completed = status.get("completed_tasks", 0)
        self.status_bar.showMessage(f"Wave {cw} | 待执行 {pending} | 已完成 {completed}")

    def _load_discussion(self) -> None:
        try:
            wave = int(self.discussion_tab.wave_input.text() or 1)
        except ValueError:
            wave = 1
        worker = ApiWorker(self.client.get_discussion, wave)
        worker.signals.result.connect(self.discussion_tab.set_content)
        worker.signals.error.connect(lambda e: self.discussion_tab.set_content(f"加载失败: {e}"))
        self.thread_pool.start(worker)

    def _maybe_load_graph(self) -> None:
        if not self._cached_status:
            return
        wave = self._cached_status.get("current_wave", 1)
        if self._cached_svg_wave == wave and self._cached_svg_data is not None:
            self.graph_tab.set_svg(self._cached_svg_data)
            return
        self._cached_svg_wave = wave
        worker = ApiWorker(self.client.get_graph_svg)
        worker.signals.result.connect(self._on_graph_fetched)
        worker.signals.error.connect(lambda e: self.graph_tab.set_svg(b""))
        self.thread_pool.start(worker)

    def _on_graph_fetched(self, data: bytes) -> None:
        self._cached_svg_data = data
        self.graph_tab.set_svg(data)

    # -----------------------------------------------------------------------
    # Approval gate
    # -----------------------------------------------------------------------
    def _check_approval_gate(self, status: dict[str, Any] | None, wave_data: dict[str, Any] | None) -> None:
        if not status or not wave_data:
            return
        tasks = wave_data.get("tasks", [])
        if not tasks:
            return
        all_done = all(t.get("passes") is True for t in tasks)
        if not all_done:
            return
        current_wave = status.get("current_wave", 1)
        if self._approval_shown_for_wave == current_wave:
            return
        self._approval_shown_for_wave = current_wave
        dlg = ApprovalDialog(current_wave, parent=self)
        result = dlg.exec()
        if dlg.selected_action == "approve":
            worker = ApiWorker(self.client.approve_wave, current_wave)
            worker.signals.result.connect(lambda r: self._on_approved(r, current_wave))
            worker.signals.error.connect(lambda e: QMessageBox.critical(self, "批准失败", str(e)) or setattr(self, "_approval_shown_for_wave", None))
            self.thread_pool.start(worker)
        elif dlg.selected_action == "retry":
            QMessageBox.information(self, "重试", "请通过 orchestrator CLI 重试失败任务。")
            self._approval_shown_for_wave = None
        else:
            pass  # Pause — dialog will reappear on next poll

    def _on_approved(self, resp: dict[str, Any], current_wave: int) -> None:
        next_wave = resp.get("next_wave", current_wave + 1)
        QMessageBox.information(self, "已批准", f"进入 Wave {next_wave}")
        self._approval_shown_for_wave = None
        self._refresh_all()

    # -----------------------------------------------------------------------
    # Window events
    # -----------------------------------------------------------------------
    def changeEvent(self, event) -> None:
        if event.type() == event.Type.WindowStateChange:
            if self.isMinimized():
                self.timer.stop()
            else:
                if not self.timer.isActive():
                    self.timer.start(POLL_INTERVAL_MS)
                    self._refresh_all()
        super().changeEvent(event)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def main() -> int:
    _fix_windows_stdio()
    parser = argparse.ArgumentParser(description="ZeusOpen v2 PyQt Dashboard")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="Zeus server base URL")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("ZeusOpen v2")
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_THEME_QSS)

    font = QFont("DM Sans", 10)
    if not QFont(font).exactMatch():
        font = QFont("Segoe UI", 10)
    if not QFont(font).exactMatch():
        font = QFont("Microsoft YaHei", 10)
    app.setFont(font)

    window = MainWindow(api_base=args.api_base)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
