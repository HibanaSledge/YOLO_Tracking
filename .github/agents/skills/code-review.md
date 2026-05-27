# Skill: Code Review

## Use When

- 用户要求审查变更、找 bug、评估风险或给改进建议。

## Review Priorities

1. 正确性：是否改变目标身份连续性、脸框几何或控制输出。
2. 回归风险：是否破坏离线/实时输出、CLI、性能记录。
3. 证据：是否有 summary、frame_metrics、performance 或测试支持。
4. 可维护性：是否重复、是否隐藏状态、是否难以回滚。

## Checklist

- 是否把 tracker id 当作业务目标。
- 是否混淆 FACE_LOCK 与 HEAD_PROXY。
- 是否只看 FPS 忽略质量。
- 是否在实时链路引入队列积压。
- 是否对可选依赖处理失败。
- 是否新增字段但未同步 summary/frame_metrics/performance。

## Output

- 按严重程度列问题。
- 每个问题给证据和影响。
- 给最小修复建议。