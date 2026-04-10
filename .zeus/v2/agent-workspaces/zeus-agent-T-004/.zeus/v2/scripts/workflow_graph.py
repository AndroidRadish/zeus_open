"""Workflow graph generator for ZeusOpen v2.

Reads task.json and generates interactive dependency diagrams in
Mermaid and Graphviz DOT formats.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


# Color palette shared across renderers
COLOR_MAP = {
    "pending": "#9ca3af",
    "in_progress": "#3b82f6",
    "done": "#22c55e",
    "failed": "#ef4444",
}


def _resolve_status(task: dict[str, Any]) -> str:
    """Determine task status from explicit field or passes flag."""
    if "status" in task:
        return task["status"]
    if task.get("passes") is True:
        return "done"
    return "pending"


def _mermaid_node_id(task_id: str) -> str:
    """Sanitize task id into a valid Mermaid node identifier."""
    return task_id.replace("-", "")


class WorkflowGraph:
    """Parses task.json and renders workflow dependency graphs."""

    def __init__(self, task_json_path: str):
        self.path = Path(task_json_path)
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        # Both v1 and v2 formats wrap tasks in a "tasks" list
        self.tasks: list[dict[str, Any]] = raw.get("tasks", [])

    def to_mermaid(self) -> str:
        """Return a Mermaid ``flowchart TD`` source string."""
        lines = ["flowchart TD"]

        # Group tasks by wave for subgraphs
        waves: dict[int, list[dict[str, Any]]] = {}
        for task in self.tasks:
            wave = task.get("wave", 0) or 0
            waves.setdefault(wave, []).append(task)

        # Render subgraphs per wave
        for wave in sorted(waves.keys()):
            lines.append(f"    subgraph Wave {wave}")
            for task in waves[wave]:
                tid = task["id"]
                node_id = _mermaid_node_id(tid)
                lines.append(f"        {node_id}[{tid}]")
            lines.append("    end")

        # Dependencies (edges) – render once outside subgraphs
        for task in self.tasks:
            tid = task["id"]
            node_id = _mermaid_node_id(tid)
            for dep in task.get("depends_on", []):
                if dep:
                    dep_node = _mermaid_node_id(dep)
                    lines.append(f"    {dep_node} --> {node_id}")

        # Styles
        for task in self.tasks:
            tid = task["id"]
            status = _resolve_status(task)
            color = COLOR_MAP.get(status, COLOR_MAP["pending"])
            node_id = _mermaid_node_id(tid)
            lines.append(f"    style {node_id} fill:{color}")

        return "\n".join(lines) + "\n"

    def to_graphviz(self) -> str:
        """Return a Graphviz DOT source string."""
        lines = ["digraph Workflow {"]
        lines.append("    node [style=filled, fontcolor=white, shape=box];")

        # Group tasks by wave for cluster subgraphs
        waves: dict[int, list[dict[str, Any]]] = {}
        for task in self.tasks:
            wave = task.get("wave", 0) or 0
            waves.setdefault(wave, []).append(task)

        for wave in sorted(waves.keys()):
            lines.append(f"    subgraph cluster_wave_{wave} {{")
            lines.append(f'        label="Wave {wave}";')
            lines.append("        style=rounded;")
            for task in waves[wave]:
                tid = task["id"]
                status = _resolve_status(task)
                color = COLOR_MAP.get(status, COLOR_MAP["pending"])
                title = task.get("title", "")
                label = f"{tid}\\n{title}" if title else tid
                lines.append(f'        "{tid}" [label="{label}", fillcolor="{color}"];')
            lines.append("    }")

        # Dependencies
        for task in self.tasks:
            tid = task["id"]
            for dep in task.get("depends_on", []):
                if dep:
                    lines.append(f'    "{dep}" -> "{tid}";')

        lines.append("}")
        return "\n".join(lines) + "\n"

    def to_svg(self, dot_path: str, output_path: str) -> str:
        """Render a DOT file to SVG using the system ``dot`` binary.

        Returns the generated SVG path on success, or an error message
        when ``dot`` is not available.
        """
        if shutil.which("dot") is None:
            return "Error: Graphviz 'dot' command not found. Please install Graphviz and ensure it is on your PATH."

        result = subprocess.run(
            ["dot", "-Tsvg", dot_path, "-o", output_path],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            err = result.stderr.strip() or "unknown error"
            return f"Error: dot command failed ({result.returncode}): {err}"
        return output_path
