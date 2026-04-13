# v3 Phase 1 A1 — CLI Runner, Stress Tests, Subprocess ARP Integration

## Decision Rationale

The Phase 1 expansion gave v3 a complete pipeline, but it lacked three critical pieces needed for production confidence:
1. A **CLI entrypoint** so v3 can be invoked like a real tool (`python run.py --project-root .`)
2. **Stress tests** that exercise concurrency, dependency chains, and quarantine behavior under load
3. **Real subprocess integration tests** that prove the ARP (`zeus-result.json`) contract works end-to-end on Windows with actual `asyncio.create_subprocess_exec`

## Execution Summary

### New files
- `.zeus/v3/scripts/run.py` — One-shot CLI runner:
  - Parses `--project-root`, `--version`, `--max-workers`, `--database-url`, `--queue-backend`, `--dispatcher`, `--import-only`
  - Pipeline: `ensure_schema -> import_tasks -> start_pool -> scheduler_loop -> report`
  - Robust shutdown: checks `pending == 0 && running == 0 && queue.size() == 0` before exiting idle loop
- `.zeus/v3/scripts/tests/test_v3_stress.py` — Two high-concurrency scenarios:
  - `test_stress_12_tasks_4_workers`: 3 waves × 4 tasks, 0.15s artificial delay per task, 4 concurrent workers. Validates full completion and parallelism (< 2.5s).
  - `test_stress_quarantine_unblocks_independent_branch`: T-101 fails → quarantined, blocking T-103. T-102 succeeds, allowing T-104 to complete independently.
- `.zeus/v3/scripts/tests/test_v3_subprocess.py` — Subprocess integration:
  - `PythonSubagentDispatcher` spawns `python -c` to write `zeus-result.json`
  - WorkerPool runs the real dispatcher, then reads ARP and marks task `completed`
- `.zeus/v3/scripts/tests/test_v3_dispatcher.py` — Dispatcher unit tests:
  - `test_kimi_command_build`, `test_claude_command_build`, `test_build_dispatcher_mock/kimi`

### Bug fixes
- **Windows path escaping in subprocess one-liner**: `open('{workspace}/zeus-result.json')` broke on Windows because `Path` stringification produced backslashes that were interpreted as escape sequences inside the `-c` script. Fixed by using `repr(str(out_path))` to emit a safe Python string literal.
- **Premature loop exit in stress tests and `run.py`**: The original idle-break condition (`ready == [] and qsize == 0`) would exit while workers were still processing inflight tasks (queue empty but tasks in `running` state). This caused T-005+ to remain `pending` forever. Fixed by only breaking after `qsize == 0` **and** `pending == 0` **and** `running == 0`.
- **Worker quarantine on failure**: `core/worker.py` already quarantines tasks on exception, invalid ARP, and non-completed status — verified by stress/quarantine tests.

### Verification
- `26/26` v3 tests passed (including 19 core + 3 dispatcher + 2 stress + 1 subprocess + 1 additional)
- `python .zeus/scripts/zeus_runner.py --status` reports v2 validation pass
- Commit `49d5199` records the A1 expansion

## Target Impact

- **developer_adoption_rate** ↑↑↑ — v3 is now invokable from the command line
- **reliability** ↑↑↑ — Stress tests catch concurrency and loop-termination bugs before they reach production
- **platform_compatibility** ↑↑ — Subprocess ARP validated on Windows, removing the stdout-encoding fragility that blocked v2's real dispatcher usage
