# Skill: Refactoring

## Use When

- 用户要求整理代码结构、去重复、拆函数、统一离线/实时共享逻辑。

## Procedure

1. 明确 refactor 是否允许改变行为；默认不允许。
2. 找到重复逻辑和调用边界。
3. 先建立行为基线或至少说明无法建立基线。
4. 小步改动，避免同时改算法和结构。
5. 验证输出字段、CLI、运行产物路径不变。

## High-Risk Areas

- 候选收集与 `TargetState` 更新。
- FACE_LOCK / HEAD_PROXY 判定。
- realtime latest-frame 缓冲与丢帧统计。
- performance recorder 的字段兼容性。

## Output

- 保持不变的行为。
- 结构变化。
- 验证证据。
- 回归风险。