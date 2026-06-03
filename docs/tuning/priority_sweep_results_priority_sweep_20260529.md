# Priority Sweep Tuning Results

- Source video: Q:\20260528-160426.mp4
- Run ID: priority_sweep_20260529
- Project: runs/lock_target_priority_sweep/priority_sweep_20260529
- Plan: docs/tuning/priority_sweep_experiment_plan_priority_sweep_20260529.md
- Live log: runs/priority_sweep_logs/priority_sweep_20260529/priority_sweep_live.log

## Experiment Table

| ID | Name | Phase | Model | ReID Model | Params | Runtime Sec | FPS | FACE_LOCK | HEAD_PROXY | LOST | SEARCHING | Tracker Switches | Reacquired | Face Detected | Face Misses | Max Face Miss Streak | Embedding Calls | MTCNN Calls | Frame Avg ms | Collect Avg ms | Embedding Avg ms | MTCNN Avg ms | Speed Impact | Quality Impact | Analysis |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | priority_baseline | baseline | yolo26n.pt | yolo26l.pt | baseline full | 843.281 | 0.918 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 766 | 737 | 1083.44 | 908.81 | 424.36 | 70.79 | near baseline | slightly better | same-source baseline for the priority sweep video |
| P1 | priority_reid_interval4 | reid-interval | yolo26n.pt | yolo26l.pt | --reid-interval 4 | 675.803 | 1.145 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 235 | 737 | 866.77 | 672.57 | 497.78 | 82.93 | slightly faster | slightly better | reid-interval: speed is slightly faster (fps 0.227; runtime -167.478 sec), quality is slightly better (FACE_LOCK 0; HEAD_PROXY 0; LOST 0; switch 0; face_miss 0) |
| P2 | priority_reid_interval6 | reid-interval | yolo26n.pt | yolo26l.pt | --reid-interval 6 | 563.545 | 1.373 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 177 | 737 | 722.61 | 566.28 | 416.34 | 64.92 | faster | slightly better | reid-interval: speed is faster (fps 0.455; runtime -279.736 sec), quality is slightly better (FACE_LOCK 0; HEAD_PROXY 0; LOST 0; switch 0; face_miss 0) |
| P3 | priority_reid_interval8 | reid-interval | yolo26n.pt | yolo26l.pt | --reid-interval 8 | 540.558 | 1.432 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 146 | 737 | 693.06 | 543.65 | 410.36 | 63 | faster | slightly better | reid-interval: speed is faster (fps 0.514; runtime -302.723 sec), quality is slightly better (FACE_LOCK 0; HEAD_PROXY 0; LOST 0; switch 0; face_miss 0) |
| P4 | priority_reid_interval10 | reid-interval | yolo26n.pt | yolo26l.pt | --reid-interval 10 | 531.158 | 1.457 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 126 | 737 | 680.91 | 530.09 | 408.42 | 63.43 | faster | slightly better | reid-interval: speed is faster (fps 0.539; runtime -312.123 sec), quality is slightly better (FACE_LOCK 0; HEAD_PROXY 0; LOST 0; switch 0; face_miss 0) |
| P5 | priority_face_scale102 | face-scale-factor | yolo26n.pt | yolo26l.pt | --face-scale-factor 1.02 | 1017.662 | 0.761 | 755 | 18 | 1 | 0 | 8 | 1 | 730 | 18 | 4 | 779 | 739 | 1309.26 | 1152.34 | 373.37 | 63.25 | slightly slower | slightly better | face-scale-factor: speed is slightly slower (fps -0.157; runtime 174.381 sec), quality is slightly better (FACE_LOCK 7; HEAD_PROXY -1; LOST 0; switch 0; face_miss -7) |
| P6 | priority_face_scale103 | face-scale-factor | yolo26n.pt | yolo26l.pt | --face-scale-factor 1.03 | 970.684 | 0.797 | 754 | 14 | 1 | 5 | 8 | 2 | 725 | 19 | 11 | 774 | 735 | 1248.48 | 1088.79 | 380.84 | 65.12 | slightly slower | slightly better | face-scale-factor: speed is slightly slower (fps -0.121; runtime 127.403 sec), quality is slightly better (FACE_LOCK 6; HEAD_PROXY -5; LOST 0; switch 0; face_miss -6) |
| P7 | priority_face_scale104 | face-scale-factor | yolo26n.pt | yolo26l.pt | --face-scale-factor 1.04 | 872.793 | 0.887 | 749 | 18 | 1 | 6 | 6 | 1 | 720 | 24 | 12 | 767 | 738 | 1121.84 | 958.57 | 395.59 | 67.12 | near baseline | slightly better | face-scale-factor: speed is near baseline (fps -0.031; runtime 29.512 sec), quality is slightly better (FACE_LOCK 1; HEAD_PROXY -1; LOST 0; switch -2; face_miss -1) |
| P8 | priority_face_conf025 | face-min-confidence | yolo26n.pt | yolo26l.pt | --face-min-confidence 0.25 | 803.217 | 0.964 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 766 | 737 | 1031.97 | 869.88 | 396.91 | 64.95 | near baseline | slightly better | face-min-confidence: speed is near baseline (fps 0.046; runtime -40.064 sec), quality is slightly better (FACE_LOCK 0; HEAD_PROXY 0; LOST 0; switch 0; face_miss 0) |
| P9 | priority_face_conf028 | face-min-confidence | yolo26n.pt | yolo26l.pt | --face-min-confidence 0.28 | 831.192 | 0.931 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 766 | 737 | 1067.9 | 897.18 | 414.8 | 67.25 | near baseline | slightly better | face-min-confidence: speed is near baseline (fps 0.013; runtime -12.089 sec), quality is slightly better (FACE_LOCK 0; HEAD_PROXY 0; LOST 0; switch 0; face_miss 0) |
| P10 | priority_detector_yolo26l | detector-model | yolo26l.pt | yolo26l.pt | --model yolo26l.pt | 1242.267 | 0.623 | 748 | 22 | 0 | 4 | 4 | 1 | 734 | 26 | 10 | 788 | 755 | 1598.96 | 866.55 | 426.76 | 61.29 | slower | slightly better | detector-model: speed is slower (fps -0.295; runtime 398.986 sec), quality is slightly better (FACE_LOCK 0; HEAD_PROXY 3; LOST -1; switch -4; face_miss 1) |
| P11 | priority_reid_yolo26n | reid-model | yolo26n.pt | yolo26n.pt | --reid-model yolo26n.pt | 537.435 | 1.44 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 766 | 737 | 689.13 | 537.33 | 72.64 | 63.48 | faster | slightly better | reid-model: speed is faster (fps 0.522; runtime -305.846 sec), quality is slightly better (FACE_LOCK 0; HEAD_PROXY 0; LOST 0; switch 0; face_miss 0) |

## Required Review After Each Round

- summary + frame_metrics + performance must all exist before a run is considered complete.
- FACE_LOCK increase must be manually reviewed for fake FACE_LOCK before it is treated as quality improvement.
- HEAD_PROXY is not equivalent to true face lock.
- Tracker id continuity is not enough to prove business identity continuity.
