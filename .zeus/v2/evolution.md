# Evolution Log — zeus-open v2

## INIT — 2026-04-10

- **Event**: Evolve to v2 for multi-agent parallel execution and GUI management
- **Project**: zeus-open
- **Version**: v2
- **Inherits**: main
- **Overrides**:
  - Parallel agent orchestration
  - GUI dashboard for wave/task monitoring
  - Agent communication bus / shared workspace
- **North star**: developer_adoption_rate
- **Notes**: This version transforms zeus-open from a single-wave manual runner into an async multi-agent orchestrator with visual management.

---

## PLAN — 2026-04-12

- **Event**: Plan v2 enhancement for adaptive wave rescheduling
- **Direction B Step 1**: Dynamic Agent Orchestration — Adaptive Wave Rescheduling
- **Deferred Step 2**: Auto-heal (zeus-fixer agent) moved to future backlog pending observability maturity
- **Rationale**:
  - Wave rescheduling directly attacks slot-waste in v2 orchestrator with low risk.
  - Auto-heal introduces code-drift and opacity risks; will be specced after T-011~T-014 ship.
- **New Artifacts**:
  - Spec: `.zeus/v2/specs/2026-04-12-adaptive-wave-rescheduling.md`
  - Roadmap: M-005 added with T-011 ~ T-014
  - PRD: US-005 added
- **North star impact**: multi_agent_adoption_rate ↑↑, developer_adoption_rate ↑

---

## SHIP — 2026-04-12

- **Event**: Complete M-005 — Adaptive Wave Rescheduling
- **Tasks completed**: T-011, T-012, T-013, T-014
- **Status**: All tests pass (35/35)
- **Key deliverables**:
  - `task.json` schema extended with `original_wave`, `scheduled_wave`, `rescheduled_from`
  - `store.py` batch update helper (`update_json_fields`)
  - `zeus_orchestrator.py` dynamic priority-queue scheduling loop with `lookahead_waves`
  - Web UI rescheduled-task badges and wave-progress corrections
  - Full test coverage for adaptive behavior, state consistency, and backward compatibility
- **Next milestone**: Backlog — Auto-heal (Step 2) remains deferred until further human decision

---

## SHIP — 2026-04-12

- **Event**: Complete M-009 — Phase Layer (Delivery Batch Management)
- **Tasks completed**: T-026, T-027, T-028, T-029
- **Status**: All v2 tests pass (53/53)
- **Key deliverables**:
  - `roadmap.json` now supports a `phases` array with title, summary, milestone_ids, and wave_range
  - `GET /phases` endpoint returns phases with computed status, progress_percent, and nested milestones
  - Web UI "Phases" tab displays summary-bearing phase cards with expandable milestone lists
  - Dashboard wave selector upgraded to a phase-aware "Phase → Wave"联动 selector
  - Header shows current phase badge (e.g. `P-002 智能与完善`)
  - `task.json` meta tracks `current_phase` automatically from wave position
  - Full test coverage for `/phases` and phase status calculation
  - Documentation updated in `skills/zeus-execute-v2.md`
- **Next milestone**: Backlog — Auto-heal (Step 2) remains deferred until further human decision

---

## PLAN — 2026-04-12 (Global Orchestrator & Agent Collaboration)

- **Event**: Plan a new milestone that breaks wave execution locks while keeping wave as a planning/observation view, and enables real-time agent collaboration with per-agent traceability
- **Objective**: 
  - Introduce `GlobalScheduler` to dispatch tasks by global dependency readiness across wave boundaries
  - Add a `quarantine` zone for failed tasks so they do not block unrelated downstream work
  - Extend `agent_bus.py` with a Mailbox protocol for point-to-point agent messaging
  - Restructure `agent-logs` from wave-centric to agent-centric directories
  - Update Web UI with Global Execution, Agent Collaboration, and per-agent log browser views
- **New Artifacts**:
  - Spec: `.zeus/v2/specs/2026-04-12-global-orchestrator-agent-collaboration.md`
  - Roadmap: M-010 added with T-030 ~ T-034
  - PRD: US-010 added
- **North star impact**: `multi_agent_efficiency` ↑↑↑, `developer_adoption_rate` ↑↑, `observability` ↑↑
- **Status**: Awaiting execution after M-009 (Phase Layer) ships

---

## PLAN — 2026-04-12 (Phase Layer)

- **Event**: Brainstorm and plan a Phase layer above Milestone to solve wave-number inflation
- **Objective**: Group milestones and waves into named delivery batches (P-001, P-002…) with human-readable summaries
- **New Artifacts**:
  - Spec: `.zeus/v2/specs/2026-04-12-phase-layer-design.md`
  - Roadmap: M-009 planned with T-026 ~ T-029
  - PRD: US-009 added
