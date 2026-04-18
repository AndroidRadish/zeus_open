# AGENTS.md — zeus-open

> 通用 AI-CLI 版 Zeus 框架快速开始
> 适用于 **Kimi Code、GLM、DeepSeek、GPT/Codex、Gemini** 等任何没有 `claude` CLI 的 AI 编程助手。

---

## 🧠 动手前四问（Think Before Coding）

在编写任何代码之前，必须显式回答以下问题。
如果答案是"不确定"或"有歧义"，**必须先提问，不要直接实现**。

1. **我做了什么假设？**
   - 用户需求中哪些信息是我推测的而非明确给出的？
   - 如果推测可能出错，我会先提问。

2. **是否存在多种理解方式？**
   - 如果指令有歧义，列出所有可能的解释，让用户（或调度器）选择。
   - **禁止在存在歧义时默默选一个然后开始做。**

3. **有没有更简单的做法？**
   - 如果我发现一个更简单的方案能达到同样效果，必须主动提出。
   - 不要为了实现"更好的架构"而增加不必要的复杂度。

4. **我对哪里感到困惑？**
   - 如果某个依赖、接口或业务逻辑不清楚，必须停下来提问。
   - 禁止带着困惑蒙混过关。

---

## 🚀 开工流程

**写代码前必须按顺序执行：**

0. 回答上面的「动手前四问」（如有歧义/困惑，先向用户/调度器提问）
1. `pwd` — 确认当前在项目根目录
2. 读取 `.zeus/ZEUS_AGENT.md` — 确认当前支持的 Zeus Agent 协议版本
3. **优先查运行时状态（真相），后看静态配置（声明）**
   - **v3**：先运行 `python .zeus/v3/scripts/run.py --status` 查看 `state.db`
     - 如果返回 0 task → 系统从未启动过，需要执行初始化（见步骤 4）
     - 如果返回 task 数据 → 以 DB 为准，task.json 仅供参考
   - **v2 / main**：`python .zeus/scripts/zeus_runner.py --status`
   - **原则**：`state.db` / `zeus_runner.py --status` 是**唯一真相**；`task.json` 只是人类声明，可能被遗忘、未加载或过期
4. **如果是 v3 新项目初始化**，按以下顺序执行：
   - 创建 `.zeus/v3/` 目录结构（`config.json` + `task.json`）
   - 运行 `python .zeus/v3/scripts/run.py --import-only` 生成 `state.db`
   - 验证：`python .zeus/v3/scripts/run.py --status` 能正常输出
   - **注意**：`--import-only` 是 v3 初始化的必需步骤，不能省略
5. 读取 `claude-progress.md`（或 `.zeus/main/evolution.md`）— 了解最新状态
6. `git log --oneline -5` — 查看最近提交
7. 如果基础验证失败，先修复基础状态

⚠️ **如果状态异常，先修复，不要继续！**

> **自然语言交互优先**：用户不会输入 `/zeus:xxx` 命令。你应该根据用户的自然语言描述识别意图（init / status / discover / brainstorm / plan / execute / feedback / evolve），然后调用对应工具。具体映射参考 `.zeus/ZEUS_AGENT.md`。

---

## 📋 工作规则

- **一次只做一个功能（一个 task）**
- 不要因为"代码已经写了"就把功能标记为完成
- 实现过程中不要悄悄改弱验证规则
- 优先依赖仓库里的持久化文件，而不是聊天记录
- **v3 状态管理规则**：
  - `.zeus/v3/state.db` 是唯一事实来源（task status、passes、commit_sha、quarantine、events）
  - `.zeus/v3/task.json` 只是静态计划导出产物，修改它不会自动同步到数据库
  - 需要通过 API/CLI（`python .zeus/v3/scripts/run.py --export-plan`）或 Dashboard 操作状态
  - 子 Agent 完成工作后必须写入 `zeus-result.json`，Worker 自动将结果同步到数据库
  - **禁止直接修改 task.json 的运行时字段（passes/status/commit_sha），这些字段在 v3 中已废弃**

### 防过度延伸
- 如果发现"需要顺便做"的其他功能：
  1. 记录下来
  2. 添加到 `task.json` 或 `feature_list.json`
  3. **不要开始做**
  4. 继续完成当前 task

### v3 高并发任务规划（DAG 设计）
> 目标：让 WorkerPool 的每个 slot 都有活干，而不是 3 个 worker 只有 1 个在跑。

- **每波至少 2-3 个独立任务**：Wave 1 应该是多个无依赖的并行任务（如 DB schema + API skeleton + config loader），而不是单个"初始化"大任务
- **扇形依赖优于链式依赖**：
  - ❌ 反模式：`T-001 → T-002 → T-003 → T-004`（4 个 wave，并发度=1）
  - ✅ 推荐：`T-001/T-002/T-003` 并行 → `T-004/T-005/T-006` 并行 → `T-007` 集成
