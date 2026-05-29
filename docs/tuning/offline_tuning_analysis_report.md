# 离线调参实验分析报告

## 1. 实验范围与目标

- 数据源：Q:\20260521-120258.mp4
- 全量质量基线：runs/lock_target/offline_run
- 轻量化基线：runs/lock_target/offline_run_light
- 调参输出目录：runs/lock_target_tuning
- 分析目标：不是只记录原始指标，而是回答每个参数或参数组对速度和质量分别带来了什么影响，并据此给出后续调参方向。

本轮实验一共完成 7 组调参，覆盖了主检测、人脸召回、重绑定阈值以及轻量化两个主要方向，目的是用最少的实验轮数先判断当前系统的主矛盾到底在哪里。

## 2. 为什么选择这 7 轮实验

这 7 轮不是随意挑的，而是按参数表中的优先级和调参路线有意识地选出来的，覆盖了四类关键问题：

1. 主检测是否是当前质量瓶颈。
2. 人脸召回是否是当前质量瓶颈。
3. 重绑定阈值是否是当前身份连续性的主要限制。
4. 轻量化时到底应该先压 ReID 刷新，还是先压 MTCNN 刷新。

对应关系如下：

| 实验 | 参数方向 | 选择原因 | 想回答的问题 |
| --- | --- | --- | --- |
| G1 | imgsz | imgsz 是最高优先级的一阶参数，直接影响主检测质量和速度 | 更大的检测分辨率是否能显著改善锁定质量 |
| G2 | face-scale-factor + face-min-confidence | 这两个参数直接影响人脸召回和 FACE_LOCK 连续性 | 当前主要问题是否出在人脸召回不够积极 |
| G3 | min-appearance + reacquire-thresh 宽松化 | 测试重绑定是否过于保守 | 放宽阈值能否带来更多正确恢复 |
| G4 | min-appearance + reacquire-thresh 严格化 | 与 G3 成对，对称验证 | 收紧阈值能否减少错误恢复或不稳定恢复 |
| G5 | reid-interval | 单独隔离 embedding 刷新成本 | ReID 是否刷得过于频繁，存在可回收的速度空间 |
| G6 | mtcnn-interval | 单独隔离真实脸框刷新成本 | 降低人脸刷新频率是否会以可接受代价换来速度收益 |
| G7 | reid-interval + mtcnn-interval | 轻量化折中组合 | 能否同时压两项开销，在速度和质量之间取得折中 |

这套设计不是对前 10 高优先级参数逐个扫描，而是先做“方向判别”。先确定最值得继续深挖的分支，再决定下一轮更细的局部 sweep 应该落在哪个参数簇上。

## 3. 七轮实验的测试方向、动机与结果

### G1：detect_img1152

- 测试方向：提高主检测分辨率。
- 动机：验证主检测细节是否不足，是否需要用更大的 imgsz 才能改善后续锁定质量。
- 参数改动：--imgsz 1152
- 返回结果：
  - FPS：1.082 -> 0.518
  - Runtime：675.325 sec -> 1411.213 sec，增加 735.888 sec
  - FACE_LOCK：565 -> 565，没有提升
  - HEAD_PROXY：98 -> 94，略有下降
  - Tracker Switches：5 -> 11，明显变差
- 结论：
  - 更大的检测分辨率没有换来更高的 FACE_LOCK，占用的计算成本却非常大。
  - 同时 tracker_switches 明显增加，说明更大 imgsz 在这段视频上没有带来更稳的业务连续性，反而破坏了稳定性。
  - 结论是：imgsz 不是这段视频最值得优先调的方向。

### G2：face_recall_boost

