# AI Log — Web UI 本地项目选择器

## Decision Rationale
- 需求是让用户在浏览器内切换不同的本地 Zeus 项目，而不是依赖 Windows 右键菜单。
- 浏览器 File System Access API 无法让后端 Python 直接写入用户选择的目录，会导致 `approve`、orchestrator 等核心写操作失效。
- 因此采用**后端动态切换 + 前端路径输入**架构：新增 `POST /project/open` 接口，前端提供 Modal 输入绝对路径，后端验证后重建全局 `store`。
- `store.py` 的 `read_json` 已在前序修复中改为 `utf-8-sig`，避免 BOM 头导致的 JSON 解析失败。

## Execution Summary

### 修改文件
1. **`.zeus/v2/scripts/zeus_server.py`**
   - `/status` 返回新增 `project_dir` 字段。
   - 新增 `POST /project/open`：验证目录存在、是目录、包含 `.zeus` 且至少一个子目录有 `task.json`；验证通过后重建全局 `store`。
   - CLI 新增 `--project-dir` 参数，启动前可指定初始项目目录。
   - 修复 `open_project` 内部调用 `get_status()` 时未传 `version` 导致的路径拼接错误。

2. **`.zeus/v2/web/index.html`**
   - Header 新增"项目路径胶囊"，显示当前目录名，悬停显示完整路径。
   - 新增"打开项目"按钮（文件夹图标）。
   - 新增 glass 风格 Modal：输入绝对路径、支持 `showDirectoryPicker()` 辅助浏览、打开/取消按钮、错误提示。
   - 成功切换后自动关闭 Modal、重置 version 为 `v2`、刷新全局数据。

3. **`.zeus/v2/scripts/test_server.py`**
   - `test_status_endpoint` 新增 `project_dir` 断言。
   - 新增 `test_open_project_success`：构造第二个临时 Zeus 项目，验证切换后 `/status` 与 `/versions` 均来自新目录。
   - 新增 `test_open_project_invalid_dir` 与 `test_open_project_not_zeus`：验证 400 错误提示。

4. **`.zeus/v2/scripts/test_integration.py`**
   - `test_api_smoke_full_lifecycle` 中断言 `status["project_dir"]` 包含临时路径。

5. **`.zeus/v2/specs/2026-04-10-web-project-picker-design.md`**
   - 设计 spec 文档。

### 测试结果
```
29 passed, 1 skipped in 2.52s
```

## Target Impact
- **developer_adoption_rate** ↑：开发者可在单一 Web UI 实例中管理多个 Zeus 项目，无需为每个项目单独启动服务器实例（除非并发需求）。
- **ui_usability** ↑：零构建前端升级为真正的多项目控制台，降低了本地多仓库工作流的上下文切换成本。
