# Harness Engineering

## Purpose

Harness engineering 是本 agent 的执行框架：为修改、实验、复盘、报告和回归建立可重复、可验证、可恢复的流程。

## Default Harness

- Task type：按 [harness/task-types.md](../harness/task-types.md) 分类。
- Routing：按 [harness/routing.md](../harness/routing.md) 选择 skill。
- Tool usage：按 [harness/tool-usage.md](../harness/tool-usage.md) 选择读取、搜索、编辑和验证方式。
- Validation：按 [harness/validation.md](../harness/validation.md) 执行验证。
- Recovery：按 [harness/recovery.md](../harness/recovery.md) 处理失败。
- Escalation：按 [harness/escalation.md](../harness/escalation.md) 判断何时需要用户决策。
- Memory：按 [harness/memory-policy.md](../harness/memory-policy.md) 维护可复用经验。

## Evidence Harness

任何性能或质量结论必须绑定以下证据之一：

- summary：初始化、tracker switches、reacquired、face misses、runtime、effective fps。
- frame metrics：逐帧 lock mode、control state、raw/filtered center、偏移。
- performance：detect、collect_candidates、face detect、MTCNN、embedding、draw、write、show。
- 视频或关键帧：用于补充统计无法捕捉的假 FACE_LOCK、框偏移、换绑。

## A/B Harness

1. 固定输入 source、模型、tracker、关键参数。
2. 标明 baseline run_dir 和 candidate run_dir。
3. 比较 summary 级指标。
4. 比较 frame_metrics 逐帧状态和中心偏移。
5. 比较 performance 阶段耗时。
6. 标记结论：pass、conditional-pass、fail、inconclusive。

## Implementation Harness

1. 影响范围声明。
2. 最小修改。
3. 保持 CLI 与输出兼容。
4. 运行静态检查或相关测试。
5. 如果修改锁定链路，更新 `lock_target_change_log.md`。