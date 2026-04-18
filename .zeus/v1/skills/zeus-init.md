# Zeus Init - Bootstrap Contract

Use this as the mandatory first step before any other Zeus workflow.

## Non-negotiable rules

1. Ask one question per message and wait for the user's response.
2. Never create planning artifacts before config baseline is valid.
3. Always append an AI log after write operations.
4. If initialization already exists, require explicit user confirmation before overwrite.

## Preconditions

- Workspace contains `.zeus/` scaffold and schema files.
- You can write under `.zeus/main/`.
- Git repository is available (or can be initialized).

## Brownfield mode

When `--import-existing` is provided:

- Read `.zeus/{version}/codebase-map.json` if present.
- Read `.zeus/{version}/existing-modules.json` if present.
- Pre-fill `project.domain` and `project.tech_stack` from discovered artifacts.
- Keep one-question loop to let user confirm or override inferred values.

## Deterministic workflow

### 1) Initialization state check

Inspect whether `.zeus/main/config.json` exists and has a non-empty `project.name`.

- If initialized: explain current state and ask whether to re-initialize.
- If user declines: stop and suggest `python .zeus/scripts/zeus_runner.py --status`.
- If not initialized: continue.

### 2) Collect baseline inputs (single question loop)

Collect, in this exact order:

1. Project name
2. Primary domain (optional)
3. Technology stack
4. Version intent (single version or future `v2/v3` tracks)

### 3) North star metric proposal

Propose one recommended metric bundle with rationale and editable weights.

### 4) Write `.zeus/main/config.json`

Write schema-compatible configuration with project metadata, metrics, git policy, and versions.

### 5) Append evolution init record

Append a new `INIT` entry to `.zeus/main/evolution.md`.

### 6) Commit baseline

```bash
git add .zeus/
git commit -m "chore(zeus): initialize zeus project structure"
```

### 7) Write AI log (mandatory)

Create `.zeus/main/ai-logs/{ISO-ts}-init.md` using the 3-section contract.

### 8) Completion message

Report created artifacts and recommend next step: `zeus:brainstorm --full` or `zeus:discover`.
