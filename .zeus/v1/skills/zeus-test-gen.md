# Zeus Test Gen — AI Test Flow Generation

Generate platform-specific end-to-end test scenarios from Zeus planning artifacts. AI authors the test cases; humans do not write scenarios manually.

## Preconditions

- `.zeus/{version}/task.json` exists and has at least one task.
- `.zeus/{version}/prd.json` exists and has at least one story.
- `.zeus/schemas/test-flow.schema.json` exists.
- `.zeus/{version}/config.json` exists.

## How to run

```bash
python .zeus/scripts/generate_tests.py --version main --platforms android,chrome,ios
```

## Deterministic workflow

1. **Check preconditions**.
2. **Show generation plan** (platforms, task count, output dir).
3. **Run `generate_tests.py`**.
4. **Validate generated files** with JSON parse check.
5. **Print coverage report** (scenarios per platform, task coverage %).
6. **Commit test files**.
7. **Write AI log**.

## Regeneration behavior

- By default, existing files are **skipped**.
- To regenerate, pass `--force`.
