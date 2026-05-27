# Skill: Experiment Design

## Use When

- 用户要求设计离线/实时实验、A/B 对比、质量评估或性能验证。

## Procedure

1. 明确实验问题：速度、身份、几何、控制、实时性还是工程便利性。
2. 固定 baseline。
3. 每次只改变一个关键变量。
4. 设计 `--name`，包含场景和参数，例如 `profile_mtcnn1_faceconf025`。
5. 指定必须检查的 summary、frame_metrics、performance 字段。
6. 定义 pass / conditional-pass / fail / inconclusive。

## Required Metrics

- 速度：runtime、effective_fps、frame_total_ms、collect_candidates_ms。
- 身份：tracker_switches、reacquired_count、误绑关键帧。
- 几何：FACE_LOCK/HEAD_PROXY 分布、center 偏移、假 FACE_LOCK。
- 实时：camera_fps、process_fps、latency、dropped_frames。

## Avoid

- 同时调 `imgsz`、`reid-interval`、`mtcnn-interval` 后做单一归因。
- 无同源 baseline 就断言优化有效。