- 测试方向：增强人脸召回。
- 动机：验证当前质量瓶颈是否主要来自人脸召回不足，而不是主检测本身。
- 参数改动：--face-scale-factor 1.03 --face-min-confidence 0.25
- 返回结果：
  - FPS：1.082 -> 0.674
  - Runtime：675.325 sec -> 1085.249 sec，增加 409.924 sec
  - FACE_LOCK：565 -> 612，增加 47
  - HEAD_PROXY：98 -> 60，减少 38
  - Face Detected Frames：551 -> 598，增加 47
  - Face Misses：110 -> 68，减少 42
- 结论：
  - 这是 7 轮实验里最明确的质量正收益路线。
  - 它直接提升了真实脸框的命中率，让更多帧从 HEAD_PROXY 回到 FACE_LOCK。
  - 代价是速度下降明显，但这个代价换来了真实质量收益，因此这是当前最值得继续深挖的质量优先路线。

### G3：reacquire_loose

- 测试方向：放宽重绑定阈值。
- 动机：验证当前系统是否因为重绑定过于保守而错失恢复机会。
- 参数改动：--min-appearance 0.32 --reacquire-thresh 0.42
- 返回结果：
  - FPS：1.082 -> 0.929
  - Runtime：675.325 sec -> 787.143 sec，增加 111.818 sec
  - FACE_LOCK：565 -> 565，没有变化
  - HEAD_PROXY：98 -> 98，没有变化
  - Tracker Switches：5 -> 5，没有变化
  - Reacquired Count：3 -> 3，没有变化
- 结论：
  - 放宽重绑定并没有带来任何可见质量收益。
  - 说明当前 baseline 并不存在“因为阈值太保守而找不回目标”的明显问题。
  - 这类参数在这段视频里属于低收益方向。

### G4：reacquire_strict

- 测试方向：收紧重绑定阈值。
- 动机：验证当前系统是否存在“重绑定过于激进”的问题，从而导致潜在误绑或不稳定恢复。
- 参数改动：--min-appearance 0.38 --reacquire-thresh 0.48
- 返回结果：
  - FPS：1.082 -> 0.938
  - Runtime：675.325 sec -> 779.289 sec，增加 103.964 sec
  - FACE_LOCK：565 -> 565，没有变化
  - HEAD_PROXY：98 -> 98，没有变化
  - Tracker Switches：5 -> 5，没有变化
  - Reacquired Count：3 -> 3，没有变化
- 结论：
  - 与 G3 一样，G4 也几乎没有改变结果。
  - 这说明当前视频上的重绑定阈值并不是主要瓶颈，不管往宽松方向还是严格方向推，都没有实质性收益。
  - G3 和 G4 形成了一组很强的反证：重绑定不是当前最值得继续投预算的方向。

### G5：reid_interval_8

- 测试方向：降低 embedding 刷新频率，回收 ReID 成本。
- 动机：验证 baseline 是否对 ReID 刷新过度配置，是否存在明显的速度回收空间。
- 参数改动：--reid-interval 8
- 返回结果：
  - FPS：1.082 -> 1.458
  - Runtime：675.325 sec -> 501.478 sec，减少 173.847 sec
  - FACE_LOCK：565 -> 565，没有变化
  - HEAD_PROXY：98 -> 98，没有变化
  - Tracker Switches：5 -> 5，没有变化
  - Embedding Calls：645 -> 168，大幅下降
- 结论：
  - 这是 7 轮实验里最明确的速度正收益路线。
  - ReID 刷新频率降低后，速度明显提升，但质量指标没有恶化。
  - 说明当前 baseline 在这段视频上对 ReID 刷新存在过度投入，reid-interval 是当前最值得继续深挖的轻量化参数。

### G6：mtcnn_interval_3

- 测试方向：降低 MTCNN 刷新频率。
- 动机：验证减少真实脸框刷新是否能带来足够速度收益，并判断这种收益是否值得。
- 参数改动：--mtcnn-interval 3
- 返回结果：
  - FPS：1.082 -> 1.099
  - Runtime：675.325 sec -> 665.433 sec，仅减少 9.892 sec
  - FACE_LOCK：565 -> 546，减少 19
  - HEAD_PROXY：98 -> 117，增加 19
  - Face Detected Frames：551 -> 532，减少 19
  - Face Misses：110 -> 129，增加 19
