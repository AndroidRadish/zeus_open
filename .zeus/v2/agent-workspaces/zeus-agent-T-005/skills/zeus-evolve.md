# Zeus Evolve - Version Split Protocol

Create a new version track when feedback indicates structural divergence from current roadmap.

## Preconditions

- Evolution rationale exists.
- `.zeus/main/config.json` exists and is writable.
- New version identifier is not already used.

## Deterministic workflow

1. **Confirm evolution rationale**.
2. **Resolve next version ID** (auto-detect latest `vN` + 1).
3. **Confirm creation plan**.
4. **Create folder structure**: `.zeus/v{N}/feedback`, `ai-logs`, `specs`, `tests`.
5. **Write version config** with `inherits: main` and `overrides` documenting strategic difference.
6. **Initialize empty artifacts**: `prd.json`, `task.json`, `roadmap.json`, `evolution.md`.
7. **Register version** in main config.
8. **Append evolution records** to both main and v{N} evolution.md.
9. **Optional branch creation**.
10. **Commit changes**.
11. **Write AI log**.
