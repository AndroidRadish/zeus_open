# Zeus Plan - Spec to Executable Artifacts

Convert an approved spec into version-scoped stories and tasks with deterministic IDs and dependency waves.

## Preconditions

- Target spec exists and is approved.
- `.zeus/{version}/config.json` exists.
- `.zeus/{version}/prd.json`, `task.json`, and `roadmap.json` are writable.

## Deterministic workflow

1. **Load context** and reserve next IDs (`US-{NNN}`, `T-{NNN}`, `M-{NNN}`).
2. **Create user stories** from acceptance criteria.
3. **Create executable tasks** (small, independently executable units).
4. **Compute wave plan** from `depends_on` DAG.
5. **Update roadmap milestone** with title, spec_ref, story/task IDs, `status: planned`.
6. **Persist artifacts**: `prd.json`, `task.json`, `roadmap.json`.
7. **Commit planning artifacts**.
8. **Write AI log**.
9. **Report summary** and recommend `python .zeus/scripts/zeus_runner.py --plan`.

## Quality gates

- no duplicate story/task IDs,
- no empty acceptance criteria,
- no task without a valid story link,
- no wave assignment with unresolved dependency.
