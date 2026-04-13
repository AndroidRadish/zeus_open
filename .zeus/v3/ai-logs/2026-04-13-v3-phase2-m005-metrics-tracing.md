# v3 Phase 2 M-005 — Metrics Collector & OpenTelemetry Tracing

## Decision Rationale

With the FastAPI server and SSE event bus in place, the next step is to turn the raw event stream into actionable insights. M-005 delivers:
1. A `MetricsCollector` that aggregates per-task execution stats, bottleneck detection, and blocked dependency chain analysis
2. Additional REST endpoints exposing these metrics
3. OpenTelemetry trace integration so each scheduler run produces a distributed trace span

## Execution Summary

### New files
- `.zeus/v3/scripts/api/metrics.py` — `MetricsCollector`
  - `task_metrics()`: per-task duration (ms), status, pass/fail, wave, start/finish timestamps
  - `bottleneck_tasks(top_n)`: longest-running tasks (useful for CI optimization)
  - `blocked_chains()`: dependency subtrees blocked by quarantine or failure (useful for identifying critical path risks)
  - `summary()`: high-level counts + average duration + pass rate
- `.zeus/v3/scripts/core/tracing.py` — `init_tracing()`
  - Safe no-op fallback when `opentelemetry` is not installed
  - Configurable `ConsoleSpanExporter` via `--trace` CLI flag
  - Wraps scheduler run and each tick in OTel spans with attributes (`tick`, `enqueued_count`, `pending`, `running`)
- `.zeus/v3/scripts/tests/test_v3_tracing.py` — verifies tracer initialization and no-op safety

### Modified files
- `.zeus/v3/scripts/api/server.py` — new endpoints:
  - `GET /metrics/summary` — now powered by `MetricsCollector.summary()` (includes `avg_duration_ms`)
  - `GET /metrics/tasks` — per-task metrics
  - `GET /metrics/bottleneck` — top-N slowest tasks
  - `GET /metrics/blocked` — blocked dependency chains
- `.zeus/v3/scripts/run.py` — added `--trace` flag; initializes tracer and wraps the scheduling loop
- `.zeus/v3/scripts/store/base.py` — `log_event()` signature extended with optional `ts` parameter
- `.zeus/v3/scripts/store/sqlalchemy_base.py` — implements `ts` override for precise event insertion (used in tests)
- `.zeus/v3/scripts/tests/test_v3_api.py` — added tests for `/metrics/tasks`, `/metrics/bottleneck`, `/metrics/blocked`

### Design notes
- **Durable + ephemeral dual-write model** is preserved: `store.log_event()` is the source of truth; `bus.emit()` is the real-time projection. Metrics are computed from the durable event log, so they remain accurate even if SSE consumers disconnect.
- **Blocked chain detection** performs a BFS from each failed/quarantined task through the reverse dependency graph. This surfaces not just "what failed" but "how much work is stuck behind it."
- **OpenTelemetry integration is lightweight**: a single `scheduler-run` span with child `scheduler-tick` spans. This gives basic distributed tracing without adding overhead to the hot path.

### Bug fixes during implementation
- `api/server.py` import fix: `MetricsCollector` was accidentally omitted from imports after a prior refactor.
- `test_metrics_bottleneck` flakiness: relying on wall-clock `asyncio.sleep` inside tests produced non-deterministic durations due to SQLite `func.now()` second-level precision. Fixed by adding an optional `ts` parameter to `log_event()`, allowing tests to inject exact timestamps.

### Verification
- `37/37` v3 tests passed (core 19 + API 9 + dispatcher 4 + stress 2 + subprocess 1 + tracing 2)
- `python .zeus/scripts/zeus_runner.py --status` reports v2 validation pass

## Target Impact

- **observability** ↑↑↑ — Metrics API answers "what is slow" and "what is blocked"
- **developer_adoption_rate** ↑↑↑ — Tracing enables integration with Jaeger/Tempo in production deployments
- **reliability** ↑↑ — Blocked-chain analysis helps prioritize root-cause fixes over downstream symptoms
