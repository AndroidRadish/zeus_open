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

Zeus works with **any AI platform** (Kimi, DeepSeek, GPT, Claude, GLM, Gemini). No special CLI or slash commands required — just talk to your AI in natural language.

### 1) One-time setup

```bash
# Install the commit message hook
cp .zeus/hooks/commit-msg .git/hooks/commit-msg
# Windows: see docs/init-harness.md for PowerShell hook
```

### 2) Start the conversation

Tell your AI what you want to do. Examples:

| You say | Zeus does |
|---|---|
| "Initialize this project" | Creates `.zeus/main/config.json`, sets north-star metrics |
| "Show me the status" | Reports completed / pending / running tasks |
| "Map the existing codebase" | Generates `codebase-map.json` for brownfield projects |
| "Design the auth module" | Writes a spec to `.zeus/main/specs/auth.md` |
| "Plan the next wave" | Converts spec into stories, tasks, and dependency waves |
| "Run pending tasks" | Executes current wave, one task at a time |
| "Generate tests for android" | Creates platform test flow JSON |

The AI reads `.zeus/ZEUS_AGENT.md` to learn the Zeus protocol and handles the rest.

### 3) For scripted / CI usage

```bash
# Check status
python .zeus/scripts/zeus_runner.py --status

# View plan
python .zeus/scripts/zeus_runner.py --plan

# Execute current wave
python .zeus/scripts/zeus_runner.py

# Execute specific wave (v3)
python .zeus/v3/scripts/run.py --wave 2 --max-workers 3
```

#### v3 Multi-Agent Framework (Beta)

For the new database-backed, horizontally-scalable execution engine with real-time dashboard and Docker Compose support, see [`.zeus/v3/README.md`](.zeus/v3/README.md).

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

See `.zeus/v1/skills/zeus-execute-v2.md` for full dispatcher options (`kimi`, `claude`, `mock`).

The `.zeus/v1/skills/` folder contains archived markdown playbooks for each workflow stage. Reference them directly in your AI session (e.g. "Please follow .zeus/v1/skills/zeus-init.md to initialize this project").

See [docs/open-agent-mapping.md](docs/open-agent-mapping.md) for platform-specific agent mappings.

## What's New in v2

- **Zero-build Web Dashboard** — Vue 3 + Tailwind CSS, dark industrial glassmorphism UI, fully in Chinese.
- **Phase Layer** — group milestones and waves into human-readable delivery phases (P-001, P-002…) with progress tracking.
- **Multi-language Support** — task titles and descriptions switch between English and Chinese with a single click.
- **Global Scheduler** — dispatch tasks across wave boundaries based purely on dependency readiness, with a quarantine zone for failed tasks.
- **Agent Collaboration** — point-to-point Mailbox protocol so agents can communicate while executing.
- **Agent-centric Logs** — per-agent isolated log directories (`activity.md` + `reasoning.jsonl`) for easier debugging and traceability.
- **One-Click Global Run** — start the global scheduler directly from the Web UI.
- **Subagent Dispatcher** — delegates task execution to `kimi --print` or `claude -p` for true unattended multi-agent runs.
- **Multi-version Switching** — switch between `main`, `v2`, and future versions directly in the Web UI.
- **Project Picker** — open and manage other local Zeus projects from the dashboard without restarting the server.

### What's New in v3 (Beta)

- **Database-centric state** — SQLite/PostgreSQL backed task state with async SQLAlchemy
- **Queue-Worker separation** — horizontally-scalable scheduler + worker pool architecture
- **Vite + Vue 3 Dashboard** — componentized SPA with Pinia state management and SSE real-time updates
- **Metrics & Observability** — bottleneck detection, blocked chain analysis, and OpenTelemetry tracing
- **Hot Reload** — runtime `task.json` re-import without server restart
- **Docker & K8s Ready** — split `api` / `scheduler` / `worker` containers with Redis queue backend
- **Wave-level Filtering** — `run.py --wave N` and `zeus_runner.py --wave N` to execute only tasks in a specific wave
- **Workspace Performance** — heavy directories (`node_modules`, `.pytest_cache`, `venv`, etc.) are now excluded from workspace copytree, cutting prepare time from seconds to milliseconds
- **High-concurrency Planning Templates** — `.zeus/v3/templates/high-concurrency-task-plan.json` provides a reference DAG for maximizing worker parallelism (≥2 independent tasks per wave)

