# Skill: Feature Design

## Use When

- 用户要求新增功能、扩展 CLI、接入输出、设计实验工具或调整实时链路。

## Procedure

1. 明确功能属于离线、实时、共享工具、评估、文档或 agent 配置。
2. 说明影响范围：CLI、输出文件、状态机、性能、质量、兼容性。
3. 优先复用已有结构和命名。
4. 设计最小可交付版本，避免一次性重构。
5. 给出验证指标和回滚方式。

## Required Checks

- 是否破坏现有 `summary.json`、`frame_metrics.json`、`performance.json` 字段。
- 是否改变 `FACE_LOCK` / `HEAD_PROXY` 语义。
- 是否影响实时 latest-frame 低延迟设计。
- 是否需要更新 `lock_target_change_log.md`。

## Avoid

- 未说明质量影响就修改检测、ReID、MTCNN 或控制参数。
- 把演示便利性设计成质量改进。