- **North star impact**: `developer_adoption_rate` ↑↑ (humans can reason in phases instead of raw wave numbers), `ui_usability` ↑↑ (scalable navigation for long-running projects)
- **Status**: Awaiting human approval before implementation

---

## SHIP — 2026-04-12

- **Event**: Complete M-008 — Web UI Improvements & Multi-language Support
- **Tasks completed**: T-023, T-024, T-025
- **Status**: All v2 tests pass (51/51)
- **Key deliverables**:
  - New `/milestones` API endpoint and Web UI "Milestones" tab for milestone-centric progress reading
  - Task schema extended with optional `title_en`, `title_zh`, `description_en`, `description_zh`
  - Web UI language toggle (中 / EN) with `getLocalized` helper and graceful fallback
  - All 25 v2 tasks seeded with bilingual titles; descriptions localized where present
  - Documentation updated in `skills/zeus-execute-v2.md`
- **Next milestone**: Backlog — Auto-heal (Step 2) remains deferred until further human decision

---

## PLAN — 2026-04-12 (Web UI Improvements & Multi-language Support)

- **Event**: Address wave-based UI redundancy and finally ship task i18n (EN/ZH)
- **Objective**: Add a Milestones-centric view for smooth human reading; extend task schema and UI for bilingual task metadata
- **New Artifacts**:
  - Spec: `.zeus/v2/specs/2026-04-12-web-ui-improvements.md`
  - Roadmap: M-008 added with T-023 ~ T-025
  - PRD: US-008 added
- **North star impact**: `developer_adoption_rate` ↑↑ (better UX for non-native speakers), `ui_usability` ↑↑ (milestone view removes wave-switching friction)

---

## PLAN — 2026-04-12 (Subagent Dispatcher)

- **Event**: Plan subagent dispatcher integration after discovering `kimi --print` and `claude -p` support
- **Objective**: Turn `dispatch_task` from a mock into a true unattended subagent runner
- **Platforms**: Kimi CLI (`kimi --print`), Claude Code (`claude`), Mock fallback
- **New Artifacts**:
  - Spec: `.zeus/v2/specs/2026-04-12-subagent-dispatcher.md`
  - Roadmap: M-006 added with T-015 ~ T-019
  - PRD: US-006 added
- **North star impact**: developer_adoption_rate ↑↑↑, multi_agent_efficiency ↑↑

---

## SHIP — 2026-04-12

- **Event**: Complete M-006 — Subagent Dispatcher Integration
- **Tasks completed**: T-015, T-016, T-017, T-018, T-019
- **Status**: All v2 tests pass (48/48)
- **Key deliverables**:
  - `subagent_dispatcher.py` with ABC + Mock + Kimi + Claude + Auto implementations
  - `zeus_orchestrator.py` refactored to delegate execution via dispatcher abstraction
  - Stdout capture, timeout handling, and uniform Agent Bus event reporting for all CLI backends
  - Web UI Agent Monitor now shows both "running" and "recent activity" panels
  - Documentation updated in README and `zeus-execute-v2.md`
- **Fixes shipped alongside**:
  - Dashboard Wave selector for historical wave inspection
  - Automatic discussion log writes on task start / completion / failure
- **Next milestone**: Backlog — Auto-heal (Step 2) remains deferred

---

## PLAN — 2026-04-12 (Subagent Workspace Bootstrap)

- **Event**: Plan workspace identity injection so subagents start with full context
- **Objective**: Copy AGENTS.md, USER.md, IDENTITY.md, and SOUL.md into every agent workspace automatically
- **New Artifacts**:
  - Spec: `.zeus/v2/specs/2026-04-12-subagent-workspace-bootstrap.md`
  - Roadmap: M-007 added with T-020 ~ T-022
  - PRD: US-007 added
- **North star impact**: `developer_adoption_rate` ↑↑ (subagents are immediately useful), `multi_agent_efficiency` ↑ (less human copy-paste)

---

## SHIP — 2026-04-12

- **Event**: Complete M-007 — Subagent Workspace Bootstrap
- **Tasks completed**: T-020, T-021, T-022
- **Status**: All v2 tests pass (50/50)
- **Key deliverables**:
  - `zeus_orchestrator.py` auto-copies identity/context files into every agent workspace before dispatch
  - `config.json` supports optional `subagent.bootstrap.files` override
  - `task.bootstrapped` event emitted for observability
  - Full test coverage for default behavior and config override
  - Documentation updated in `skills/zeus-execute-v2.md`
- **Next milestone**: Backlog — Auto-heal (Step 2) remains deferred until further human decision
