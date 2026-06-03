# 离线调参实验分析报告

## 1. 实验范围与目标

- 数据源：Q:\20260521-120258.mp4
- 全量质量基线：runs/lock_target/offline_run
- 轻量化基线：runs/lock_target/offline_run_light
- 调参输出目录：runs/lock_target_tuning
- 分析目标：不仅记录原始指标，还要回答每个参数或参数组合对速度、质量、锁定稳定性分别带来了什么影响，并据此给出后续调参方向。

本报告前半部分汇总早期 G1-G7 离线调参，以及后续 C0-C8 corner case 补充实验。分析原则保持一致：不把 tracker id 连续性直接等同于业务目标身份连续性；不把 HEAD_PROXY 当作真实 FACE_LOCK；涉及速度、质量、实时性和轻量化的结论，都同时参考 summary.json、frame_metrics.json、performance.json 和 live log。

### 1.1 主要指标解释与直观观感含义

本报告中的指标分为四类：锁定状态指标、身份连续性指标、人脸召回指标、性能耗时指标。阅读实验表时，不能只看单个数字，需要同时判断“画面里看起来是否真的锁住目标脸”“是否锁错人”“是否足够实时”。其中 `HESD_PROXY` 如有出现应理解为笔误，正确指标名是 `HEAD_PROXY`。

| 指标 | 含义 | 数值变好意味着什么 | 画面观感上会怎么体现 | 注意事项 |
| --- | --- | --- | --- | --- |
| FACE_LOCK | 系统当前锁定到了目标的真实脸框，控制中心主要来自脸部位置。 | 越多越好，说明真实脸锁定覆盖更连续。 | 视频叠加框/中心点更稳定地贴在目标脸部，云台会更像在“盯脸”。 | 必须人工复核是否真的是目标脸；假脸框、旁人脸、后脑误检不能算真实收益。 |
| HEAD_PROXY | 没有可靠脸框时，用人体/头部代理位置继续跟踪目标。 | 通常越少越好，说明系统更少依赖兜底代理。 | 画面中仍可能跟着人走，但中心点可能落在头部、上半身或人体框估计位置，而不是脸。 | `HEAD_PROXY` 不是失败，但也不是高质量脸锁定；不能把它等同于 `FACE_LOCK`。 |
| LOST | 目标锁定丢失，系统无法给出可靠目标。 | 越少越好。 | 画面中锁定框/中心点消失或进入丢失状态，云台可能停止有效跟随或等待重获。 | 少量 `LOST` 不一定严重，要看是否发生在关键遮挡、交叉、快速运动片段。 |
| SEARCHING | 系统正在搜索或尚未确认目标。 | 越少越好。 | 画面中可能没有稳定目标框，或处于重新寻找目标阶段。 | 初始阶段或严重遮挡后短暂出现可以接受，长时间出现说明恢复能力不足。 |
| Tracker Switches | 底层 tracker id 切换次数。 | 通常越少越好，说明底层轨迹更稳定。 | 画面中如果 switch 伴随锁框跳到旁人，观感就是“换人了”或“跳锁”。 | tracker id 连续不等于业务目标连续；必须结合人工关键帧判断是否真的没锁错人。 |
| Reacquired | 目标从丢失/不稳定后重新被业务层找回的次数。 | 不是单纯越多越好，要结合场景看。 | 遮挡或交叉后，锁定框重新回到目标身上。 | 如果频繁 reacquire，可能说明链路不稳定；如果该恢复时没恢复，则说明找回能力不足。 |
| Face Detected | 检测到真实脸的帧数。 | 通常越多越好。 | 更多帧能看到脸框贴在脸上，`HEAD_PROXY` 会减少。 | 如果增加来自假脸框或旁人脸，则是负收益。 |
| Face Misses | 应该尝试找脸但未找到可靠脸的次数。 | 越少越好。 | 漏检少时，脸框不容易断；漏检多时，画面会频繁退回 `HEAD_PROXY`。 | 要和 `Max Miss Streak` 一起看，连续漏检比零散漏检更影响观感。 |
| Max Miss Streak | 最长连续脸部漏检长度。 | 越低越好。 | 数值高时，观感上会有一段时间持续没有脸锁定，只能靠代理跟随。 | P5 的主要价值之一就是把连续漏检从 12 降到 4，但仍需确认新增脸框真实。 |
| FPS | 有效处理帧率。 | 越高越好。 | FPS 高时画面和控制响应更跟手；FPS 低时画面卡顿，云台控制会滞后。 | 离线 FPS 不等于实时摄像头 FPS，但能反映相对计算负担。 |
| Runtime Sec | 完整处理视频的耗时。 | 越低越好。 | 同一视频处理得越快，实际部署时越有机会降低延迟。 | 必须和质量一起看，不能为了快牺牲真实锁定。 |
| Embedding Calls | ReID 外观特征提取次数。 | 在质量不变时越少越好。 | 调低后画面不一定直接变化，但处理会更快。 | 过少可能导致遮挡、交叉后身份纠错变慢或漂移。 |
| MTCNN Calls | MTCNN 人脸检测调用次数。 | 不是单纯越少越好。 | 调用过少时，脸框刷新变稀，画面更容易从 `FACE_LOCK` 退到 `HEAD_PROXY`。 | C8/G6 已证明 MTCNN 稀疏化会明显损伤 FACE_LOCK 连续性。 |
| Frame Avg ms | 单帧总平均耗时。 | 越低越好。 | 越低越接近实时，控制延迟越小。 | 要结合 `Collect Avg ms`、`Embedding Avg ms`、`MTCNN Avg ms` 判断瓶颈在哪里。 |
| Collect Avg ms | 候选收集与人脸/ReID相关处理平均耗时。 | 越低越好。 | 下降通常意味着单帧处理更快、响应更及时。 | 这是当前链路的重要耗时来源。 |
| Embedding Avg ms | 单次 ReID embedding 平均耗时。 | 越低越好。 | 画面观感未必变化，但速度会明显改善。 | P11 的优势就是 embedding 单次耗时大幅下降；仍需人工复核身份漂移。 |
| MTCNN Avg ms | 单次 MTCNN 检测平均耗时。 | 越低越好，但调用频率不能盲目降低。 | 检测慢会拖累帧率；检测太稀会导致脸锁定断续。 | 优先优化实现或模型，而不是直接大幅减少调用次数。 |

