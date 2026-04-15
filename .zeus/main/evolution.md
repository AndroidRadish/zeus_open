# Evolution Log — zeus-open

## INIT — 2026-04-08

- **Event**: Initialize zeus-open (universal AI-CLI adapter for Zeus)
- **Project**: zeus-open
- **North star**: adoption_rate
- **Weights**:
  - adoption_rate: 0.5
  - cross_platform_coverage: 0.3
  - documentation_completeness: 0.2
- **Stack snapshot**: Python 3, JSON Schema, Markdown
- **Notes**: Forked from zeus-main to provide a claude-CLI-free experience for Kimi, GLM, DeepSeek, GPT, and Gemini users.

---

## FEATURE — 2026-04-09

- **Event**: Complete universal AI-CLI adapter core (T-002 ~ T-006)
- **Project**: zeus-open
- **Version**: main
- **Deliverables**:
  - `generate_tests.py` replaces `generate-tests.sh` (no claude/jq dependency)
  - `collect_metrics.py` replaces `collect-metrics.sh` (cross-platform Python)
  - `zeus_runner.py` gains JSON validation and dependency-cycle detection
  - Added missing `assets/` (workflow SVGs and community image)
  - Aligned all README/skills/docs references to Python scripts
  - Added `.gitignore` for generated metrics and `__pycache__`
- **North star impact**: adoption_rate ↑ (lower barrier for Windows/non-bash users), cross_platform_coverage ↑, documentation_completeness ↑
- **Notes**: Development was driven by Harness Engineering workflow; Harness scaffolding will be removed before final release.

---

## EVOLVE — 2026-04-10

- **Event**: Split v2 track for multi-agent parallel execution and GUI management
- **Version**: v2
- **Rationale**: Core framework (main) is complete. Structural features (parallel orchestration, GUI dashboard, agent communication bus) require a new version track.
- **Next**: zeus:brainstorm --full on v2 architecture.


---

## EVOLVE — 2026-04-15

- **Event**: v3 Dashboard 功能补全与后端能力对齐 (T-V3-021)
- **Version**: v3
- **Deliverables**:
  - 新增 MetricsPanel：Task Metrics / Bottleneck / Blocked Chains 分析视图
  - 新增 TaskDetailDrawer：右侧滑出任务详情抽屉，展示完整字段
  - PhasesPanel 增强：支持 Phase 与 Milestone 的创建、编辑、删除
  - MailboxPanel 增强：支持发送跨 Agent 消息
  - EventsPanel 增强：Live / History 双模式，支持历史事件过滤与分页
  - Dashboard 新增 Health 状态徽章与 Metrics Tab
  - 更新 i18n 双语文案，重新构建静态资源
- **North star impact**: adoption_rate ↑↑ (Dashboard 完整度提升，可直接操作所有后端能力)
- **Notes**: 75/75 tests passed. Build successful. Commit `e953375`.

---

## FEATURE — 2026-04-15

- **Event**: v3 Dashboard Pinia 状态管理迁移 (T-V3-026)
- **Version**: v3
- **Deliverables**:
  - 安装并集成 `pinia`，重构 Dashboard 状态层
  - 新增 `taskStore`：统一管理任务、指标、健康状态、SSE 连接与轮询
  - 新增 `eventStore`：统一管理实时事件流与历史事件
  - 新增 `uiStore`：统一管理标签页、日志弹窗、任务详情抽屉
  - `Dashboard.vue`、`TasksPanel.vue`、`EventsPanel.vue` 消除 props drilling，直接消费 store
  - 保持所有组件模板与视觉风格不变，零破坏性迁移
- **North star impact**: adoption_rate ↑ (Dashboard 可维护性提升，为后续功能扩展打下基础)
- **Notes**: 75/75 tests passed. Build successful. Commit `33e0e94`.

---

## CHORE — 2026-04-15

- **Event**: v1/v2 废弃代码与临时产物清理 (T-V3-027)
- **Version**: v3
- **Deliverables**:
  - 清理 `.zeus/v2/agent-workspaces/` 与 `agent-logs/` 中的历史运行残留（约 1800+ 文件）
  - 清理 `.zeus/v2/` 下的 `__pycache__` 与 `.pyc` 文件
  - 更新 `.gitignore`，防止临时产物再次进入版本控制
- **North star impact**: cross_platform_coverage ↑（减少仓库体积，降低克隆时间）
- **Notes**: Commit `3deb5af`.

---

## DOCS — 2026-04-15

- **Event**: v3 文档同步与 README 更新 (T-V3-028)
- **Version**: v3
- **Deliverables**:
  - 更新 `.zeus/v3/README.md`：补充 Dashboard 新功能（Metrics、Task Detail Drawer、Events History、Hot Reload、Pinia 架构）
  - 更新主 `README.md` / `README.zh-CN.md`：新增 v3 Beta 特性摘要与开发状态
- **North star impact**: documentation_completeness ↑，adoption_rate ↑（降低新用户上手成本）
- **Notes**: Commit `ac546c4`.
