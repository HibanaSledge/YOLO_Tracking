# Evaluation

## Evaluation Axes

### Identity

- 是否仍是同一个业务目标。
- 是否出现换绑、误重绑定或 tracker id 漂移。
- 指标：`tracker_switches`、`reacquired_count`、关键帧人工检查。

### Geometry

- FACE_LOCK 是否是真实脸框。
- HEAD_PROXY 是否仍在合理头部区域。
- 指标：lock mode 分布、raw/filtered center 偏移、关键帧框位置。

### Control

- filtered target center 是否稳定。
- 控制输出是否抖动、拖尾或断续。
- 指标：`control_state`、`control_distance_to_center`、`deadband_active`。

### Performance

- 是否真正提升处理吞吐。
- 是否只是减少写盘或显示开销。
- 指标：`effective_fps`、`process_latency_ms`、`frame_total_ms`、`collect_candidates_ms`、`embedding_ms`、`face_detect_mtcnn_ms`。

### Realtime

- 是否低延迟显示。
- 是否仍大量丢帧。
- 指标：`camera_fps`、`process_fps`、`display_fps`、`total_dropped_frames`、`dropped_frames_before`。

## Evaluation Rules

- summary 接近不代表质量等价。
- FPS 提升不代表可用性提升。
- FACE_LOCK 帧数高不代表没有假脸框。
- 轻量化必须同时评估质量代价。
- 没有同源 A/B 时，只能给趋势判断，不能给确定归因。