直观判断时可以按下面的规则读表：

1. 真正的质量提升通常表现为 `FACE_LOCK` 增加、`HEAD_PROXY` 降低、`Face Misses` 降低、`Max Miss Streak` 降低，并且关键帧里确实锁在目标脸上。
2. 真正的速度提升通常表现为 `FPS` 增加、`Runtime Sec` 降低、`Frame Avg ms` 降低，并且 `FACE_LOCK` / `HEAD_PROXY` / `LOST` / `Switches` 没有恶化。
3. 如果 `FACE_LOCK` 增加但画面里锁到旁人脸、后脑或背景，这是“假收益”。
4. 如果 `Tracker Switches` 下降但画面里仍会换错目标，这不能证明业务身份连续性变好。
5. 如果 `HEAD_PROXY` 增加，观感上通常是“还能跟着人，但不再稳定盯脸”；对云台闭环来说，这通常会降低控制精度。
6. 如果 `FPS` 很低，即使离线指标看起来更好，真实云台上也可能因为控制滞后而变差。

## 2. 为什么选择 G1-G7 七轮实验

G1-G7 不是随机 sweep，而是按调参优先级做方向判别：先判断主检测、人脸召回、重绑定阈值、ReID 刷新、MTCNN 刷新分别是不是当前瓶颈，再决定下一轮是否需要局部细扫。

| 实验 | 参数方向 | 选择原因 | 想回答的问题 |
| --- | --- | --- | --- |
| G1 | imgsz | 主检测分辨率直接影响检测质量和速度 | 更大检测分辨率是否能显著改善锁定质量 |
| G2 | face-scale-factor + face-min-confidence | 直接影响人脸召回和 FACE_LOCK 连续性 | 当前主要问题是否来自人脸召回不足 |
| G3 | min-appearance + reacquire-thresh 宽松化 | 测试重绑定是否过于保守 | 放宽阈值能否带来更多正确恢复 |
| G4 | min-appearance + reacquire-thresh 严格化 | 与 G3 成对验证 | 收紧阈值能否减少错误恢复或不稳定恢复 |
| G5 | reid-interval | 单独隔离 embedding 刷新成本 | ReID 是否刷得过于频繁，是否存在可回收速度空间 |
| G6 | mtcnn-interval | 单独隔离真实脸框刷新成本 | 降低人脸刷新频率是否能以可接受代价换来速度收益 |
| G7 | reid-interval + mtcnn-interval | 轻量化折中组合 | 能否同时压缩两项开销，在速度和质量之间取得折中 |

## 3. G1-G7 单轮实验结论

### 3.1 G1：detect_img1152

- 测试方向：提高主检测分辨率。
- 参数改动：--imgsz 1152。
- 主要结果：FPS 从 1.082 降到 0.518；runtime 从 675.325 sec 增加到 1411.213 sec；FACE_LOCK 仍为 565；HEAD_PROXY 从 98 降到 94；tracker_switches 从 5 增到 11。
- 结论：更大 imgsz 没有带来 FACE_LOCK 提升，反而显著增加运行成本和 tracker switches。因此 imgsz 上探不是当前优先方向。

### 3.2 G2：face_recall_boost

- 测试方向：增强人脸召回。
- 参数改动：--face-scale-factor 1.03 --face-min-confidence 0.25。
- 主要结果：FPS 从 1.082 降到 0.674；runtime 从 675.325 sec 增加到 1085.249 sec；FACE_LOCK 从 565 增到 612；HEAD_PROXY 从 98 降到 60；face_detected_frames 从 551 增到 598；face_misses 从 110 降到 68。
- 结论：这是 G1-G7 中最明确的质量正收益路线。它直接提升真实脸框命中率，让更多帧从 HEAD_PROXY 回到 FACE_LOCK。代价是速度下降明显，但收益与业务目标相关，值得继续深挖。

### 3.3 G3：reacquire_loose

- 测试方向：放宽重绑定阈值。
- 参数改动：--min-appearance 0.32 --reacquire-thresh 0.42。
- 主要结果：FPS 0.929；runtime 787.143 sec；FACE_LOCK、HEAD_PROXY、tracker_switches、reacquired_count 基本不变。
- 结论：放宽重绑定没有带来可见质量收益，说明当前 baseline 不存在明显“阈值太保守导致找不回目标”的问题。

### 3.4 G4：reacquire_strict

