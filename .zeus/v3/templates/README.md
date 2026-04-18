# High-Concurrency Task Plan Template

> 解决 v3 框架并发调度失效的核心问题：**任务 DAG 并行度过低**。

## 问题诊断

v3 WorkerPool + Queue + Scheduler 的并发引擎本身无缺陷。但如果 task.json 中大部分任务处于**链式依赖**（A→B→C→D），则无论有多少 worker，实际并发度 ≈ 1。

## 设计原则

### 1. 每波至少 2-3 个独立任务

| Wave | 低并行（反模式） | 高并行（推荐） |
|------|----------------|---------------|
| 1 | T-001 (单个) | T-001, T-002, T-003 (3 个并行) |
| 2 | T-002 → T-001 | T-004→T-001, T-005→T-002, T-006→T-003 |
| 3 | T-003 → T-002 | T-007→(T-004,T-005), T-008→T-006 |

### 2. 横向扩展优于纵向链式

- ❌ 反模式：`T-001 → T-002 → T-003 → T-004`（链式 4 个 wave，并发度=1）
- ✅ 推荐：把大任务拆成独立子任务，共用同一组前置依赖

### 3. 依赖关系尽量"扇形"而非"线形"

```
低并行（线形）          高并行（扇形）
T-001                  T-001   T-002   T-003
  ↓                      ↓       ↓       ↓
T-002                  T-004   T-005   T-006
  ↓                      ↓       ↓       ↓
T-003                  T-007   T-008   T-009
  ↓                        \       |       /
T-004                       \      |      /
                               T-010
```

### 4. Wave 分配规则

- **Wave 1**：所有无依赖的任务（通常是基础设施、脚手架）
- **Wave 2**：依赖 Wave 1 的模块级实现（可以按模块拆分多个并行任务）
- **Wave 3+**：依赖 Wave 2 的集成、测试、UI
- **避免**：为一个 task 独占一个 wave

## 快速验证

在规划 task.json 后，运行：

```bash
python .zeus/v3/scripts/run.py --project-root . --import-only
python .zeus/scripts/zeus_runner.py --version v3 --plan
```

检查输出中每个 wave 的 task 数量。如果某个 wave 只有 1 个 task，考虑拆分或调整依赖。

## 参考模板

- `high-concurrency-task-plan.json` — 12 任务 / 4 wave / 每波 3-4 个并行任务
