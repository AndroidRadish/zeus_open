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