- 测试方向：收紧重绑定阈值。
- 参数改动：--min-appearance 0.38 --reacquire-thresh 0.48。
- 主要结果：FPS 0.938；runtime 779.289 sec；FACE_LOCK、HEAD_PROXY、tracker_switches、reacquired_count 基本不变。
- 结论：与 G3 一致，重绑定阈值不是当前视频的主要瓶颈，不值得优先反复细调。

### 3.5 G5：reid_interval_8

- 测试方向：降低 embedding 刷新频率，回收 ReID 成本。
- 参数改动：--reid-interval 8。
- 主要结果：FPS 从 1.082 提升到 1.458；runtime 从 675.325 sec 降到 501.478 sec；FACE_LOCK、HEAD_PROXY、tracker_switches 基本不变；embedding calls 明显下降。
- 结论：这是 G1-G7 中最明确的速度正收益路线。ReID 刷新频率降低后速度明显提升，自动质量指标没有恶化，因此 reid-interval 是最值得继续深挖的轻量化参数。

### 3.6 G6：mtcnn_interval_3

- 测试方向：降低 MTCNN 刷新频率。
- 参数改动：--mtcnn-interval 3。
- 主要结果：FPS 1.099；runtime 665.433 sec；FACE_LOCK 从 565 降到 546；HEAD_PROXY 从 98 增到 117；face_detected_frames 从 551 降到 532；face_misses 从 110 增到 129。
- 结论：这是坏交易。速度收益很小，但 FACE_LOCK 连续性明显下降。MTCNN 刷新频率会直接影响真实脸框覆盖，不适合作为第一轻量化旋钮。

### 3.7 G7：light_balanced

- 测试方向：同时压缩 ReID 与 MTCNN 刷新，尝试折中。
- 参数改动：--reid-interval 4 --mtcnn-interval 2。
- 主要结果：FPS 1.358；runtime 538.486 sec；FACE_LOCK 从 565 降到 552；HEAD_PROXY 从 98 增到 110；tracker_switches 基本不变；embedding calls 和 MTCNN calls 均下降。
- 结论：G7 速度优于 full baseline，但仍继承 MTCNN 稀疏化导致的质量损失。它是可用但非最优的折中档位，不应直接替代 G2 或 G5 方向。

## 4. G1-G7 交叉对比分析

### 4.1 最值得做质量优化的方向

G2 对应的人脸召回方向最值得继续做质量优化。G1 提高 imgsz 成本极高且没有增加 FACE_LOCK；G3/G4 调重绑定阈值几乎不改变结果；只有 G2 明确带来 FACE_LOCK 增加、HEAD_PROXY 降低和 face_misses 降低。

### 4.2 最值得做轻量化的方向

G5 对应的 reid-interval 是最值得继续做的轻量化方向。G5 明显提速且质量指标基本不变；G6 几乎没有速度收益却损失质量；G7 有速度收益但质量仍下降。因此轻量化时应先调 ReID 刷新，而不是先稀疏化 MTCNN。

### 4.3 重绑定参数是否值得继续深挖

现阶段不值得优先深挖。G3/G4 一宽一严，但 FACE_LOCK、HEAD_PROXY、tracker_switches、reacquired_count 都没有实质变化。只有后续视频明确出现遮挡后找不回、多人交错后误绑定、tracker_switches 或 reacquired_count 异常时，才建议重新打开这条线。

### 4.4 G7 的工程意义

G7 说明组合调参可以得到中速档位，但折中上限受 MTCNN 稀疏化拖累。它的意义是提供备选方案，而不是证明组合一定优于单独调 reid-interval。

## 5. G1-G7 最终结论

### 5.1 质量优先结论

- 当前最值得优先优化的不是 imgsz，而是人脸召回参数。
- 当前最有效的质量路线是 G2：face-scale-factor 与 face-min-confidence 的组合。
- 后续如果继续追求质量，应围绕 G2 附近做局部细扫，而不是继续把 imgsz 往上推。

### 5.2 速度优先结论

- 当前最值得优先优化的轻量化参数是 reid-interval。
- G5 证明可以显著减少 embedding 调用，同时保持质量指标基本不变。
- 后续轻量化实验应以 reid-interval 为主线，而不是先动 mtcnn-interval。

### 5.3 折中方案结论

- G7 可以作为备选折中，但不是当前最佳质量方案，也不是当前最佳速度方案。
- 如果业务目标是身份连续性和真实脸框优先，G7 不应直接替代 full baseline 或 G2 路线。

### 5.4 暂时不值得优先投入的方向

- imgsz 上探到 1152：不值得。
- 在当前 clip 上反复微调 reacquire 阈值：不值得。
- 优先通过 mtcnn-interval 做轻量化：不值得。

## 6. 后续调参建议

### 6.1 下一轮质量向实验建议

围绕 G2 做局部 sweep：

1. 固定 face-scale-factor 1.03，测试 face-min-confidence 0.22 / 0.25 / 0.28。
2. 固定 face-min-confidence 0.25，测试 face-scale-factor 1.02 / 1.03 / 1.04。
3. 在最优点附近再小范围测试 face-min-neighbors，避免引入过多假脸候选。

### 6.2 下一轮轻量化实验建议

以 G5 为起点：

1. 继续测试 reid-interval 4 / 6 / 8 / 10。
2. 在不动 mtcnn-interval 的前提下先找出 reid-interval 的安全上限。
3. 只有在必须更激进轻量化时，再谨慎把 mtcnn-interval 从 1 提到 2，避免直接提到 3。

