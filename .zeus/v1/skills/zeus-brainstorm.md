# Zeus Brainstorm - Design-First Planning Loop

Transform broad requests into approved design specs before implementation.

## Guardrails

1. Never skip design, even for "small" features.
2. Ask exactly one clarifying question at a time.
3. Propose 2-3 options before selecting final architecture.
4. Require explicit user approval before planning artifacts are generated.

## Preconditions

- `.zeus/main/config.json` exists and is valid.
- Target version folder exists.
- You can read prior artifacts (`prd`, `task`, `roadmap`, `specs`, `ai-logs`).

## Deterministic workflow

1. **Silent context exploration**: summarize baseline, overlaps, constraints.
2. **Scope fit check**: classify as single feature, multi-feature bundle, or multi-system program.
3. **Clarifying question loop**: focus on success criteria, constraints, user roles, non-goals.
4. **Approach options (2-3)**: present trade-offs tied to north star impact.
5. **Section-by-section design review**: architecture, components, data contracts, errors, tests, acceptance criteria.
6. **Write spec file** to `.zeus/{version}/specs/{YYYY-MM-DD}-{topic}-design.md`.
7. **Spec self-review**: scan for TODO/TBD, consistency, scope fit.
8. **User review gate**: wait for explicit approval.
9. **AI log write**.
10. **Hand-off to planning**: trigger `zeus:plan --spec <file> --version <version>`.
