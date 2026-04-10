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

## How to run (Dashboard)

```bash
# 1) Start the backend
python .zeus/v2/scripts/zeus_server.py --port 8234

# 2a) Open the zero-build Web UI
#    Visit http://localhost:8234/web in your browser

# 2b) Or launch the PyQt desktop GUI
python .zeus/v2/scripts/zeus_gui.py --api-base http://localhost:8234
```

## Wave approval flow

The GUI shows a modal when a wave completes. Approving the modal advances `meta.current_wave`, unlocking the next wave for dispatch. The orchestrator will not start a new wave until the previous wave is explicitly approved.

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
