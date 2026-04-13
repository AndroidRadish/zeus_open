# v3 M-007 — Vite + Vue 3 Dashboard (Production Frontend)

## Decision Rationale

The zero-build `index.html` dashboard proved that a live web UI is both valuable and technically feasible. M-007 upgrades this to a real frontend engineering stack: Vite + Vue 3 + TypeScript. This provides component reuse, type safety, and a clear path to adding more views (task details, analytics charts, settings) in the future.

## Execution Summary

### New files
- `.zeus/v3/web/` — Complete Vite + Vue 3 + TypeScript project
  - `src/components/Dashboard.vue` — Main dashboard component with SSE stream, metrics cards, task table, and live event log
  - `src/App.vue` — Root app shell
  - `src/main.ts` — Vue application entrypoint
  - Standard Vite scaffolding (`index.html`, `tsconfig.json`, `vite.config.ts`, etc.)

### Modified files
- `.zeus/v3/web/vite.config.ts` — configured `base: '/dashboard/'` and `build.outDir: '../scripts/api/static'`
  - This makes `npm run build` output directly into the FastAPI static files directory
- `.zeus/v3/web/package.json` — adjusted build script for Windows PowerShell compatibility (`;` instead of `&&`)
- `.zeus/v3/scripts/tests/test_v3_api.py` — updated dashboard assertion to recognize the Vite-built SPA (`<div id="app"></div>`)

### Build verification
- `npm run build` succeeded in ~300ms
- FastAPI `GET /dashboard/` now serves the compiled Vue SPA
- Asset references (`/dashboard/assets/...`) are correctly resolved by `StaticFiles`

### Verification
- `47/47` v3 tests passed
- `python .zeus/scripts/zeus_runner.py --status` reports v2 validation pass

## Target Impact

- **ui_usability** ↑↑↑ — Modern component-based UI that can be extended with new views easily
- **developer_adoption_rate** ↑↑ — Familiar Vue/TS stack lowers the barrier for frontend contributions
- **observability** ↑↑ — Same real-time SSE + metrics features, but with a polished, maintainable codebase
