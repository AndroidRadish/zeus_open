# Zeus - AI Project Evolution Operating System

[![Language](https://img.shields.io/badge/language-English%20%7C%20中文-blue)](README.zh-CN.md)
[![Workflow](https://img.shields.io/badge/workflow-init%E2%86%92brainstorm%E2%86%92plan%E2%86%92execute%E2%86%92feedback-green)](#workflow)
[![Adapter](https://img.shields.io/badge/adapter-universal-orange)](#universal-adapter)
[![Status](https://img.shields.io/badge/status-active-success)](#)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](#license)

Structured, version-aware AI delivery framework for long-running projects.

Zeus combines:
- deterministic planning artifacts (`spec`, `prd`, `task`, `roadmap`),
- wave-based execution with atomic commits,
- mandatory attribution loop from production feedback to roadmap evolution.

Language: [English](README.md) | [简体中文](README.zh-CN.md)

## Quick Start

### Claude Code Users

```bash
# 1) Install the commit message hook (one-time)
cp .zeus/hooks/commit-msg .git/hooks/commit-msg

# 2) Initialize the Zeus project workspace
/zeus:init

# Optional for brownfield repositories: map the existing codebase first
/zeus:discover --depth auto

# 3) Build the first design spec
/zeus:brainstorm --full

# 4) Convert approved spec to executable artifacts
/zeus:plan

# 5) Run pending tasks in dependency waves
/zeus:execute
```

### Universal AI Users (Kimi / GLM / DeepSeek / GPT / Gemini)

These platforms do not have the `claude` CLI or `/zeus:*` skill routing. Use `zeus_runner.py` instead:

```bash
# 1) Install the commit-msg hook (Bash)
cp .zeus/hooks/commit-msg .git/hooks/commit-msg

# Windows PowerShell users: see docs/init-harness.md

# 2) Check project status
python .zeus/scripts/zeus_runner.py --status

# 3) Run current wave (runner prints task prompts; you complete them in your AI session)
python .zeus/scripts/zeus_runner.py

# 4) View execution plan
python .zeus/scripts/zeus_runner.py --plan
```

#### v2 Parallel Mode with Web Dashboard

For parallel wave execution and a visual dashboard, start the v2 backend and open the zero-build Web UI:

```bash
# Start server (optionally point to a project directory)
python .zeus/v2/scripts/zeus_server.py --port 8234 --project-dir .

# Open dashboard
# http://localhost:8234/web
```

To enable true unattended execution, configure the subagent dispatcher in `.zeus/v2/config.json`:

```json
{
  "subagent": {
    "dispatcher": "auto",
    "timeout_seconds": 600
  }
}
```

See `skills/zeus-execute-v2.md` for full dispatcher options (`kimi`, `claude`, `mock`).

The `skills/` folder contains markdown playbooks for each workflow stage. Reference them directly in your AI session (e.g. "Please follow skills/zeus-init.md to initialize this project").

See [docs/open-agent-mapping.md](docs/open-agent-mapping.md) for platform-specific agent mappings.

## What's New in v2

- **Zero-build Web Dashboard** — Vue 3 + Tailwind CSS, dark industrial glassmorphism UI, fully in Chinese.
- **Phase Layer** — group milestones and waves into human-readable delivery phases (P-001, P-002…) with progress tracking.
- **Multi-language Support** — task titles and descriptions switch between English and Chinese with a single click.
- **Global Scheduler** 🚧 *In Progress* — dispatch tasks across wave boundaries based purely on dependency readiness.
- **Agent Collaboration** 🚧 *In Progress* — point-to-point Mailbox protocol so agents can communicate while executing.
- **Agent-centric Logs** 🚧 *In Progress* — per-agent isolated log directories for easier debugging and traceability.
- **Subagent Dispatcher** — delegates task execution to `kimi --print` or `claude -p` for true unattended multi-agent runs.
- **Interactive Workflow Graph** — powered by Vis-Network.js with drag, zoom, and hover tooltips.
- **Graphviz-free SVG Fallback** — `workflow_graph.py` renders dependency diagrams in pure Python when `dot` is unavailable.
- **Multi-version Switching** — switch between `main`, `v2`, and future versions directly in the Web UI.
- **Project Picker** — open and manage other local Zeus projects from the dashboard without restarting the server.

### Current Development Status

| Milestone | Status | Tasks |
|---|---|---|
| M-008 — Web UI & Multi-language | ✅ Completed | T-023 ~ T-025 |
| M-009 — Phase Layer | ✅ Completed | T-026 ~ T-029 |
| M-010 — Global Orchestrator & Agent Collaboration | 🚧 In Progress | **T-030** ✅ → **T-031** 🚧 → **T-032** 🚧 → **T-033** 🚧 → **T-034** 🚧 |

## Workflow

Zeus follows a deterministic, feedback-driven lifecycle:

```
init → discover → brainstorm → plan → execute → feedback → evolve
         ↑                                              |
         └──────────────────────────────────────────────┘
```

1. **init** — initialize north-star metrics and project config.
2. **discover** *(optional)* — map existing codebase for brownfield projects.
3. **brainstorm** — design specs and produce `.zeus/{version}/specs/*.md`.
4. **plan** — convert specs into executable stories, tasks, and roadmaps.
5. **execute** — run tasks in dependency-aware waves (v2 supports global scheduling and parallel agents).
6. **feedback** — capture production signals and attribute them to tasks.
7. **evolve** — create new version tracks (v2, v3…) based on validated learning.

> **Note:** The legacy SVG workflow diagrams have been retired. The above text diagram reflects the current universal workflow.

## Skill Commands

| Command | Purpose | Main Output |
|---|---|---|
| `/zeus:init` | Initialize Zeus workspace and north star metrics | `.zeus/main/config.json`, `evolution.md` |
| `/zeus:discover [--version v2] [--depth quick\|auto\|full]` | Map existing codebase and generate brownfield context artifacts | `codebase-map.json`, `existing-modules.json`, `tech-inventory.md`, `architecture.md` |
| `/zeus:brainstorm --full` | Full-scope design dialogue and spec authoring | `.zeus/main/specs/*.md` |
| `/zeus:brainstorm --feature <name>` | Single-feature design loop | feature spec |
| `/zeus:plan [--version v2]` | Convert spec to user stories and tasks | `prd.json`, `task.json`, `roadmap.json` |
| `/zeus:execute [--version v2]` | Execute pending tasks wave by wave (see `skills/zeus-execute-v2.md` for v2) | atomic commits, task pass states |
| `/zeus:test-gen [--version v2] [--platforms android,chrome,ios]` | AI-generate platform test flows from task/prd artifacts | `{version}/tests/*.test.json` |
| `/zeus:feedback` | Capture feedback and run attribution | `feedback/*.json`, evolution entry |
| `/zeus:evolve` | Create a new version branch/folder model | `.zeus/vN/*` |
| `/zeus:status` | Render global status report and next action | health snapshot + recommendation |

## Repository Layout

```text
.zeus/
  main/
    config.json
    prd.json
    task.json
    roadmap.json
    evolution.md
    feedback/
    ai-logs/
    specs/
    tests/
      android.test.json   ← AI-generated, do not edit manually
      chrome.test.json
      ios.test.json
  v2/ ... vN/
  schemas/
    config.schema.json
    codebase-map.schema.json
    existing-modules.schema.json
    prd.schema.json
    task.schema.json
    roadmap.schema.json
    spec.schema.json
    feedback.schema.json
    ai-log.schema.json
    test-flow.schema.json
  scripts/
    zeus_runner.py
    generate_tests.py
    collect_metrics.py
  hooks/
    commit-msg
    commit-msg.ps1

.claude/
  skills/zeus-*/SKILL.md
  agents/*.md

assets/
  zeus-workflow.en.svg
  zeus-workflow.zh-CN.svg
```

## v2 Dashboard

Zeus v2 provides a zero-build Web UI served by `zeus_server.py` (FastAPI):

- **Dashboard** — real-time wave progress, pending/completed stats, and task validation status.
- **Phases** — milestone-centric delivery batches with phase-aware wave filtering.
- **Agent Monitor** — shows currently running agents and their assigned tasks.
- **Global Execution** 🚧 — cross-wave running task list and quarantine zone for failures.
- **Agent Collaboration** 🚧 — live message stream between agents via the Mailbox protocol.
- **Agent Logs** 🚧 — per-agent isolated log browser (`activity.md`, `reasoning.jsonl`).
- **Discussion Log** — per-wave markdown discussion logs with lightweight rendering.
- **Dependency Graph** — interactive Vis-Network graph with color-coded task status; falls back to a pure-Python SVG renderer when Graphviz is not installed.
- **Version Switcher** — automatically discovers all `.zeus/{version}/task.json` folders.
- **Open Project** — switch to another Zeus project directory on the fly via the UI.

Start the server:

```bash
python .zeus/v2/scripts/zeus_server.py --port 8234 --project-dir .
```

Then visit `http://localhost:8234/web`.

For a GUI-focused quick-start guide, see [`docs/zeus-v2-gui-quickstart.md`](docs/zeus-v2-gui-quickstart.md).

## Brownfield Adoption

For existing repositories, run this path:

```bash
# 1) Build codebase context artifacts
/zeus:discover --version main --depth auto

# 2) Initialize config using discovered context
/zeus:init --import-existing --version main

# 3) Design and plan a scoped feature against existing modules
/zeus:brainstorm --feature <name> --version main
/zeus:plan --version main

# 4) Execute with wave gates
/zeus:execute --version main
```

This keeps Zeus backward-compatible for greenfield projects while adding safe brownfield onboarding.

## Agent Model

Zeus uses phase-specific agents under `.claude/agents`:

- `zeus-researcher`: context discovery and dependency checks
- `zeus-planner`: spec decomposition and artifact shaping
- `zeus-executor`: wave execution orchestration with quality gates
- `zeus-analyst`: attribution confidence and evolution decisions
- `zeus-docs`: bilingual consistency and docs quality checks
- `zeus-tester`: AI test case authoring for android / chrome / ios platforms

Skills should delegate intentionally:
- brainstorming -> researcher
- plan -> planner
- execute -> executor
- test generation -> tester (via `generate_tests.py`)
- feedback/evolve -> analyst
- docs quality checks -> docs

## Testing

Zeus uses AI-generated test flows. **Do not write test cases manually.**

```bash
# Generate test flows for all platforms (after zeus:plan)
python .zeus/scripts/generate_tests.py --version main --platforms android,chrome,ios

# Or via skill
/zeus:test-gen

# Target a single platform
/zeus:test-gen --platforms chrome

# Regenerate (overwrite existing)
python .zeus/scripts/generate_tests.py --version main --force
```

Generated files live at `.zeus/{version}/tests/{platform}.test.json` and conform to `.zeus/schemas/test-flow.schema.json`.

Test execution uses the native platform toolchain directly:

| Platform | Toolchain |
|---|---|
| Android | `adb shell` |
| Chrome | `chrome-cli` / Chrome DevTools Protocol |
| iOS | `xcrun simctl` / `libimobiledevice` |

Test flows are regenerated automatically when `/zeus:test-gen` is invoked, and optionally after each execution wave completes.

## AI Log Contract

Each skill execution must append one markdown log in `ai-logs/`:

```markdown
## Decision Rationale
Why this approach was selected.

## Execution Summary
What changed and where.

## Target Impact
Expected impact on the north star metric.
```

## Commit Convention

```text
feat(T-003): implement user registration form
fix(T-007): correct session token expiry
docs(zeus): update prd from auth-design spec
chore(zeus): initialize v2 evolution
```

## Troubleshooting

- If `/zeus:*` commands are not discovered, restart your AI runtime session.
- If execution stalls, verify `python .zeus/scripts/zeus_runner.py --status` works.
- If task updates fail, check JSON validity in `.zeus/*/task.json`.
- If commit hook fails, re-copy `.zeus/hooks/commit-msg` into `.git/hooks/`.
- On Windows, if the bash hook fails, use `.zeus/hooks/commit-msg.ps1` instead (see `docs/init-harness.md`).

## Contributing

1. Keep prompt specs deterministic and artifact-driven.
2. Keep shell snippets in English only.
3. Preserve backward compatibility for core `.zeus` schema files.
4. Add docs updates for any workflow changes.

## Acknowledgements / 友链

- [LINUX DO](https://linux.do/) — 开源社区支持

## Contact / 交流群

<p align="center">
  <img src="assets/image.png" alt="交流群" width="300" />
</p>

## License

MIT License — see [LICENSE](LICENSE).
