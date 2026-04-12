# ZeusOpen v3 — Production Multi-Agent Framework Plan

> 演进目标：将 zeus-open v2 从"可运行的并发原型"升级为"可生产、可扩展、可维护的多 Agent 框架"。
> 规划日期：2026-04-13
> 规划者：基于 T-036 完成后对 v2 架构的深度评估

---

## 背景：v2 已经证明了什么？

v2 成功验证了以下假设：
1. **真并发可行**：`asyncio.Semaphore` + 隔离 workspace + 子 Agent CLI 调度器可以并行执行多个任务。
2. **跨 wave 调度可行**：Global Scheduler 打破 wave 锁定，按依赖就绪度 dispatch。
3. **可观测性有价值**：Web UI 的 Global Execution、Agent Mailbox、Agent Logs 三视图提供了良好的操作体验。
4. **状态恢复可行**：SQLite `scheduler_state.db` 可以在服务器重启后恢复运行中的任务。

但 v2 仍是一个**单进程、文件锁、黑盒进程调度的原型**。要成为生产框架，必须进行架构升级。

---

## v3 核心目标

| 维度 | v2 现状 | v3 目标 |
|------|---------|---------|
| **状态存储** | 单一 `task.json`，每状态变更全量读写+文件锁 | SQLite/PostgreSQL 动态状态库，`task.json` 退化为只读计划源 |
| **调度-执行关系** | 调度器与执行器强耦合在一个 `run_global()` while 循环中 | Queue-Worker 分离，调度器无状态化，worker 可水平扩展 |
| **Agent 通信** | 黑盒子进程，只看 exit code 和 stdout | 结构化 `zeus-result.json` 协议 + 可选心跳进度上报 |
| **实时性** | HTTP 轮询（前端 setInterval） | SSE `/events/stream` 事件驱动推送 |
| **可观测性** | JSONL/Markdown 文件日志，线性扫描 | 可查询事件数据库 + OpenTelemetry Trace/Span |
| **前端工程** | 零构建单文件 `index.html` (~1500 行) | Vite + Vue/TS 组件化工程 |
| **部署形态** | 单 Python 进程 | 多容器拆分：`zeus-api` / `zeus-scheduler` / `zeus-worker` |
| **Workspace 隔离** | `shutil.copytree` 全量复制项目源码 | `git worktree` / reflink copy / overlayfs 差异层 |
| **安全沙箱** | 子 Agent 与父进程同用户、同网络、同文件系统 | Docker / gVisor 沙箱执行，带 cgroup 资源限制 |

---

## Phase 1 — 夯实内核（P0，预计 4-6 周）

### M-001: 状态层重构 — 从 `task.json` 到数据库
- **T-101** 设计动态状态 Schema（tasks_status / quarantine / scheduler_meta / events）
- **T-102** 实现 `SqliteStateStore`（填实 v2 中预留的 `AbstractStore` 第三实现）
- **T-103** 实现 `PostgresStateStore`（基于 `asyncpg` 或 `psycopg`）
- **T-104** 迁移 `ZeusOrchestrator` 所有 `_update_task_status` / `_quarantine_task` 逻辑到数据库
- **T-105** `task.json` 降级为静态计划配置，启动时只读，运行时不写
- **T-106** 向后兼容验证：v1 `zeus_runner.py --status` 仍能正确读取并展示

### M-002: Agent Result Protocol (ARP)
- **T-107** 制定 `zeus-result.json` Schema v1
  - `status`: `completed` | `failed` | `partial`
  - `changed_files`: list[str]
  - `test_summary`: {passed, failed, skipped}
  - `commit_sha`: str
  - `artifacts`: {log, error, coverage_report, ...}
- **T-108** 修改 `subagent_dispatcher.py`，子进程退出后优先读取 `zeus-result.json`
- **T-109** 修改 Prompt 模板，要求子 Agent 必须输出 `zeus-result.json`
- **T-110** 集成测试：mock agent 产出 ARP，dispatcher 正确解析并更新状态

### M-003: Queue-Worker 分离
- **T-111** 设计 `TaskQueue` 抽象（支持 asyncio.Queue / Redis List / SQLite 队列表）
- **T-112** 重构 `ZeusOrchestrator.run_global()`：Scheduler 只负责 enqueue，不再直接 await dispatcher
- **T-113** 实现 `Worker` 类：消费 queue，执行 dispatcher，回写结果，支持失败重试（指数退避）
- **T-114** 实现 `WorkerPool`：动态扩容/缩容 worker 数量（受 `max_parallel` 限制）
- **T-115** 集成测试：多 worker + mock dispatcher 的端到端验证