- **大任务横向拆分**：如果一个 task 预计需要改 10+ 个文件，拆成 2-3 个按模块划分的独立 task，共用同一前置依赖
- **验证方式**：`zeus_runner.py --plan --version v3` 检查每个 wave 的 task 数量；如果某个 wave 只有 1 个 task，考虑拆分或调整依赖
- **参考模板**：`.zeus/v3/templates/high-concurrency-task-plan.json`

---

## ✂️ 代码简洁性三原则（Simplicity First）

**默认规则：用最小代码解决当前问题。不为未来做 speculation。**

### 原则 1：不超需求加功能
- 只实现明确要求的内容，以及为了该功能"能跑通"所必需的最小配套代码。
- 不要提前实现"以后可能用得上的"配置项、开关、通用接口。

### 原则 2：不为一行代码建抽象
- 如果一个抽象（类、接口、策略模式、工厂）只为当前这一个用例服务，不要建。
- 直接写函数。当同一个逻辑真的出现了第 3 次重复时，再考虑提取。

### 原则 3：不写不可能触发的错误处理
- 不要为"理论上可能但实际永远不会发生"的情况写复杂的防御代码。
- 如果无法判断某个异常是否真会发生，先实现最简单的路径，并在注释中标记：`# TODO: 评估此处是否需要处理 X 异常`。

### 自检问题
在提交任何代码前，问自己：
> "如果一位资深工程师 review 这段代码，他会不会说'这太过度设计了'？"
> 如果答案是"会"，立即简化。

---

## 🔪 手术式修改规范（Surgical Changes）

**核心原则：只碰必须碰的。只清理自己制造的。**

### 规则 1：禁止顺手改进相邻代码
当任务要求"修复 A"时：
- ❌ 不要重构与 A 无关的函数 B
- ❌ 不要为相邻的类添加类型提示
- ❌ 不要修改无关的注释和文档字符串
- ❌ 不要调整引号风格、缩进或换行

### 规则 2：匹配现有风格
即使你认为另一种风格更好，也要匹配当前文件的：
- 引号风格（`'` vs `"`）
- 类型提示使用习惯（有或无）
- 异常处理方式
- 命名惯例

### 规则 3：orphan 清理
- 如果你的修改导致某些 import / 变量 / 函数不再被使用 → **必须删除**
- 预先存在的死代码 / 未使用 import → **不要动**（除非 task 明确要求清理）

### 规则 4：diff 自检
在标记任务完成之前，必须在脑海中检查：
> "每一行改动是否都能直接追溯到用户的这个请求？"
> 如果有任何一行不能，撤销它。

---

## 🎯 验证循环工作法（Goal-Driven Execution）

**核心原则：把指令转化为可验证的目标，循环直到通过。**

### 指令转换表

| 收到的指令 | 必须转化成的目标 |
|-----------|-----------------|
| "修复 bug" | 1) 写复现测试 → 2) 确认失败 → 3) 修复 → 4) 确认通过 |
| "添加功能" | 1) 明确输入输出 → 2) 写测试 → 3) 实现 → 4) 测试通过 |
| "重构 X" | 1) 记录现有通过数 → 2) 重构 → 3) 确保通过数不变 |
| "优化性能" | 1) 测量基准 → 2) 优化 → 3) 再次测量确认提升 |

### 测试范围矩阵

**禁止不加区分地跑全量测试。** 根据 task 的修改范围，只跑相关验证：

| 修改类型 | 必须跑的验证 | 不需要跑的验证 |
|---------|-------------|---------------|
| **纯前端 / Dashboard / UI** | 前端 `npm run build` 通过；如有前端单测则跑前端测试 | 不需要跑后端 Python 全量测试（core/api/concurrency） |
| **纯后端 API / 核心逻辑** | 相关后端测试文件通过（如 `test_v3_api.py`）；如改动调度器/工作器/队列，再跑 `test_v3_core.py` | 不需要跑前端构建（除非改动 static 资源） |
| **DB model / store 变更** | `test_v3_core.py` 中涉及 store 的测试；如有 schema 变更需确认迁移 | 不需要跑并发/压力测试，除非改动的是并发控制 |
| **跨前后端的全栈功能** | 前端构建 + 相关后端测试 | 不需要跑与功能无关的测试模块 |
| **文档 / 配置 / 脚本** | 最小可用性验证（如脚本语法检查、配置文件 JSON 合法） | 不需要跑单元测试 |

**判断原则**：如果某个测试与当前 task 的改动没有**直接因果关系**，就不要跑它。

### 多步骤任务的计划格式

对于涉及多个文件的复杂任务，在动手前必须给出简要计划：

```
1. [步骤描述] → 验证：[如何确认这一步成功]
2. [步骤描述] → 验证：[如何确认这一步成功]
3. [步骤描述] → 验证：[如何确认这一步成功]
```

