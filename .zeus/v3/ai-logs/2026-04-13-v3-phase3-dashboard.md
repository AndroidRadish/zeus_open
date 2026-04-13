# v3 Phase 3 Pre-work — Zero-build Real-time Dashboard

## Decision Rationale

Phase 3's formal plan calls for a Vite + Vue 3 engineering migration (M-007). However, before committing to a full build pipeline, it is more valuable to have a working, zero-build web UI that exercises the SSE and Metrics APIs we just built. This gives v3 an immediately usable observability surface and validates the API design under real browser interaction.

## Execution Summary

### New files
- `.zeus/v3/scripts/api/static/index.html` — Zero-build real-time dashboard
  - Dark-themed responsive layout with metrics cards, task table, and live event stream
  - Connects to `GET /events/stream` via `EventSource` and updates task/metrics views in real time
  - Falls back to 5-second polling for tasks and metrics while SSE is connecting
  - Keeps the last 50 events in a scrollable list

### Modified files
- `.zeus/v3/scripts/api/server.py` — mounted `StaticFiles` at `/dashboard`
  - Added root `GET /` endpoint that returns `{ "dashboard": "/dashboard" }`
- `.zeus/v3/scripts/tests/test_v3_api.py` — added tests verifying:
  - `GET /dashboard/` returns HTML containing the dashboard title
  - `GET /` returns the dashboard URL

### Design notes
- **Truly zero-build**: a single self-contained HTML file with inline CSS and JS. No bundler, no npm, no CI frontend step.
- **Event-driven refresh**: when SSE messages with `task.*` event types arrive, the dashboard immediately refetches `/tasks` and `/metrics/summary` instead of waiting for the next poll interval.
- **Backward compatible**: the FastAPI server works exactly as before if the `static/` directory is absent (guarded by `exists()` check).

### Verification
- `41/41` v3 tests passed
- `python .zeus/scripts/zeus_runner.py --status` reports v2 validation pass

## Target Impact

- **ui_usability** ↑↑↑ — v3 now has a live web dashboard out of the box
- **developer_adoption_rate** ↑↑↑ — Users can open `http://127.0.0.1:8000/dashboard` while `run.py --serve` is running and watch tasks execute in real time
- **observability** ↑↑ — SSE-driven UI removes the need for manual HTTP polling by the operator

## Next Step (when user returns)

Decide whether to:
1. Proceed with full M-007 Vite + Vue 3 frontend engineering
2. Continue M-008 multi-container Docker Compose split
3. Continue M-009 Docker sandbox dispatcher mode
4. Continue M-010 unified CLI and v1 retirement