### 6.3 什么时候重新考虑重绑定参数

只有当新视频明确暴露以下问题时，才建议重开 G3/G4 路线：

- 强遮挡后无法恢复同一人。
- 多人交错后出现明显误绑定。
- tracker_switches 或 reacquired_count 出现显著异常。

## 7. G1-G7 推荐结论摘要

- 最佳质量方向：G2，人脸召回增强。
- 最佳速度方向：G5，增大 reid-interval。
- 最佳折中方向：G7，但仅作为备选折中，不是最优解。
- 应降低优先级的方向：G1、G3、G4、G6。

如果后续只允许继续做一条质量线和一条轻量线，建议质量线围绕 G2 展开，轻量线围绕 G5 展开。

---

## 8. Corner Case 九轮补充实验范围

本节补充 2026-05-28 对新输入视频完成的 C0-C8 九轮 corner case 调参分析，用于验证 G1-G7 的方向结论在新视频和极端输入上的稳定性。

- 数据源：Q:\20260528-160426.mp4
- Run ID：corner_20260528_160426
- 实验输出目录：runs/lock_target_corner_cases/corner_20260528_160426
- 实时监控日志：runs/corner_case_tuning_logs/corner_20260528_160426/corner_case_tuning_live.log
- 进度记录：docs/tuning/corner_case_tuning_progress_corner_20260528_160426.md
- 结果表：docs/tuning/corner_case_tuning_results_corner_20260528_160426.md

C0-C8 已全部完成。分析仍遵循同一原则：不把 tracker id 连续性等同于业务身份连续性，不把 HEAD_PROXY 当作真实 FACE_LOCK；涉及质量、速度和实时性的结论同时查看 summary、frame_metrics 和 performance。

## 9. C0-C8 实验结果总表

| ID | Name | 参数变化 | Runtime Sec | FPS | FACE_LOCK | HEAD_PROXY | LOST | SEARCHING | Switches | Reacquired | Face Detected | Face Misses | Max Miss Streak | Embedding Calls | MTCNN Calls | Frame Avg ms | Collect Avg ms | Embedding Avg ms | MTCNN Avg ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | corner_baseline | baseline full | 953.338 | 0.812 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 766 | 737 | 1224.88 | 1024.57 | 502.41 | 81.69 |
| C1 | corner_img1152 | --imgsz 1152 | 1025.827 | 0.755 | 724 | 16 | 29 | 5 | 13 | 3 | 671 | 20 | 11 | 771 | 686 | 1318.44 | 1049.96 | 530.92 | 77.62 |
| C2 | corner_conf020 | --conf 0.20 | 824.391 | 0.939 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 766 | 737 | 1059.21 | 893.40 | 412.90 | 66.34 |
| C3 | corner_face_scale103 | --face-scale-factor 1.03 | 966.650 | 0.801 | 754 | 14 | 1 | 5 | 8 | 2 | 725 | 19 | 11 | 774 | 735 | 1243.20 | 1084.50 | 379.34 | 62.81 |
| C4 | corner_face_conf025 | --face-min-confidence 0.25 | 793.773 | 0.975 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 766 | 737 | 1019.80 | 859.15 | 391.26 | 62.80 |
| C5 | corner_reacq_loose | --min-appearance 0.30 --reacquire-thresh 0.40 | 779.494 | 0.993 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 766 | 737 | 1001.45 | 845.40 | 384.23 | 61.16 |
| C6 | corner_reacq_strict | --min-appearance 0.40 --reacquire-thresh 0.50 | 788.452 | 0.982 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 766 | 737 | 1012.98 | 854.61 | 388.50 | 62.46 |
| C7 | corner_control_stable | --control-alpha 0.82 --control-max-step 25 | 789.735 | 0.980 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 766 | 737 | 1014.68 | 855.49 | 389.07 | 62.07 |
| C8 | corner_mtcnn2 | --mtcnn-interval 2 | 783.675 | 0.988 | 713 | 54 | 1 | 6 | 8 | 2 | 688 | 56 | 12 | 735 | 372 | 1006.77 | 846.96 | 427.51 | 63.51 |

## 10. C0-C8 单轮结论

### 10.1 C0：corner_baseline

C0 是新视频同源 baseline。核心指标：FPS 0.812，FACE_LOCK 748，HEAD_PROXY 19，LOST 1，tracker_switches 8。所有 C 组结论都应相对 C0 判断，不能直接拿旧视频 G 组 baseline 比较。

### 10.2 C1：corner_img1152

C1 提高 imgsz 到 1152 后，FPS 下降，FACE_LOCK 减少 24，LOST 增加 28，tracker_switches 增加 5。它复现了 G1 的负面结论：继续上探 imgsz 不值得优先投入。

### 10.3 C2：corner_conf020

C2 将 person 检测置信度降到 0.20。FACE_LOCK、HEAD_PROXY、LOST、tracker_switches、face_misses 和调用次数均与 C0 一致，只有运行时间波动。结论是 conf 0.20 没有可解释质量收益，不应过度归因于参数本身。

### 10.4 C3：corner_face_scale103

C3 提高 face-scale-factor 到 1.03，FACE_LOCK +6，HEAD_PROXY -5，face_detected +6，face_misses -6。它是本轮唯一明确的质量正收益参数，说明 face-scale-factor 仍是有效的人脸召回方向，但收益幅度小于旧视频 G2，需要关键帧复核确认新增 FACE_LOCK 不是假脸框。

