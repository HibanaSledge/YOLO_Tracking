# Offline Tuning Progress

## Status

- State: completed
- Last update: 2026-05-28 11:13:03
- Current experiment: all experiments finished
- Source video: Q:\20260521-120258.mp4
- Python: C:/Users/Stuart.Cai/AppData/Local/Programs/Python/Python310/python.exe
- Live log: runs/offline_tuning_logs/offline_tuning_live.log
- Results table: docs/tuning/offline_tuning_results.md

- Note: G2-G7 auto-resume completed successfully.

## Completed Summary

- 本文档记录的 G1-G7 常规离线调参已经全部完成，当前职责主要是保留执行过程和完成状态。
- 从后续总分析看，这一阶段最重要的结论不是直接选出最终参数，而是先定位了 `imgsz`、ReID 刷新、人脸检测刷新和重绑定阈值各自的影响方向。
- 当前应结合 [docs/tuning/offline_tuning_analysis_report.md](docs/tuning/offline_tuning_analysis_report.md) 一起阅读，避免只根据本页日志把某个单轮实验误判为最终答案。

## Next Step

- 如果需要当前可执行结论，请转到主报告中的 C0-C8 和 P0-P11 分析，而不要停留在 G1-G7 单阶段判断。
- 如果需要复盘执行过程，本页保留的 heartbeat 和 completed 日志仍可用于确认实验是否完整落盘。

## Planned Experiments

| ID | Name | Parameter Changes | Status | Notes |
| --- | --- | --- | --- | --- |
| G1 | detect_img1152 | --imgsz 1152 | completed | JSON ready |
| G2 | face_recall_boost | --face-scale-factor 1.03 --face-min-confidence 0.25 | completed | JSON ready |
| G3 | reacquire_loose | --min-appearance 0.32 --reacquire-thresh 0.42 | completed | JSON ready |
| G4 | reacquire_strict | --min-appearance 0.38 --reacquire-thresh 0.48 | completed | JSON ready |
| G5 | reid_interval_8 | --reid-interval 8 | completed | JSON ready |
| G6 | mtcnn_interval_3 | --mtcnn-interval 3 | completed | JSON ready |
| G7 | light_balanced | --reid-interval 4 --mtcnn-interval 2 | completed | JSON ready |

## Execution Log

- [2026-05-28 09:58:41] Heartbeat G1 pid=18812 mp4_bytes=23855148
- [2026-05-28 09:58:56] Completed G1 detect_img1152 fps=0.557 runtime=1311.694
- [2026-05-28 09:58:56] Starting G2 face_recall_boost
- [2026-05-28 09:59:11] Heartbeat G1 pid=18812 mp4_bytes=24228284
- [2026-05-28 09:59:12] Detected completion for G1 detect_img1152; continuing remaining experiments
- [2026-05-28 09:59:12] Starting G2 face_recall_boost
- [2026-05-28 10:03:12] Completed G1 detect_img1152 fps=0.518 runtime=1411.213
- [2026-05-28 10:04:50] Resume runner armed after G2 face_recall_boost
- [2026-05-28 10:17:52] Detected completion for G2 face_recall_boost; continuing remaining experiments
- [2026-05-28 10:17:52] Starting G3 reacquire_loose
- [2026-05-28 10:31:08] Completed G3 reacquire_loose fps=0.929 runtime=787.143
- [2026-05-28 10:31:08] Starting G4 reacquire_strict
- [2026-05-28 10:44:15] Completed G4 reacquire_strict fps=0.938 runtime=779.289
- [2026-05-28 10:44:15] Starting G5 reid_interval_8
- [2026-05-28 10:52:44] Completed G5 reid_interval_8 fps=1.458 runtime=501.478
- [2026-05-28 10:52:44] Starting G6 mtcnn_interval_3
- [2026-05-28 11:03:56] Completed G6 mtcnn_interval_3 fps=1.099 runtime=665.433
- [2026-05-28 11:03:56] Starting G7 light_balanced
- [2026-05-28 11:13:02] Completed G7 light_balanced fps=1.358 runtime=538.486
- [2026-05-28 11:13:03] Remaining experiments completed successfully.