**禁止行为：**
- ❌ "我先看看代码，然后改改看"
- ❌ 一次性修改 5 个文件后再统一测试
- ❌ 用"应该可以了"代替实际验证
- ❌ **不加区分地跑全量测试 suite**

---

## 🔄 Zeus 工作流

```
init → discover → brainstorm → plan → execute → feedback → evolve
```

### 常用命令

| 目标 | 命令 |
|---|---|
| 查看全局状态 | `python .zeus/scripts/zeus_runner.py --status` |
| 查看执行计划 | `python .zeus/scripts/zeus_runner.py --plan` |
| 执行当前 wave | `python .zeus/scripts/zeus_runner.py` |
| 执行指定 wave | `python .zeus/scripts/zeus_runner.py --wave 2` |
| 执行指定 task | `python .zeus/scripts/zeus_runner.py --task T-001` |

---

## ✅ 完成定义

一个 task 只有在以下条件**全部满足**时才算完成：

- [ ] 目标行为已经实现
- [ ] **修复类 task**：已先写复现测试，测试从"失败"变"通过"
- [ ] **功能类 task**：已写对应测试/可运行脚本，且通过
- [ ] **相关验证通过**（根据「测试范围矩阵」只跑必要的验证，禁止不加区分跑全量测试）
- [ ] Lint / 类型检查无错误
- [ ] **v2 / main**：`task.json` 已更新（`passes: true`, `commit_sha` 已填）
- [ ] **v3**：`state.db` 已同步（通过 `python .zeus/v3/scripts/run.py --status` 确认 task 状态为 completed，且 `zeus-result.json` 已写入 workspace）
- [ ] AI log 已写入 `.zeus/main/ai-logs/`
- [ ] 代码已 `git commit`（格式：`feat(T-001): description`）
- [ ] `zeus_runner.py --status` 显示正常
- [ ] **diff 自检通过**：每一行改动都能直接追溯到当前 task 需求

---

## 🎭 Agent 映射与自然语言意图

Zeus 不再依赖 `/zeus:*` 斜杠命令。用户通过自然语言表达意图，Agent 识别后执行对应阶段。

### 意图识别表

| 用户说 | 识别意图 | 推荐处理方式 |
|---|---|---|
| "初始化项目" / "Setup Zeus" / "开始吧" | **init** | 主会话直接执行（单轮问答） |
| "看看进度" / "Status?" / "到哪了" | **status** | 主会话直接执行（调用 runner --status） |
| "扫一下代码" / "Map codebase" | **discover** | 子 Agent 探索（Kimi: `Agent(explore)`） |
| "设计 XX 功能" / "写个 spec" | **brainstorm** | 子 Agent 规划（Kimi: `Agent(plan)`） |
| "拆一下任务" / "Plan next wave" | **plan** | 子 Agent 规划（Kimi: `Agent(plan)`） |
| "执行当前 wave" / "Run tasks" | **execute** | 子 Agent 编码（Kimi: `Agent(coder)`） |
| "生成测试" / "Write tests" | **test-gen** | 子 Agent 编码（Kimi: `Agent(coder)`） |
| "记录反馈" / "Production issue" | **feedback** | 主会话或子 Agent 分析 |
| "版本演进" / "Create v3" | **evolve** | 主会话直接执行 |

### 传统 Agent 角色（内部实现参考）

- **zeus-researcher** → 只读探索（代码库扫描、状态检查）
- **zeus-planner** → 规划拆解（spec → story → task → wave）
- **zeus-executor** → 执行与验证（代码实现、测试、commit）
- **zeus-analyst** → 反馈归因（信号收集、演化判定）
- **zeus-tester** → 测试生成（平台测试流程 JSON）
- **zeus-docs** → 文档一致性（双语对齐、格式校验）

---

## 🏁 收尾流程

**结束会话前必须执行：**

1. 更新 `claude-progress.md`（或 `evolution.md`）
2. **v2 / main**：更新 `task.json`（`passes` / `commit_sha`）
3. **v3**：确认 `state.db` 已同步（通过 `python .zeus/v3/scripts/run.py --status` 或 Dashboard 验证），**禁止直接修改 `task.json` 的运行时字段**
4. 代码审查和验证
5. `git commit`
6. 确认状态检查命令显示正常

---

## 🆘 遇到问题时

### 如果 runner 报错
1. 检查 `.zeus/main/task.json` 格式是否合法 JSON
2. 检查 `.zeus/main/config.json` 是否存在且包含 `project.name`
3. 查看 `ai-logs/` 中最近一次的执行记录

### 如果遇到 blocker
1. 停止当前工作
2. 在 `task.json` 中标记相关 task 的 `passes: false` 并添加备注
3. 选择另一个独立 task 继续