- 结论：
  - 这是一个典型的坏交易：质量明显下降，但速度几乎没有真正改善。
  - MTCNN 刷新频率对 FACE_LOCK 连续性影响非常直接，一旦拉大间隔，真实脸框覆盖立刻退化。
  - 对当前系统来说，mtcnn-interval 不是适合优先轻量化的方向。

### G7：light_balanced

- 测试方向：同时压缩 ReID 和 MTCNN 刷新，尝试做轻量化折中。
- 动机：验证能否利用 G5 的速度收益，同时避免 G6 那种过于明显的质量损失。
- 参数改动：--reid-interval 4 --mtcnn-interval 2
- 返回结果：
  - FPS：1.082 -> 1.358
  - Runtime：675.325 sec -> 538.486 sec，减少 136.839 sec
  - FACE_LOCK：565 -> 552，减少 13
  - HEAD_PROXY：98 -> 110，增加 12
  - Tracker Switches：5 -> 5，没有变化
  - Embedding Calls：645 -> 231，明显下降
  - MTCNN Calls：791 -> 462，明显下降
- 结论：
  - G7 确实拿回了一部分速度，但仍然出现了质量退化。
  - 相比 G6，G7 的退化更温和；相比 G5，G7 又明显更差。
  - 这说明“同时压 ReID 和 MTCNN”虽然能做出折中，但折中的上限仍然受 MTCNN 稀疏化拖累。

## 4. 七轮实验交叉对比分析

### 4.1 哪个方向最值得做质量优化

结论很明确：G2 对应的人脸召回方向最值得继续做。

原因是：

- G1 动的是主检测分辨率，成本极高，但没有带来 FACE_LOCK 提升。
- G2 动的是人脸召回，虽然变慢，但直接带来了 FACE_LOCK 大幅增加、HEAD_PROXY 大幅下降。
- G3 和 G4 动的是重绑定阈值，几乎没有改变结果。

这说明当前视频的主要质量瓶颈不在主检测分辨率，也不在重绑定阈值，而在人脸召回链路。

### 4.2 哪个方向最值得做轻量化

结论也很明确：G5 对应的 reid-interval 是最值得继续做的轻量化方向。

原因是：

- G5：速度明显提升，质量基本不动。
- G6：速度几乎不变，但质量明显下降。
- G7：速度有收益，但质量仍然下降。

这意味着轻量化时不能把 ReID 和 MTCNN 看成同类参数。对当前视频来说：

- ReID 刷新偏稀一点是可以接受的。
- MTCNN 刷新一旦变稀，FACE_LOCK 就会明显退化。

### 4.3 重绑定参数是否值得继续深挖

现阶段不值得优先深挖。

G3 和 G4 一宽一严，两边都测了，但 FACE_LOCK、HEAD_PROXY、tracker_switches、reacquired_count 都没有变化，只多花了一点运行时间。这说明在当前 clip 上，重绑定阈值不是系统主要矛盾。

只有当后续换到更复杂的视频，明确出现以下问题时，才值得重新把这条线提上优先级：

- 遮挡后找不回同一目标。
- 频繁换绑到别的人。
- reacquired_count 和 tracker_switches 明显恶化。

### 4.4 G7 的意义是什么

G7 的意义不是证明“组合调参一定更优”，而是验证现实工程里最常见的问题：如果两个模块都各自省一点，能不能得到一个还能接受的折中版本。

结果表明：

- 可以得到比 full baseline 更快的速度。
- 但这种折中依旧会继承一部分 MTCNN 稀疏化带来的质量损失。

因此 G7 不是当前最佳质量方案，也不是当前最佳轻量方案，它更像一个“可用但非最优”的中间档位。

