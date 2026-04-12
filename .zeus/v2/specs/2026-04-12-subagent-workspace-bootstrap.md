# v2 Subagent Workspace Bootstrap Design Spec

> **Project**: zeus-open v2 enhancement  
> **Topic**: Auto-inject identity and context files into every agent workspace  
> **North Star Impact**: `developer_adoption_rate` ↑↑, `multi_agent_efficiency` ↑  

---

## 1. Problem Statement

When `zeus_orchestrator.py` dispatches a task to a subagent, it copies the project source into an isolated workspace and writes `PROMPT.md`. However, the workspace lacks the project's `AGENTS.md`, `USER.md`, `IDENTITY.md`, and `SOUL.md` files.

This means every subagent starts **without continuity context**:
- It doesn't know who it is (no `IDENTITY.md`).
- It doesn't know who the human is (no `USER.md`).
- It doesn't know the project's agent-specific conventions (no `AGENTS.md`).
- It doesn't know its own values and boundaries (no `SOUL.md`).

In practice, this forces the human to re-paste context into every subagent session, breaking the promise of unattended execution.

## 2. Objectives

- Automatically seed every agent workspace with the same identity/context files that the main session uses.
- Allow optional override via `config.json` so projects can customize the file list.
- Keep the mechanism transparent: if a file doesn't exist in the project root, skip it silently.

## 3. Guiding Principles

1. **Zero-config by default** — if the files exist in `project_root`, they are copied automatically.
2. **Explicit override wins** — `config.subagent.bootstrap.files` can add or replace the default list.
3. **Never fail the dispatch** — missing bootstrap files are a warning, not an error.
4. **Respect isolation** — only *copy* files; never symlink back to the original project root.

## 4. Architecture

### 4.1 Default Bootstrap File List

```python
DEFAULT_BOOTSTRAP_FILES = [
    "AGENTS.md",
    "USER.md",
    "IDENTITY.md",
    "SOUL.md",
]
```

### 4.2 Config Extension (optional)

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

If `subagent.bootstrap.files` is present, it replaces the default list entirely.

### 4.3 Orchestrator Integration

In `ZeusOrchestrator.dispatch_task`, after copying the project tree and before writing `PROMPT.md`:

```python
await self._bootstrap_workspace(workspace_path, store)
```

`_bootstrap_workspace` implementation:

1. Resolve the effective file list (default or config override).
2. For each file:
   - Check `project_root / filename`.
   - If it exists, copy it into `workspace_path / filename`.
   - If it doesn't exist, skip.
3. Emit a single `task.bootstrapped` event to the bus listing which files were injected.

### 4.4 Event Contract

```json
{
  "type": "task.bootstrapped",
  "task_id": "T-020",
  "agent_id": "zeus-orchestrator",
  "payload": {
    "workspace": ".zeus/v2/agent-workspaces/zeus-agent-T-020",
    "injected": ["AGENTS.md", "USER.md"],
    "skipped": ["IDENTITY.md", "SOUL.md"]
  }
}
```

## 5. Testing Strategy

### 5.1 Unit Test

- Create a temporary project that contains `AGENTS.md` and `USER.md` but lacks `IDENTITY.md`.
- Call `ZeusOrchestrator.dispatch_task` with a mock dispatcher.
- Assert that the workspace contains the two existing files and does not contain the missing one.
- Assert that a `task.bootstrapped` event is emitted with correct `injected`/`skipped` lists.

### 5.2 Config Override Test

- Set `config.subagent.bootstrap.files` to `["CUSTOM.md"]`.
- Assert that only `CUSTOM.md` is copied, even if `AGENTS.md` exists in the project root.

## 6. Acceptance Criteria

- [ ] `zeus_orchestrator.py` copies default identity files into every agent workspace before dispatch.
- [ ] `config.json` optionally accepts `subagent.bootstrap.files` to customize the list.
- [ ] Missing files are skipped without raising exceptions.
- [ ] A `task.bootstrapped` event is emitted for observability.
- [ ] Tests cover default behavior and config override.
- [ ] `skills/zeus-execute-v2.md` documents the bootstrap behavior and config option.