### 10.5 C4：corner_face_conf025

C4 单独降低 face-min-confidence 到 0.25，主要质量指标完全不变。它说明 corner 输入上真正有效的因子更可能是 face-scale-factor，而不是单独压低 face confidence。

### 10.6 C5 / C6：reacquire 阈值宽松与严格

C5 与 C6 分别放宽和收紧重绑定阈值，但锁定质量指标、tracker_switches、reacquired_count、face_misses 和调用次数均不变。它们再次证明当前视频上重绑定阈值不是主要矛盾。

### 10.7 C7：corner_control_stable

C7 不改变检测/锁定质量，但控制输出明显更平滑：avg control_distance_to_center 从 151.276 降到 136.738，P95 从 290.42 降到 229.74；filtered center 平均步长从 5.183 降到 3.553，P95 步长从 11.203 降到 4.505。它是面向云台前端最有工程意义的方向，但仍需要真实云台闭环验证。

### 10.8 C8：corner_mtcnn2

C8 将 MTCNN calls 从 737 降到 372，但 FACE_LOCK -35，HEAD_PROXY +35，face_detected -31，face_misses +31。它复现了 G6/G7 的核心风险：MTCNN 稀疏化会直接损伤 FACE_LOCK 连续性。

## 11. Corner Case 交叉分析

### 11.1 主检测参数不是当前优先方向

C1 和 C2 共同说明：提高 imgsz 到 1152 会变慢且恶化 LOST / tracker_switches；降低 conf 到 0.20 没有改变质量指标。因此当前主检测瓶颈不是“分辨率不够”或“conf 太高导致漏检”。

### 11.2 人脸召回方向仍然有效，但有效参数更集中

C3 的 FACE_LOCK +6、HEAD_PROXY -5、face_misses -6 表明 face-scale-factor 仍有正收益；C4 单独降低 face-min-confidence 没有变化，说明后续更应优先细扫 face-scale-factor。

### 11.3 重绑定参数连续两组视频都不是主要矛盾

G3/G4 与 C5/C6 都显示，宽松/严格两边调 reacquire 门限都没有改变 FACE_LOCK、HEAD_PROXY、tracker_switches 和 reacquired_count。这是较强的跨视频证据。

### 11.4 云台前端应单独看控制稳定性

C7 表明锁定质量相同的情况下，控制输出可以明显更平滑。面向云台控制时不能只按 FACE_LOCK 和 HEAD_PROXY 排名，还要看 filtered_target_center 步长、control_distance_to_center、deadband_active 和真实闭环响应。

### 11.5 MTCNN interval 仍是高风险轻量化参数

C8 将 MTCNN 调用减半，但 FACE_LOCK 明显下降、HEAD_PROXY 明显上升。轻量化优先级仍应是先调 reid-interval，再谨慎评估 mtcnn-interval。

## 12. 与 G1-G7 结论的合并判断

综合两段视频实验，当前较稳定的结论如下：

1. imgsz 上探不是优先方向，G1 与 C1 都显示 imgsz 1152 成本高且没有稳定质量收益。
2. 人脸召回是质量向核心方向，但后续应优先细扫 face-scale-factor。
3. face-min-confidence 单独降低不一定有效，不能作为通用旋钮。
4. reacquire 门限不是当前主要瓶颈，G3/G4/C5/C6 均无明显质量影响。
5. mtcnn-interval 是高风险轻量化参数，G6/G7/C8 均显示 MTCNN 稀疏化会降低 FACE_LOCK 或增加 HEAD_PROXY。
6. 控制稳定性应独立成线，C7 证明控制参数可在不改变锁定质量的前提下改善控制中心平滑度。

## 13. 更新后的推荐配置方向

### 13.1 质量优先

优先围绕 face-scale-factor 做局部细扫：1.02 / 1.03 / 1.04。每个点都要同时检查 FACE_LOCK、HEAD_PROXY、face_misses 和关键帧，确认新增 FACE_LOCK 不是假脸框。

不建议继续优先投入 imgsz 1152 或单独降低 face-min-confidence。

### 13.2 速度优先

优先围绕 reid-interval 做轻量化，不要先动 mtcnn-interval。建议继续验证 reid-interval 4 / 6 / 8 / 10，并寻找不产生身份漂移的安全上限。

### 13.3 云台控制优先

如果目标是云台前端可用性，C7 是值得保留的工程方向。建议继续验证 control-alpha 0.78 / 0.82 / 0.86 与 control-max-step 20 / 25 / 30，并记录 avg / P95 control_distance_to_center、filtered_target_center 步长、过冲、滞后和稳态误差。

但 C7 只能证明视觉控制输出更平滑，不能替代真实云台闭环测试。

## 14. Corner Case 最终结论摘要

- 最佳质量方向：C3，face-scale-factor 1.03，小幅提升 FACE_LOCK 并降低 HEAD_PROXY / face_misses。
- 最差质量方向：C1 和 C8。C1 增加 LOST 与 tracker_switches；C8 将 FACE_LOCK 明显转移为 HEAD_PROXY。
- 最佳控制方向：C7，在锁定质量不变的前提下降低 control_distance_to_center 和 filtered center 抖动。
- 中性方向：C2、C4、C5、C6。它们没有改变主要质量指标，其中 C5/C6 再次证明当前重绑定阈值不是主要矛盾。
- 总体策略：质量线继续围绕 face-scale-factor；轻量线继续围绕 reid-interval；云台线继续围绕 control-alpha / control-max-step；暂时降低 imgsz、reacquire 阈值和 mtcnn-interval 的优先级。

