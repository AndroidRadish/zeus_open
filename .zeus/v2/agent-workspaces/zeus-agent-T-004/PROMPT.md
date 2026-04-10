# ZeusOpen v2 Agent Task Prompt

## 项目信息
- 项目名称：zeus-open
- 北极星指标：developer_adoption_rate
- Zeus 版本：v2

## 当前任务
- 任务 ID：T-004
- 所属 Wave：2
- 类型：feat
- 标题：Implement zeus_orchestrator.py with async dispatch, wave logic, and task.json batch updates
- 描述：
- 涉及文件：N/A
- 依赖任务：T-001, T-002

## 执行要求
1. 在隔离工作区中实现上述任务，遵循项目现有的代码风格和架构模式。
2. 如有 typecheck / lint / test 配置，运行并保证通过。
3. 完成后立即进行原子 git commit，格式建议：
   ```
   feat(T-004): Implement zeus_orchestrator.py with async dispatch, wave logic, and task.json batch updates
   ```
4. 更新 `.zeus/v2/task.json` 中此任务的 `passes` 为 `true`，并填写 `commit_sha`。
5. 在 `.zeus/v2/ai-logs/` 目录写入 ai-log 文件（如 `T-004.md`），包含以下内容：
   - **Decision Rationale**：关键技术选择及原因
   - **Execution Summary**：修改了哪些文件，新增了什么，commit SHA
   - **Target Impact**：此 task 如何贡献北极星指标 `developer_adoption_rate`，尽量量化

## 注意事项
- 本 Prompt 所在目录即为你的隔离工作区，项目源码已复制至此。
- 请勿直接修改原始项目目录中的文件；所有改动应在此工作区完成，随后由主会话合并。
- 若遇到设计疑问，优先保持简单（KISS 原则），并在 ai-log 中记录决策。

完成后，请在 Kimi Code 主会话中报告执行结果。
