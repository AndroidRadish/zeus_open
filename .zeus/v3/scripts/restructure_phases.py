"""
Restructure v3 Phase/Milestone from 3 Phase/3 Milestone to 4 Phase/8 Milestone.
Direct SQLite operation — no runtime dependencies on async store.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def main() -> None:
    db_path = Path(".zeus/v3/state.db")
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    # Backup
    backup_path = db_path.with_suffix(".db.backup.restructure")
    backup_path.write_bytes(db_path.read_bytes())
    print(f"Backup created: {backup_path}")

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    # ------------------------------------------------------------------
    # 1. Delete old phases and milestones
    # ------------------------------------------------------------------
    c.execute("DELETE FROM phase")
    c.execute("DELETE FROM milestone")
    print("Deleted old phases and milestones.")

    # ------------------------------------------------------------------
    # 2. Insert new phases
    # ------------------------------------------------------------------
    phases = [
        {
            "id": "P-V3-001",
            "title": "Foundation",
            "title_en": "Foundation",
            "title_zh": "基础架构",
            "summary": "Observable sub-agent execution",
            "summary_en": "Observable sub-agent execution",
            "summary_zh": "子 Agent 执行可观测化",
            "status": "completed",
            "progress_percent": 100,
            "milestone_ids": json.dumps(["M-V3-001"]),
            "wave_start": 1,
            "wave_end": 3,
            "extra": None,
        },
        {
            "id": "P-V3-002",
            "title": "Dashboard & Observability",
            "title_en": "Dashboard & Observability",
            "title_zh": "仪表盘与可观测性",
            "summary": "Dashboard experience, interactivity and visualization",
            "summary_en": "Dashboard experience, interactivity and visualization",
            "summary_zh": "Dashboard 体验、交互与可视化",
            "status": "completed",
            "progress_percent": 100,
            "milestone_ids": json.dumps(["M-V3-002", "M-V3-003", "M-V3-004"]),
            "wave_start": 2,
            "wave_end": 11,
            "extra": None,
        },
        {
            "id": "P-V3-003",
            "title": "Infrastructure",
            "title_en": "Infrastructure",
            "title_zh": "基础设施",
            "summary": "Persistence and containerization hardening",
            "summary_en": "Persistence and containerization hardening",
            "summary_zh": "持久化与容器化加固",
            "status": "completed",
            "progress_percent": 100,
            "milestone_ids": json.dumps(["M-V3-005", "M-V3-006"]),
            "wave_start": 12,
            "wave_end": 14,
            "extra": None,
        },
        {
            "id": "P-V3-004",
            "title": "Quality & Standards",
            "title_en": "Quality & Standards",
            "title_zh": "质量与规范",
            "summary": "Code cleanup, docs and engineering standards",
            "summary_en": "Code cleanup, docs and engineering standards",
            "summary_zh": "代码清理、文档与工程规范",
            "status": "completed",
            "progress_percent": 100,
            "milestone_ids": json.dumps(["M-V3-007", "M-V3-008"]),
            "wave_start": 15,
            "wave_end": 17,
            "extra": None,
        },
    ]

    for p in phases:
        c.execute(
            """
            INSERT INTO phase (id, title, title_en, title_zh, summary, summary_en, summary_zh,
                               status, progress_percent, milestone_ids, wave_start, wave_end, extra)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                p["id"], p["title"], p["title_en"], p["title_zh"],
                p["summary"], p["summary_en"], p["summary_zh"],
                p["status"], p["progress_percent"], p["milestone_ids"],
                p["wave_start"], p["wave_end"], p["extra"],
            ),
        )
    print(f"Inserted {len(phases)} phases.")

    # ------------------------------------------------------------------
    # 3. Insert new milestones
    # ------------------------------------------------------------------
    milestones = [
        {
            "id": "M-V3-001",
            "title": "Core Execution",
            "task_ids": json.dumps(["T-V3-001", "T-V3-003"]),
            "status": "completed",
            "progress_percent": 100,
            "spec_ref": None,
            "story_ids": json.dumps(["US-V3-001", "US-V3-003"]),
            "extra": None,
        },
        {
            "id": "M-V3-002",
            "title": "Dashboard Core",
            "task_ids": json.dumps(["T-V3-002", "T-V3-015", "T-V3-021"]),
            "status": "completed",
            "progress_percent": 100,
            "spec_ref": None,
            "story_ids": json.dumps(["US-V3-002", "US-V3-005", "US-V3-008"]),
            "extra": None,
        },
        {
            "id": "M-V3-003",
            "title": "Dashboard Interactivity",
            "task_ids": json.dumps(["T-V3-018", "T-V3-019", "T-V3-026"]),
            "status": "completed",
            "progress_percent": 100,
            "spec_ref": None,
            "story_ids": json.dumps(["US-V3-006", "US-V3-007", "US-V3-008"]),
            "extra": None,
        },
        {
            "id": "M-V3-004",
            "title": "Visualization",
            "task_ids": json.dumps(["T-V3-030", "T-V3-031"]),
            "status": "completed",
            "progress_percent": 100,
            "spec_ref": None,
            "story_ids": json.dumps(["US-V3-012"]),
            "extra": None,
        },
        {
            "id": "M-V3-005",
            "title": "Persistence",
            "task_ids": json.dumps(["T-V3-022"]),
            "status": "completed",
            "progress_percent": 100,
            "spec_ref": None,
            "story_ids": json.dumps(["US-V3-009"]),
            "extra": None,
        },
        {
            "id": "M-V3-006",
            "title": "Containerization",
            "task_ids": json.dumps(["T-V3-023", "T-V3-024"]),
            "status": "completed",
            "progress_percent": 100,
            "spec_ref": None,
            "story_ids": json.dumps(["US-V3-010"]),
            "extra": None,
        },
        {
            "id": "M-V3-007",
            "title": "Cleanup & Docs",
            "task_ids": json.dumps(["T-V3-027", "T-V3-028"]),
            "status": "completed",
            "progress_percent": 100,
            "spec_ref": None,
            "story_ids": json.dumps(["US-V3-011"]),
            "extra": None,
        },
        {
            "id": "M-V3-008",
            "title": "Engineering Standards",
            "task_ids": json.dumps(["T-V3-029", "T-V3-032"]),
            "status": "completed",
            "progress_percent": 100,
            "spec_ref": None,
            "story_ids": json.dumps(["US-V3-012"]),
            "extra": None,
        },
    ]

    for m in milestones:
        c.execute(
            """
            INSERT INTO milestone (id, title, task_ids, status, progress_percent, spec_ref, story_ids, extra)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                m["id"], m["title"], m["task_ids"], m["status"],
                m["progress_percent"], m["spec_ref"], m["story_ids"], m["extra"],
            ),
        )
    print(f"Inserted {len(milestones)} milestones.")

    # ------------------------------------------------------------------
    # 4. Update task_state milestone_id
    # ------------------------------------------------------------------
    task_to_ms = {
        "T-V3-001": "M-V3-001",
        "T-V3-003": "M-V3-001",
        "T-V3-002": "M-V3-002",
        "T-V3-015": "M-V3-002",
        "T-V3-021": "M-V3-002",
        "T-V3-018": "M-V3-003",
        "T-V3-019": "M-V3-003",
        "T-V3-026": "M-V3-003",
        "T-V3-030": "M-V3-004",
        "T-V3-031": "M-V3-004",
        "T-V3-022": "M-V3-005",
        "T-V3-023": "M-V3-006",
        "T-V3-024": "M-V3-006",
        "T-V3-027": "M-V3-007",
        "T-V3-028": "M-V3-007",
        "T-V3-029": "M-V3-008",
        "T-V3-032": "M-V3-008",
    }

    for tid, mid in task_to_ms.items():
        c.execute("UPDATE task_state SET milestone_id = ? WHERE id = ?", (mid, tid))

    updated = conn.total_changes - len(phases) - len(milestones)
    print(f"Updated {updated} task_state rows with new milestone_id.")

    conn.commit()
    conn.close()
    print("Restructure complete.")


if __name__ == "__main__":
    main()
