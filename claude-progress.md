# zeus-open 开发进度

## 当前状态
- **项目**: zeus-open (通用 AI-CLI 版 Zeus 框架)
- **版本**: v2 全部 41 个任务已完成；v3 Phase 1 A1 已完成
- **状态**: v2 Validation pass | 26/26 v3 tests green
- **最后提交**: `49d5199` (v3 Phase 1 A1: CLI runner, stress tests, subprocess ARP integration)
- **当前阶段**: v3 Phase 1 — async state store, ARP schema, queue-worker, importer, dispatcher, workspace, CLI, stress/subprocess tests

## v2 已完成里程碑

### Wave 1 — 核心基础设施
- `store.py` (AbstractStore + LocalStore + 文件锁)
- `agent_bus.py` (JSONL events + Markdown discussion)
- `workflow_graph.py` (Mermaid / Graphviz / Native SVG)

### Wave 2 — 调度器与后端
- `zeus_orchestrator.py` (异步调度、Wave 逻辑、task.json 批量更新)
- `zeus_server.py` (FastAPI: /status /wave /events /discussion /graph)

### Wave 3 — Web 控制台
- 零构建 `index.html` 仪表盘
- 移除废弃 PyQt GUI

### Wave 4 — 集成与文档
- E2E 2-wave 执行测试
- API smoke tests
- `zeus-execute-v2.md` 初版

### Wave 5~7 — 自适应调度与子 Agent
- `original_wave/scheduled_wave/rescheduled_from` 字段
- 自适应优先队列 + 前瞻槽位填充
- `subagent_dispatcher.py` (Mock / Kimi / Claude / Auto)
- Agent Monitor (last_seen + 活动指示器)

### Wave 8 — 引导与国际化
- Workspace bootstrap (AGENTS.md / USER.md / IDENTITY.md / SOUL.md 自动注入)
- `/milestones` 端点 + Milestones Tab
- 多语言支持 (EN/ZH) + i18n 数据填充

### Wave 9 — Phase Layer
- `roadmap.json` `phases` 数组
- `GET /phases` + Phases Tab + Phase-aware wave selector

### Wave 10~11 — Global Orchestrator & Agent Collaboration
- **T-030** GlobalScheduler + quarantine (wave-as-view)
- **T-031** Agent Mailbox 协议 (`send` / `receive`, JSONL 持久化)
- **T-032** Agent-level isolated logs (`{agent_id}/activity.md` + `reasoning.jsonl`)
- **T-033** Web UI 新增 Global Execution / Agent Collaboration / Agent Logs 三视图
- **T-034** 集成测试、向后兼容验证、文档更新

## Wave 12 执行进度 (US-011: Production Hardening)

| Task | 标题 | 状态 |
|------|------|------|
| **T-035** | 任务生命周期控制（retry / cancel / pause）API + Web UI | ✅ 已完成 |
| **T-036-A** | SQLite 持久化核心（scheduler_state.py） | ✅ 已完成 |
| **T-036-B** | 优雅关闭 + SIGTERM 处理器 + SQLite 状态保存 | ✅ 已完成 |
| **T-036-C** | 启动状态恢复 + resume_from_state + /global/status | ✅ 已完成 |
| **T-036-D** | Web UI 恢复横幅和刷新后的全局状态 | ✅ 已完成 |
| **T-036-E** | 集成测试（shutdown-resume 周期）+ 文档更新 | ✅ 已完成 |
| **T-037** | Dockerfile + 一键启动脚本 (start.sh / start.ps1) | ✅ 已完成 |

## v3 Phase 1 执行进度

| 模块 | 标题 | 状态 |
|------|------|------|
| **Foundation** | Async DB (SQLite+Postgres), ARP schema, Queue-Worker, alembic | ✅ 已完成 (`634f6d9`) |
| **Expansion** | task.json importer, dispatcher bridge, workspace manager, worker integration | ✅ 已完成 (`fc974e8`) |
| **A1 CLI** | `run.py` CLI entrypoint (`import → schedule → pool → report`) | ✅ 已完成 (`49d5199`) |
| **A1 Tests** | Stress tests (12 tasks / 4 workers), subprocess ARP integration, dispatcher tests | ✅ 已完成 (`49d5199`) |
| **P2 M-004** | FastAPI server + SSE `/events/stream` + EventBus + metrics summary | ✅ 已完成 (`e7ce198`) |
| **P2 M-005** | MetricsCollector (tasks, bottleneck, blocked chains) + OpenTelemetry tracing | ✅ 已完成 (`6525dd5`) |
| **P2 M-006** | Git worktree workspace backend (zero-copy isolation) | ✅ 已完成 (`4840f60`) |
| **P3 Dashboard** | Zero-build real-time dashboard (`/dashboard`) with SSE + metrics | ✅ 已完成 (`6c0b697`) |
| **P3 M-010 Pre** | `zeus_runner.py --status --version v3` reads v3 SQLite database | ✅ 已完成 (`933aa28`) |
| **Redis Queue** | Redis-backed task queue (`--queue-backend redis`) + fakeredis tests | ✅ 已完成 (`7909a74`) |
| **M-008 Docker** | `docker-compose.yml` + Dockerfile, split api/scheduler/worker via `--mode` | ✅ 已完成 (`b96466b`) |
| **M-009 Docker** | Docker sandbox dispatcher (`dispatcher=docker`) with cgroup/volume support | ✅ 已完成 (`2dd0f05`) |
| **M-007 Vite** | Vite + Vue 3 + TypeScript dashboard, builds into `/dashboard/` | ✅ 已完成 (`98c93e9`) |
| **Docs** | `.zeus/v3/README.md` + main README v3 section | ✅ 已完成 (`c750360`) |
| **Heartbeat** | Worker heartbeat + scheduler lease recovery (crash tolerance) | ✅ 已完成 (`05360fe`) |
| **M-010 CLI** | `zeus_runner.py --version v3` supports `status`, `plan`, and `run` | ✅ 已完成 (`8870b0d`) |
| **K8s** | Kubernetes manifests (api, scheduler, worker, redis, HPA, PVC) | ✅ 已完成 |
| **Dashboard Controls** | Task-level actions (retry/cancel/pause/resume/quarantine) + Control Center (scheduler/worker/import/run) | ✅ 已完成 |
| **ControlPlane** | Embedded subprocess manager for local API server (`/control/*` endpoints) | ✅ 已完成 |

