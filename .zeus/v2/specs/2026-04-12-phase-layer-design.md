# v2 Phase Layer Design Spec

> **Project**: zeus-open v2 enhancement  
> **Topic**: Introduce Phase (delivery batch) layer above Milestone to manage wave proliferation  
> **North Star Impact**: `developer_adoption_rate` ↑↑, `ui_usability` ↑↑  

---

## 1. Problem Statement

### 1.1 Wave-number inflation breaks readability
As a long-running project evolves, wave count inevitably grows (20, 50, 100+). The current Dashboard forces users to pick a raw integer from a dropdown. Humans do not reason in raw wave numbers; they reason in **delivery batches** such as "Foundation", "Alpha", "GA".

### 1.2 Milestone is the wrong granularity for narrative
Milestones (M-001 ~ M-008) group tasks by **functional module** (Infrastructure, Core Engine, UI…). They do not answer the question: *"What is the current big push?"* For example, M-001~M-004 together constitute the "v2 Foundation" push, while M-005~M-008 constitute the "v2 Intelligence & Polish" push. A higher-level container is needed.

## 2. Objectives

- Provide a **Phase-centric** view of progress that groups consecutive milestones and waves into named, summary-bearing delivery batches.
- Make the Web UI scalable: a user on wave 47 should still know which Phase they are in without mental arithmetic.
- Preserve backward compatibility: waves and milestones continue to work exactly as before.

## 3. Guiding Principles

1. **Phases are narrative, not scheduling** — the orchestrator still dispatches by wave; phases are for human readability.
2. **Single source of truth** — phases live in `roadmap.json` because they are planning artifacts.
3. **Optional but discoverable** — if no phases are defined, the UI falls back to the current milestone-only view.
4. **Re-use i18n** — phases support `title_en/title_zh` and `summary_en/summary_zh` leveraging the existing M-008 infrastructure.

## 4. Architecture

### 4.1 Phase Data Model

```json
{
  "id": "P-001",
  "title": "v2 Foundation",
  "title_en": "v2 Foundation",
  "title_zh": "v2 基础架构",
  "summary": "Core storage, async orchestrator, FastAPI backend, Web dashboard, integration validation",
  "summary_en": "Core storage, async orchestrator, FastAPI backend, Web dashboard, integration validation",
  "summary_zh": "核心存储、异步调度器、FastAPI 后端、Web 仪表盘、集成验证",
  "milestone_ids": ["M-001", "M-002", "M-003", "M-004"],
  "wave_start": 1,
  "wave_end": 4,
  "target_date": "2026-04-10",
  "status": "completed"
}
```

`status` rules:
- `completed` — all linked milestones are completed
- `in_progress` — at least one milestone is in_progress or completed, but not all completed
- `pending` — no milestone has started

### 4.2 Roadmap.json Extension

```json
{
  "version": "v2",
  "phases": [
    { "id": "P-001", ... },
    { "id": "P-002", ... }
  ],
  "milestones": [ ... ]
}
```

If `phases` is absent, the UI behaves as today (M-008).

### 4.3 Task.json Extension (optional)

```json
{
  "meta": {
    "current_wave": 5,
    "current_phase": "P-002",
    "wave_approval_required": true
  }
}
```

`current_phase` is **read-only metadata** updated by the orchestrator or server whenever `current_wave` advances past `wave_end` of the previous phase.

### 4.4 API Additions

- `GET /phases?version=v2`
  - Returns phases with computed `status`, `progress_percent`, and nested `milestones`.
- `GET /status` (enhanced)
  - Optionally includes `current_phase` if configured.

### 4.5 Web UI Additions

1. **Dashboard Wave Selector → Phase-aware**
   - Dropdown 1: Phase (e.g. "P-001 v2 Foundation")
   - Dropdown 2: Wave within that phase (filtered)
2. **New "Phases" Tab**
   - Replaces or augments the Milestones tab.
   - Each phase is a large card with:
     - Phase title + status badge
     - One-sentence summary
     - Progress bar (aggregated from milestones)
     - Expandable list of milestones (each milestone further expandable to tasks)
3. **Header Badge**
   - Next to the wave badge, show the current phase pill: `P-002 智能与完善`.

## 5. Alternative Approaches Considered

### A. Wave semantic labels only
Allow arbitrary string labels on waves (e.g. `wave 5` → label "Subagent"). Rejected because labels are unstructured, cannot carry summaries, and do not span multiple waves naturally.

### B. Sprint/Release tracks
Bind every N waves to a hard release tag (e.g. `v2.0.0-alpha`). Rejected because it couples scheduling with release management prematurely; not all projects use semver releases.

### C. Milestone nesting (milestones inside milestones)
Rejected because it complicates the already-clear milestone definition and blurs the boundary between functional module and delivery batch.

## 6. Recommended Approach

**Adopt the full Phase layer (Section 4)**. The cost is low because:
- `roadmap.json` is the only new authoritative source.
- The existing Milestones tab (T-023) can be upgraded into a "Phases & Milestones" tab with ~60% code reuse.
- i18n helpers from T-024 apply directly to Phase titles/summaries.

## 7. Acceptance Criteria

- [ ] `roadmap.json` schema supports an optional `phases` array.
- [ ] `GET /phases` endpoint returns phases with progress and nested milestones.
- [ ] Web UI shows a "Phases" tab with summary-bearing phase cards.
- [ ] Dashboard wave selector is filtered by the selected phase.
- [ ] `task.json` optionally tracks `meta.current_phase`.
- [ ] All tests pass; new tests cover `/phases` and phase status calculation.
- [ ] Documentation (`zeus-execute-v2.md`) explains how to define phases in `roadmap.json`.

## 8. Task Breakdown

| Wave | Task | Description |
|------|------|-------------|
| 8 | T-026 | Extend `roadmap.json` schema with `phases`; add `GET /phases` endpoint; compute status/progress |
| 8 | T-027 | Update Web UI: add Phases tab, phase header badge, and phase-aware wave selector |
| 8 | T-028 | Seed phases P-001/P-002 for existing v2 data; update `task.json` meta with `current_phase` |
| 8 | T-029 | Add tests for `/phases`, phase status rules, and documentation |
