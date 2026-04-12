# Spec: Web UI 本地项目选择器

## 1. 需求摘要
在 ZeusOpen v2 零构建 Web 控制台中增加"打开本地项目"能力：用户无需离开浏览器即可将后端工作目录切换到另一个本地 Zeus 项目，并立即查看该项目的 wave 状态、任务列表、agents、讨论日志与依赖图谱。

## 2. 基线状态
- `zeus_server.py` 的 `store` 在模块导入时固定初始化，指向单一项目根目录。
- Web UI 已支持同一项目内切换 version（`main` / `v2`），但无法跨项目。
- 后端已有 `/versions`（扫描 `.zeus/` 子目录）等接口。
- 全部 pytest 通过，零构建前端使用 Vue 3 + Tailwind CDN。

## 3. 架构选项

### 选项 A：后端动态切换 + 前端路径输入（推荐）
- 后端新增 `POST /project/open`，接收 `project_dir` 字符串，验证后重建全局 `store`。
- 前端 Header 增加"打开项目"按钮，弹出 Modal 让用户输入/粘贴本地绝对路径，确认后调用 API。
- **优点**：实现轻量；后端所有现有接口（`/status`、`/wave/{n}`、`/graph/*`、`/approve`）无需改动即可立即在新项目上工作；读写能力完整保留。
- **缺点**：依赖用户手动输入路径，无法直接弹出系统文件选择器获取绝对路径（浏览器安全限制）。

### 选项 B：纯前端 File System Access API（`showDirectoryPicker`）
- 前端使用 `showDirectoryPicker()` 选择本地目录，获得 `FileSystemDirectoryHandle`。
- 前端递归读取 `.zeus/v2/task.json`、events、discussion 等文件，完全在内存中渲染。
- **优点**：有系统级文件夹选择器，体验现代。
- **缺点**：无法让后端 Python 直接写入所选目录；`approve`、`wave` 推进、agents 状态等需要后端写入的功能将失效；权限在页面刷新后丢失。架构改动过大（需把所有写入逻辑迁到前端或改为纯前端代理模式）。

### 选项 C：混合模式（前端选目录 + 后端代理写入）
- 前端通过 File System Access API 读取和修改本地文件，后端退化为纯计算/验证服务。
- **优点**：既有系统选择器，又能写回本地。
- **缺点**：彻底颠覆现有架构；需要把 `store.py`、`agent_bus.py`、orchestrator 的文件操作全部搬到前端 JavaScript 中，超出当前迭代范围。

## 4. 推荐方案
**采用选项 A**。在 localhost 开发工具场景下，"路径输入框 + 后端切换"是性价比最高且功能完整的路径。可在支持的浏览器中额外提供 `showDirectoryPicker()` 作为辅助验证，但不依赖它。

## 5. 数据契约与 API 变更

### 5.1 `GET /status`（扩展）
Response 增加字段：
```json
{
  "version": "v2",
  "project_name": "zeus-open",
  "current_wave": 1,
  "pending_tasks": 2,
  "completed_tasks": 1,
  "validation": "pass",
  "project_dir": "D:\\schooldoc\\TrueProject\\zeus-open"
}
```

### 5.2 `POST /project/open`（新增）
Request:
```json
{ "project_dir": "D:\\schooldoc\\TrueProject\\another-zeus" }
```

Success (200):
```json
{
  "success": true,
  "project_dir": "D:\\schooldoc\\TrueProject\\another-zeus",
  "status": { /* 同 GET /status */ }
}
```

Error (400) — 路径不存在或不是 Zeus 项目：
```json
{ "detail": "Not a valid Zeus project: .zeus directory missing or no task.json found" }
```

Error (400) — 路径不是目录：
```json
{ "detail": "project_dir must be a directory" }
```

## 6. 前端交互设计
- **Header 项目路径胶囊**：在"任务"下拉框左侧新增一个玻璃胶囊，显示当前项目目录名（`project_dir` 的最后一级）。过长时使用 `truncate`，`title` 属性显示完整路径。
- **"打开项目"按钮**：在刷新按钮旁边增加一个文件夹图标按钮。
- **Modal**（glass 风格，与现有 UI 一致）：
  - 标题：打开本地 Zeus 项目
  - 输入框：`project_dir` 绝对路径，placeholder 为 `例如 D:\projects\my-zeus-project`
  - 辅助按钮："浏览..."（在支持的浏览器中调用 `showDirectoryPicker()` 做目录存在性验证，若浏览器不支持则隐藏）。
  - 操作区："打开"（主按钮，cyan 风格）、"取消"
  - 错误提示：红色文本显示于 Modal 底部。
- **切换后行为**：Modal 关闭，调用 `refreshAll()`，页面所有 Tab 数据立即来自新项目。

## 7. 错误处理
- 后端验证失败时返回 400，前端直接展示 `detail` 文本。
- 若切换后新项目的 `.zeus/{version}/task.json` 结构损坏，`/status` 的 `validation` 字段为 `fail`，前端在 Dashboard 上已有异常状态展示，无需额外处理。
- 端口占用、网络错误等已有离线提示条覆盖。

## 8. 测试策略
- `test_server.py`：
  - 更新 `test_status_endpoint`：断言 `project_dir` 为绝对路径。
  - `test_open_project_success`：构造第二个临时 zeus 项目，调用 `POST /project/open`，验证 `/status` 和 `/versions` 均来自新目录。
  - `test_open_project_invalid_dir`：传入不存在路径，断言 400。
  - `test_open_project_not_zeus`：传入存在但无 `.zeus` 的目录，断言 400。
- `test_integration.py`：
  - 在 `test_api_smoke_full_lifecycle` 末尾追加一步：切到另一个临时项目再切回，验证状态恢复。

## 9. 验收标准
- [ ] Web UI Header 正确显示当前项目目录名，完整路径可悬停查看。
- [ ] 点击"打开项目"弹出 Modal，输入有效 Zeus 项目路径后成功切换。
- [ ] 切换后 Dashboard、Wave 任务、Agents、Discussion、Graph 全部来自新项目。
- [ ] 对无效目录返回明确错误提示（中文或英文）。
- [ ] 全部 v2 pytest 通过（≥26 passed）。

## 10. 北极星指标影响
- **developer_adoption_rate** ↑：降低多项目开发者的上下文切换成本。
- **ui_usability** ↑：零构建 Web UI 成为真正的多项目控制台。
