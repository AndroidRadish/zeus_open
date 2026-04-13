# v3 Phase 2 M-006 — Git Worktree Workspace Backend

## Decision Rationale

M-006 addresses one of the biggest operational costs in v2: `shutil.copytree` duplicates the entire project tree for every agent task. For large repositories this is slow and wastes disk space. Git worktrees provide a lightweight, zero-copy alternative: they create a new working directory linked to the same `.git` database, avoiding full tree copies while still maintaining full isolation.

## Execution Summary

### New files
- `.zeus/v3/scripts/workspace/base.py` — `BaseWorkspaceManager`
  - Extracted shared logic (`workspace_path`, `prompt_path`, `result_path`, `_bootstrap`, `_write_prompt`, `_build_prompt`, `_to_thread`)
  - Provides a stable interface so that runner code can swap backends without changes
- `.zeus/v3/scripts/workspace/git_worktree.py` — `GitWorktreeWorkspaceManager`
  - `prepare(task)`:
    1. Removes any existing worktree for the task (`git worktree remove --force` + prune fallback)
    2. Creates a detached worktree via `git worktree add --detach <path>`
    3. Bootstraps context files and writes `PROMPT.md`
  - Cleanup is handled inside `prepare()` so repeated runs for the same task do not leak worktrees
- `.zeus/v3/scripts/tests/test_v3_workspace_git_worktree.py` — integration tests
  - Validates that a real git worktree is created and listed by `git worktree list`
  - Validates that re-preparing the same task cleans the old workspace

### Modified files
- `.zeus/v3/scripts/workspace/manager.py` — `WorkspaceManager` now inherits from `BaseWorkspaceManager` and only contains the copytree-specific `_copy_project` logic
- `.zeus/v3/scripts/workspace/__init__.py` — added `build_workspace_manager(project_root, version, backend)` factory
  - Reads `workspace.backend` from `config.json` (default: `"copytree"`)
  - Returns `GitWorktreeWorkspaceManager` when backend is `"git_worktree"`
- `.zeus/v3/scripts/config.py` — added `workspace_backend` property
- `.zeus/v3/scripts/run.py` — switched from `WorkspaceManager(...)` to `build_workspace_manager(...)`

### Design notes
- **Backward compatibility**: existing code that imports `WorkspaceManager` directly continues to work unchanged. All v2-style tests pass without modification.
- **Graceful fallback**: if `git worktree add` fails (e.g., not inside a git repo), the exception propagates so the user can switch back to `copytree` via config.
- **Windows compatible**: assertions use `Path.as_posix()` to handle the forward-slash output of `git worktree list` on Windows.

### Verification
- `39/39` v3 tests passed (37 previous + 2 new git-worktree tests)
- `python .zeus/scripts/zeus_runner.py --status` reports v2 validation pass

## Target Impact

- **multi_agent_efficiency** ↑↑↑ — Git worktree eliminates redundant file copies, dramatically reducing workspace preparation time for large repositories
- **disk_usage** ↑↑ — Multiple agent workspaces share the same git object store
- **developer_adoption_rate** ↑↑ — Configurable backend (`copytree` vs `git_worktree`) lets teams choose the strategy that fits their environment
