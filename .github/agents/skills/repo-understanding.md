# Skill: Repo Understanding

## Use When

- 用户要求解释仓库结构、模块职责、技术路线或当前进度。
- 用户问某个输出、参数、脚本属于哪条链路。

## Procedure

1. 先读 [../context/repo-map.md](../context/repo-map.md) 和 [../context/architecture.md](../context/architecture.md)。
2. 再按需要读取核心文件：`lock_target.py`、`lock_target_realtime.py`、`perf_utils.py`。
3. 若涉及阶段演进，读取 `lock_target_change_log.md`。
4. 若涉及路线判断，读取 `lock_target_project_report.md` 和 `docs/tuning/lock_target_parameter_table.md`。

## Output

- 模块职责。
- 数据流。
- 关键参数或输出。
- 已验证事实与证据缺口。

## Project Notes

- 本仓库不是原始 Ultralytics demo，而是在其上扩展了单目标业务锁定层。
- 底层 tracker 只提供候选轨迹；业务层 `TargetState` 决定目标连续性。
- 离线链路重证据留存，实时链路重低延迟显示。