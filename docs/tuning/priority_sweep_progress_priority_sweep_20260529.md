# Priority Sweep Tuning Progress

- State: completed
- Last update: 2026-05-29 21:10:18
- Current experiment: all experiments finished
- Source video: Q:\20260528-160426.mp4
- Python: C:/Users/Stuart.Cai/AppData/Local/Programs/Python/Python310/python.exe
- Run ID: priority_sweep_20260529
- Plan: docs/tuning/priority_sweep_experiment_plan_priority_sweep_20260529.md
- Results table: docs/tuning/priority_sweep_results_priority_sweep_20260529.md
- Live log: runs/priority_sweep_logs/priority_sweep_20260529/priority_sweep_live.log

- Note: Priority sweep experiments completed successfully.

## Completed Summary

- P0-P11 priority sweep 已全部完成，当前这是离线调参链路中最接近“下一步默认候选筛选”的一轮实验。
- 从总分析口径看，P4、P5、P6、P11 是当前最值得继续复核的方向，但这些结果仍不能脱离人工关键帧复核单独成立。
- 本页的职责是保留 sweep 计划和执行日志；真正的工程结论应以 [docs/tuning/offline_tuning_analysis_report.md](docs/tuning/offline_tuning_analysis_report.md) 中对应章节为准。

## Next Step

- 如果当前目标是选默认方案，先做 P4、P5、P6、P11 的人工关键帧复核。
- 如果当前目标是继续扩参，先确认现有候选的真收益与假收益，再决定是否新增实验，而不是继续盲目 sweep。

## Planned Experiments

| ID | Name | Phase | Model | ReID Model | Params | Status | Direction | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | priority_baseline | baseline | yolo26n.pt | yolo26l.pt | baseline full | completed | Same-source baseline for priority sweep | Must run first; all deltas are relative to this baseline |
| P1 | priority_reid_interval4 | reid-interval | yolo26n.pt | yolo26l.pt | --reid-interval 4 | completed | Test first lightweight ReID refresh step | May reduce identity stability around occlusion or crossings |
| P2 | priority_reid_interval6 | reid-interval | yolo26n.pt | yolo26l.pt | --reid-interval 6 | completed | Measure medium ReID refresh sparsity | Embedding calls should drop; quality must not be inferred from speed alone |
| P3 | priority_reid_interval8 | reid-interval | yolo26n.pt | yolo26l.pt | --reid-interval 8 | completed | Re-test previous speed-oriented boundary on this source | Higher risk of delayed identity correction |
| P4 | priority_reid_interval10 | reid-interval | yolo26n.pt | yolo26l.pt | --reid-interval 10 | completed | Stress-test upper ReID interval boundary | May over-sparsify appearance refresh and hide ID drift |
| P5 | priority_face_scale102 | face-scale-factor | yolo26n.pt | yolo26l.pt | --face-scale-factor 1.02 | completed | Local sweep around C3 face-scale-factor gain | More face candidates and false FACE_LOCK risk |
| P6 | priority_face_scale103 | face-scale-factor | yolo26n.pt | yolo26l.pt | --face-scale-factor 1.03 | completed | Repeat previous best face-scale setting in priority sequence | Needs manual key-frame review before calling it better |
| P7 | priority_face_scale104 | face-scale-factor | yolo26n.pt | yolo26l.pt | --face-scale-factor 1.04 | completed | Check whether gain remains near default scale | May lose C3 benefit while retaining extra cost |
| P8 | priority_face_conf025 | face-min-confidence | yolo26n.pt | yolo26l.pt | --face-min-confidence 0.25 | completed | Relax MTCNN confidence for face recall | False FACE_LOCK risk; do not equate more detections with better lock |
| P9 | priority_face_conf028 | face-min-confidence | yolo26n.pt | yolo26l.pt | --face-min-confidence 0.28 | completed | Intermediate face confidence threshold between C4 and baseline | Small deltas may be inconclusive without key-frame review |
| P10 | priority_detector_yolo26l | detector-model | yolo26l.pt | yolo26l.pt | --model yolo26l.pt | completed | Detector model A/B: yolo26n.pt versus yolo26l.pt | Likely slower; quality must improve enough to justify cost |
| P11 | priority_reid_yolo26n | reid-model | yolo26n.pt | yolo26n.pt | --reid-model yolo26n.pt | completed | ReID model A/B for lightweight embedding cost | May reduce appearance discrimination even if faster |
| skipped | priority_detector_yolo26x | optional-detector-model | yolo26x.pt | yolo26l.pt | --model yolo26x.pt | skipped | Optional quality-first test | yolo26x.pt is missing |

## Execution Log

- [2026-05-29 21:00:43] Starting P11 priority_reid_yolo26n model=yolo26n.pt reid_model=yolo26n.pt params=--reid-model yolo26n.pt
- [2026-05-29 21:01:13] Heartbeat P11 pid=35068 mp4_bytes=786476
- [2026-05-29 21:01:43] Heartbeat P11 pid=35068 mp4_bytes=2097196
- [2026-05-29 21:02:13] Heartbeat P11 pid=35068 mp4_bytes=2883628
- [2026-05-29 21:02:43] Heartbeat P11 pid=35068 mp4_bytes=3932204
- [2026-05-29 21:03:13] Heartbeat P11 pid=35068 mp4_bytes=4456492
- [2026-05-29 21:03:43] Heartbeat P11 pid=35068 mp4_bytes=5242924
- [2026-05-29 21:04:13] Heartbeat P11 pid=35068 mp4_bytes=6291500
- [2026-05-29 21:04:43] Heartbeat P11 pid=35068 mp4_bytes=7602220
- [2026-05-29 21:05:13] Heartbeat P11 pid=35068 mp4_bytes=8388652
- [2026-05-29 21:05:43] Heartbeat P11 pid=35068 mp4_bytes=9699372
- [2026-05-29 21:06:13] Heartbeat P11 pid=35068 mp4_bytes=10485804
- [2026-05-29 21:06:43] Heartbeat P11 pid=35068 mp4_bytes=11010092
- [2026-05-29 21:07:13] Heartbeat P11 pid=35068 mp4_bytes=11796524
- [2026-05-29 21:07:43] Heartbeat P11 pid=35068 mp4_bytes=12582956
- [2026-05-29 21:08:13] Heartbeat P11 pid=35068 mp4_bytes=13893676
- [2026-05-29 21:08:43] Heartbeat P11 pid=35068 mp4_bytes=14680108
- [2026-05-29 21:09:13] Heartbeat P11 pid=35068 mp4_bytes=15728684
- [2026-05-29 21:09:44] Heartbeat P11 pid=35068 mp4_bytes=16777260
- [2026-05-29 21:10:14] Completed P11 priority_reid_yolo26n fps=1.44 runtime=537.435 face_lock=748 head_proxy=19 lost=1 switches=8 embedding_calls=766 mtcnn_calls=737