See [`.zeus/v3/README.md`](.zeus/v3/README.md) for the v3 quick-start guide.

### Current Development Status

| Milestone | Status | Tasks |
|---|---|---|
| M-008 — Web UI & Multi-language | ✅ Completed | T-023 ~ T-025 |
| M-009 — Phase Layer | ✅ Completed | T-026 ~ T-029 |
| M-010 — Global Orchestrator & Agent Collaboration | ✅ Completed | T-030 ~ T-034 |
| v3 Phase 1 — Foundation & Queue-Worker | ✅ Completed | T-V3-001 ~ T-V3-003 |
| v3 Phase 2 — Real-time Dashboard & Control Plane | ✅ Completed | T-V3-015, T-V3-018, T-V3-019, T-V3-021, T-V3-026 |
| v3 Phase 3 — Performance & Planning | ✅ Completed | T-V3-034 ~ T-V3-036 |

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

## Natural Language Intents

No slash commands needed. Just tell your AI what you want.

| Intent | Example phrases | What happens |
|---|---|---|
| **init** | "Initialize this project", "Setup Zeus", "开始吧" | Creates config, north-star metrics, evolution baseline |
| **status** | "What's the status?", "看看进度", "到哪了" | Reports task completion, pending queue, next action |
| **discover** | "Map the codebase", "扫一下现有代码", "Brownfield check" | Generates codebase-map and module inventory |
| **brainstorm** | "Design the auth flow", "写个 spec", "Brainstorm payments" | Writes structured spec to `.zeus/{version}/specs/` |
| **plan** | "Plan the next wave", "拆一下任务", "Convert spec to tasks" | Creates stories, tasks, wave DAG, writes `task.json` |
| **execute** | "Run pending tasks", "执行当前 wave", "Start working" | Runs scheduler + worker pool, executes task prompts |
| **execute-one** | "Run T-001 only", "只做这个 task" | Executes a single task by ID |
| **test-gen** | "Generate tests", "写安卓测试" | Creates platform test flow JSON files |
| **feedback** | "Login is slow", "用户反馈", "Record production issue" | Attributes signals to tasks, updates evolution |
| **evolve** | "Create v3", "版本演进", "Start next phase" | Spins up new version track, migrates tasks |

The AI uses `.zeus/ZEUS_AGENT.md` as its instruction manual. It knows which scripts to call and what files to write.

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
  v1/                    ← archived v1-era artifacts
    skills/              ← skill playbooks (moved from root)
    scripts/             ← utility scripts
    docs/
    logs/
  v2/ ... vN/
  v3/
    templates/           ← high-concurrency task planning templates
    scripts/
    web/
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

assets/
  zeus-workflow.en.svg
  zeus-workflow.zh-CN.svg
```

## v3 Dashboard

Zeus v3 provides a Vite + Vue 3 dashboard served by the built-in FastAPI server:

- **Overview** — live metrics, task list, and real-time SSE event stream
- **Tasks** — inline actions (Retry / Cancel / Pause / Resume / Quarantine / Logs / Detail)
- **Task Detail Drawer** — slide-out panel with full fields, dependencies, and activity logs
- **Events** — searchable real-time SSE event history with progress highlights
- **Metrics** — bottleneck analysis, blocked dependency chains, per-task duration stats
- **Graph** — task dependency graph (SVG / Mermaid / ECharts)
- **Phases** — phase & milestone CRUD with drill-down to task lists
- **Mailbox** — AgentBus point-to-point message inbox with send form
- **Control** — scheduler / worker management and one-click global run
- **Hot Reload** — auto re-imports `task.json` changes in `serve` mode

Start the server:

```bash
python .zeus/v3/scripts/run.py --mode serve --project-root . --host 0.0.0.0 --port 8000
```

Then visit `http://127.0.0.1:8000/dashboard`.

