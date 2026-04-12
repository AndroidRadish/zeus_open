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

## Failure policy

- Agent timeout >10 min marks task failed.
- Git commit failure pauses the wave.
- Repeated failure (>3 retries): stop current wave and request task split.
- Interruption: resume by skipping already passed tasks.
