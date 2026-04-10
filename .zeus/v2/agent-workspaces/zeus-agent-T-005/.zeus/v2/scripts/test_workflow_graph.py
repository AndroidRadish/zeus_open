"""Tests for workflow_graph.py."""

import json
import shutil
from pathlib import Path

import pytest

from workflow_graph import WorkflowGraph


SAMPLE_TASKS = {
    "meta": {"current_wave": 2},
    "tasks": [
        {
            "id": "T-001",
            "title": "First task",
            "wave": 1,
            "depends_on": [],
            "passes": True,
        },
        {
            "id": "T-002",
            "title": "Second task",
            "wave": 1,
            "depends_on": [],
            "passes": False,
        },
        {
            "id": "T-003",
            "title": "Third task",
            "wave": 2,
            "depends_on": ["T-001", "T-002"],
            "status": "in_progress",
        },
    ],
}


def _write_sample(tmp_path: Path) -> Path:
    p = tmp_path / "task.json"
    p.write_text(json.dumps(SAMPLE_TASKS), encoding="utf-8")
    return p


def test_to_mermaid_basic(tmp_path: Path) -> None:
    p = _write_sample(tmp_path)
    graph = WorkflowGraph(str(p))
    out = graph.to_mermaid()

    assert out.startswith("flowchart TD\n")

    # Nodes inside wave subgraphs
    assert "T001[T-001]" in out
    assert "T002[T-002]" in out
    assert "T003[T-003]" in out

    # Wave subgraphs
    assert "subgraph Wave 1" in out
    assert "subgraph Wave 2" in out

    # Edges
    assert "T001 --> T003" in out
    assert "T002 --> T003" in out

    # Colors
    assert "style T001 fill:#22c55e" in out  # done
    assert "style T002 fill:#9ca3af" in out  # pending (passes false)
    assert "style T003 fill:#3b82f6" in out  # in_progress


def test_to_graphviz_basic(tmp_path: Path) -> None:
    p = _write_sample(tmp_path)
    graph = WorkflowGraph(str(p))
    out = graph.to_graphviz()

    assert out.startswith("digraph Workflow {\n")
    assert 'node [style=filled, fontcolor=white, shape=box];' in out

    # Clusters
    assert "subgraph cluster_wave_1 {" in out
    assert "subgraph cluster_wave_2 {" in out

    # Labels with titles
    assert 'label="T-001\\nFirst task"' in out
    assert 'label="T-003\\nThird task"' in out

    # Colors
    assert 'fillcolor="#22c55e"' in out  # done
    assert 'fillcolor="#9ca3af"' in out  # pending
    assert 'fillcolor="#3b82f6"' in out  # in_progress

    # Edges
    assert '"T-001" -> "T-003";' in out
    assert '"T-002" -> "T-003";' in out


def test_status_colors(tmp_path: Path) -> None:
    """Verify that status/passes map to the expected hex colours."""
    data = {
        "tasks": [
            {"id": "T-010", "wave": 1, "depends_on": [], "status": "pending"},
            {"id": "T-011", "wave": 1, "depends_on": [], "status": "in_progress"},
            {"id": "T-012", "wave": 1, "depends_on": [], "status": "done"},
            {"id": "T-013", "wave": 1, "depends_on": [], "status": "failed"},
            {"id": "T-014", "wave": 1, "depends_on": [], "passes": True},
            {"id": "T-015", "wave": 1, "depends_on": [], "passes": False},
            {"id": "T-016", "wave": 1, "depends_on": []},  # no passes, no status
        ]
    }
    p = tmp_path / "task.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    graph = WorkflowGraph(str(p))

    mermaid = graph.to_mermaid()
    graphviz = graph.to_graphviz()

    expected = {
        "T010": "#9ca3af",
        "T011": "#3b82f6",
        "T012": "#22c55e",
        "T013": "#ef4444",
        "T014": "#22c55e",
        "T015": "#9ca3af",
        "T016": "#9ca3af",
    }

    for node_id, color in expected.items():
        assert f"style {node_id} fill:{color}" in mermaid
        assert f'"T-{node_id[1:]}"' in graphviz  # sanity check node exists
        # In DOT we just verify the color appears; all nodes in same wave so cluster check is enough
        assert color in graphviz


@pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz dot not installed")
def test_to_svg_success(tmp_path: Path) -> None:
    p = _write_sample(tmp_path)
    graph = WorkflowGraph(str(p))

    dot_file = tmp_path / "workflow.dot"
    svg_file = tmp_path / "workflow.svg"
    dot_file.write_text(graph.to_graphviz(), encoding="utf-8")

    result = graph.to_svg(str(dot_file), str(svg_file))
    assert result == str(svg_file)
    assert svg_file.exists()


def test_to_svg_missing_dot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When dot is absent we should get a clear error message."""
    p = _write_sample(tmp_path)
    graph = WorkflowGraph(str(p))

    # Force shutil.which to return None regardless of system state
    monkeypatch.setattr(shutil, "which", lambda _cmd: None)

    dot_file = tmp_path / "workflow.dot"
    svg_file = tmp_path / "workflow.svg"
    dot_file.write_text(graph.to_graphviz(), encoding="utf-8")

    result = graph.to_svg(str(dot_file), str(svg_file))
    assert "dot' command not found" in result or "Graphviz" in result
