# ZeusOpen v2 GUI 快速开始手册

> 适用于习惯通过图形界面操作的用户。无需记忆命令行，5 分钟内启动 Web 控制台并观测多 Agent 并发执行。

---

## 1. 环境检查

打开 PowerShell（或任意终端），进入项目根目录，运行：

```powershell
python .zeus/scripts/zeus_runner.py --status --version v2
```

看到 `Validation: pass` 表示环境正常，可以开始使用 GUI。

---

## 2. 启动 Web 控制台

在项目根目录执行：

```powershell
python .zeus/v2/scripts/zeus_server.py
```

成功后会显示：

```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

> 💡 如需指定端口：`python .zeus/v2/scripts/zeus_server.py --port 8080`

---

## 3. 打开浏览器访问

在浏览器地址栏输入：

```
http://127.0.0.1:8000
```

页面加载后，你会看到顶部导航栏包含以下标签页：

| 标签页 | 用途 |
|--------|------|
| **仪表盘** | 查看当前 Wave 的任务列表、完成进度 |
| **里程碑** | 按里程碑分组查看任务，带进度条 |
| **Agent 监控** | 查看正在运行和最近活跃的 Agent |
| **讨论日志** | 按 Wave 查看 Agent 执行的讨论记录 |
| **依赖图谱** | Mermaid / ECharts 可视化任务依赖关系 |

（M-009 完成后还将新增 **阶段** 标签页；M-010 完成后将新增 **全局执行** 和 **Agent 协作** 视图。）

---

## 4. 切换项目（可选）

如果你需要管理多个 Zeus 项目：

1. 点击页面右上角的 **"打开项目"** 按钮
2. 在弹出的 Modal 中输入项目绝对路径（如 `D:\projects\my-zeus-project`）
3. 点击 **确认**

系统会验证该目录是否为合法的 Zeus 项目（包含 `.zeus` 目录和 `task.json`），验证通过后整个页面会刷新为新项目的数据。

---

## 5. 查看任务与批准下一 Wave

### 5.1 查看当前 Wave 任务
进入 **"仪表盘"** 标签页：
- 顶部 Wave 下拉框可切换不同 Wave
- 绿色徽章 = 已完成，灰色 = 待执行
- 如果任务被自适应重调度过，会显示 `已调整` 蓝色小标签

### 5.2 批准执行下一 Wave
当当前 Wave 的所有任务完成后，仪表盘顶部会出现 **"批准并进入下一 Wave"** 按钮：
- 点击后，系统会将 `meta.current_wave` +1
- 正在运行的 Agent 不会被中断

> 💡 如果你使用 CLI 批准，也可以运行：`python .zeus/v2/scripts/zeus_orchestrator.py --approve-next`

---

## 6. 语言切换

页面右上角有 **"中 / EN"** 切换按钮：
- 点击后会即时切换任务标题和描述的语言
- 如果某个任务没有对应语言的字段，会自动回退到默认标题

---

## 7. 启动一次实际执行（通过 CLI）

目前任务分发仍需要通过 CLI 触发。在 Web 控制台保持打开的同时，在另一个终端窗口运行：

```powershell
# 执行当前 Wave（默认 Mock 模式，安全无害）
python .zeus/v2/scripts/zeus_orchestrator.py --wave 1

# 使用 Kimi 子代理执行（需已安装 kimi CLI）
python .zeus/v2/scripts/zeus_orchestrator.py --wave 1 --dispatcher kimi

# 使用 Claude 子代理执行（需已安装 claude CLI）
python .zeus/v2/scripts/zeus_orchestrator.py --wave 1 --dispatcher claude
```

执行过程中，Web 控制台的 **"Agent 监控"** 标签页会实时显示运行状态。

---

## 8. 常见问题

### Q1: 页面显示 "连接失败" 或空白
- 确认 `zeus_server.py` 仍在运行
- 确认浏览器地址和终端显示的端口一致（默认 `8000`）
- 按 `F12` 打开浏览器开发者工具，查看 Console 是否有 CORS 错误

### Q2: 任务执行后 Web UI 没有更新
- 仪表盘每 5 秒自动轮询一次
- 如果等待超过 5 秒仍未更新，点击顶部 **"刷新"** 按钮或切换标签页再切回来

### Q3: 如何查看某个 Agent 的具体日志
- 当前版本（M-008）：进入 **"讨论日志"** 标签页，选择对应 Wave 查看
- M-010 上线后：将进入 **"Agent 日志"** 标签页，直接按 Agent ID 筛选查看独立日志

---

## 9. M-010 上线后的新体验预告

| 功能 | 体验变化 |
|------|---------|
| **全局执行视图** | 不再局限于 Wave 下拉框，一眼看到所有跨 Wave 的运行中任务 |
| **隔离区** | 失败任务会显示在独立的 "隔离区" 面板，不会误导你以为整个项目卡住 |
| **Agent 协作** | 可看到 Agent 之间互相发送的消息流，像在围观一群程序员在 Slack 里讨论 |
| **Agent 日志浏览器** | 点选某个 Agent，直接查看它的 `activity.md` 和 `reasoning.jsonl` |

---

** happy orchestrating! 🚀**
