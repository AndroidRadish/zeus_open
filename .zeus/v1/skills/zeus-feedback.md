# Zeus Feedback - Attribution and Evolution Trigger

Convert real-world feedback into traceable product decisions.

## Core rule

Never recommend roadmap actions before attribution analysis is complete.

## Preconditions

- `.zeus/{version}/task.json` exists.
- `.zeus/{version}/feedback/` is writable.
- `.zeus/{version}/evolution.md` is writable.

## Deterministic workflow

1. **Capture raw feedback** (natural language or structured metrics).
2. **Fill missing context** (time window, metric deltas, user segment).
3. **Optional metrics enrichment** via `collect_metrics.py`.
4. **Run attribution analysis** linking feedback to completed tasks and AI logs.
5. **Evaluate evolution signal** (structural gap, repeated unmet need, segment divergence).
6. **Write feedback artifact** to `.zeus/{version}/feedback/{YYYY-MM-DD-HHmmss}.json`.
7. **Append evolution timeline**.
8. **Write AI log**.
9. **Ask for decision**: evolve / backlog / ignore.
10. **Apply selected action**.
