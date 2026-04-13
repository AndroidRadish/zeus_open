# v3 M-008 — Multi-container Docker Compose Deployment

## Decision Rationale

With the Redis queue backend now available, v3 can finally be deployed as a horizontally-scaled multi-service architecture. M-008 delivers the container artifacts needed to run ZeusOpen v3 in production: a shared Dockerfile and a `docker-compose.yml` that splits the monolithic runner into API, Scheduler, and Worker services.

## Execution Summary

### New files
- `.zeus/v3/Dockerfile` — Production Python 3.13 image
  - Installs `git` (required for the `git_worktree` workspace backend)
  - Copies v3 scripts and config into `/app/.zeus/v3/`
  - Sets `PYTHONPATH` and exposes port `8000`
  - Default `ENTRYPOINT` is `run.py` with overridable `CMD`
- `.zeus/v3/docker-compose.yml` — 4-service stack
  - `redis` — Redis 7 Alpine with persistent volume
  - `zeus-api` — `run.py --mode serve` (FastAPI + dashboard)
  - `zeus-scheduler` — `run.py --mode scheduler` (enqueue ready tasks)
  - `zeus-worker` — `run.py --mode worker` (2 replicas consuming queue)
  - Shared `zeus_state` volume for SQLite database persistence across containers
  - `docker.sock` mounted for future Docker-dispatcher sandbox support (M-009)
- `.zeus/v3/task.json` — minimal default task plan so that `run.py` can import without error even on first launch

### Modified files
- `.zeus/v3/scripts/run.py` — new `--mode` flag replacing `--serve`
  - `combined` (default): scheduler + worker pool in one process
  - `scheduler`: scheduling loop only
  - `worker`: worker pool only; idles until queue + DB are empty, then exits gracefully
  - `serve`: API server (replaces previous `--serve` boolean flag)
  - Each mode shuts down the appropriate components cleanly

### Design notes
- **Scheduler singleton**: Only one `zeus-scheduler` container is deployed. The in-memory `enqueued_ids` set remains safe because there is only one scheduler instance.
- **Worker horizontal scaling**: `zeus-worker` uses Docker Compose `deploy.replicas: 2`, demonstrating how the worker pool can scale independently.
- **Shared state**: All services mount the same `zeus_state` Docker volume so the SQLite database is consistent across API, scheduler, and workers.
- **Queue backend**: All non-API services use `--queue-backend=redis` so workers can consume from the same queue regardless of which host they run on.

### Verification
- `45/45` v3 tests passed (no regressions in combined mode)
- `python .zeus/scripts/zeus_runner.py --status` reports v2 validation pass

## Target Impact

- **scalability** ↑↑↑ — Workers can be scaled up/down independently via Docker Compose or Kubernetes
- **multi_agent_efficiency** ↑↑↑ — Redis queue + multi-container split removes the single-process bottleneck
- **developer_adoption_rate** ↑↑ — `docker compose up` gives new users a one-command production-like stack