### 证据缺口

- 本轮报告已经使用 summary.json、frame_metrics.json、performance.json 和 live log 做指标分析。
- 仍缺少人工关键帧复核，因此不能完全排除 C3、P5、P6 新增 FACE_LOCK 中存在假脸框。
- 仍缺少真实 QGimbal 云台闭环验证，因此 C7 只能说明视觉控制输出更平滑，不能直接证明实际云台跟踪更稳。

<!-- priority_sweep_priority_sweep_20260529_analysis_start -->

## 15. 最新 Priority Sweep P0-P11 实验分析（priority_sweep_20260529）

### 15.1 实验范围、目标与证据来源

- 数据源：Q:\20260528-160426.mp4
- Run ID：priority_sweep_20260529
- 实验计划：docs/tuning/priority_sweep_experiment_plan_priority_sweep_20260529.md
- 实验进度：docs/tuning/priority_sweep_progress_priority_sweep_20260529.md
- 实验结果表：docs/tuning/priority_sweep_results_priority_sweep_20260529.md
- 输出目录：runs/lock_target_priority_sweep/priority_sweep_20260529
- live log：runs/priority_sweep_logs/priority_sweep_20260529/priority_sweep_live.log
- 自动分析时间：2026-05-30 00:00:41
- 本次补充分析时间：2026-06-01

本轮实验的目的不是重新做大范围随机搜索，而是按前几轮结论做优先级验证：先确认 reid-interval 的轻量化上限，再确认 face-scale-factor / face-min-confidence 的局部质量收益，最后做 detector model 与 ReID model 的 A/B。所有结论均基于同一视频、同一输出结构下的 summary.json、frame_metrics.json、performance.json 和 live log。

重要约束：本节仍然不把 tracker id 连续性等同于业务身份连续性，也不把 HEAD_PROXY 当成真实 FACE_LOCK。FACE_LOCK 增加必须经过关键帧人工复核后，才能作为最终质量提升结论。

### 15.2 完成状态

P0-P11 已全部完成。P9 曾中断，后续恢复脚本清理残留输出后从 P9 继续，最终 P9、P10、P11 均完成。三小时延迟检查在 P0-P11 完整后自动触发分析，并已把结果写入本报告。

关键日志结论：

- P9 恢复后完成：priority_face_conf028，FPS 0.931，runtime 831.192 sec。
- P10 完成：priority_detector_yolo26l，FPS 0.623，runtime 1242.267 sec。
- P11 完成：priority_reid_yolo26n，FPS 1.44，runtime 537.435 sec。
- 所有实验完成：All priority sweep experiments completed successfully。
- 延迟检查确认完成并触发分析：Delayed check: P0-P11 complete; starting priority sweep analysis。

### 15.3 指标总表

| ID | 名称 | 方向 | 参数 | Runtime Sec | FPS | FACE_LOCK | HEAD_PROXY | LOST | SEARCHING | Switches | Reacquired | Face Detected | Face Misses | Max Miss Streak | Embedding Calls | MTCNN Calls | Frame Avg ms | Collect Avg ms | Embedding Avg ms | MTCNN Avg ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | priority_baseline | baseline | baseline full | 843.281 | 0.918 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 766 | 737 | 1083.44 | 908.81 | 424.36 | 70.79 |
| P1 | priority_reid_interval4 | reid-interval | --reid-interval 4 | 675.803 | 1.145 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 235 | 737 | 866.77 | 672.57 | 497.78 | 82.93 |
| P2 | priority_reid_interval6 | reid-interval | --reid-interval 6 | 563.545 | 1.373 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 177 | 737 | 722.61 | 566.28 | 416.34 | 64.92 |
| P3 | priority_reid_interval8 | reid-interval | --reid-interval 8 | 540.558 | 1.432 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 146 | 737 | 693.06 | 543.65 | 410.36 | 63.00 |
| P4 | priority_reid_interval10 | reid-interval | --reid-interval 10 | 531.158 | 1.457 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 126 | 737 | 680.91 | 530.09 | 408.42 | 63.43 |
| P5 | priority_face_scale102 | face-scale-factor | --face-scale-factor 1.02 | 1017.662 | 0.761 | 755 | 18 | 1 | 0 | 8 | 1 | 730 | 18 | 4 | 779 | 739 | 1309.26 | 1152.34 | 373.37 | 63.25 |
| P6 | priority_face_scale103 | face-scale-factor | --face-scale-factor 1.03 | 970.684 | 0.797 | 754 | 14 | 1 | 5 | 8 | 2 | 725 | 19 | 11 | 774 | 735 | 1248.48 | 1088.79 | 380.84 | 65.12 |
| P7 | priority_face_scale104 | face-scale-factor | --face-scale-factor 1.04 | 872.793 | 0.887 | 749 | 18 | 1 | 6 | 6 | 1 | 720 | 24 | 12 | 767 | 738 | 1121.84 | 958.57 | 395.59 | 67.12 |
| P8 | priority_face_conf025 | face-min-confidence | --face-min-confidence 0.25 | 803.217 | 0.964 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 766 | 737 | 1031.97 | 869.88 | 396.91 | 64.95 |
| P9 | priority_face_conf028 | face-min-confidence | --face-min-confidence 0.28 | 831.192 | 0.931 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 766 | 737 | 1067.90 | 897.18 | 414.80 | 67.25 |
| P10 | priority_detector_yolo26l | detector-model | --model yolo26l.pt | 1242.267 | 0.623 | 748 | 22 | 0 | 4 | 4 | 1 | 734 | 26 | 10 | 788 | 755 | 1598.96 | 866.55 | 426.76 | 61.29 |
| P11 | priority_reid_yolo26n | reid-model | --reid-model yolo26n.pt | 537.435 | 1.440 | 748 | 19 | 1 | 6 | 8 | 2 | 719 | 25 | 12 | 766 | 737 | 689.13 | 537.33 | 72.64 | 63.48 |

