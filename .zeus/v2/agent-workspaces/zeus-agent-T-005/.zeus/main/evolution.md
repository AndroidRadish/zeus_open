# Evolution Log — zeus-open

## INIT — 2026-04-08

- **Event**: Initialize zeus-open (universal AI-CLI adapter for Zeus)
- **Project**: zeus-open
- **North star**: adoption_rate
- **Weights**:
  - adoption_rate: 0.5
  - cross_platform_coverage: 0.3
  - documentation_completeness: 0.2
- **Stack snapshot**: Python 3, JSON Schema, Markdown
- **Notes**: Forked from zeus-main to provide a claude-CLI-free experience for Kimi, GLM, DeepSeek, GPT, and Gemini users.

---

## FEATURE — 2026-04-09

- **Event**: Complete universal AI-CLI adapter core (T-002 ~ T-006)
- **Project**: zeus-open
- **Version**: main
- **Deliverables**:
  - `generate_tests.py` replaces `generate-tests.sh` (no claude/jq dependency)
  - `collect_metrics.py` replaces `collect-metrics.sh` (cross-platform Python)
  - `zeus_runner.py` gains JSON validation and dependency-cycle detection
  - Added missing `assets/` (workflow SVGs and community image)
  - Aligned all README/skills/docs references to Python scripts
  - Added `.gitignore` for generated metrics and `__pycache__`
- **North star impact**: adoption_rate ↑ (lower barrier for Windows/non-bash users), cross_platform_coverage ↑, documentation_completeness ↑
- **Notes**: Development was driven by Harness Engineering workflow; Harness scaffolding will be removed before final release.

---

## EVOLVE — 2026-04-10

- **Event**: Split v2 track for multi-agent parallel execution and GUI management
- **Version**: v2
- **Rationale**: Core framework (main) is complete. Structural features (parallel orchestration, GUI dashboard, agent communication bus) require a new version track.
- **Next**: zeus:brainstorm --full on v2 architecture.

