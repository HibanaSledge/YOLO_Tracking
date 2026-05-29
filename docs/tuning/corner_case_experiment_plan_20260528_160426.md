# Corner Case 调参实验计划：20260528-160426

## 1. 实验目标

本轮实验使用新输入视频 `Q:\20260528-160426.mp4`，目标是按 [lock_target_parameter_table.md](lock_target_parameter_table.md) 中列出的高影响参数，测试 corner case 下算法质量、速度和控制输出的变化。

本轮不是随机扫参，而是围绕 corner case 最可能受影响的五类问题设计：

1. 主检测召回和 person 框稳定性。
2. FACE_LOCK 真实脸框召回。
3. 遮挡/转身/多人干扰后的业务目标重绑定。
4. 云台前端需要的 filtered target center 稳定性。
5. 轻量化参数对 corner case 质量退化的边界。

## 2. 固定基线

所有实验默认保持：

- `--model yolo26n.pt`
- `--tracker cfg/trackers/botsort.yaml`
- `--reid-model yolo26l.pt`
- `--classes 0`
- `--conf 0.25`
- `--iou 0.5`
- `--imgsz 960`
- `--initial-track-id 1`
- `--fallback-to-first-face`
- `--save-all-boxes`

输出目录：

- `runs/lock_target_corner_cases/corner_20260528_160426/`

日志目录：

- `runs/corner_case_tuning_logs/corner_20260528_160426/`

结果表：

- `docs/tuning/corner_case_tuning_results_corner_20260528_160426.md`

进度表：

- `docs/tuning/corner_case_tuning_progress_corner_20260528_160426.md`

## 3. 实验轮次设计

| ID | Name | 测试方向 | 参数变化 | 动机 | 主要观察指标 | 风险 |
| --- | --- | --- | --- | --- | --- | --- |
| C0 | `corner_baseline` | 新视频同源基线 | baseline | 必须先建立同源 baseline，否则 C1-C8 无法归因 | 全部 summary/frame_metrics/performance 指标 | 无对照前不能下结论 |
| C1 | `corner_img1152` | 主检测细节增强 | `--imgsz 1152` | 参数表第 1 优先级；验证小脸、边缘目标、模糊目标是否改善 | FACE_LOCK、tracker_switches、runtime、frame_total_ms | 速度显著下降；底层轨迹分布可能改变 |
| C2 | `corner_conf020` | 弱检测召回 | `--conf 0.20` | 暗光、运动模糊、高速场景下弱检测更容易被过滤 | face_detected_frames、FACE_LOCK、tracker_switches | 误检增加，可能导致误绑 |
| C3 | `corner_face_scale103` | classical face 召回 | `--face-scale-factor 1.03` | 参数表中 face-scale-factor 是脸框召回核心参数 | FACE_LOCK、HEAD_PROXY、face_misses、collect_candidates_ms | 更慢，假脸候选可能增加 |
| C4 | `corner_face_conf025` | MTCNN face 召回 | `--face-min-confidence 0.25` | 侧脸、遮挡、暗光会让 MTCNN 置信度下降 | FACE_LOCK、HEAD_PROXY、max_face_miss_streak | 假 FACE_LOCK 风险上升，需要人工抽查视频 |
| C5 | `corner_reacq_loose` | 宽松重绑定 | `--min-appearance 0.30 --reacquire-thresh 0.40` | 测试遮挡、转身、ID 断裂后是否更容易找回同一业务目标 | tracker_switches、reacquired_count、误绑关键帧 | 多人/相似外观时更容易误绑 |
| C6 | `corner_reacq_strict` | 严格重绑定 | `--min-appearance 0.40 --reacquire-thresh 0.50` | 测试收紧身份门限是否减少错误恢复和误绑 | tracker_switches、reacquired_count、LOST、HEAD_PROXY | 过保守会找不回目标 |
| C7 | `corner_control_stable` | 控制中心稳定 | `--control-alpha 0.82 --control-max-step 25` | 面向云台控制，测试强抖动下输出是否更稳 | filtered_target_center、control_active、control_distance_to_center | 响应变慢，快速运动拖尾 |
| C8 | `corner_mtcnn2` | 真实脸刷新频率轻量化边界 | `--mtcnn-interval 2` | 单独测试 mtcnn-interval，不与 reid-interval 混改，观察速度收益与脸框退化 | MTCNN calls、face_detect_mtcnn_ms、FACE_LOCK、HEAD_PROXY | 真实脸框刷新变稀，中心偏移可能恶化 |

## 4. 为什么选择这 9 轮

- C0 是新视频基线，必须有。
- C1、C2 对应主检测质量：`imgsz` 和 `conf` 是参数表中最高优先级检测参数。
- C3、C4 对应脸框几何：`face-scale-factor` 与 `face-min-confidence` 直接决定 FACE_LOCK 召回。
- C5、C6 对应身份连续性：`min-appearance` 和 `reacquire-thresh` 是重绑定核心闸门，宽松/严格成对测试便于判断方向。
- C7 对应云台控制输出：corner case 不只看锁定框，也要看 filtered target center 是否适合控制。
- C8 对应轻量化风险边界：单独测试 `mtcnn-interval`，避免和 `reid-interval` 混合后无法归因。

## 5. 每轮必须检查的指标

### summary.json

- `runtime_sec`
- `effective_fps`
- `tracker_switches`
- `reacquired_count`
- `face_detected_frames`
- `total_face_misses`
- `max_face_miss_streak`

### frame_metrics.json

- `lock_mode` 分布：FACE_LOCK / HEAD_PROXY / LOST / SEARCHING。
- `filtered_target_center` 是否抖动或拖尾。
- `control_offset` 和 `control_distance_to_center` 是否异常。
- 人工抽查是否存在假 FACE_LOCK：框在耳侧、后脑、头顶，但被统计为 FACE_LOCK。

### performance.json

- `frame_total_ms`
- `collect_candidates_ms`
- `embedding_ms`
- `face_detect_mtcnn_ms`
- `embedding_calls`
- `face_detect_mtcnn_calls`

## 6. 判定标准

| 标签 | 判定条件 |
| --- | --- |
| pass | 质量指标改善，且速度退化可接受；或速度改善且 FACE_LOCK/HEAD_PROXY/误绑没有明显恶化 |
| conditional-pass | 某一目标达成，但存在明确场景限制，例如更稳但拖尾、更快但 FACE_LOCK 小幅下降 |
| fail | FACE_LOCK 明显下降、HEAD_PROXY/LOST 明显上升、误绑增加，或速度下降但质量无收益 |
| inconclusive | 缺少同源 baseline、关键 JSON 不完整、或未人工抽查关键帧 |

## 7. 执行命令

在仓库根目录执行：

```powershell
.\tools\tuning\run_corner_case_tuning.ps1 -SourceVideo "Q:\20260528-160426.mp4" -RunId corner_20260528_160426
```

如果需要覆盖已经存在的同名实验输出：

```powershell
.\tools\tuning\run_corner_case_tuning.ps1 -SourceVideo "Q:\20260528-160426.mp4" -RunId corner_20260528_160426 -Force
```

## 8. 证据缺口

本计划尚未运行实验，因此目前只有实验设计和执行脚本，没有新视频上的真实结论。实验完成后必须以 `summary.json`、`frame_metrics.json`、`performance.json` 和视频关键帧人工检查共同下结论。