### 15.4 相对 P0 的主要变化

| 组别 | 主要变化 | 速度影响 | 质量影响 | 初步判定 |
| --- | --- | --- | --- | --- |
| P1 | reid-interval 4 | FPS +0.227，runtime -167.478 sec | FACE_LOCK / HEAD_PROXY / LOST / switches 不变 | 可用，但不是最优 |
| P2 | reid-interval 6 | FPS +0.455，runtime -279.736 sec | 质量指标不变 | 通过，速度收益明确 |
| P3 | reid-interval 8 | FPS +0.514，runtime -302.723 sec | 质量指标不变 | 通过，接近最优 |
| P4 | reid-interval 10 | FPS +0.539，runtime -312.123 sec | 质量指标不变 | 本轮速度优先最佳候选 |
| P5 | face-scale-factor 1.02 | FPS -0.157，runtime +174.381 sec | FACE_LOCK +7，HEAD_PROXY -1，face_misses -7，max miss streak 12 -> 4 | 质量候选，但成本高 |
| P6 | face-scale-factor 1.03 | FPS -0.121，runtime +127.403 sec | FACE_LOCK +6，HEAD_PROXY -5，face_misses -6 | 质量候选，成本略低于 P5 |
| P7 | face-scale-factor 1.04 | FPS -0.031，runtime +29.512 sec | FACE_LOCK +1，HEAD_PROXY -1，switches -2 | 收益偏小，保守候选 |
| P8 | face-min-confidence 0.25 | FPS +0.046，runtime -40.064 sec | 质量指标不变 | 基本等同 baseline |
| P9 | face-min-confidence 0.28 | FPS +0.013，runtime -12.089 sec | 质量指标不变 | 基本等同 baseline |
| P10 | detector yolo26l.pt | FPS -0.295，runtime +398.986 sec | LOST -1，switches -4，但 HEAD_PROXY +3、face_misses +1 | 有稳定性信号但代价过高，需人工复核 |
| P11 | ReID yolo26n.pt | FPS +0.522，runtime -305.846 sec | 质量指标不变 | 轻量 ReID 候选，需人工复核身份漂移 |

### 15.5 ReID interval 线分析

P1-P4 形成了非常清晰的速度收益曲线：reid-interval 从 4 增加到 10 时，embedding calls 从 P0 的 766 次下降到 235 / 177 / 146 / 126 次，frame_total_avg_ms 从 1083.44 ms 下降到 866.77 / 722.61 / 693.06 / 680.91 ms。

最关键的是，P1-P4 的 FACE_LOCK、HEAD_PROXY、LOST、SEARCHING、tracker_switches、face_misses、max_face_miss_streak 均与 P0 保持一致。这说明在这段视频上，降低 ReID 刷新频率没有被自动指标捕捉到质量退化。

当前结论：

- P4 是本轮速度优先的第一候选配置。
- P3 与 P4 的差距较小，P3 更保守，P4 更激进。
- 如果人工关键帧复核发现 P4 在遮挡、交叉或回头时有身份漂移，应回退到 P3。
- 如果 P4 人工复核通过，下一轮可以围绕 reid-interval 10 附近做组合实验，而不是继续优先压 MTCNN。

### 15.6 face-scale-factor 线分析

P5-P7 说明 face-scale-factor 仍然是质量向调参的有效方向，但收益和成本不线性。

P5 的表现最偏质量优先：FACE_LOCK 从 748 提升到 755，face_misses 从 25 降到 18，max miss streak 从 12 降到 4，说明短时脸部漏检被明显缓解。但代价是 runtime 增加 174.381 sec，FPS 从 0.918 降到 0.761，frame_total_avg_ms 升到 1309.26 ms。

P6 的 HEAD_PROXY 改善最明显：HEAD_PROXY 从 19 降到 14，FACE_LOCK 增加 6，face_misses 减少 6。它比 P5 稍快，但 max miss streak 仍为 11，说明漏检连续性改善不如 P5。

P7 的速度接近 baseline，但质量收益明显减弱：FACE_LOCK 只增加 1，face_misses 只减少 1，不过 tracker_switches 从 8 降到 6。

当前结论：

- 质量优先候选：P5 与 P6。
- P5 更适合“减少连续漏检”的目标。
- P6 更适合“减少 HEAD_PROXY 占比”的目标。
- P7 可作为低成本保守候选，但不是本轮质量最优点。
- face-scale-factor 的最终选择必须看视频关键帧，确认新增 FACE_LOCK 不是假脸框或几何漂移。

### 15.7 face-min-confidence 线分析

