# Corner Case Tuning Progress

## Status

- State: ready-for-next-manual
- Last update: 2026-05-28 18:32:51
- Current experiment: waiting for next manual launch
- Source video: Q:\20260528-160426.mp4
- Python: C:/Users/Stuart.Cai/AppData/Local/Programs/Python/Python310/python.exe
- Live log: runs/corner_case_tuning_logs/corner_20260528_160426/corner_case_tuning_live.log
- Results table: docs/tuning/corner_case_tuning_results_corner_20260528_160426.md

- Note: Completed C8. Results table updated.

## Completed Summary

- C0-C8 corner case 调参已经全部完成，本页当前主要用于保留执行顺序、完成时间和落盘状态。
- 这一阶段的核心价值是把评估场景从早期基线视频推进到更具遮挡、转头和控制稳定性挑战的 source 上，为后续 priority sweep 提供更有针对性的参数方向。
- 其中与人脸尺度、MTCNN 调用频率、控制稳定性相关的观察，已经被吸收到主分析报告中，后续判断应以总报告为准。

## Next Step

- 继续判断参数优劣时，应优先参考后续 P0-P11 的 priority sweep，而不是只看 C0-C8 的单轮结果。
- 如果要复盘本阶段执行是否完整，本页日志和对应 results 文档仍是最直接的核验入口。

## Planned Experiments

| ID | Name | Parameter Changes | Status | Notes |
| --- | --- | --- | --- | --- |
| C0 | corner_baseline | baseline full | completed | JSON ready |
| C1 | corner_img1152 | --imgsz 1152 | completed | JSON ready |
| C2 | corner_conf020 | --conf 0.20 | completed | JSON ready |
| C3 | corner_face_scale103 | --face-scale-factor 1.03 | completed | JSON ready |
| C4 | corner_face_conf025 | --face-min-confidence 0.25 | completed | JSON ready |
| C5 | corner_reacq_loose | --min-appearance 0.30 --reacquire-thresh 0.40 | completed | JSON ready |
| C6 | corner_reacq_strict | --min-appearance 0.40 --reacquire-thresh 0.50 | completed | JSON ready |
| C7 | corner_control_stable | --control-alpha 0.82 --control-max-step 25 | completed | JSON ready |
| C8 | corner_mtcnn2 | --mtcnn-interval 2 | completed | JSON ready |

## Execution Log

- [2026-05-28 18:24:49] Heartbeat C8 pid=38808 mp4_bytes=7864364
- [2026-05-28 18:25:19] Heartbeat C8 pid=38808 mp4_bytes=8912940
- [2026-05-28 18:25:49] Heartbeat C8 pid=38808 mp4_bytes=9699372
- [2026-05-28 18:26:19] Heartbeat C8 pid=38808 mp4_bytes=10223660
- [2026-05-28 18:26:49] Heartbeat C8 pid=38808 mp4_bytes=11010092
- [2026-05-28 18:27:19] Heartbeat C8 pid=38808 mp4_bytes=11796524
- [2026-05-28 18:27:49] Heartbeat C8 pid=38808 mp4_bytes=12320812
- [2026-05-28 18:28:19] Heartbeat C8 pid=38808 mp4_bytes=12845100
- [2026-05-28 18:28:49] Heartbeat C8 pid=38808 mp4_bytes=13369388
- [2026-05-28 18:29:19] Heartbeat C8 pid=38808 mp4_bytes=13893676
- [2026-05-28 18:29:49] Heartbeat C8 pid=38808 mp4_bytes=14680108
- [2026-05-28 18:30:19] Heartbeat C8 pid=38808 mp4_bytes=15728684
- [2026-05-28 18:30:49] Heartbeat C8 pid=38808 mp4_bytes=16515116
- [2026-05-28 18:31:19] Heartbeat C8 pid=38808 mp4_bytes=17039404
- [2026-05-28 18:31:49] Heartbeat C8 pid=38808 mp4_bytes=17563692
- [2026-05-28 18:32:19] Heartbeat C8 pid=38808 mp4_bytes=18612268
- [2026-05-28 18:32:46] Completed C8 corner_mtcnn2 fps=0.988 runtime=783.675 face_lock=713 head_proxy=54 switches=8
- [2026-05-28 18:32:49] All corner-case experiments completed successfully.
- [2026-05-28 18:32:49] Heartbeat C8 pid=38808 mp4_bytes=19256303
- [2026-05-28 18:32:51] Completed C8 corner_mtcnn2 fps=0.988 runtime=783.675