### v3 已修复关键问题
- **Windows subprocess ARP 路径转义**: `repr(str(path))` 保证 `python -c` 中的字符串字面量安全
- **调度循环过早退出**: 现在仅在 `pending == 0 && running == 0 && queue.size == 0` 时才终止
- **Worker 失败自动隔离**: 异常、无效 ARP、非 completed 状态均触发 quarantine

## 会话记录

### 2026-04-12
- 完成 T-031 ~ T-034 的开发、测试与文档
- 70/70 测试全绿，v2 Validation pass
- 添加并发实验脚本 `.zeus/v2/scripts/experiment_concurrency.py`
- 优化 Web UI 国际化与交互体验
- 添加 `POST /global/run` 一键启动全局调度器能力
- 同步外部知识库文档（Bit & Beat 工程知识库）
- 创建 US-011 与 Wave 12 任务队列，准备进入 Production Hardening

### 2026-04-13
- v3 foundation 完成：数据库、迁移、队列、worker 基础架构 (`634f6d9`)
- v3 Phase 1 expansion 完成：importer、dispatcher、workspace、worker 集成 (`fc974e8`)
- v3 Phase 1 A1 完成：CLI runner、stress tests、subprocess 集成测试 (`49d5199`)
- 26/26 v3 测试全部通过
- v3 Dashboard Control Center 完成：任务板内嵌操作 + 系统控制中心 Tab
- 新增 14 个 API 端点（6 task actions + 8 control plane）
- 64/64 v3 测试全绿（含 18 个新增测试）
- 将 v3 Specs 中的 Option B（watch-mode state machine）纳入未来演进规划
- **已完成（T-V3-001）**：子 Agent 进度上报机制（A+B 方案）
  - ✅ `workspace/base.py`：Prompt 新增 `progress.jsonl` 文件日志 + HTTP 主动上报说明
  - ✅ `core/worker.py`：Heartbeat loop 每 10 秒扫描 `progress.jsonl`，去重后写入 `EventLog` 并触发 SSE `task.progress`
  - ✅ `api/server.py`：新增 `POST /tasks/{id}/progress` HTTP 接收端点
  - ✅ `dispatcher/mock.py`：Mock dispatcher 分阶段模拟写入 `progress.jsonl`
  - ✅ `EventsPanel.vue`：Dashboard 对 `task.progress` 事件进行彩色 step 标签展示
  - ✅ `tests/test_v3_api.py`：新增 HTTP 进度上报端点测试（200 + 404 + event + bus emit 验证）

### 2026-04-14
- **已完成（T-V3-015）**：Phase & Milestone API 与 Dashboard 面板
  - ✅ `db/models.py`：补全 `Phase`、`Milestone` 模型（已有 groundwork）
  - ✅ `store/base.py` / `sqlalchemy_base.py`：新增 Phase/Milestone 的 CRUD 抽象与实现
  - ✅ `api/server.py`：新增 `/phases`、`/milestones` REST 端点（CRUD + 嵌套任务查询）
  - ✅ `web/src/components/PhasesPanel.vue`：Dashboard Phase 卡片列表 + Milestone 钻取 + 任务列表
  - ✅ `web/src/i18n/locales/*.json`：新增 `phases.*` 翻译键（EN/ZH）
  - ✅ `tests/test_v3_api.py`：新增 `test_phase_crud`、`test_milestone_crud`