## 5. 最终结论

### 5.1 质量优先结论

- 当前最值得优先优化的不是 imgsz，而是人脸召回参数。
- 当前最有效的质量路线是 G2：降低 face-scale-factor、降低 face-min-confidence。
- 如果后续继续追求质量，应围绕 G2 附近继续做局部细扫，而不是继续把 imgsz 往上推。

### 5.2 速度优先结论

- 当前最值得优先优化的轻量化参数是 reid-interval。
- G5 证明可以显著减少 embedding 调用，同时保持质量指标基本不变。
- 因此后续轻量化实验应以 reid-interval 为主线，而不是先动 mtcnn-interval。

### 5.3 折中方案结论

- G7 说明“适度放宽 ReID 刷新 + 适度放宽 MTCNN 刷新”可以得到一个中速档位。
- 但只要 MTCNN 刷新被拉稀，FACE_LOCK 还是会下滑。
- 所以如果业务目标是身份连续性和真实脸框优先，G7 只能作为备选折中，不应直接替代 full baseline 或 G2 路线。

### 5.4 不值得优先继续投入的方向

- imgsz 上探到 1152：不值得。
- 当前 clip 上继续反复微调 reacquire 阈值：不值得。
- 先动 mtcnn-interval 做轻量化：不值得。

## 6. 后续调参建议

### 6.1 下一轮质量向实验建议

围绕 G2 继续做局部 sweep，而不是再开大而散的参数搜索。建议顺序：

1. 固定 face-scale-factor 1.03，测试 face-min-confidence 在 0.22、0.25、0.28。
2. 固定 face-min-confidence 0.25，测试 face-scale-factor 在 1.02、1.03、1.04。
3. 在 G2 最优点附近补 face-min-neighbors 的小范围测试，例如 2、3、4。

目标是进一步确认：

- FACE_LOCK 是否还能继续提升。
- HEAD_PROXY 是否还能继续下降。
- 新增收益是否开始边际递减。

### 6.2 下一轮轻量化实验建议

以 G5 为起点，而不是以 G6 为起点。建议顺序：

1. 继续测试 reid-interval，例如 4、6、8、10。
2. 在不动 mtcnn-interval 的前提下先找出 reid-interval 的安全上限。
3. 如果必须做更激进轻量化，再考虑把 mtcnn-interval 从 1 提到 2，而不是直接提到 3。

### 6.3 什么时候重新考虑重绑定参数

只有当新视频明确暴露以下问题，才建议重开 G3/G4 这条路线：

- 强遮挡后无法恢复同一人。
- 多人交错后出现明显误绑。
- tracker_switches 或 reacquired_count 出现显著异常。

否则，对当前这种 clip 来说，重绑定阈值不是优先方向。

## 7. 推荐结论摘要

- 最佳质量方向：G2，人脸召回增强。
- 最佳速度方向：G5，增大 reid-interval。
- 最佳折中方向：G7，但仅为备选折中，不是最优解。
- 应降级优先级的方向：G1、G3、G4、G6。

如果后续只允许继续做一条质量线和一条轻量线，那么建议：

- 质量线继续围绕 G2 展开。
- 轻量线继续围绕 G5 展开。

---

## 8. Corner Case 九轮补充实验范围

本节补充 2026-05-28 对新输入视频完成的 C0-C8 九轮 corner case 调参分析，用于验证前面 G1-G7 得出的方向在新视频和极端场景输入上的稳定性。

- 数据源：Q:\20260528-160426.mp4
- Run ID：corner_20260528_160426
- 实验输出目录：runs/lock_target_corner_cases/corner_20260528_160426
- 实时监控日志：runs/corner_case_tuning_logs/corner_20260528_160426/corner_case_tuning_live.log
- 进度记录：docs/tuning/corner_case_tuning_progress_corner_20260528_160426.md
- 结果表：docs/tuning/corner_case_tuning_results_corner_20260528_160426.md

