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

## PLAN — 2026-04-12 (Subagent Dispatcher)

- **Event**: Plan subagent dispatcher integration after discovering `kimi --print` and `claude -p` support
- **Objective**: Turn `dispatch_task` from a mock into a true unattended subagent runner
- **Platforms**: Kimi CLI (`kimi --print`), Claude Code (`claude`), Mock fallback
- **New Artifacts**:
  - Spec: `.zeus/v2/specs/2026-04-12-subagent-dispatcher.md`
  - Roadmap: M-006 added with T-015 ~ T-019
  - PRD: US-006 added
- **North star impact**: developer_adoption_rate ↑↑↑, multi_agent_efficiency ↑↑
