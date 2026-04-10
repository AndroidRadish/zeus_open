## Decision Rationale

用户报告 PyQt GUI 无法加载图谱，提示"请确保后端已启动且 Graphviz 已安装"。

根本原因分析：
- 当前 Windows 环境中 `graphviz` 的 `dot` 可执行文件未安装，导致后端 `/graph/svg` 返回 503 错误。
- 通过 Chocolatey 安装需要管理员权限且超时失败，无法在当前会话中完成系统级安装。
- 要求用户必须手动安装 Graphviz 会显著降低 `developer_adoption_rate`。

设计决策：
- 为 `WorkflowGraph` 实现纯 Python 的 `to_svg_native()` 方法，作为 `dot` 不可用的降级方案。
- 布局策略：按 wave 分组，每 wave 一列，任务从上到下排列，依赖项用三次贝塞尔曲线连接。
- 修改 `zeus_server.py` 的 `/graph/svg` 端点：优先使用 `dot`（保留高质量渲染），若未找到则自动 fallback 到原生 SVG 生成器。
- 这样 PyQt GUI 的图谱功能开箱即用，无需额外系统依赖。

## Execution Summary

修改文件：
- `.zeus/v2/scripts/workflow_graph.py`
  - 新增 `to_svg_native()` 方法，生成左到右流程图 SVG
  - 包含箭头标记、wave 列标签、任务矩形（带圆角和状态色）、标题截断显示
- `.zeus/v2/scripts/zeus_server.py`
  - `/graph/svg` 端点重构为 if-else 结构
  - `dot` 可用时走原有 Graphviz 渲染路径
  - `dot` 不可用时调用 `graph.to_svg_native()` 并直接返回 SVG 响应

验证：
- `python -m py_compile` 通过
- 命令行快速测试：`WorkflowGraph('.zeus/v2/task.json').to_svg_native()` 成功生成 5.7KB SVG，包含 Wave 1~4 的全部任务节点和依赖连线

Commit: fix(T-006): add pure-Python SVG fallback for graph rendering when Graphviz is missing

## Target Impact

- **developer_adoption_rate**：消除了"必须安装 Graphviz 才能看到图谱"的入门门槛，Windows 用户下载项目后可直接运行 GUI 并查看完整 workflow 图。
- **ui_usability**：PyQt 和 Web 控制台的图谱功能现在在任何平台上都能一致工作。
- **cross_platform_coverage**：原生 fallback 提升了对未预装 Graphviz 环境（如 Windows、部分 CI 容器）的兼容性。
