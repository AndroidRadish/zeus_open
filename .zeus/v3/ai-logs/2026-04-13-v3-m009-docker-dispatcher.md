# v3 M-009 Pre-work — Docker Sandbox Dispatcher

## Decision Rationale

M-009 calls for running subagents inside Docker containers to provide filesystem and network isolation. While a full implementation would include a custom agent image with the Kimi/Claude CLI pre-installed, the foundational piece is the `DockerSubagentDispatcher` that knows how to construct `docker run` commands with proper volume mounts, working directory, and resource limits.

## Execution Summary

### New files
- `.zeus/v3/scripts/dispatcher/docker.py` — `DockerSubagentDispatcher`
  - Mounts the writable workspace and the read-only project source
  - Supports `memory_limit` and `cpu_limit` cgroup constraints
  - Supports `extra_volumes` for additional mounts
  - Writes the prompt to `.docker-prompt.txt` inside the workspace so the container can consume it
  - Heuristic to discover `project_root` from the workspace path
- `.zeus/v3/scripts/tests/test_v3_dispatcher_docker.py` — command-building tests
  - Validates `docker run` arguments, resource limits, and image selection
  - Validates project-root heuristic without requiring a live Docker daemon

### Modified files
- `.zeus/v3/scripts/dispatcher/cli.py` — `build_dispatcher()` now recognizes `mode == "docker"`
  - Reads `subagent.docker.image`, `memory_limit`, `cpu_limit`, `extra_volumes` from config

### Design notes
- **Stub inner command**: The current implementation uses a Python one-liner stub that writes `zeus-result.json`. In production, this will be replaced by a real agent CLI invocation inside a custom image (e.g., `kimi-cli` or a script that calls the Kimi API).
- **docker-in-docker ready**: The `docker-compose.yml` already mounts `/var/run/docker.sock`, so `zeus-worker` containers can spawn sibling containers on the host Docker daemon.

### Verification
- `47/47` v3 tests passed (including 2 new docker dispatcher tests)
- `python .zeus/scripts/zeus_runner.py --status` reports v2 validation pass

## Target Impact

- **security** ↑↑↑ — Subagents can be sandboxed with cgroup limits and read-only source mounts
- **reliability** ↑↑ — Resource limits prevent runaway agents from exhausting host resources
- **multi_agent_efficiency** ↑↑ — Docker dispatching is the gateway to Kubernetes Jobs and serverless container execution
