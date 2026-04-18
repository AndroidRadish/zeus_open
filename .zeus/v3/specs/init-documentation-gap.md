# Feedback: v3 Init Documentation Gap

> Source: Agent execution feedback (2026-04-18)
> Status: **FIXED** in commits after `ab28461`

---

## Problem Statement

When an Agent is asked to "initialize a Zeus v3 project", the existing documentation led to incomplete or incorrect initialization because the v3-specific steps were scattered, implicit, or missing.

---

## Root Cause 1: AGENTS.md init description stuck in v1/v2 mode

**Location**: AGENTS.md line 224 (before fix)

The intent mapping table said:

> "初始化项目" / "Setup Zeus" / "开始吧" | **init** | 主会话直接执行（单轮问答）

But it did **not** list the v3-specific initialization steps:

1. Create `.zeus/v3/` directory structure
2. Write `config.json`
3. Write initial `task.json`
4. Run `python run.py --import-only` to generate `state.db`

Step 4 was completely missing. The Agent had no way to know that `--import-only` is mandatory for v3 cold-start.

**Fix**: AGENTS.md "开工流程" step 3 now explicitly lists the v3 init sequence, including `--import-only` as mandatory.

---

## Root Cause 2: v3 README only had migration guide, no bootstrap guide

**Location**: `.zeus/v3/README.zh-CN.md` lines 354-356 (before fix)

The README said:

> 1. 将 v2 的 `task.json` 复制到 `.zeus/v3/task.json`
> 2. 运行 `python run.py --import-only` 将运行时状态迁移到 v3 数据库
> 3. 启动调度器 / 工作器或 Docker Compose 集群

This is a **migration guide** (v2 → v3), not a **bootstrap guide** for a brand-new project. For new projects, the docs did not say you need to run `--import-only` to create `state.db` from scratch.

**Fix**: Both `.zeus/v3/README.md` and `.zeus/v3/README.zh-CN.md` now have a "Bootstrap a New Project" section with the full 5-step cold-start flow.

---

## Root Cause 3: AGENTS.md "Definition of Done" contradicted v3 state rules

**Location**: AGENTS.md line 208 (before fix)

> - [ ] `task.json` 已更新（`passes: true`, `commit_sha` 已填）

But the same file line 62 said:

> **禁止直接修改 task.json 的运行时字段（passes/status/commit_sha），这些字段在 v3 中已废弃**

This is a direct contradiction. An Agent reading line 208 would try to edit `task.json`, then read line 62 and be confused about whether it's allowed.

**Fix**: "完成定义" now has separate checklist items for v2/main (`task.json`) and v3 (`state.db` via `--status`).

---

## Timeline Verification

- `awesome-cloudbase-examples` `state.db` creation time: 2026-04-18 15:01
  - Created implicitly by `--status` when importer detected no database.
  - This behavior is **implicit**, and AGENTS.md did not tell the Agent "run `--import-only` after init to create `state.db`".
- `coffee_agents` problem: v3 framework was not even copied over, so no `state.db` could exist.

---

## Files Changed

| File | Change |
|------|--------|
| `AGENTS.md` | Added v3 init steps to 开工流程; split "完成定义" into v2/v3 versions |
| `.zeus/v3/README.md` | Added "Bootstrap a New Project" section |
| `.zeus/v3/README.zh-CN.md` | Added "从零初始化新项目" section |