For the full v3 guide, see [`.zeus/v3/README.md`](.zeus/v3/README.md).

## v2 Dashboard

Zeus v2 provides a zero-build Web UI served by `zeus_server.py` (FastAPI):

- **Dashboard** — real-time wave progress, pending/completed stats, and task validation status.
- **Phases** — milestone-centric delivery batches with phase-aware wave filtering.
- **Milestones** — expandable milestone cards with task lists and progress bars.
- **Global Execution** — cross-wave running task list, pending queue, quarantine zone, and one-click scheduler launch.
- **Agent Collaboration** — live message stream between agents via the Mailbox protocol.
- **Agent Logs** — per-agent isolated log browser (`activity.md`, `reasoning.jsonl`).
- **Version Switcher** — automatically discovers all `.zeus/{version}/task.json` folders.
- **Open Project** — switch to another Zeus project directory on the fly via the UI.

Start the server:

```bash
python .zeus/v2/scripts/zeus_server.py --port 8234 --project-dir .
```

Then visit `http://localhost:8234/web`.

For a GUI-focused quick-start guide, see [`docs/zeus-v2-gui-quickstart.md`](docs/zeus-v2-gui-quickstart.md).

## Deployment

### One-click start scripts

```bash
# Linux / macOS (native Python)
./start.sh --port 8234

# Windows (native Python)
.\start.ps1 -Port 8234

# Docker build & run (any platform)
./start.sh --build
.\start.ps1 -Build
```

### Docker (manual)

```bash
# Build image
docker build -t zeus-open:v2 .

# Run container
docker run --rm -p 8234:8234 -v $(pwd):/app zeus-open:v2
```

The container exposes port `8234` and mounts the current directory so that `.zeus/v2/task.json` and project files remain editable on the host.

## Brownfield Adoption

For existing repositories, tell your AI:

> "Map the codebase and initialize Zeus using what you find."

The AI will:
1. Run **discover** to scan your code and generate `codebase-map.json`
2. Run **init** with discovered context pre-filled
3. Ask you to confirm or override inferred values
4. Then proceed to **brainstorm** → **plan** → **execute**

Or step-by-step:
```bash
# Discover
"Scan the project structure and create a codebase map"

# Init
"Initialize Zeus with the discovered context"

# Brainstorm + Plan
"Design the auth module and plan the tasks"

# Execute
"Run the planned tasks"
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

Tell your AI:
> "Generate tests for android, chrome, and ios"

Or run directly:
```bash
# All platforms
python .zeus/scripts/generate_tests.py --version main --platforms android,chrome,ios

# Single platform
python .zeus/scripts/generate_tests.py --version main --platforms chrome

# Force regenerate
python .zeus/scripts/generate_tests.py --version main --force
```

Generated files live at `.zeus/{version}/tests/{platform}.test.json` and conform to `.zeus/schemas/test-flow.schema.json`.

Test execution uses the native platform toolchain directly:

| Platform | Toolchain |
|---|---|
| Android | `adb shell` |
| Chrome | `chrome-cli` / Chrome DevTools Protocol |
| iOS | `xcrun simctl` / `libimobiledevice` |

Test flows are regenerated when you ask your AI to generate them, or optionally after each execution wave completes.

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

- If the AI doesn't recognize Zeus workflows, point it to `.zeus/ZEUS_AGENT.md`.
- If execution stalls, verify `python .zeus/scripts/zeus_runner.py --status` works.
- If task updates fail, check JSON validity in `.zeus/*/task.json` (v2) or DB state (v3).
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
