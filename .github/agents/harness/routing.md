# Routing

## Skill Routing

| Task | Skill |
| --- | --- |
| 仓库解释 | `repo-understanding.md` |
| 新功能方案 | `feature-design.md` |
| 代码实现 | `implementation.md` |
| 报错/异常 | `bugfix.md` |
| 结构整理 | `refactoring.md` |
| 变更审查 | `code-review.md` |
| 测试补充 | `test-generation.md` |
| 实验设计/A/B | `experiment-design.md` |
| 文档/报告 | `documentation.md` |
| 论文/外部方法 | `literature-alignment.md` |

## Context Routing

- 涉及性能：必须读取 performance 相关产物或说明缺失。
- 涉及质量：必须读取 frame_metrics 或说明缺失。
- 涉及项目路线：读取 project report 和 parameter table。
- 涉及历史修改：读取 change log。

## Multi-Skill Tasks

当任务同时包含设计、实现和验证时，顺序为：repo-understanding -> feature-design -> implementation -> validation -> documentation。