- **已完成（T-V3-018）**：AgentBus Mailbox API、DB 模型与 Dashboard 面板
  - ✅ `db/models.py`：新增 `Mailbox` 表（`id`, `ts`, `from_agent`, `to_agent`, `message`, `read`）
  - ✅ `store/base.py` / `sqlalchemy_base.py`：新增 Mailbox `send_message`、`list_messages`、`mark_message_read`
  - ✅ `api/server.py`：新增 `GET /mailbox`、`POST /mailbox`、`POST /mailbox/{id}/read`
  - ✅ `web/src/components/MailboxPanel.vue`：Dashboard 消息列表、未读过滤、标记已读
  - ✅ `web/src/i18n/locales/*.json`：新增 `mailbox.*` 翻译键（EN/ZH）
  - ✅ `tests/test_v3_api.py`：新增 `test_mailbox`
- **测试状态**：73/73 v3 测试全绿（新增 3 个 API 集成测试）
- **构建状态**：Vue Dashboard `npm run build` 零错误产出静态资源
  - ✅ `tests/test_v3_core.py`：新增 Worker heartbeat 扫描 `progress.jsonl` 及去重逻辑测试
  - ✅ 67/67 v3 测试全绿，Dashboard 构建成功

- **已完成（T-V3-002）**：Dashboard Control Center 体验优化
  - ✅ `api/server.py`：
    - 新增 `_auto_detect_project_root`，支持从 `.zeus/v3/scripts/api/` 自动探测项目根目录
    - 模块级别暴露 `app = main([])`，使 `uvicorn api.server:app` 可直接启动
    - 自动创建 `.zeus/v3/` 数据库目录，避免首次启动时 `unable to open database file`
  - ✅ `web/package.json`：安装 `lucide-vue-next` 图标库
  - ✅ `ControlCenter.vue` 全面重构：
    - 引入 lucide 图标（Upload / Play / Square / Clock / Users / Rocket / Activity / CircleOff / Loader2 / AlertCircle / Info）
    - 紧凑 Bento 布局：2×2 Grid + Global 跨列卡片
    - 503 禁用状态：顶部显示不可用 Banner，整个面板置灰
    - 错误状态：顶部 Error Banner，支持一键关闭
    - 加载状态：所有操作按钮内置旋转 Spinner
    - 新增队列长度 / 上次导入时间等辅助信息
  - ✅ `i18n/locales/{zh,en}.json`：新增 `lastImport`、`unavailableTitle`、`unavailableDesc`、`globalHint` 文案
  - ✅ 67/67 v3 测试全绿，Dashboard 构建成功

- **已完成（T-V3-003）**：v3 ControlPlane 进程管理 Option B 预研
  - ✅ `api/control_plane.py`：移除 `subprocess.Popen` 子进程管理，改为纯 `SchedulerMeta` 读写模式
    - `spawn_scheduler` -> 写 `scheduler_target_state="running"`
    - `stop_scheduler` -> 写 `scheduler_target_state="stopped"`
    - `spawn_workers` -> 写 `worker_target_count`
    - `stop_workers` -> 写 `worker_target_count=0`
    - `status` -> 从 meta 读取 `actual/target` 状态组合返回
  - ✅ `api/server.py`：所有 control plane 端点增加 `await`，适配异步 meta 操作
  - ✅ `core/worker_pool.py`：新增 `scale_to(count)` 方法，支持动态扩缩容并清理已完成的 task
  - ✅ `run.py`：
    - `--mode scheduler` 增加 watch-mode：每轮检查 `scheduler_target_state`，仅当 `"running"` 时执行 tick，否则优雅退出
    - `--mode worker` 增加 watch-mode：每 2 秒检查 `worker_target_count`，调用 `pool.scale_to(target)` 动态调整，目标为 0 或无任务时退出
    - `--mode combined` 保持原有内联行为不变
    - 顺手修复 `--queue-backend redis` 时 `config` 变量未定义的 bug
  - ✅ `tests/test_v3_control.py`：移除 `FakePopen` mock，改为验证 `scheduler_meta` 的读写结果
  - ✅ `tests/test_v3_watch_mode.py`：新增 3 个集成测试，覆盖 scheduler watch 启停与 worker pool 动态扩缩容
  - ✅ 70/70 v3 测试全绿，Dashboard 构建成功

- **已完成（T-V3-019）**：Config and task.json hot reload in serve mode
  - ✅ `api/server.py`：lifespan 中新增后台文件 watcher，监控 `.zeus/v3/task.json` 与 `config.json`
  - ✅ 文件变更时自动 `import_tasks_from_json`，并通过 EventBus 发射 `config.reloaded`
  - ✅ reload 期间暂停 embedded scheduler（写 `scheduler_target_state="stopped"`），完成后恢复，保护并发 tick
  - ✅ `web/src/components/Dashboard.vue`：SSE 监听 `config.reloaded`，自动刷新任务列表与指标
  - ✅ `web/src/components/EventsPanel.vue`：新增 `RefreshCw` / `AlertCircle` 图标与青色/红色样式，热重载事件更易识别
  - ✅ `tests/test_v3_api.py`：新增 `test_hot_reload_task_json` 集成测试（含手动 `_LifespanManager` 适配 httpx 无 lifespan 版本）
  - ✅ 74/74 v3 API 测试全绿，Dashboard 构建成功
