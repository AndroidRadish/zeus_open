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

### Claude Code 用户

```bash
# 1) 安装 commit-msg hook（一次）
cp .zeus/hooks/commit-msg .git/hooks/commit-msg

# 2) 初始化 Zeus
/zeus:init

# 老项目推荐先做代码基线映射
/zeus:discover --depth auto

# 3) 首次全量设计
/zeus:brainstorm --full

# 4) 将 spec 转为执行资产
/zeus:plan

# 5) 按依赖波次执行任务
/zeus:execute
```

### 通用 AI 用户（Kimi / GLM / DeepSeek / GPT / Gemini）

由于这些平台没有 `claude` CLI 和 `/zeus:xxx` skill 路由，请使用 `zeus_runner.py` 和人机协同模式：

```bash
# 1) 安装 commit-msg hook（Bash 用户）
cp .zeus/hooks/commit-msg .git/hooks/commit-msg

# Windows PowerShell 用户
# 参见 docs/init-harness.md 中的 Windows hook 安装说明

# 2) 查看全局状态
python .zeus/scripts/zeus_runner.py --status

# 3) 执行当前 wave（runner 会逐个输出 task prompt，由你在 AI 会话中完成）
python .zeus/scripts/zeus_runner.py

# 4) 查看执行计划
python .zeus/scripts/zeus_runner.py --plan
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

Zeus 的 `skills/` 目录中存放了每个工作环节的 markdown 指令文档，直接在 AI 会话中引用即可（例如："请按照 skills/zeus-init.md 初始化本项目"）。

更多映射关系参见 [docs/open-agent-mapping.md](docs/open-agent-mapping.md)。

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

详见 [`.zeus/v3/README.md`](.zeus/v3/README.md)。

### 当前开发状态

| 里程碑 | 状态 | 任务 |
|---|---|---|
| M-008 — Web UI 与多语言 | ✅ 已完成 | T-023 ~ T-025 |
| M-009 — 阶段（Phase）层 | ✅ 已完成 | T-026 ~ T-029 |
| M-010 — 全局调度器与 Agent 协作 | ✅ 已完成 | T-030 ~ T-034 |
| v3 Phase 1 — 基础架构与队列 worker | ✅ 已完成 | T-V3-001 ~ T-V3-003 |
| v3 Phase 2 — 实时控制台与控制平面 | ✅ 已完成 | T-V3-015、T-V3-018、T-V3-019、T-V3-021、T-V3-026 |

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

## Skill 命令

| 命令 | 用途 | 主要产物 |
|---|---|---|
| `/zeus:init` | 初始化 Zeus 工作区与北极星指标 | `.zeus/main/config.json`、`evolution.md` |
| `/zeus:discover [--version v2] [--depth quick\|auto\|full]` | 映射现有代码库并生成 brownfield 上下文资产 | `codebase-map.json`、`existing-modules.json`、`tech-inventory.md`、`architecture.md` |
| `/zeus:brainstorm --full` | 全量设计对话与 spec 编写 | `.zeus/main/specs/*.md` |
| `/zeus:brainstorm --feature <name>` | 单功能设计循环 | feature spec |
| `/zeus:plan [--version v2]` | 将 spec 拆解为故事与任务 | `prd.json`、`task.json`、`roadmap.json` |
| `/zeus:execute [--version v2]` | 按 wave 执行未完成任务 | 原子提交、task pass 状态 |
| `/zeus:test-gen [--version v2] [--platforms android,chrome,ios]` | AI 生成平台测试流程文件 | `{version}/tests/*.test.json` |
| `/zeus:feedback` | 录入反馈并做归因分析 | `feedback/*.json`、演化记录 |
| `/zeus:evolve` | 创建新版本轨道 | `.zeus/vN/*` |
| `/zeus:status` | 输出全局状态与下一步建议 | 状态快照 + 推荐动作 |

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
  v2/ ... vN/
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

.claude/
  skills/zeus-*/SKILL.md
  agents/*.md

assets/
  zeus-workflow.en.svg
  zeus-workflow.zh-CN.svg
```

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

针对已有代码库，建议按如下顺序：

```bash
# 1) 先生成代码地图与上下文资产
/zeus:discover --version main --depth auto

# 2) 使用 discover 结果初始化配置
/zeus:init --import-existing --version main

# 3) 在既有模块约束下做功能设计与拆解
/zeus:brainstorm --feature <name> --version main
/zeus:plan --version main

# 4) 按 wave 执行
/zeus:execute --version main
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

```bash
# 在 zeus:plan 之后为所有平台生成测试流程
python .zeus/scripts/generate_tests.py --version main --platforms android,chrome,ios

# 通过 skill 调用
/zeus:test-gen

# 仅生成指定平台
/zeus:test-gen --platforms chrome

# 强制重新生成（覆盖已有文件）
python .zeus/scripts/generate_tests.py --version main --force
```

生成的文件位于 `.zeus/{version}/tests/{platform}.test.json`，遵守 `.zeus/schemas/test-flow.schema.json` 结构规范。

测试执行直接使用各平台原生工具链：

| 平台 | 工具链 |
|---|---|
| Android | `adb shell` |
| Chrome | `chrome-cli` / Chrome DevTools Protocol |
| iOS | `xcrun simctl` / `libimobiledevice` |

`/zeus:plan` 完成后会自动询问是否生成测试；`/zeus:execute` 每个 wave 完成后也可选择刷新测试流程。

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

- 若 `/zeus:*` 命令无法识别，请重启 AI 运行时会话。
- 若执行阶段卡住，检查 `python .zeus/scripts/zeus_runner.py --status` 是否能正常运行。
- 若任务更新失败，先校验 `.zeus/*/task.json` 的 JSON 格式。
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
