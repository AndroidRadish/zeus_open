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
| **M-010 CLI** | `zeus_runner.py --version v3` supports `status`, `plan`, and `run` | ✅ 已完成 |

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
