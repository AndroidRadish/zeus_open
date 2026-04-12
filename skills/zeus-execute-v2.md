# Zeus Execute v2 - Parallel Orchestration & Dashboard

Run pending tasks in parallel with dependency-aware wave orchestration, real-time status tracking, and an optional visual dashboard.

## Preconditions

- `.zeus/v2/task.json` exists and contains pending tasks.
- `.zeus/v2/config.json` exists.
- v2 scripts exist under `.zeus/v2/scripts/`.

## How to run (CLI)

```bash
# Print v2 status
python .zeus/v2/scripts/zeus_orchestrator.py --status

# Dispatch current wave
python .zeus/v2/scripts/zeus_orchestrator.py --wave 1

# Approve next wave
python .zeus/v2/scripts/zeus_orchestrator.py --approve-next
```

## Subagent Dispatcher Configuration

Zeus v2 can delegate task execution to platform-native AI CLIs. Add the optional `subagent` block to `.zeus/v2/config.json`:

```json
{
  "subagent": {
    "dispatcher": "auto",
    "timeout_seconds": 600
  }
}
```

Supported `dispatcher` values:

| Value | Behavior |
|-------|----------|
| `"auto"` (default) | Detect `kimi` → `claude` → fallback to `mock` |
| `"kimi"` | Use `kimi --print --prompt ... --work-dir ...` |
| `"claude"` | Use `claude -p ... --allowedTools Read,Edit,Bash,Agent --cwd ...` |
| `"mock"` | Write prompt and return immediately (backward-compatible) |

**Note for Kimi users:** `kimi --print` implicitly runs in `--yolo` mode (auto-approve). Ensure your workspace is the isolated copy under `.zeus/v2/agent-workspaces/`.

**Note for Claude users:** The `claude` CLI must be installed and authenticated separately.

## Subagent Workspace Bootstrap

Before dispatching a task, the orchestrator automatically copies identity and context files from the project root into the isolated agent workspace. This ensures every subagent starts with the same continuity context as the main session.

**Default files copied:**
- `AGENTS.md`
- `USER.md`
- `IDENTITY.md`
- `SOUL.md`

If a file does not exist in the project root, it is skipped silently.

### Customizing the bootstrap file list

You can override the default list in `.zeus/v2/config.json`:

```json
{
  "subagent": {
    "dispatcher": "auto",
    "timeout_seconds": 600,
    "bootstrap": {
      "files": [
        "AGENTS.md",
        "USER.md",
        "IDENTITY.md",
        "SOUL.md",
        "MEMORY.md"
      ]
    }
  }
}
```

When `subagent.bootstrap.files` is present, it **replaces** the default list entirely.

## How to run (Dashboard)

```bash
# 1) Start the backend
python .zeus/v2/scripts/zeus_server.py --port 8234

# 2) Open the zero-build Web UI
#    Visit http://localhost:8234/web in your browser
```

## Wave approval flow

The Web UI shows a modal when a wave completes. Approving the modal advances `meta.current_wave`, unlocking the next wave for dispatch. The orchestrator will not start a new wave until the previous wave is explicitly approved.

## Per-task execution contract

Same as v1:

1. Quality checks (typecheck/lint/tests when configured)
2. Atomic commit with format `{type}({task_id}): {description}`
3. `task.json` update (`passes`, `commit_sha`, optional `ai_log_ref`)
4. Task-level AI log `.zeus/v2/ai-logs/{ISO-ts}-{task_id}.md`
5. Progress append to `.zeus/v2/progress.txt`

## Task Multi-language Support

Zeus v2 task metadata supports bilingual fields. In `task.json`, you can optionally add localized versions of `title` and `description`:

```json
{
  "id": "T-026",
  "title": "Implement feature X",
  "title_en": "Implement feature X",
  "title_zh": "实现功能 X",
  "description": "Detailed English description...",
  "description_en": "Detailed English description...",
  "description_zh": "详细的中文描述..."
}
```

**Rules:**
- All i18n fields are optional.
- The Web UI language toggle (中 / EN) reads `title_{lang}` / `description_{lang}` first, then falls back to the base `title` / `description`.
- The orchestrator prompt builder uses `title_zh` / `description_zh` when generating Chinese prompts.

## Phase Layer

For long-running projects, raw wave numbers become unreadable. Zeus v2 supports **Phases** — named delivery batches that group consecutive milestones and waves.

Phases live in `roadmap.json` under the top-level `phases` array:

```json
{
  "version": "v2",
  "phases": [
    {
      "id": "P-001",
      "title": "v2 Foundation",
      "title_en": "v2 Foundation",
      "title_zh": "v2 基础架构",
      "summary": "Core storage, async orchestrator, FastAPI backend, Web dashboard",
      "summary_en": "Core storage, async orchestrator, FastAPI backend, Web dashboard",
      "summary_zh": "核心存储、异步调度器、FastAPI 后端、Web 仪表盘",
      "milestone_ids": ["M-001", "M-002", "M-003"],
      "wave_start": 1,
      "wave_end": 4
    }
  ],
  "milestones": [ ... ]
}
```

**Web UI impact:**
- **Phases tab**: shows phase cards with summaries, progress bars, and nested milestones.
- **Dashboard wave selector**: becomes a "Phase → Wave"联动 selector, eliminating huge wave dropdowns.
- **Header badge**: displays the current phase next to the current wave.

**Backend impact:**
- `GET /phases` returns phases with computed `status` and `progress_percent`.
- `/status` includes `current_phase` based on `meta.current_wave` and phase `wave_start`/`wave_end`.

## Failure policy

- Agent timeout >10 min marks task failed.
- Git commit failure pauses the wave.
- Repeated failure (>3 retries): stop current wave and request task split.
- Interruption: resume by skipping already passed tasks.
