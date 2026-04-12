# v2 Subagent Dispatcher Integration Design Spec

> **Project**: zeus-open v2 enhancement  
> **Topic**: Pluggable subagent dispatcher supporting Kimi CLI, Claude CLI, and mock fallback  
> **North Star Impact**: `developer_adoption_rate` ↑↑↑, `multi_agent_efficiency` ↑↑  

---

## 1. Problem Statement

Current `zeus_orchestrator.py::dispatch_task` is a mock: it copies source code, writes a `PROMPT.md`, and immediately emits `task.completed`. The actual coding work still requires a human to copy the prompt into an AI session manually.

This breaks the core value proposition of v2: **unattended multi-agent parallel execution**.

## 2. Objectives

- Enable true unattended task execution by delegating to platform-native AI CLI tools.
- Support both **Kimi CLI** (`kimi --print`) and **Claude Code** (`claude`) out of the box.
- Preserve backward compatibility: if no AI CLI is installed, fall back to the existing mock behavior.
- Keep the orchestrator scheduling loop unchanged; only the execution backend changes.

## 3. Guiding Principles

1. **Workspace isolation is the safety boundary** — the subagent only sees a disposable copy of the project.
2. **YOLO-aware** — `kimi --print` implies auto-approval; therefore, the workspace must NEVER be the original project root.
3. **CLI detection, not configuration** — default behavior is auto-discovery; explicit config is optional.
4. **Stdout as artifact** — CLI output is captured to `agent-logs/{task_id}-stdout.txt` for observability.

## 4. Architecture

### 4.1 Dispatcher Interface

```python
class SubagentDispatcher(abc.ABC):
    @abc.abstractmethod
    async def run(self, task: dict, workspace: Path, prompt: str, bus: AgentBus) -> dict:
        """Execute the task in *workspace* and return a result dict.

        Must emit task.started and task.completed/failed to the bus.
        """
```

### 4.2 Implementations

#### MockSubagentDispatcher
- Behavior: writes `DONE` marker file and returns immediately.
- Used when: no external CLI is detected and `config.subagent_mode == "mock"`.

#### KimiSubagentDispatcher
- Command:
  ```bash
  kimi --print --prompt "{prompt}" --work-dir "{workspace}" --output-format text
  ```
- Notes:
  - `--print` implicitly adds `--yolo`.
  - stdout is tee'd to `{workspace}/.zeus/agent-logs/T-xxx-stdout.txt`.
  - If returncode != 0, the task is marked failed but we still inspect the workspace for any partial changes.

#### ClaudeSubagentDispatcher
- Command:
  ```bash
  claude -p "{prompt}" --allowedTools "Read,Edit,Bash,Agent" --cwd "{workspace}"
  ```
- Notes:
  - `claude` CLI availability is detected via `shutil.which("claude")`.
  - Similar stdout capture pattern.

#### AutoSubagentDispatcher
- Detection order:
  1. `shutil.which("kimi")` → KimiSubagentDispatcher
  2. `shutil.which("claude")` → ClaudeSubagentDispatcher
  3. Fallback → MockSubagentDispatcher

### 4.3 Orchestrator Integration

`ZeusOrchestrator.dispatch_task` is refactored:

```python
async def dispatch_task(self, task: dict, bus: AgentBus, store: LocalStore) -> dict:
    ...
    dispatcher = self._build_dispatcher()
    result = await dispatcher.run(task, workspace_path, prompt, bus)
    return result
```

`_build_dispatcher()` reads `.zeus/v2/config.json`:
- `config.subagent.dispatcher` can be `"auto"`, `"kimi"`, `"claude"`, `"mock"`.
- Default is `"auto"`.

### 4.4 Timeout & Observability

- Default timeout per task: 10 minutes (configurable via `config.subagent.timeout_seconds`).
- If timeout occurs, subprocess is killed and task is marked `failed`.
- Stdout is streamed to a log file so the Web UI "Agent Monitor" can (in the future) display last lines.
- Discussion log (`bus.post`) is updated at start and completion, including a summary of the CLI exit code.

## 5. Data Contracts

### 5.1 Config Extension (optional)

```json
{
  "subagent": {
    "dispatcher": "auto",
    "timeout_seconds": 600
  }
}
```

### 5.2 Task Result Contract

`dispatcher.run()` returns:

```python
{
  "task_id": "T-001",
  "status": "completed",  # or "failed"
  "exit_code": 0,
  "stdout_path": ".zeus/v2/agent-logs/T-001-stdout.txt",
  "workspace": str(workspace_path),
}
```

## 6. Testing Strategy

### 6.1 Unit Tests
- Mock `subprocess.run` / `asyncio.create_subprocess_exec` to verify Kimi/Claude command construction.
- Verify `AutoSubagentDispatcher` picks the right backend based on `shutil.which` patches.

### 6.2 Integration Test
- Use `MockSubagentDispatcher` in the existing 2-wave integration test (no regression).
- Add a new test with a fake `kimi` shell script (echo + touch marker) to prove end-to-end subprocess dispatch works.

## 7. Acceptance Criteria

- [ ] `subagent_dispatcher.py` exists with `SubagentDispatcher` ABC and 4 implementations.
- [ ] `zeus_orchestrator.py` uses the dispatcher abstraction without leaking platform specifics.
- [ ] `config.json` optionally accepts `subagent.dispatcher` and `subagent.timeout_seconds`.
- [ ] Kimi CLI users can set `"subagent.dispatcher": "kimi"` and run `zeus_orchestrator.py --wave N` to see true unattended execution.
- [ ] All 35+ v2 tests pass; new dispatcher tests are added.

## 8. Task Breakdown

| Wave | Task | Description |
|------|------|-------------|
| 5 | T-015 | Create `subagent_dispatcher.py` with ABC + Mock + Kimi + Claude + Auto implementations |
| 6 | T-016 | Refactor `zeus_orchestrator.py` to delegate execution to dispatcher; add config parsing |
| 6 | T-017 | Add unit tests for dispatcher command construction and auto-selection |
| 7 | T-018 | Update Web UI Agent Monitor to show "last_seen" and simple activity indicators even for short mocks |
| 7 | T-019 | Update README and zeus-execute-v2.md with subagent setup instructions |
