# Skill: Test Generation

## Use When

- 用户要求补测试、回归验证、边界测试或构造实验检查。

## Test Targets

- CLI 参数解析与默认值。
- `TargetState` 状态转移。
- FACE_LOCK / HEAD_PROXY / LOST 语义。
- `PerformanceRecorder` 聚合统计。
- output save/no-save/demo-only 开关。
- realtime dropped frame 统计口径。

## Procedure

1. 确认可自动测试还是需要实验验证。
2. 优先写小而确定的单元测试。
3. 对视频链路，用固定输入和固定输出目录做回归。
4. 测试命名必须表达场景和关键参数。

## Avoid

- 用随机视频或非固定输入做不可复现测试。
- 只测是否运行成功，不检查输出字段和关键指标。