# Zeus Status - Global Health Report

Render a deterministic snapshot across active versions and recommend the next best action.

## How to run

```bash
python .zeus/scripts/zeus_runner.py --status
```

## Deterministic workflow

1. **Load project state**: config, prd, task, feedback, evolution, recent AI logs.
2. **Compute metrics**: story totals, task completion %, current/next pending wave.
3. **Select next-action recommendation**:
   - missing config -> `zeus:init`
   - codebase map exists but config not imported -> `zeus:init --import-existing`
   - no tasks -> `zeus:brainstorm --full`
   - pending tasks -> `zeus:execute`
   - tasks complete but no feedback -> `zeus:feedback`
   - evolution signal unresolved -> `zeus:evolve`
   - stable -> `zeus:brainstorm --feature <next-feature>`
4. **Render output** with clear version-by-version progress.
