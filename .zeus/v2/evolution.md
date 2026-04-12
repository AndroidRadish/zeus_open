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
- **North star impact**: multi_agent_efficiency ↑↑, developer_adoption_rate ↑
