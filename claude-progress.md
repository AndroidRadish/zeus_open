# zeus-open 开发进度

## 当前状态
- **项目**: zeus-open (通用 AI-CLI 版 Zeus 框架)
- **版本**: v2 全部 34 个任务已完成，进入 Wave 12 / US-011 Production Hardening
- **状态**: Validation pass | 70/70 tests green | 34/34 completed
- **最后提交**: `5303275` (scheduler_active + wave fix)
- **当前阶段**: P-003 — v2 Global Orchestrator & Agent Collaboration（已完成），准备进入 Production Hardening

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
| **T-036** | 优雅关闭 + SQLite 调度器状态持久化 | ⏳ 待执行 |
| **T-037** | Dockerfile + 一键启动脚本 (start.sh / start.ps1) | ⏳ 待执行 |

## 会后增强 (Post-T-034)
- **i18n 补全**: 里程碑、阶段、新标签页全部支持中英切换
- **Agent ID 下拉框**: `GET /agent-ids` 服务 + Collaboration/Logs 标签页自动枚举所有历史 agent
- **Web UI 精简**: 移除 `Agent 监控`、`Discussion`、`Graph` 三个低价值标签，从 9 个减至 6 个
- **一键全局运行**: `POST /global/run` 端点 + Global Execution 页面启动按钮

## 会话记录

### 2026-04-12
- 完成 T-031 ~ T-034 的开发、测试与文档
- 70/70 测试全绿，v2 Validation pass
- 添加并发实验脚本 `.zeus/v2/scripts/experiment_concurrency.py`
- 优化 Web UI 国际化与交互体验
- 添加 `POST /global/run` 一键启动全局调度器能力
- 同步外部知识库文档（Bit & Beat 工程知识库）
- 创建 US-011 与 Wave 12 任务队列，准备进入 Production Hardening
