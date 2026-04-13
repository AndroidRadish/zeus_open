# v3 Phase 1 Expansion — Importer, Dispatcher, Workspace, Worker Integration

## Decision Rationale

After laying the v3 database foundation, the next priority was to bridge v2's proven execution capabilities (subagent dispatcher, workspace isolation, prompt generation) into the v3 Queue-Worker architecture. The user chose option A: expand Phase 1 until a complete subagent task can run end-to-end through v3.

Key design decisions:
- **Importer pattern**: `task.json` remains the static plan source, but `import_tasks_from_json()` migrates all runtime fields into the database. This allows backward compatibility while transitioning to the database-centric state model.
- **WorkspaceManager**: extracted the workspace preparation logic (project copy, bootstrap file injection, PROMPT.md generation) from v2's `ZeusOrchestrator` into a dedicated v3 module. This keeps the Worker focused on execution and state updates.
- **Dispatcher v3 redesign**: the CLI dispatcher now treats `zeus-result.json` as the **primary source of truth** for task success. It is read immediately after the subprocess exits. The exit code is only used as a fallback or for the known Windows stdout-crash tolerance patch.
- **Worker integration**: `ZeusWorker` now orchestrates the full lifecycle: `prepare workspace -> dispatch -> read ARP -> validate ZeusResult -> update database -> ack/nack queue`. This completes the separation between "scheduling" and "execution".
- **Package rename**: the queue package was renamed from `queue` to `task_queue` to avoid a circular import with Python's stdlib `queue` module (which `redis` imports internally).

## Execution Summary

### New files
- `.zeus/v3/scripts/importer.py` — `import_tasks_from_json(store, path)` migrates v2 plan + state into v3 DB
- `.zeus/v3/scripts/config.py` — `ZeusConfig` loader for `.zeus/v3/config.json`
- `.zeus/v3/scripts/workspace/manager.py` — `WorkspaceManager` handles workspace creation, bootstrap, and prompt generation
- `.zeus/v3/scripts/workspace/__init__.py`
- `.zeus/v3/scripts/dispatcher/base.py` — `SubagentDispatcher` ABC
- `.zeus/v3/scripts/dispatcher/mock.py` — `MockSubagentDispatcher` writes `zeus-result.json`
- `.zeus/v3/scripts/dispatcher/cli.py` — `KimiSubagentDispatcher`, `ClaudeSubagentDispatcher`, `AutoSubagentDispatcher`, plus `build_dispatcher()`
  - Key v3 improvement: `_read_zeus_result()` is checked before falling back to `exit_code`
- `.zeus/v3/scripts/dispatcher/__init__.py`

### Modified files
- `.zeus/v3/scripts/core/worker.py` — fully rewritten to integrate `WorkspaceManager` + dispatcher + ARP reading + state store updates
- `.zeus/v3/scripts/core/worker_pool.py` — updated constructor to accept `dispatcher` and `workspace_manager`
- `.zeus/v3/scripts/tests/test_v3_core.py` — expanded from 13 to 19 tests:
  - `test_import_tasks_from_json` / `test_import_preserves_extra_fields`
  - `test_workspace_prepare_cleans_and_copies`
  - `test_sqlite_queue_dead_letter_after_retries`
  - `test_worker_reads_zeus_result_json` — validates ARP file overrides dispatcher return value
  - `test_worker_retries_and_eventually_fails` — validates nack/retry path
  - Existing end-to-end test updated to use real workspace + mock dispatcher

### Bug fixes during implementation
- `workspace/manager.py` `_build_prompt`: `task.get("files", [])` failed when DB stored `files=None`. Fixed to `task.get("files") or []`.

## Verification
- `19/19` v3 core tests passed
- End-to-end flow confirmed: scheduler enqueues -> worker prepares workspace -> mock dispatcher executes -> zeus-result.json read -> DB updated to completed

## Target Impact

- **developer_adoption_rate** ↑↑↑ — v3 now has a complete, runnable task pipeline from plan (task.json) → schedule → execute → result.
- **multi_agent_efficiency** ↑↑ — Queue-Worker separation is no longer theoretical; it is exercised with real workspace preparation and dispatcher integration.
- **observability** ↑↑ — Every stage (started, enqueued, completed, failed) is logged to the indexed `EventLog` table.
- **reliability** ↑↑ — ARP (`zeus-result.json`) removes the fragile stdout/exit-code dependency that plagued v2's dispatcher.
