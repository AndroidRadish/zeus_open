"""
Workflow graph generator for ZeusOpen v3.

Builds interactive dependency diagrams from runtime task state.
"""
from __future__ import annotations

from typing import Any


COLOR_MAP = {
    "pending": "#9ca3af",
    "running": "#3b82f6",
    "completed": "#22c55e",
    "failed": "#ef4444",
    "paused": "#a78bfa",
    "cancelled": "#64748b",
}


def _resolve_status(task: dict[str, Any]) -> str:
    status = task.get("status", "pending")
    if status:
        return status
    if task.get("passes") is True:
        return "completed"
    return "pending"


def _mermaid_node_id(task_id: str) -> str:
    return task_id.replace("-", "_")


class WorkflowGraph:
    """Renders workflow dependency graphs from a list of task dicts."""

    def __init__(self, tasks: list[dict[str, Any]]):
        self.tasks = tasks

    def to_mermaid(self) -> str:
        lines = ["flowchart TD"]

        waves: dict[int, list[dict[str, Any]]] = {}
        for task in self.tasks:
            wave = task.get("wave", 0) or 0
            waves.setdefault(wave, []).append(task)

        for wave in sorted(waves.keys()):
            lines.append(f"    subgraph Wave {wave}")
            for task in waves[wave]:
                tid = task["id"]
                node_id = _mermaid_node_id(tid)
                lines.append(f"        {node_id}[{tid}]")
            lines.append("    end")

        for task in self.tasks:
            tid = task["id"]
            node_id = _mermaid_node_id(tid)
            for dep in task.get("depends_on", []):
                if dep:
                    dep_node = _mermaid_node_id(dep)
                    lines.append(f"    {dep_node} --> {node_id}")

        for task in self.tasks:
            tid = task["id"]
            status = _resolve_status(task)
            color = COLOR_MAP.get(status, COLOR_MAP["pending"])
            node_id = _mermaid_node_id(tid)
            lines.append(f"    style {node_id} fill:{color}")

        return "\n".join(lines) + "\n"

    def to_graphviz(self) -> str:
        lines = ["digraph Workflow {"]
        lines.append("    node [style=filled, fontcolor=white, shape=box];")

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

        for task in self.tasks:
            tid = task["id"]
            for dep in task.get("depends_on", []):
                if dep:
                    lines.append(f'    "{dep}" -> "{tid}";')

        lines.append("}")
        return "\n".join(lines) + "\n"

    def to_echarts(self) -> dict[str, Any]:
        waves: dict[int, list[dict[str, Any]]] = {}
        for task in self.tasks:
            wave = task.get("wave", 0) or 0
            waves.setdefault(wave, []).append(task)

        sorted_waves = sorted(waves.keys())
        wave_to_category = {wave: idx for idx, wave in enumerate(sorted_waves)}

        nodes: list[dict[str, Any]] = []
        for task in self.tasks:
            tid = task["id"]
            status = _resolve_status(task)
            wave = task.get("wave", 0) or 0
            title = task.get("title", "")
            label = f"{tid}\n{title}" if title else tid

            dep_count = len(task.get("depends_on", []))
            downstream = sum(1 for t in self.tasks if tid in t.get("depends_on", []))
            symbol_size = 40 + (dep_count + downstream) * 6

            nodes.append(
                {
                    "id": tid,
                    "name": tid,
                    "value": downstream + dep_count + 1,
                    "category": wave_to_category.get(wave, 0),
                    "symbolSize": min(symbol_size, 80),
                    "status": status,
                    "wave": wave,
                    "title": title,
                    "description": task.get("description", ""),
                }
            )

        links: list[dict[str, str]] = []
        for task in self.tasks:
            tid = task["id"]
            for dep in task.get("depends_on", []):
                if dep:
                    links.append({"source": dep, "target": tid})

        categories = [{"name": f"Wave {w}"} for w in sorted_waves]

        return {"nodes": nodes, "links": links, "categories": categories}

    def to_svg_native(self) -> str:
        BOX_W = 200
        BOX_H = 56
        COL_W = 260
        ROW_H = 76
        MARGIN_X = 40
        MARGIN_Y = 30

        waves: dict[int, list[dict[str, Any]]] = {}
        for task in self.tasks:
            wave = task.get("wave", 0) or 0
            waves.setdefault(wave, []).append(task)
        sorted_waves = sorted(waves.keys())

        if not self.tasks:
            width, height = 320, 120
            return (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
                f'viewBox="0 0 {width} {height}" style="background:#0a0a0f">\n'
                f'  <text x="{width // 2}" y="{height // 2}" text-anchor="middle" '
                'fill="#94a3b8" font-size="14" font-weight="500">No tasks available</text>\n'
                '</svg>\n'
            )

        positions: dict[str, tuple[int, int]] = {}
        for wave in sorted_waves:
            for idx, task in enumerate(waves[wave]):
                tid = task["id"]
                x = MARGIN_X + (wave - 1) * COL_W if wave > 0 else MARGIN_X
                y = MARGIN_Y + idx * ROW_H
                positions[tid] = (x, y)

        max_wave = max(sorted_waves) if sorted_waves else 0
        max_len = max(len(waves[w]) for w in sorted_waves) if sorted_waves else 0
        width = MARGIN_X * 2 + max(0, max_wave - 1) * COL_W + BOX_W
        height = MARGIN_Y * 2 + max_len * ROW_H

        lines: list[str] = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="background:#0a0a0f">',
            '  <defs>',
            '    <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">',
            '      <path d="M0,0 L0,6 L9,3 z" fill="#64748b"/>',
            '    </marker>',
            '  </defs>',
        ]

        for wave in sorted_waves:
            x = MARGIN_X + (wave - 1) * COL_W if wave > 0 else MARGIN_X
            lines.append(
                f'  <text x="{x + BOX_W // 2}" y="{MARGIN_Y - 10}" text-anchor="middle" fill="#94a3b8" font-size="12" font-weight="600">Wave {wave}</text>'
            )

        for task in self.tasks:
            tid = task["id"]
            tx, ty = positions[tid]
            for dep in task.get("depends_on", []):
                if not dep:
                    continue
                sx, sy = positions.get(dep, (tx - COL_W, ty))
                start_x = sx + BOX_W
                start_y = sy + BOX_H // 2
                end_x = tx
                end_y = ty + BOX_H // 2
                cp1_x = start_x + (end_x - start_x) // 2
                cp2_x = end_x - (end_x - start_x) // 2
                lines.append(
                    f'  <path d="M{start_x},{start_y} C{cp1_x},{start_y} {cp2_x},{end_y} {end_x},{end_y}" '
                    f'stroke="#475569" stroke-width="2" fill="none" marker-end="url(#arrow)"/>'
                )

        for task in self.tasks:
            tid = task["id"]
            tx, ty = positions[tid]
            status = _resolve_status(task)
            color = COLOR_MAP.get(status, COLOR_MAP["pending"])
            title = task.get("title", "")

            lines.append(
                f'  <rect x="{tx}" y="{ty}" width="{BOX_W}" height="{BOX_H}" rx="8" ry="8" '
                f'fill="{color}" stroke="rgba(255,255,255,0.15)" stroke-width="1"/>'
            )
            lines.append(
                f'  <text x="{tx + 12}" y="{ty + 22}" fill="#0a0a0f" font-size="13" font-weight="700">{tid}</text>'
            )
            if title:
                display = title if len(title) <= 24 else title[:23] + "…"
                lines.append(
                    f'  <text x="{tx + 12}" y="{ty + 44}" fill="#0a0a0f" font-size="11" font-weight="500" opacity="0.85">{display}</text>'
                )

        lines.append("</svg>")
        return "\n".join(lines) + "\n"
