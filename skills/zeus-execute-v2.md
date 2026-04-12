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

# Global scheduler (cross-wave, dependency-ready dispatch)
python .zeus/v2/scripts/zeus_orchestrator.py --run-global

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

## Global Scheduler

In addition to wave-by-wave dispatch, v2 supports a **global scheduler** that treats wave numbers as planning/observation fields only. Tasks are dispatched as soon as their dependencies are satisfied, across all waves.

```bash
python .zeus/v2/scripts/zeus_orchestrator.py --run-global
```

**Key behaviors:**
- Failed tasks are moved to `task.json["quarantine"]`.
- Quarantined tasks block their downstream dependents, but do **not** block unrelated tasks.
- The Web UI **Global Execution** tab shows running tasks, pending tasks grouped by wave, and the quarantine panel in real time.

## Graceful Shutdown & State Recovery

The v2 server can survive restarts without losing track of in-flight tasks.

**Persistence:** `.zeus/v2/scheduler_state.db` (SQLite)

**What is persisted on shutdown:**
- `scheduler_active` flag
- List of currently running tasks (task_id, agent_id, wave, status)

**Triggering persistence:**
- Sending `SIGINT` or `SIGTERM` to `zeus_server.py` triggers a graceful shutdown. The orchestrator saves active tasks to SQLite before exiting.
- The FastAPI `shutdown` event also triggers the same save path.

**Recovery on startup:**
- When `zeus_server.py` starts, it checks `scheduler_state.db`. If `scheduler_active` is true, it automatically restores those tasks as `running` in `task.json` and the Web UI shows a recovery banner.
- `/global/status` merges recovered tasks into the `running` list so the dashboard is accurate immediately after restart.
- `/global/recovery` returns `{recovered, recovered_at, active_tasks_count}` for custom UI handling.

**Normal completion:**
- When the global scheduler finishes all tasks successfully, it clears the SQLite snapshot so the next startup does not trigger a false recovery.

## Agent Mailbox

Agents can communicate asynchronously via a lightweight mailbox backed by JSONL files.

**Persistence:** `.zeus/v2/agent-logs/mailbox/{to_agent_id}.jsonl`

**API:**
- `GET /mailbox/{agent_id}` — retrieve unread/read messages.
- `GET /mailbox/{agent_id}?mark_read=true` — retrieve and mark messages as read.

**Python usage (`agent_bus.py`):**
```python
bus.send("zeus-agent-T-002", "Need help with tests")
inbox = bus.receive("zeus-agent-T-002", mark_read=True)
```

The Web UI **Agent Collaboration** tab provides a live (polling) message stream.

## Agent-level Isolated Logs

Every dispatched agent now has its own isolated log directory:

```
.zeus/v2/agent-logs/{agent_id}/
  activity.md       # Human-readable Markdown log
  reasoning.jsonl   # Machine-readable event stream
```

**Backward compatibility:** Legacy aggregated `wave-{n}-events.jsonl` and `wave-{n}-discussion.md` are still written so existing tools and tests continue to work.

**API:**
- `GET /agents/{agent_id}/logs` — returns `{activity, reasoning}`.

The Web UI **Agent Logs** tab lets you select an agent and browse both views side-by-side.

## Failure policy

- Agent timeout >10 min marks task failed.
- Git commit failure pauses the wave.
- Repeated failure (>3 retries): stop current wave and request task split.
- Interruption: resume by skipping already passed tasks.
