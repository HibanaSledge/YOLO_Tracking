# Offline Tuning Results

## Experiment Table

| ID | Name | Parameter Focus | Params | Runtime Sec | FPS | FACE_LOCK | HEAD_PROXY | LOST | Tracker Switches | Reacquired | Face Detected | Face Misses | Embedding Calls | MTCNN Calls | Speed vs Full | Quality vs Full | Speed vs Light | Quality vs Light | Speed Impact | Quality Impact | Analysis |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline_full | offline_run | baseline | baseline full | 675.325 | 1.082 | 565 | 98 | 48 | 5 | 3 | 551 | 110 | 645 | 791 | fps 0; runtime 0 sec | FACE_LOCK =0; HEAD_PROXY =0; switch =0 | fps -0.601; runtime 241.076 sec | FACE_LOCK +19; HEAD_PROXY -19; switch =0 | near baseline | slightly better | reference row |
| baseline_light | offline_run_light | lightweight preset | lightweight preset | 434.249 | 1.683 | 546 | 117 | 48 | 5 | 3 | 532 | 129 | 166 | 355 | fps 0.601; runtime -241.076 sec | FACE_LOCK -19; HEAD_PROXY +19; switch =0 | fps 0; runtime 0 sec | FACE_LOCK =0; HEAD_PROXY =0; switch =0 | faster | worse | reference row |
| G1 | detect_img1152 | imgsz | --imgsz 1152 | 1411.213 | 0.518 | 565 | 94 | 54 | 11 | 4 | 545 | 100 | 637 | 681 | fps -0.564; runtime 735.888 sec | FACE_LOCK =0; HEAD_PROXY -4; switch +6 | fps -1.165; runtime 976.964 sec | FACE_LOCK +19; HEAD_PROXY -23; switch +6 | slower | worse | imgsz changed fps by -0.564, FACE_LOCK by 0, HEAD_PROXY by -4, tracker_switches by 6 |
| G2 | face_recall_boost | face-scale-factor + face-min-confidence | --face-scale-factor 1.03 --face-min-confidence 0.25 | 1085.249 | 0.674 | 612 | 60 | 48 | 5 | 3 | 598 | 68 | 710 | 773 | fps -0.408; runtime 409.924 sec | FACE_LOCK +47; HEAD_PROXY -38; switch =0 | fps -1.009; runtime 651 sec | FACE_LOCK +66; HEAD_PROXY -57; switch =0 | slower | better | face-scale-factor + face-min-confidence changed fps by -0.408, FACE_LOCK by 47, HEAD_PROXY by -38, tracker_switches by 0 |
| G3 | reacquire_loose | min-appearance + reacquire-thresh (loose) | --min-appearance 0.32 --reacquire-thresh 0.42 | 787.143 | 0.929 | 565 | 98 | 48 | 5 | 3 | 551 | 110 | 645 | 791 | fps -0.153; runtime 111.818 sec | FACE_LOCK =0; HEAD_PROXY =0; switch =0 | fps -0.754; runtime 352.894 sec | FACE_LOCK +19; HEAD_PROXY -19; switch =0 | slightly slower | slightly better | min-appearance + reacquire-thresh (loose) changed fps by -0.153, FACE_LOCK by 0, HEAD_PROXY by 0, tracker_switches by 0 |
| G4 | reacquire_strict | min-appearance + reacquire-thresh (strict) | --min-appearance 0.38 --reacquire-thresh 0.48 | 779.289 | 0.938 | 565 | 98 | 48 | 5 | 3 | 551 | 110 | 645 | 791 | fps -0.144; runtime 103.964 sec | FACE_LOCK =0; HEAD_PROXY =0; switch =0 | fps -0.745; runtime 345.04 sec | FACE_LOCK +19; HEAD_PROXY -19; switch =0 | slightly slower | slightly better | min-appearance + reacquire-thresh (strict) changed fps by -0.144, FACE_LOCK by 0, HEAD_PROXY by 0, tracker_switches by 0 |
| G5 | reid_interval_8 | reid-interval | --reid-interval 8 | 501.478 | 1.458 | 565 | 98 | 48 | 5 | 3 | 551 | 110 | 168 | 791 | fps 0.376; runtime -173.847 sec | FACE_LOCK =0; HEAD_PROXY =0; switch =0 | fps -0.225; runtime 67.229 sec | FACE_LOCK +19; HEAD_PROXY -19; switch =0 | faster | slightly better | reid-interval changed fps by 0.376, FACE_LOCK by 0, HEAD_PROXY by 0, tracker_switches by 0 |
| G6 | mtcnn_interval_3 | mtcnn-interval | --mtcnn-interval 3 | 665.433 | 1.099 | 546 | 117 | 48 | 5 | 3 | 532 | 129 | 626 | 355 | fps 0.017; runtime -9.892 sec | FACE_LOCK -19; HEAD_PROXY +19; switch =0 | fps -0.584; runtime 231.184 sec | FACE_LOCK =0; HEAD_PROXY =0; switch =0 | near baseline | worse | mtcnn-interval changed fps by 0.017, FACE_LOCK by -19, HEAD_PROXY by 19, tracker_switches by 0 |
| G7 | light_balanced | reid-interval + mtcnn-interval | --reid-interval 4 --mtcnn-interval 2 | 538.486 | 1.358 | 552 | 110 | 48 | 5 | 3 | 538 | 123 | 231 | 462 | fps 0.276; runtime -136.839 sec | FACE_LOCK -13; HEAD_PROXY +12; switch =0 | fps -0.325; runtime 104.237 sec | FACE_LOCK +6; HEAD_PROXY -7; switch =0 | faster | worse | reid-interval + mtcnn-interval changed fps by 0.276, FACE_LOCK by -13, HEAD_PROXY by 12, tracker_switches by 0 |

## Notes

- quality deltas are relative summaries against the current full and lightweight baselines.
- speed deltas use effective FPS and runtime_sec from summary.json.
- speed impact and quality impact labels are interpreted against baseline_full.

## Current Analysis

- G1 imgsz: speed is slower, quality is worse. imgsz changed fps by -0.564, FACE_LOCK by 0, HEAD_PROXY by -4, tracker_switches by 6.
- G2 face-scale-factor + face-min-confidence: speed is slower, quality is better. face-scale-factor + face-min-confidence changed fps by -0.408, FACE_LOCK by 47, HEAD_PROXY by -38, tracker_switches by 0.
- G3 min-appearance + reacquire-thresh (loose): speed is slightly slower, quality is slightly better. min-appearance + reacquire-thresh (loose) changed fps by -0.153, FACE_LOCK by 0, HEAD_PROXY by 0, tracker_switches by 0.
- G4 min-appearance + reacquire-thresh (strict): speed is slightly slower, quality is slightly better. min-appearance + reacquire-thresh (strict) changed fps by -0.144, FACE_LOCK by 0, HEAD_PROXY by 0, tracker_switches by 0.
- G5 reid-interval: speed is faster, quality is slightly better. reid-interval changed fps by 0.376, FACE_LOCK by 0, HEAD_PROXY by 0, tracker_switches by 0.
- G6 mtcnn-interval: speed is near baseline, quality is worse. mtcnn-interval changed fps by 0.017, FACE_LOCK by -19, HEAD_PROXY by 19, tracker_switches by 0.
- G7 reid-interval + mtcnn-interval: speed is faster, quality is worse. reid-interval + mtcnn-interval changed fps by 0.276, FACE_LOCK by -13, HEAD_PROXY by 12, tracker_switches by 0.