P8 和 P9 单独调整 face-min-confidence 后，FACE_LOCK、HEAD_PROXY、LOST、switches、face_misses 与 P0 完全一致，只有 runtime 和 FPS 有轻微波动。

当前结论：

- 在本轮视频上，单独调 face-min-confidence 0.25 或 0.28 没有形成可解释质量收益。
- 后续不建议把 face-min-confidence 作为单独优先方向。
- 如果继续使用它，应放在 face-scale-factor 已确定后的组合实验中验证，而不是单独 sweep。

### 15.8 detector model A/B 分析

P10 使用 yolo26l.pt 作为 detector，表现为更慢但某些稳定性指标改善：runtime 从 843.281 sec 增加到 1242.267 sec，FPS 从 0.918 降到 0.623；同时 tracker_switches 从 8 降到 4，LOST 从 1 降到 0，face_detected_frames 从 719 增加到 734。

但 P10 也有反向信号：HEAD_PROXY 从 19 增加到 22，face_misses 从 25 增加到 26，frame_total_avg_ms 升到 1598.96 ms。也就是说，大 detector 可能让底层轨迹更稳，但没有直接提高 FACE_LOCK 数量，反而略微增加 HEAD_PROXY。

当前结论：

- P10 不能直接作为推荐配置。
- 如果业务更重视 tracker_switches 和 LOST，它值得人工关键帧复核。
- 如果业务优先实时性或 FACE_LOCK 占比，P10 当前不划算。
- 是否采用 yolo26l.pt detector，必须同时看视频关键帧、identity continuity 和实时 FPS。

### 15.9 ReID model A/B 分析

P11 使用 yolo26n.pt 作为 ReID model，速度收益非常明显：runtime 从 843.281 sec 降到 537.435 sec，FPS 从 0.918 提升到 1.440，frame_total_avg_ms 从 1083.44 ms 降到 689.13 ms。与 P4 相比，P11 的 FPS 略低于 P4 的 1.457，但非常接近。

P11 的关键特征是 embedding calls 仍为 766 次，但 embedding_avg_ms 从 P0 的 424.36 ms 降到 72.64 ms。这说明它不是靠减少调用次数提速，而是靠轻量化 ReID 模型本身降低单次 embedding 成本。

自动质量指标上，P11 与 P0 完全一致：FACE_LOCK 748、HEAD_PROXY 19、LOST 1、switches 8、face_misses 25。

当前结论：

- P11 是轻量 ReID 模型方向的强候选。
- P4 是减少 ReID 调用次数方向的强候选。
- P11 与 P4 的速度接近，但机制不同；后续值得做组合实验：yolo26n.pt ReID + reid-interval 6 / 8 / 10。
- 采用 P11 前必须人工复核身份漂移，因为小 ReID 模型可能降低外观区分度，自动统计未必能发现误身份连续。

### 15.10 本轮最终判断

| 目标 | 推荐候选 | 结论 |
| --- | --- | --- |
| 速度优先 | P4 priority_reid_interval10 | 本轮最快，且自动质量指标不变。人工复核通过后可作为速度优先默认候选。 |
| 质量优先 | P5 priority_face_scale102 / P6 priority_face_scale103 | 有 FACE_LOCK、HEAD_PROXY、face_misses 改善，但明显变慢。需要按业务目标二选一。 |
| 低风险折中 | P3 priority_reid_interval8 或 P7 priority_face_scale104 | P3 是保守轻量化，P7 是低成本质量微调。 |
| 模型替换 | P11 priority_reid_yolo26n | 速度收益接近 P4，适合进入下一轮组合实验。 |
| 暂不推荐 | P10 priority_detector_yolo26l | 耗时太大，质量收益不够直接。除非人工关键帧证明它显著改善身份连续性。 |

### 15.11 下一轮实验建议

建议下一轮不要继续扩大参数面，而是做组合验证：

1. 速度组合线：P11 + reid-interval 6 / 8 / 10。
2. 质量组合线：P5 或 P6 + P11，观察能否用轻量 ReID 抵消 face-scale-factor 的耗时成本。
3. 折中线：P3 + P6，验证是否能在低风险轻量化下保留 face-scale-factor 的质量收益。
4. detector 线只保留一个人工复核任务，不建议继续 sweep yolo26l.pt，除非关键帧显示 P10 明显减少错误身份或丢失。

优先验证顺序：

1. 人工复核 P0、P4、P5、P6、P10、P11 的关键帧。
2. 若 P4 无身份漂移，先做 P11 + reid-interval 8 / 10。
3. 若 P5/P6 的新增 FACE_LOCK 为真，再做 P11 + P5/P6。
4. 若真实云台要上机，先选速度候选而不是质量候选，避免低 FPS 放大控制滞后。

### 15.12 证据缺口与风险

- 尚未做人工关键帧复核，不能最终确认 P5/P6 的新增 FACE_LOCK 都是真实脸锁定。
- 尚未检查 P4/P11 在遮挡、交叉、回头片段中的身份连续性，不能只凭 tracker_switches 和 FACE_LOCK 数量下最终结论。
- 本轮是离线视频证据，不等同于实时摄像头 FPS。
- 本轮没有真实 QGimbal 云台闭环遥测，不能证明云台跟踪稳定性。
- 当前报告前半部分存在历史编码乱码，最新本节为可读中文，但旧章节仍建议后续统一修复或重生成。

<!-- priority_sweep_priority_sweep_20260529_analysis_end -->

