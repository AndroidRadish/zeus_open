# Zeus Discover - Brownfield Codebase Mapper

Map an existing (brownfield) codebase into deterministic Zeus artifacts under `.zeus/{version}/`.

## Preconditions

- `.zeus/{version}/` exists (default `main`).
- You can write to `.zeus/{version}/`.
- The target project root is readable.

## Inputs

- `--project-root <path>` (optional, default current workspace root)
- `--depth quick|auto|full` (optional, default `auto`)
- `--version vN` (optional, default `main`)

## Security rules

- Never read or print secret values from `.env*`, `*secret*`, `*credential*`, key/cert files.
- For sensitive files, only record existence and path.
- Output must contain no credentials or token-like strings.

## Deterministic workflow

1. **Collect structural inventory**: top-level directories, entry points, manifests, tests, TODOs.
2. **Collect dependency signals**: languages, frameworks, critical deps, external integrations.
3. **Build module map**: path, role, approximate LOC, dependencies, risk markers.
4. **Write artifacts**:
   - `codebase-map.json`
   - `existing-modules.json`
   - `tech-inventory.md`
   - `architecture.md`
5. **Validate** against schemas.
6. **Recommend next step**:
   - `zeus:init --import-existing` if config not aligned,
   - otherwise `zeus:brainstorm --feature <name>`.
