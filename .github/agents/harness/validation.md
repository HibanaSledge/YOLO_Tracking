# Validation

## Documentation / Agent Config Validation

- 文件结构符合目标目录。
- Markdown 链接指向真实文件。
- agent 入口引用 instruction、skills、context、harness、templates。
- 无旧路径误导，例如把 harness 工程放在 skill 文件里。

## Code Validation

- 语法检查。
- 相关单元测试。
- CLI `--help` 或最小运行。
- 输出字段兼容性检查。

## Offline Experiment Validation

- summary：processed_frames、runtime、effective_fps、tracker_switches、reacquired_count。
- frame_metrics：FACE_LOCK/HEAD_PROXY/LOST 分布、center 偏移。
- performance：collect_candidates、embedding、MTCNN、frame_total。

## Realtime Validation

- camera_fps、process_fps、display_fps。
- process_latency_ms。
- total_dropped_frames、max_dropped_frames、dropped_frames_before。
- 保存视频是否符合处理帧语义。

## Verdict Labels

- pass：目标达成且无关键回归。
- conditional-pass：目标达成但有场景限制或可接受退化。
- fail：关键指标恶化。
- inconclusive：证据不足。