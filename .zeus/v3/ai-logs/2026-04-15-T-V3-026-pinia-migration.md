# T-V3-026 AI Log — Dashboard Pinia 状态管理迁移

## Decision Rationale

1. **消除 props drilling 导致的维护负担**：Dashboard 与 TasksPanel / EventsPanel 之间通过多层 props 传递任务、事件、UI 状态，新增功能时容易漏传或破坏响应式。
2. **Pinia 是 Vue 生态官方推荐的全局状态方案**：相比 EventBus 或 provide/inject，Pinia 具备更好的 TypeScript 支持、Devtools 集成与可测试性。
3. **按领域拆分 store**：taskStore（任务与指标）、eventStore（实时与历史事件）、uiStore（标签页、弹窗、抽屉），职责清晰，避免单文件膨胀。
4. **保持组件界面零破坏**：Dashboard.vue、TasksPanel.vue、EventsPanel.vue 的模板结构与 CSS 完全保留，仅将数据来源从本地 ref 切换为 store，降低回归风险。

## Execution Summary

- **新增文件**：
  - `web/src/stores/taskStore.ts` — 任务列表、指标摘要、健康检查、SSE 连接、轮询生命周期
  - `web/src/stores/eventStore.ts` — 实时事件流、历史事件、加载状态
  - `web/src/stores/uiStore.ts` — 当前标签页、日志弹窗、任务详情抽屉
- **修改文件**：
  - `web/src/main.ts` — `createApp(App).use(createPinia()).use(i18n).mount('#app')`
  - `web/src/components/Dashboard.vue` — 移除本地 `tasks` / `metrics` / `events` / `health` / `logsModal` / `detailDrawer` 等 ref，统一通过 store 消费与调用 action
  - `web/src/components/TasksPanel.vue` — 移除 props 与 emits，直接读取 `taskStore.tasks`，调用 `taskStore.taskAction()` 与 `uiStore.openLogs()` / `uiStore.openDetail()`
  - `web/src/components/EventsPanel.vue` — 移除 `events` props，直接读取 `eventStore.liveEvents` / `eventStore.historyEvents`
  - `web/package.json` / `package-lock.json` — 安装 `pinia` 依赖
- **验证**：
  - `npm run build` 零错误，静态资源重新生成到 `scripts/api/static/`
  - `python -m pytest scripts/tests/` — 75/75 测试全绿
  - `python .zeus/scripts/zeus_runner.py --status` — Validation [OK] pass

## Target Impact

- **dashboard_maintainability**（直接提升）：props drilling 完全消除，后续新增 Dashboard 功能（如全局筛选、主题切换）只需修改对应 store。
- **developer_experience**（直接提升）：Pinia 的响应式语义与 Devtools 支持让前端调试更高效。
- **regression_risk**（降低）：组件模板与样式零改动，视觉与交互行为 100% 兼容。
