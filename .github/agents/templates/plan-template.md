# Plan Template

用于复杂任务开始前的计划输出。计划必须体现 context engineering 与 harness engineering：先构建上下文，再执行，再验证。

## 目标

- 用户原始目标：
- 本次可交付结果：
- 不在本次范围内的内容：

## 任务类型

- 类型：repo-understanding / feature-design / implementation / bugfix / refactoring / code-review / test-generation / experiment-design / documentation / literature-alignment
- 使用 skill：
- 是否涉及代码修改：是 / 否
- 是否涉及锁定链路：是 / 否
- 是否涉及性能或质量结论：是 / 否

## 影响范围

- 代码文件：
- 文档文件：
- 运行产物：summary / frame_metrics / performance / video
- CLI 或输出字段兼容性：
- 离线链路影响：
- 实时链路影响：

## 上下文来源

- 指令：
- skills：
- context：
- harness：
- 项目文件：
- 运行产物：
- 用户现场反馈：

## 执行步骤

1. 读取必要上下文，区分事实、推断和缺口。
2. 确认 baseline、目标文件或目标产物。
3. 执行最小修改、分析或文档整理。
4. 按 validation harness 检查结果。
5. 输出结论、证据、风险和下一步。

## 验证计划

- 静态检查：
- 单元测试或最小运行：
- 离线指标：
- 实时指标：
- 文档/链接完整性：

## 风险与证据缺口

- 可能回归：
- 需要用户确认：
- 当前无法验证：
- 后续补证方式：