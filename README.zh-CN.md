# Zeus - AI 项目演化操作系统

[![语言](https://img.shields.io/badge/language-English%20%7C%20中文-blue)](README.md)
[![工作流](https://img.shields.io/badge/workflow-init%E2%86%92brainstorm%E2%86%92plan%E2%86%92execute%E2%86%92feedback-green)](#工作流)
[![适配](https://img.shields.io/badge/adapter-universal-orange)](#通用适配说明)
[![状态](https://img.shields.io/badge/status-active-success)](#)
[![许可证](https://img.shields.io/badge/license-MIT-lightgrey)](#许可证)

用于长期项目交付的结构化、版本化 AI 研发框架。

Zeus 核心能力：
- 可追踪的规划资产（`spec`、`prd`、`task`、`roadmap`）
- 基于依赖波次的执行与原子提交
- 从线上反馈到版本演化的强制归因闭环

语言切换：[English](README.md) | [简体中文](README.zh-CN.md)

## 快速开始

Zeus 支持**所有 AI 平台**（Kimi、DeepSeek、GPT、Claude、GLM、Gemini）。不需要特殊的 CLI 或斜杠命令——用自然语言跟你的 AI 交流即可。

### 1) 一次性设置

```bash
# 安装 commit message hook
cp .zeus/hooks/commit-msg .git/hooks/commit-msg
# Windows 用户参见 docs/init-harness.md 中的 PowerShell hook 安装说明
```

### 2) 开始对话

告诉你的 AI 你想做什么。例如：

| 你说 | Zeus 会 |
|---|---|
| "初始化这个项目" / "Setup Zeus" | 创建 `.zeus/main/config.json`，设置北极星指标 |
| "看看现在进度" / "Status?" | 报告已完成 / 待执行 / 运行中任务 |
| "扫一下代码库" / "Map codebase" | 生成 `codebase-map.json`（老项目适用） |
| "设计一下鉴权模块" / "Brainstorm auth" | 写 spec 到 `.zeus/main/specs/auth.md` |
| "规划一下任务" / "Plan next wave" | 将 spec 拆为 story、task、wave |
| "执行当前 wave" / "Run tasks" | 按 wave 逐个执行任务 |
| "生成安卓测试" / "Generate android tests" | 创建平台测试流程 JSON |

AI 会读取 `.zeus/ZEUS_AGENT.md` 学习 Zeus 协议，自动处理后续步骤。

### 3) 脚本 / CI 用法

```bash
# 查看状态
python .zeus/scripts/zeus_runner.py --status

# 查看计划
python .zeus/scripts/zeus_runner.py --plan

# 执行当前 wave
python .zeus/scripts/zeus_runner.py

# 执行指定 wave（v3）
python .zeus/v3/scripts/run.py --wave 2 --max-workers 3
```

#### v3 多 Agent 框架（Beta）

全新的数据库化、水平可扩展执行引擎，支持实时 SSE 控制台与 Docker Compose 部署：
详见 [`.zeus/v3/README.md`](.zeus/v3/README.md)。

#### v2 并行模式与 Web 控制台

如需并行波次执行和可视化控制台，启动 v2 后端并打开零构建 Web UI：

```bash
# 启动服务（可指定项目目录）
python .zeus/v2/scripts/zeus_server.py --port 8234 --project-dir .

# 打开控制台
# http://localhost:8234/web
```

Zeus 的 `.zeus/ZEUS_AGENT.md` 是所有 AI 平台的通用交互协议。将项目路径提供给 AI 后，它会自动识别 Zeus 工作流并按自然语言指令执行。

v1 时代的 skill 文件已归档至 `.zeus/v1/skills/`，如需参考旧版指令格式可查阅。

## v2 新特性

- **零构建 Web 控制台** — Vue 3 + Tailwind CSS，暗色工业风玻璃拟态界面，完整中文适配。
- **阶段（Phase）视图** — 将里程碑与 Wave 分组为可读的交付阶段（P-001、P-002…），支持进度追踪。
- **多语言支持** — 任务标题与描述支持中英一键切换。
- **全局调度器** — 打破 Wave 执行锁，按全局依赖就绪状态跨 Wave 调度任务，失败任务自动进入隔离区。
- **Agent 协作** — 基于 Mailbox 协议的 Agent 点对点通信，支持执行中实时协作。
- **Agent 独立日志** — 每个 Agent 拥有独立的日志目录（`activity.md` + `reasoning.jsonl`），便于溯源与调试。
- **一键全局运行** — 直接在 Web UI 中启动全局调度器。
- **子代理分发器** — 支持将任务执行委托给 `kimi --print` 或 `claude -p`，实现真正的无人值守多 Agent 运行。
- **多版本切换** — 在 Web UI 中直接切换 `main`、`v2` 及未来版本。
- **项目选择器** — 无需重启服务，即可在控制台中打开并管理其他本地 Zeus 项目。

### v3 新特性（Beta）

- **数据库化状态管理** — 基于 SQLite/PostgreSQL 的异步任务状态存储，彻底替代文件锁
- **调度-执行分离** — 调度器与 Worker 池解耦，支持水平扩展
- **Vite + Vue 3 控制台** — 组件化单页应用，采用 Pinia 全局状态管理，SSE 实时推送
- **Metrics 与可观测性** — 瓶颈检测、阻塞链分析、OpenTelemetry 链路追踪
- **热重载** — `serve` 模式下自动监听 `task.json` 变更并重新导入，无需重启服务
- **Docker 与 K8s 就绪** — 支持 `api` / `scheduler` / `worker` 多容器拆分，Redis 队列后端
- **Wave 级别过滤** — `run.py --wave N` 和 `zeus_runner.py --wave N` 仅执行指定 wave 的任务
- **工作区性能优化** — `node_modules`、`.pytest_cache`、`venv` 等大目录不再被复制到隔离工作区，prepare 耗时从数秒降至毫秒级
- **高并发规划模板** — `.zeus/v3/templates/high-concurrency-task-plan.json` 提供最大化 Worker 并行的 DAG 参考（每波 ≥2 个独立任务）

详见 [`.zeus/v3/README.md`](.zeus/v3/README.md)。

### 当前开发状态

| 里程碑 | 状态 | 任务 |
|---|---|---|
| M-008 — Web UI 与多语言 | ✅ 已完成 | T-023 ~ T-025 |
| M-009 — 阶段（Phase）层 | ✅ 已完成 | T-026 ~ T-029 |
| M-010 — 全局调度器与 Agent 协作 | ✅ 已完成 | T-030 ~ T-034 |
| v3 Phase 1 — 基础架构与队列 worker | ✅ 已完成 | T-V3-001 ~ T-V3-003 |
| v3 Phase 2 — 实时控制台与控制平面 | ✅ 已完成 | T-V3-015、T-V3-018、T-V3-019、T-V3-021、T-V3-026 |
| v3 Phase 3 — 性能优化与规划模板 | ✅ 已完成 | T-V3-034 ~ T-V3-036 |

## 工作流

Zeus 遵循确定性的、由反馈驱动的生命周期：

```
init → discover → brainstorm → plan → execute → feedback → evolve
         ↑                                              |
         └──────────────────────────────────────────────┘
```

1. **init** — 初始化北极星指标与项目配置。
2. **discover** *（可选）* — 为老项目映射现有代码库。
3. **brainstorm** — 设计规范并产出 `.zeus/{version}/specs/*.md`。
4. **plan** — 将规范转换为可执行的故事、任务与路线图。
5. **execute** — 按依赖波次运行任务（v2 支持全局调度与并行 Agent）。
6. **feedback** — 采集生产信号并归因到具体任务。
7. **evolve** — 基于验证后的学习创建新版本轨道（v2、v3…）。

> **说明：** 旧的 SVG 流程图已退役。上面的文字流程图反映了当前通用工作流。

## 自然语言意图

不需要斜杠命令。直接告诉你的 AI 你想做什么。

| 意图 | 示例说法 | 执行内容 |
|---|---|---|
| **init** | "初始化这个项目"、"Setup Zeus"、"开始吧" | 创建配置、北极星指标、演化基线 |
| **status** | "看看进度"、"Status?"、"到哪了" | 报告任务完成数、待执行队列、下一步建议 |
| **discover** | "扫一下代码"、"Map the codebase"、"现有代码什么情况" | 生成代码地图与模块清单 |
| **brainstorm** | "设计鉴权流程"、"写个 spec"、"Brainstorm payments" | 写结构化 spec 到 `.zeus/{version}/specs/` |
| **plan** | "拆一下任务"、"Plan next wave"、"把 spec 转成 task" | 创建 story、task、依赖 wave，写 `task.json` |
| **execute** | "执行当前 wave"、"Run pending"、"开始做" | 运行调度器 + Worker 池，按 task prompt 执行 |
| **execute-one** | "只做 T-001"、"Run this task" | 按 ID 执行单个任务 |
| **test-gen** | "生成测试"、"写安卓测试" | 创建平台测试流程 JSON |
| **feedback** | "登录很慢"、"用户反馈"、"Record issue" | 将信号归因到 task，更新演化记录 |
| **evolve** | "创建 v3"、"版本演进"、"进入下一阶段" | 创建新版本轨道，迁移未完成任务 |

AI 以 `.zeus/ZEUS_AGENT.md` 为操作手册，知道调用哪些脚本、写入哪些文件。

## 目录结构

```text
.zeus/
  main/
    config.json
    prd.json
    task.json
    roadmap.json
    evolution.md
    feedback/
    ai-logs/
    specs/
    tests/
      android.test.json   ← AI 自动生成，不要手动编辑
      chrome.test.json
      ios.test.json
  v1/                    ← v1 时代归档
    skills/              ← skill 手册（已从根目录移入）
    scripts/             ← 工具脚本
    docs/
    logs/
  v2/ ... vN/
  v3/
    templates/           ← 高并发任务规划模板
    scripts/
    web/
  schemas/
    config.schema.json
    codebase-map.schema.json
    existing-modules.schema.json
    prd.schema.json
    task.schema.json
    roadmap.schema.json
    spec.schema.json
    feedback.schema.json
    ai-log.schema.json
    test-flow.schema.json
  scripts/
    zeus_runner.py
    generate_tests.py
    collect_metrics.py
  hooks/
    commit-msg
    commit-msg.ps1

assets/
  zeus-workflow.en.svg
  zeus-workflow.zh-CN.svg
```

## v3 控制台

Zeus v3 提供基于 Vite + Vue 3 的实时控制台，由内置 FastAPI 服务器驱动：

- **概览** — 实时指标、任务列表、SSE 事件流
- **任务** — 内联操作（重试 / 取消 / 暂停 / 恢复 / 隔离 / 日志 / 详情）
- **任务详情抽屉** — 滑出面板展示完整字段、依赖关系与活动日志
- **事件** — 可搜索的实时 SSE 事件历史，含进度高亮
- **指标** — 瓶颈分析、阻塞依赖链、单任务耗时统计
- **图** — 任务依赖图（SVG / Mermaid / ECharts）
- **阶段** — 阶段与里程碑的增删改查，支持下钻到任务列表
- **邮箱** — AgentBus 点对点消息收件箱与发送表单
- **控制** — 调度器 / 工作器管理与一键全局运行
- **热重载** — `serve` 模式下自动重新导入 `task.json` 变更

启动服务：

```bash
python .zeus/v3/scripts/run.py --mode serve --project-root . --host 0.0.0.0 --port 8000
```

然后访问 `http://127.0.0.1:8000/dashboard`。

完整 v3 指南请见 [`.zeus/v3/README.zh-CN.md`](.zeus/v3/README.zh-CN.md)。

## v2 控制台

Zeus v2 由 `zeus_server.py`（FastAPI）驱动零构建 Web UI：

- **仪表盘** — 实时 wave 进度、待完成/已完成统计、任务校验状态。
- **阶段（Phases）** — 以里程碑为中心的交付批次，支持按阶段过滤 Wave。
- **里程碑（Milestones）** — 可展开的里程碑卡片，含任务列表与进度条。
- **全局执行** — 跨 Wave 运行任务列表、待执行队列、失败隔离区（quarantine），支持一键启动调度器。
- **Agent 协作** — 基于 Mailbox 协议的 Agent 间实时消息流。
- **Agent 日志** — 按 Agent 筛选的独立日志浏览器（`activity.md`、`reasoning.jsonl`）。
- **版本切换** — 自动发现 `.zeus/{version}/task.json` 下的所有版本。
- **打开项目** — 通过 UI 动态切换其他 Zeus 项目目录，无需重启服务。

启动服务：

```bash
python .zeus/v2/scripts/zeus_server.py --port 8234 --project-dir .
```

然后访问 `http://localhost:8234/web`。

GUI 快速上手指南请见 [`docs/zeus-v2-gui-quickstart.md`](docs/zeus-v2-gui-quickstart.md)。

## 部署

### 一键启动脚本

```bash
# Linux / macOS（本机 Python）
./start.sh --port 8234

# Windows（本机 Python）
.\start.ps1 -Port 8234

# Docker 构建并运行（全平台）
./start.sh --build
.\start.ps1 -Build
```

### Docker（手动）

```bash
# 构建镜像
docker build -t zeus-open:v2 .

# 运行容器
docker run --rm -p 8234:8234 -v $(pwd):/app zeus-open:v2
```

容器暴露 `8234` 端口，并挂载当前目录，因此 `.zeus/v2/task.json` 和项目文件在宿主机上仍可编辑。

## 老项目接入（Brownfield）

针对已有代码库，直接告诉你的 AI：

> "扫一下现有代码，然后用发现的结果初始化 Zeus。"

AI 会：
1. 运行 **discover** 扫描代码，生成 `codebase-map.json`
2. 运行 **init**，将发现的内容预填入配置
3. 问你确认或修改推断值
4. 继续 **brainstorm** → **plan** → **execute**

或分步执行：
```bash
# 发现
"扫描项目结构并创建代码地图"

# 初始化
"用扫描结果初始化 Zeus"

# 设计 + 规划
"设计鉴权模块并拆解任务"

# 执行
"运行已规划的任务"
```

该流程对新项目保持兼容：不运行 discover 时，原有 init -> brainstorm -> plan -> execute 路径不变。

## Agent 模型

Zeus 在 `.claude/agents` 下定义阶段化代理：

- `zeus-researcher`：上下文探索与依赖检查
- `zeus-planner`：spec 拆解与执行资产构建
- `zeus-executor`：wave 执行编排与质量门禁
- `zeus-analyst`：反馈归因与演化判定
- `zeus-docs`：双语文档一致性与可读性校验
- `zeus-tester`：AI 测试用例编写（android / chrome / ios）

推荐委派关系：
- brainstorming -> researcher
- plan -> planner
- execute -> executor
- 测试生成 -> tester（通过 `generate_tests.py`）
- feedback/evolve -> analyst
- docs quality -> docs

## 测试

Zeus 使用 AI 自动生成测试流程。**不要手写测试用例。**

告诉你的 AI：
> "为 android、chrome、ios 生成测试"

或直接运行：
```bash
# 所有平台
python .zeus/scripts/generate_tests.py --version main --platforms android,chrome,ios

# 单个平台
python .zeus/scripts/generate_tests.py --version main --platforms chrome

# 强制重新生成
python .zeus/scripts/generate_tests.py --version main --force
```

生成的文件位于 `.zeus/{version}/tests/{platform}.test.json`，遵守 `.zeus/schemas/test-flow.schema.json` 结构规范。

测试执行直接使用各平台原生工具链：

| 平台 | 工具链 |
|---|---|
| Android | `adb shell` |
| Chrome | `chrome-cli` / Chrome DevTools Protocol |
| iOS | `xcrun simctl` / `libimobiledevice` |

plan 完成后可以要求 AI 生成测试；execute 每个 wave 完成后也可选择刷新测试流程。

## AI 日志约定

每次 skill 执行必须在 `ai-logs/` 追加一条 markdown：

```markdown
## Decision Rationale
Why this approach was selected.

## Execution Summary
What changed and where.

## Target Impact
Expected impact on the north star metric.
```

## Commit 规范

```text
feat(T-003): implement user registration form
fix(T-007): correct session token expiry
docs(zeus): update prd from auth-design spec
chore(zeus): initialize v2 evolution
```

## 故障排查

- 若 AI 不认识 Zeus 工作流，请指引它阅读 `.zeus/ZEUS_AGENT.md`。
- 若执行阶段卡住，检查 `python .zeus/scripts/zeus_runner.py --status` 是否能正常运行。
- 若任务更新失败，校验 `.zeus/*/task.json` 的 JSON 格式（v2）或 DB 状态（v3）。
- 若 commit hook 异常，重新复制 `.zeus/hooks/commit-msg` 到 `.git/hooks/`。
- Windows 环境下若 bash hook 执行失败，可改用 `.zeus/hooks/commit-msg.ps1`（详见 `docs/init-harness.md`）。

## 贡献指南

1. 提示词应保持可执行、可追踪、可审计。
2. shell 片段统一使用英文。
3. 保持 `.zeus` 核心 schema 向后兼容。
4. 工作流变化必须同步更新文档。

## 交流群

<p align="center">
  <img src="assets/image.png" alt="交流群" width="300" />
</p>

## 许可证

MIT License — 见 [LICENSE](LICENSE)。
