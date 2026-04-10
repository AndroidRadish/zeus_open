# Open Agent Mapping — 通用 AI 平台 Agent 映射表

Zeus 原生设计了 6 个专业 agent。在 Claude Code 中它们通过 `.claude/agents/` 自动加载；在其他 AI 平台中，你可以通过下表找到对应的调用方式。

---

## Agent 职责速查

| Zeus Agent | 职责 | 推荐调用方式 |
|---|---|---|
| **zeus-researcher** | 代码库扫描、状态检查、依赖风险识别 | 只读探索任务 |
| **zeus-planner** | 将 spec 拆解为 story 和 task，计算 wave | 规划任务 |
| **zeus-executor** | 监督波次执行、质量门禁、完成验证 | 代码实现与验证 |
| **zeus-analyst** | 反馈归因、演化判定、影响分析 | 数据分析与决策 |
| **zeus-tester** | 生成平台测试流程 JSON | 测试生成任务 |
| **zeus-docs** | 文档一致性、双语对齐 | 文档审阅任务 |

---

## 平台映射

### Kimi Code

Kimi 提供内置 `Agent` tool：

- `zeus-researcher` → `Agent(explore)`
- `zeus-planner` → `Agent(plan)`
- `zeus-executor` → `Agent(coder)`
- `zeus-analyst` → `Agent(coder)` 或主会话
- `zeus-tester` → `Agent(coder)`
- `zeus-docs` → 主会话

### GLM / Z.ai

GLM 没有专门的 agent 文件系统，建议在**主会话中通过系统提示切换角色**：

1. 先发送 agent markdown 内容作为上下文
2. 然后给出具体任务

### DeepSeek / GPT (OpenAI Codex)

- Codex CLI 提供 `codex` 命令，但没有自动 subagent 委派
- 建议所有 Zeus 任务在主会话中顺序执行
- 对于大段探索，可拆分为多个独立 prompt

### Gemini (Google)

- Gemini CLI 支持 `gemini` 命令
- 与 Codex 类似，建议主会话顺序执行
- 复杂探索可手动分段

### 通用原则

> **Runner 负责编排，AI 负责执行。**
>
> `zeus_runner.py` 是状态与流程的单一事实来源。无论你的 AI 平台是什么，runner 都会输出清晰的 task prompt，你只需把 prompt 复制到当前 AI 会话中（或直接在支持工具的会话中继续），完成后回车确认，runner 会自动更新 `task.json`。
