# Corner Case Tuning Results

- Source video: Q:\20260528-160426.mp4
- Run ID: corner_20260528_160426
- Project: runs/lock_target_corner_cases/corner_20260528_160426
- Live log: runs/corner_case_tuning_logs/corner_20260528_160426/corner_case_tuning_live.log

## Experiment Table

| ID | Name | Params | Runtime Sec | FPS | FACE_LOCK | HEAD_PROXY | LOST | Tracker Switches | Reacquired | Face Detected | Face Misses | Embedding Calls | MTCNN Calls | Quality vs C0 | Speed vs C0 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | corner_baseline | baseline full | 953.338 | 0.812 | 748 | 19 | 1 | 8 | 2 | 719 | 25 | 766 | 737 | FACE_LOCK =0; HEAD_PROXY =0; switch =0 | fps 0; runtime 0 sec |
| C1 | corner_img1152 | --imgsz 1152 | 1025.827 | 0.755 | 724 | 16 | 29 | 13 | 3 | 671 | 20 | 771 | 686 | FACE_LOCK -24; HEAD_PROXY -3; switch +5 | fps -0.057; runtime 72.489 sec |
| C2 | corner_conf020 | --conf 0.20 | 824.391 | 0.939 | 748 | 19 | 1 | 8 | 2 | 719 | 25 | 766 | 737 | FACE_LOCK =0; HEAD_PROXY =0; switch =0 | fps 0.127; runtime -128.947 sec |
| C3 | corner_face_scale103 | --face-scale-factor 1.03 | 966.65 | 0.801 | 754 | 14 | 1 | 8 | 2 | 725 | 19 | 774 | 735 | FACE_LOCK +6; HEAD_PROXY -5; switch =0 | fps -0.011; runtime 13.312 sec |
| C4 | corner_face_conf025 | --face-min-confidence 0.25 | 793.773 | 0.975 | 748 | 19 | 1 | 8 | 2 | 719 | 25 | 766 | 737 | FACE_LOCK =0; HEAD_PROXY =0; switch =0 | fps 0.163; runtime -159.565 sec |
| C5 | corner_reacq_loose | --min-appearance 0.30 --reacquire-thresh 0.40 | 779.494 | 0.993 | 748 | 19 | 1 | 8 | 2 | 719 | 25 | 766 | 737 | FACE_LOCK =0; HEAD_PROXY =0; switch =0 | fps 0.181; runtime -173.844 sec |
| C6 | corner_reacq_strict | --min-appearance 0.40 --reacquire-thresh 0.50 | 788.452 | 0.982 | 748 | 19 | 1 | 8 | 2 | 719 | 25 | 766 | 737 | FACE_LOCK =0; HEAD_PROXY =0; switch =0 | fps 0.17; runtime -164.886 sec |
| C7 | corner_control_stable | --control-alpha 0.82 --control-max-step 25 | 789.735 | 0.98 | 748 | 19 | 1 | 8 | 2 | 719 | 25 | 766 | 737 | FACE_LOCK =0; HEAD_PROXY =0; switch =0 | fps 0.168; runtime -163.603 sec |
| C8 | corner_mtcnn2 | --mtcnn-interval 2 | 783.675 | 0.988 | 713 | 54 | 1 | 8 | 2 | 688 | 56 | 735 | 372 | FACE_LOCK -35; HEAD_PROXY +35; switch =0 | fps 0.176; runtime -169.663 sec |

## Notes

- Monitor output is updated by tools/tuning/monitor_manual_offline_experiment.ps1 in corner mode.
- Final conclusions still require summary.json, frame_metrics.json, performance.json, and manual key-frame review.