这 9 轮实验已经全部完成。进度文件显示 C0-C8 均为 completed / JSON ready；live log 记录了每一轮的 heartbeat 和完成时间，最终写入 “All corner-case experiments completed successfully.”。

本轮分析仍遵循前面 G1-G7 的原则：不把 tracker id 连续性直接等同于业务目标连续性，不把 HEAD_PROXY 当成真实 FACE_LOCK；涉及质量、速度和实时性结论时，同时查看 summary、frame_metrics 和 performance。

## 9. Corner Case 九轮实验结果总表

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

### C0：corner_baseline

- 测试方向：新视频同源 baseline。
- 核心结果：FPS 0.812，FACE_LOCK 748，HEAD_PROXY 19，LOST 1，tracker_switches 8。
- 作用：C0 是本轮所有 corner case 结论的唯一可比基线，不能拿旧视频 G1-G7 的 baseline 直接比较。

### C1：corner_img1152

- 测试方向：提高主检测分辨率。
- 相对 C0：FPS 下降 0.057，runtime 增加 72.489 sec，FACE_LOCK 减少 24，LOST 增加 28，tracker_switches 增加 5。
- 结论：在新视频上，imgsz 1152 仍然不是有效方向。它没有改善真实脸锁定，反而带来 LOST 和 tracker_switches 恶化。
- 与 G1 的关系：C1 复现了 G1 的负面结论，即继续上探 imgsz 不值得优先投入。

### C2：corner_conf020

- 测试方向：降低 person 检测置信度。
- 相对 C0：FACE_LOCK、HEAD_PROXY、LOST、tracker_switches、face_misses、embedding_calls 和 MTCNN calls 全部不变；FPS 从 0.812 到 0.939。
- 结论：降低 conf 到 0.20 没有带来质量收益，也没有引入可见身份连续性风险。
- 注意：虽然 runtime 和 frame_avg_ms 明显下降，但检测链路输出、调用次数和质量指标完全相同，因此不应把这次速度差异过度归因于 conf 本身；更可能包含运行时负载、缓存或系统状态波动。

### C3：corner_face_scale103

- 测试方向：提高 classical face 召回。
- 相对 C0：FACE_LOCK 增加 6，HEAD_PROXY 减少 5，face_detected 增加 6，face_misses 减少 6；FPS 从 0.812 小幅下降到 0.801。
- 结论：这是本轮唯一明确的质量正收益参数。收益幅度比旧视频 G2 小，但方向一致：更积极的人脸召回可以把部分 HEAD_PROXY 拉回 FACE_LOCK。
- 风险：收益较小，且需要人工抽查确认新增 FACE_LOCK 不是假脸框。

### C4：corner_face_conf025

- 测试方向：放宽 MTCNN face confidence。
- 相对 C0：FACE_LOCK、HEAD_PROXY、LOST、tracker_switches、face_detected、face_misses 和调用次数完全不变。
- 结论：单独降低 face-min-confidence 到 0.25 对这个新视频没有可见质量收益。
- 与 G2 的关系：旧视频 G2 同时改 face-scale-factor 和 face-min-confidence 有明显收益；本轮拆开后显示，corner 输入上的主要有效因子更可能是 face-scale-factor，而不是 face-min-confidence。

### C5：corner_reacq_loose

- 测试方向：放宽重绑定阈值。
- 相对 C0：所有锁定质量指标、tracker_switches、reacquired_count、face_misses 和调用次数完全不变。
- 结论：和 G3 一致，当前 clip 上不存在明显“重绑定过保守导致找不回”的问题。

### C6：corner_reacq_strict

- 测试方向：收紧重绑定阈值。
- 相对 C0：所有锁定质量指标、tracker_switches、reacquired_count、face_misses 和调用次数完全不变。
- 结论：和 G4 一致，当前 clip 上也没有明显“重绑定过激进导致误恢复”的可见证据。
- 综合 C5/C6：重绑定阈值不是本轮 corner case 的主要矛盾。

