# AGENTS.md — zeus-open

> 通用 AI-CLI 版 Zeus 框架快速开始
> 适用于 **Kimi Code、GLM、DeepSeek、GPT/Codex、Gemini** 等任何没有 `claude` CLI 的 AI 编程助手。

---

## 🚀 开工流程

**写代码前必须按顺序执行：**

1. `pwd` — 确认当前在项目根目录
2. 读取 `claude-progress.md`（或 `.zeus/main/evolution.md`）— 了解最新状态
3. 读取 `.zeus/main/task.json` — 查看待完成任务
4. `git log --oneline -5` — 查看最近提交
5. 运行状态检查：
   ```bash
   python .zeus/scripts/zeus_runner.py --status
   ```
6. 如果基础验证失败，先修复基础状态

⚠️ **如果状态异常，先修复，不要继续！**

---

## 📋 工作规则

- **一次只做一个功能（一个 task）**
- 不要因为"代码已经写了"就把功能标记为完成
- 实现过程中不要悄悄改弱验证规则
- 优先依赖仓库里的持久化文件，而不是聊天记录

### 防过度延伸
- 如果发现"需要顺便做"的其他功能：
  1. 记录下来
  2. 添加到 `task.json` 或 `feature_list.json`
  3. **不要开始做**
  4. 继续完成当前 task

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
- [ ] 测试全部通过
- [ ] Lint / 类型检查无错误
- [ ] `task.json` 已更新（`passes: true`, `commit_sha` 已填）
- [ ] AI log 已写入 `.zeus/main/ai-logs/`
- [ ] 代码已 `git commit`（格式：`feat(T-001): description`）
- [ ] `zeus_runner.py --status` 显示正常

---

## 🎭 Agent 映射

Zeus 原生定义了 6 个专业 agent。在通用 AI 平台中，请参考 `docs/open-agent-mapping.md` 进行角色切换：

- **zeus-researcher** → 只读探索（Kimi: `Agent(explore)`）
- **zeus-planner** → 规划拆解（Kimi: `Agent(plan)`）
- **zeus-executor** → 执行与验证（Kimi: `Agent(coder)`）
- **zeus-analyst** → 反馈归因
- **zeus-tester** → 测试生成
- **zeus-docs** → 文档一致性

---

## 🏁 收尾流程

**结束会话前必须执行：**

1. 更新 `claude-progress.md`（或 `evolution.md`）
2. 更新 `task.json`
3. 代码审查和验证
4. `git commit`
5. 确认 `python .zeus/scripts/zeus_runner.py --status` 正常

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