---

## Phase 2 — 实时与可观测（P1，预计 3-4 周）

### M-004: 实时事件推送
- **T-116** FastAPI 增加 `GET /events/stream` (SSE)
- **T-117** `AgentBus.emit()` 同时向 SSE 连接广播
- **T-118** Web UI 迁移到事件驱动刷新（逐步替代 setInterval 轮询）
- **T-119** 集成测试：SSE 端到端验证

### M-005: 可查询事件存储与 Metrics
- **T-120** 设计 `events` 数据库表（indexed by task_id, agent_id, event_type, ts）
- **T-121** 实现 `MetricsCollector`：从事件表聚合失败率、平均执行时长、瓶颈任务
- **T-122** Web UI 新增 Analytics Tab：展示全局 metrics 和 per-task 历史趋势
- **T-123** 可选：OpenTelemetry Trace 集成，一次 `run_global()` = 一个 Trace

### M-006: Workspace 优化
- **T-124** 用 `git worktree` 替代 `shutil.copytree` 创建 agent workspace
- **T-125** 在支持的文件系统上启用 reflink copy（零拷贝）
- **T-126** 调研并 PoC overlayfs（Linux）或类似分层挂载方案

---

## Phase 3 — 生产级扩展（P2，预计 4-6 周）

### M-007: 前端工程化
- **T-127** 初始化 Vite + Vue 3 + TypeScript 项目（保留现有 UI 设计语言）
- **T-128** 组件化迁移：GlobalExecutionPanel, TaskLifecycleControls, AgentMailbox, AgentLogsViewer
- **T-129** 引入 Pinia 状态管理，对接 SSE 事件流
- **T-130** 替换现有 `index.html` CDN 引入方式，改为构建产物挂载到 FastAPI

### M-008: 多容器拆分与部署
- **T-131** 拆分 `Dockerfile` 为 `zeus-api`, `zeus-scheduler`, `zeus-worker` 三个镜像
- **T-132** 提供 `docker-compose.yml` 一键启动完整集群
- **T-133** Worker 支持通过环境变量注册到 Queue（Redis / RabbitMQ / SQS）
- **T-134** K8s manifest 示例（Deployment + Service + HPA）

### M-009: 安全沙箱
- **T-135** 子 Agent 默认在 Docker 容器内执行（`dispatcher` 新增 `docker` 模式）
- **T-136** 容器内只读挂载源码 + 指定输出 volume
- **T-137** cgroup / memory / CPU 限制配置
- **T-138** 环境变量与 secret 隔离（子 Agent 不继承父进程 `.env`）

### M-010: 统一 CLI 与 v1 退役
- **T-139** 升级 `zeus_runner.py` 为 v3 的兼容前端（交互模式保留，底层调用新框架）
- **T-140** 正式移除 v1 代码路径，文档全面迁移到 v3
- **T-141** 全量回归测试 + 性能基准测试

---

## 风险与依赖

| 风险 | 缓解措施 |
|------|----------|
| 数据库迁移导致向后兼容断裂 | 保留 `task.json` 只读导入路径，提供一次性迁移脚本 |
| Queue-Worker 拆分引入分布式调试复杂度 | 本地开发默认使用 `asyncio.Queue`（单进程模式），生产切 Redis |
| Docker 沙箱在 Windows 上运行困难 | Windows 默认回退到进程模式，Linux/macOS 默认容器模式 |
| 前端工程化增加构建步骤 | 提供 `make build-ui` 和 CI pipeline，保持后端仍可零构建启动 |

---

## 北极星指标预期影响

- `multi_agent_efficiency` ↑↑↑（Queue-Worker 水平扩展 + 跨机器调度）
- `developer_adoption_rate` ↑↑↑（实时 UI + 结构化 ARP + 可查询 metrics）
- `ui_usability` ↑↑（组件化前端 + SSE 实时推送）
- `observability` ↑↑↑（Trace + Metrics + 可查询事件存储）

---

## 下一步动作（明早由人类决策者确认）

1. 审阅本计划
2. 决定是否将本 spec 提升为正式 `.zeus/v3/prd.json` 和 `.zeus/v3/roadmap.json`
3. 为 Phase 1 的 M-001 ~ M-003 拆分具体任务并启动执行