### C7：corner_control_stable

- 测试方向：控制中心稳定性。
- 锁定质量相对 C0：FACE_LOCK、HEAD_PROXY、LOST、tracker_switches、face_misses 和调用次数完全不变。
- 控制指标相对 C0：平均 control_distance_to_center 从 151.276 降到 136.738；P95 control_distance_to_center 从 290.42 降到 229.74；filtered center 平均步长从 5.183 降到 3.553；P95 步长从 11.203 降到 4.505。
- 结论：C7 不改变检测/锁定质量，但明显让控制中心输出更平滑、更靠近中心，是云台前端最有意义的工程参数方向。
- 风险：更平滑不等于真实云台闭环更好；仍需真实云台或仿真闭环验证响应滞后、过冲和稳态误差。

### C8：corner_mtcnn2

- 测试方向：降低 MTCNN 刷新频率。
- 相对 C0：MTCNN calls 从 737 降到 372，FACE_LOCK 减少 35，HEAD_PROXY 增加 35，face_detected 减少 31，face_misses 增加 31；tracker_switches 不变。
- 结论：C8 复现了 G6/G7 的核心风险：降低 MTCNN 刷新频率会直接损伤 FACE_LOCK 连续性。虽然 runtime 下降，但质量代价明确，不适合作为质量优先配置。

## 11. Corner Case 交叉分析

### 11.1 主检测参数不是当前优先方向

C1 和 C2 共同说明：

- 提高 imgsz 到 1152 会变慢且恶化 LOST / tracker_switches。
- 降低 conf 到 0.20 没有改变质量指标。

因此，新视频上的主检测瓶颈不是“分辨率不够”或“conf 太高导致漏检”。主检测参数可以保持当前基线，不建议继续优先上探 imgsz。

### 11.2 人脸召回方向仍然有效，但有效参数更集中

C3 的 FACE_LOCK +6、HEAD_PROXY -5、face_misses -6 表明 face-scale-factor 方向仍有正收益。C4 单独降低 face-min-confidence 没有变化，说明本视频上 MTCNN 置信度阈值不是主要限制。

这修正了 G2 的结论粒度：旧视频 G2 的组合收益成立，但在 corner case 输入上，真正值得优先细扫的是 face-scale-factor，而不是盲目同时压低所有 face 阈值。

### 11.3 重绑定参数连续两组视频都不是主要矛盾

G3/G4 和 C5/C6 都显示，宽松/严格两边调 reacquire 门限都没有改变 FACE_LOCK、HEAD_PROXY、tracker_switches 和 reacquired_count。这是比较强的跨视频证据：当前系统的主要问题不在重绑定阈值。

只有当新视频出现强遮挡后找不回、多人交错后误绑、tracker_switches 或 reacquired_count 异常时，才建议重新打开这条线。

### 11.4 云台前端应单独看控制稳定性，不能只看 FACE_LOCK

C7 是一个典型例子：锁定质量表面上和 C0 完全相同，但控制输出明显更平滑。它不会让 FACE_LOCK 增加，却可能让云台前端更可用。

因此，面向云台控制时，不能只用 FACE_LOCK 和 HEAD_PROXY 排名，还要看 filtered_target_center 步长、control_distance_to_center、deadband_active 和真实闭环响应。

### 11.5 MTCNN interval 仍然是高风险轻量化参数

C8 把 MTCNN calls 减少约一半，但 FACE_LOCK -35、HEAD_PROXY +35、face_misses +31。这个结果和 G6/G7 同向：MTCNN 稀疏化会直接把真实脸框覆盖退化为 HEAD_PROXY。

因此，轻量化优先级仍然应该是先调 reid-interval，再谨慎评估 mtcnn-interval。除非业务允许更多 HEAD_PROXY，否则不建议把 mtcnn-interval 作为第一轻量化旋钮。

