# Priority Sweep Experiment Plan

- Source video: Q:\20260528-160426.mp4
- Run ID: priority_sweep_20260529
- Project: runs/lock_target_priority_sweep/priority_sweep_20260529
- Live log: runs/priority_sweep_logs/priority_sweep_20260529/priority_sweep_live.log
- yolo26x.pt available: False

## Order

1. Baseline on the same source.
2. ReID interval sweep: 4 / 6 / 8 / 10.
3. Face recall local sweep: face-scale-factor, then face-min-confidence.
4. Detector model A/B: yolo26n.pt versus yolo26l.pt.
5. ReID model A/B: yolo26l.pt versus yolo26n.pt.
6. Optional yolo26x.pt only if the weight exists.

## Planned Experiments

| ID | Name | Phase | Model | ReID Model | Params | Direction | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | priority_baseline | baseline | yolo26n.pt | yolo26l.pt | baseline full | Same-source baseline for priority sweep | Must run first; all deltas are relative to this baseline |
| P1 | priority_reid_interval4 | reid-interval | yolo26n.pt | yolo26l.pt | --reid-interval 4 | Test first lightweight ReID refresh step | May reduce identity stability around occlusion or crossings |
| P2 | priority_reid_interval6 | reid-interval | yolo26n.pt | yolo26l.pt | --reid-interval 6 | Measure medium ReID refresh sparsity | Embedding calls should drop; quality must not be inferred from speed alone |
| P3 | priority_reid_interval8 | reid-interval | yolo26n.pt | yolo26l.pt | --reid-interval 8 | Re-test previous speed-oriented boundary on this source | Higher risk of delayed identity correction |
| P4 | priority_reid_interval10 | reid-interval | yolo26n.pt | yolo26l.pt | --reid-interval 10 | Stress-test upper ReID interval boundary | May over-sparsify appearance refresh and hide ID drift |
| P5 | priority_face_scale102 | face-scale-factor | yolo26n.pt | yolo26l.pt | --face-scale-factor 1.02 | Local sweep around C3 face-scale-factor gain | More face candidates and false FACE_LOCK risk |
| P6 | priority_face_scale103 | face-scale-factor | yolo26n.pt | yolo26l.pt | --face-scale-factor 1.03 | Repeat previous best face-scale setting in priority sequence | Needs manual key-frame review before calling it better |
| P7 | priority_face_scale104 | face-scale-factor | yolo26n.pt | yolo26l.pt | --face-scale-factor 1.04 | Check whether gain remains near default scale | May lose C3 benefit while retaining extra cost |
| P8 | priority_face_conf025 | face-min-confidence | yolo26n.pt | yolo26l.pt | --face-min-confidence 0.25 | Relax MTCNN confidence for face recall | False FACE_LOCK risk; do not equate more detections with better lock |
| P9 | priority_face_conf028 | face-min-confidence | yolo26n.pt | yolo26l.pt | --face-min-confidence 0.28 | Intermediate face confidence threshold between C4 and baseline | Small deltas may be inconclusive without key-frame review |
| P10 | priority_detector_yolo26l | detector-model | yolo26l.pt | yolo26l.pt | --model yolo26l.pt | Detector model A/B: yolo26n.pt versus yolo26l.pt | Likely slower; quality must improve enough to justify cost |
| P11 | priority_reid_yolo26n | reid-model | yolo26n.pt | yolo26n.pt | --reid-model yolo26n.pt | ReID model A/B for lightweight embedding cost | May reduce appearance discrimination even if faster |
| skipped | priority_detector_yolo26x | optional-detector-model | yolo26x.pt | yolo26l.pt | --model yolo26x.pt | Optional quality-first test | Skipped because yolo26x.pt is missing |

## Required Evidence

- summary: runtime_sec, effective_fps, tracker_switches, reacquired_count, face_detected_frames, total_face_misses, max_face_miss_streak.
- frame_metrics: FACE_LOCK / HEAD_PROXY / LOST / SEARCHING distribution and manual key-frame review for fake FACE_LOCK.
- performance: frame_total_ms, collect_candidates_ms, embedding_ms, face_detect_mtcnn_ms, embedding_calls, face_detect_mtcnn_calls.
- A speed win is not accepted unless quality stays same-source comparable.
