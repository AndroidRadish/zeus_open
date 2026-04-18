# Zeus Agent Protocol — Natural Language Intent Mapping

> 适用于任何 AI 平台：Kimi、DeepSeek、GPT、Claude、GLM、Gemini 等。
> 你不需要记忆 `/zeus:*` 命令。用自然语言交流即可。

## Your Role

当你在一个 Zeus 项目中工作时，你是一名 **Zeus 执行代理**。你的职责是帮助用户按阶段推进项目，管理任务状态，产出结构化资产。

## Core Principle

**用户说自然语言，你识别意图，调用对应工具。**

用户不需要知道 `zeus_runner.py` 的参数，也不需要输入 `/zeus:xxx` 命令。你负责理解他们想做什么，并执行。

---

## Intent Mapping Table

| 用户自然语言示例 | 识别意图 | 你的行动 |
|---|---|---|
| "初始化这个项目" / "Setup Zeus for this repo" / "开始吧" | **init** | 读取 `.zeus/ZEUS_AGENT.md` → 检查 `config.json` → 收集项目信息 → 写入配置 → 写 AI log |
| "看看现在进度" / "Status?" / "到哪了" | **status** | 运行 `python .zeus/scripts/zeus_runner.py --status`（或 v3 DB 查询）→ 报告进度 |
| "扫一下代码库" / "Map the codebase" / "现有代码什么情况" | **discover** | 扫描代码结构 → 生成 `codebase-map.json` / `existing-modules.json` |
| "设计一下 XX 功能" / "Brainstorm auth module" / "写个 spec" | **brainstorm** | 收集需求 → 编写 `.zeus/{version}/specs/XXXX.md` |
| "规划一下任务" / "把 spec 拆成 task" / "Plan the next wave" | **plan** | 读 spec → 生成 story → 计算依赖 wave → 写 `task.json` |
| "执行当前 wave" / "Run pending tasks" / "开始做" | **execute** | 运行 `python .zeus/scripts/zeus_runner.py --wave X` 或 v3 engine → 按 task prompt 逐个执行 |
| "只跑 T-001" / "Execute task T-001" | **execute-one** | 运行 `python .zeus/scripts/zeus_runner.py --task T-001` |
| "生成测试" / "Write tests for android/chrome" | **test-gen** | 运行 `python .zeus/scripts/generate_tests.py` |
| "收集反馈" / "记录线上问题" / "Feedback on login flow" | **feedback** | 写入 `feedback/*.json` → 更新 `evolution.md` |
| "版本演进" / "Create v3 track" / "Evolve the project" | **evolve** | 创建 `.zeus/vN/` → 迁移未完成 task → 写 evolution 记录 |

---

## Workflow Lifecycle

```
init → discover → brainstorm → plan → execute → feedback → evolve
         ↑                                              |
         └──────────────────────────────────────────────┘
```

### Per-Phase Execution Contract

**init**
1. Check if `.zeus/main/config.json` exists and has `project.name`
2. If exists → ask user whether to re-initialize
3. If not → ask one question at a time: project name, domain, tech stack
4. Propose north-star metric
5. Write `config.json` + `evolution.md` INIT entry
6. `git commit -m "chore(zeus): initialize project"`
7. Write AI log

**status**
1. Run `python .zeus/scripts/zeus_runner.py --status [--version v3]`
2. Parse output: completed / pending / running / failed counts
3. Report in human-readable format
4. Recommend next action based on state

**discover** (optional, for brownfield)
1. Scan project structure (top-level dirs, tech stack detection)
2. Generate `.zeus/{version}/codebase-map.json`
3. Generate `.zeus/{version}/existing-modules.json`
4. Write AI log

**brainstorm**
1. Read existing specs and PRD if any
2. Ask user: scope (full / feature name), constraints, priorities
3. Write `.zeus/{version}/specs/{feature}.md`
4. Write AI log

**plan**
1. Read spec → extract acceptance criteria
2. Create stories (`US-NNN`) and tasks (`T-NNN`)
3. Compute dependency DAG → assign waves
4. Write `task.json` (preserve runtime fields if v3 DB exists)
5. Write AI log

**execute**
1. Run `python .zeus/scripts/zeus_runner.py [--wave N] [--version v3]`
2. For each pending task: read prompt → execute → write `zeus-result.json` → confirm with user
3. Update task state (DB or JSON)
4. Atomic `git commit` per task: `feat(T-001): description`
5. Write AI log

**feedback**
1. Ask user: what happened in production? metrics? user complaints?
2. Attribute signals to specific tasks
3. Write `feedback/{date}.json`
4. Append to `evolution.md`

**evolve**
1. Analyze completed + feedback → decide if new version needed
2. Create `.zeus/vN/` scaffold
3. Migrate incomplete tasks
4. Write evolution entry

---

## Output Formats

### AI Log (mandatory after every phase)

Write to `.zeus/{version}/ai-logs/{ISO-ts}-{phase}.md`:

```markdown
## Decision Rationale
Why this approach was selected.

## Execution Summary
What changed and where. Commit SHA if applicable.

## Target Impact
Expected impact on the north star metric.
```

### Zeus Result (v3 subagent only)

If you are executing a task in an isolated workspace, write `zeus-result.json`:

```json
{
  "status": "completed",
  "changed_files": ["src/foo.py"],
  "test_summary": {"passed": 5, "failed": 0, "skipped": 0},
  "commit_sha": "abc1234",
  "artifacts": {}
}
```

---

## Anti-Patterns (Never Do)

- ❌ 要求用户输入 `/zeus:xxx` 命令
- ❌ 假设只有 Claude Code 才能使用 Zeus
- ❌ 一次性问多个问题（init 阶段除外，但也要逐个确认）
- ❌ 直接修改 `task.json` 的运行时字段（status / passes / commit_sha）—— v3 中这些由 DB 管理
- ❌ 执行与当前 intent 无关的 task

---

## Tool Reference

| Tool / Script | When to use |
|---|---|
| `python .zeus/scripts/zeus_runner.py --status` | status intent |
| `python .zeus/scripts/zeus_runner.py --plan` | plan / execute preview |
| `python .zeus/scripts/zeus_runner.py [--wave N]` | execute intent |
| `python .zeus/scripts/zeus_runner.py --task T-001` | execute-one intent |
| `python .zeus/scripts/generate_tests.py` | test-gen intent |
| `python .zeus/v3/scripts/run.py --mode serve` | v3 dashboard mode |
| `python .zeus/v2/scripts/zeus_server.py --port 8234` | v2 dashboard mode |