## 12. 与 G1-G7 结论的合并判断

综合两段视频的实验，当前更稳定的结论如下：

1. imgsz 上探不是优先方向。G1 和 C1 都表明 imgsz 1152 成本高，且没有稳定质量收益。
2. 人脸召回是质量向的核心方向，但应优先细扫 face-scale-factor。G2 的组合收益和 C3 的单因子收益共同支持这条线。
3. face-min-confidence 单独降低不一定有效。C4 没有质量变化，说明它不是所有视频都有效的通用旋钮。
4. reacquire 门限不是当前主要瓶颈。G3/G4/C5/C6 均无明显质量影响。
5. mtcnn-interval 是高风险轻量化参数。G6/G7/C8 均显示 MTCNN 稀疏化会降低 FACE_LOCK 或增加 HEAD_PROXY。
6. 控制稳定性应独立成线。C7 证明控制参数可以在不改变锁定质量的前提下改善控制中心平滑度。

## 13. 更新后的推荐配置方向

### 13.1 质量优先

优先方向：face-scale-factor 局部细扫。

建议下一轮只围绕 C3 展开，例如：

1. 固定其他参数，测试 face-scale-factor 1.02、1.03、1.04。
2. 对每个点同时检查 FACE_LOCK、HEAD_PROXY、face_misses 和人工关键帧。
3. 如果 1.03 仍然最优，再小范围测试 face-min-neighbors，避免引入过多假脸候选。

不建议继续优先投入 imgsz 1152 或单独降低 face-min-confidence。

### 13.2 速度优先

优先方向仍然是 G5 的 reid-interval，而不是 C8 的 mtcnn-interval。

原因是：

- G5 已证明 embedding calls 大幅下降且质量指标基本不变。
- C8 虽然 MTCNN calls 明显下降，但 FACE_LOCK 明确下降、HEAD_PROXY 明确上升。

因此，下一轮轻量化应继续测试 reid-interval 的安全上限，例如 4、6、8、10；在没有必要时不要先动 mtcnn-interval。

### 13.3 云台控制优先

如果目标是云台前端可用性，而不是单纯提高 FACE_LOCK，C7 是本轮最值得保留的工程配置方向。

推荐继续验证：

1. control-alpha 0.78、0.82、0.86。
2. control-max-step 20、25、30。
3. 同时记录 avg / P95 control_distance_to_center、filtered_target_center 步长、过冲和滞后。

但 C7 只能证明视觉输出更平滑，不能替代真实云台闭环测试。

## 14. Corner Case 最终结论摘要

- 最佳质量方向：C3，face-scale-factor 1.03，小幅提升 FACE_LOCK 并降低 HEAD_PROXY / face_misses。
- 最差质量方向：C1 和 C8。C1 增加 LOST 和 tracker_switches；C8 明确把 FACE_LOCK 转移为 HEAD_PROXY。
- 最佳控制方向：C7，在锁定质量不变的前提下降低 control_distance_to_center 和 filtered center 抖动。
- 中性方向：C2、C4、C5、C6。它们没有改变主要质量指标；其中 C5/C6 再次证明当前重绑定阈值不是主矛盾。
- 更新后的总体策略：质量线继续围绕 face-scale-factor；轻量线继续围绕 reid-interval；云台线继续围绕 control-alpha / control-max-step；暂时降级 imgsz、reacquire 阈值和 mtcnn-interval 的优先级。

### 证据缺口

- 本轮报告已经使用 summary.json、frame_metrics.json、performance.json 和 live log 做指标分析。
- 仍缺少人工关键帧复核，因此不能完全排除 C3 新增 FACE_LOCK 中存在假脸框。
- 仍缺少真实云台闭环验证，因此 C7 只能说明视觉控制输出更平滑，不能直接证明云台实际跟踪更稳。