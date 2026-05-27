# Skill: Bug Fix

## Use when
- 用户报告 bug
- 用户提供报错日志
- 用户要求定位异常原因

## Inputs
- 报错描述
- 相关文件
- 测试或复现步骤
- 日志/堆栈

## Procedure
1. 明确期望行为与实际行为
2. 找到故障入口
3. 向上追踪调用链
4. 找到最小修复点
5. 评估副作用
6. 建议回归测试

## Project-Specific Checks

- 实时卡顿：先区分 camera 采集、processing、display、write_video 和算法阶段耗时。
- 锁错目标：先区分 tracker id 切换、业务重绑定错误、假 FACE_LOCK、HEAD_PROXY 漂移。
- 性能异常：优先查 `performance.json`，不要只看窗口体感。
- 指标矛盾：优先检查统计口径，例如 `process_fps` 是否与 `process_latency_ms` 一致。

## Output
- 根因
- 修复建议
- 风险点
- 建议测试

## Avoid
- 未定位根因就直接猜改法
- 一次改多个无关点
- 忽略可复现条件