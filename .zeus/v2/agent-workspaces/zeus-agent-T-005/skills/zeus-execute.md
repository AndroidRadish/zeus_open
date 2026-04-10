# Zeus Execute - Wave Orchestration Engine

Run pending tasks with dependency awareness, strict quality gates, and atomic commits.

## Preconditions

- `.zeus/{version}/config.json` exists.
- `.zeus/{version}/task.json` exists and contains pending tasks.
- `zeus_runner.py` exists.

## How to run

```bash
python .zeus/scripts/zeus_runner.py --wave 1
python .zeus/scripts/zeus_runner.py --task T-001
```

## Per-task execution contract

Each task completion must include:

1. Quality checks (typecheck/lint/tests when configured)
2. Atomic commit with format `{type}({task_id}): {description}`
3. `task.json` update (`passes`, `commit_sha`, optional `ai_log_ref`)
4. Task-level AI log `.zeus/{version}/ai-logs/{ISO-ts}-{task_id}.md`
5. Progress append to `.zeus/{version}/progress.txt`

## Failure policy

- quality check failure: pause and surface error details,
- repeated failure (>3 retries): stop current wave and request task split,
- interruption: resume by skipping already passed tasks.
