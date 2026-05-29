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
