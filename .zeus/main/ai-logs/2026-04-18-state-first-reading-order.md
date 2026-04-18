# AI Log: State-First Reading Order Fix

**Date**: 2026-04-18
**Task**: Fix agent reading order cognitive bias — enforce "state before declaration"
**Commit**: `1bcfed2`

## Problem

External agent feedback revealed that AI agents read `task.json` before `state.db` because text files are easier to read than SQLite databases. This violates the v3 core principle that the database is the single source of truth.

## Root Cause

Tool convenience bias: agents prefer `ReadFile` over `sqlite3` queries, leading them to treat `task.json` (a static planning artifact) as authoritative instead of `state.db` (runtime truth).

## Changes

### 1. AGENTS.md — 开工流程 step 5

Rewrote to enforce:
- **1st**: Query `state.db` (runtime truth)
- **2nd**: Read actual code (real logic)
- **3rd**: Read `task.json` (design intent only)

### 2. `.zeus/ZEUS_AGENT.md` — New "Reading Order" section

Added explicit table with priority ranking, plus:
- Concrete v3 example (`python .zeus/v3/scripts/run.py --status`)
- Meta-cognitive analogy (doctor checking symptoms vs running tests)
- Clear distinction: `task.json` = declaration, `state.db` = truth

## Validation

- `python .zeus/scripts/zeus_runner.py --status` → OK
- `git diff --cached --stat` → 2 files, 32 insertions(+), 8 deletions(-)
- Commit message includes reasoning and references

## Impact

This is a meta-cognitive fix: it changes *how* agents think about information hierarchy, not just *what* they read. By making the rule explicit and providing a concrete example, future agents are less likely to fall into the "text is easier" trap.
