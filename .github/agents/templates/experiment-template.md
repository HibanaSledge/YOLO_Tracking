# Experiment Template

用于离线、实时、轻量化、质量、性能或参数调优实验。必须保证可复现、可归因、可比较。

## 实验问题

- 要回答的问题：
- 实验类型：速度 / 身份连续性 / 脸框几何 / 控制中心 / 实时延迟 / 输出开销
- 核心假设：
- 只改变的变量：

## Baseline

- run_dir：
- source：
- model：
- tracker：
- reid-model：
- 关键参数：
- 产物：summary / frame_metrics / performance / video

## Candidate

- run_dir：
- source：
- model：
- tracker：
- reid-model：
- 关键参数：
- 产物：summary / frame_metrics / performance / video

## 可复现命令

### Baseline command

- 从项目根目录运行：

### Candidate command

- 从项目根目录运行：

## 需比较指标

### Summary

- processed_frames：
- runtime_sec / effective_fps：
- tracker_switches：
- reacquired_count：
- face_detected_frames：
- total_face_misses / max_face_miss_streak：

### Frame Metrics

- FACE_LOCK / HEAD_PROXY / LOST 分布：
- filtered_target_center 平均偏移：
- filtered_target_center 最大偏移：
- control_state 分布：
- 关键帧：

### Performance

- frame_total_ms：
- collect_candidates_ms：
- detect_track_ms：
- face_detect_total_ms：
- face_detect_mtcnn_ms：
- embedding_ms：
- write_video_ms / show_ms：

### Realtime Only

- camera_fps：
- process_fps：
- display_fps：
- process_latency_ms：
- total_dropped_frames：
- max_dropped_frames：
- dropped_frames_before：

## 判定标准

- pass：目标指标达成，且身份、几何和控制中心无关键回归。
- conditional-pass：有收益，但存在可接受退化或使用场景限制。
- fail：关键质量、身份连续性、实时性或输出兼容性恶化。
- inconclusive：缺少同源 A/B、逐帧指标、性能证据或关键帧检查。

## 结论

- Verdict：
- 速度结论：
- 质量结论：
- 实时结论：
- 证据缺口：
- 下一步：