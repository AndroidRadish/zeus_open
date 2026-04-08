# init-harness.md — 通用 AI 版 Zeus 初始化指南

> 适用于 Kimi Code、GLM、DeepSeek、GPT/Codex、Gemini 等任何没有 `claude` CLI 的 AI 编程助手。

---

## 前置条件

1. **Git 仓库**：你的项目根目录应该是一个 Git 仓库（或准备初始化）。
2. **Python 3.10+**：`zeus_runner.py` 需要 Python 3 环境。
3. **复制 Zeus 框架**：将 `zeus-open` 的 `.zeus/`、`skills/`、`docs/`、`AGENTS.md` 复制到你的项目根目录。

---

## 第一步：安装 commit-msg hook

### macOS / Linux / Git Bash (Windows)

```bash
cp .zeus/hooks/commit-msg .git/hooks/commit-msg
chmod +x .git/hooks/commit-msg
```

### Windows PowerShell

Git for Windows 的 hook 机制默认调用 bash。如果你主要在 PowerShell 下工作，有两种方案：

**方案 A：使用 Git Bash**
在 Git Bash 中执行上面的 `cp` 和 `chmod` 命令即可。bash hook 会在你每次 `git commit` 时自动运行。

**方案 B：PowerShell hook（高级）**
如果你需要纯 PowerShell 环境，可以创建一个桥接脚本 `.git/hooks/commit-msg`（无扩展名），内容为：

```bash
#!/bin/sh
powershell.exe -ExecutionPolicy Bypass -File .zeus/hooks/commit-msg.ps1 "$1"
```

然后在 PowerShell 中：

```powershell
# 确保 hook 文件存在且可执行
copy .zeus\hooks\commit-msg.ps1 .git\hooks\commit-msg.ps1
```

---

## 第二步：初始化 Zeus 配置

直接告诉你的 AI 助手：

> "请按照 `skills/zeus-init.md` 的指引，为本项目初始化 Zeus 工作区。"

AI 助手会帮你：
1. 检查 `.zeus/main/config.json` 是否存在
2. 询问项目名称、领域、技术栈、版本意图
3. 推荐北极星指标
4. 生成 `config.json` 和 `evolution.md`
5. 执行 `git commit -m "chore(zeus): initialize zeus project structure"`

---

## 第三步：老项目接入（可选）

如果是已有代码的项目，在初始化前先做代码测绘：

> "请按照 `skills/zeus-discover.md` 扫描现有代码库，生成 `codebase-map.json` 和 `existing-modules.json`。"

测绘完成后，再运行初始化并带上 `--import-existing` 逻辑：

> "请按照 `skills/zeus-init.md` 的 Brownfield 模式，导入 discover 结果生成 config。"

---

## 第四步：查看状态

```bash
python .zeus/scripts/zeus_runner.py --status
```

如果显示正常，说明初始化成功。

---

## 第五步：后续工作流

| 阶段 | 你对 AI 说的话 | runner 命令 |
|---|---|---|
| 设计 | "请按照 `skills/zeus-brainstorm.md` 做全量设计" | 无需 runner |
| 规划 | "请按照 `skills/zeus-plan.md` 拆解 spec" | 无需 runner |
| 执行 | runner 输出 task prompt，你把 prompt 贴给 AI 会话 | `python .zeus/scripts/zeus_runner.py` |
| 反馈 | "请按照 `skills/zeus-feedback.md` 分析反馈" | 无需 runner |
| 演化 | "请按照 `skills/zeus-evolve.md` 创建新版本" | 无需 runner |

---

## Agent 映射速查

当你需要委派子任务时，参考下表：

| Zeus Agent | Kimi Code | GLM | Codex/Gemini |
|---|---|---|---|
| researcher | `Agent(explore)` | 主会话（只读模式） | 主会话分段探索 |
| planner | `Agent(plan)` | 主会话 | 主会话 |
| executor | `Agent(coder)` | 主会话 | 主会话 |
| analyst | `Agent(coder)` | 主会话 | 主会话 |
| tester | `Agent(coder)` | 主会话 | 主会话 |
| docs | 主会话 | 主会话 | 主会话 |

更多细节见 [open-agent-mapping.md](open-agent-mapping.md)。
