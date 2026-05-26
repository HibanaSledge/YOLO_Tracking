# 单目标人脸锁定项目进度与技术路线报告

## 1. 项目概述

本项目基于本地 Ultralytics 代码仓，目标是构建一套可用于云台视觉前端的单目标锁定系统。系统需要在 YOLO 检测和多目标跟踪的基础上，对业务目标实现持续身份保持、脸部级别的几何定位、逐帧控制量输出，以及离线分析和实时摄像头运行两种工作模式。

项目已经从最初的 tracker 复现与原理验证，演进到当前的双模式业务系统：

- 离线模式：面向实验复跑、指标统计、视频检查和参数对比。
- 实时模式：面向本机 RGB 摄像头接入、低延迟显示和会话结果保存。

当前系统已具备完整的原型链路，但距离“可直接上云台产品化”的目标仍存在两类核心差距：

- 锁定几何质量在侧脸、遮挡和快速转头场景下仍不够稳定。
- CPU-only 环境下的实时吞吐量远低于业务级实时要求。

## 2. 业务目标与阶段演进

项目需求经历了以下四个阶段：

1. 跟踪算法复现阶段
   - 复现并理解 BoT-SORT 与 ByteTrack。
   - 明确 BoT-SORT 可选 ReID，ByteTrack 主要依赖框与运动关联。

2. 单目标业务锁定阶段
   - 在底层 tracker 之上新增业务层目标状态，而不是直接依赖 tracker id。
   - 从整个人体框锁定，逐步演进到真实人脸框锁定。

3. 云台视觉前端阶段
   - 新增逐帧 frame_metrics 输出，提供目标中心、画面中心、偏移量和滤波控制中心。
   - 新增 TRACKING、HOLD、LOST、REACQUIRE 等控制状态，以及 FACE_LOCK、HEAD_PROXY 等锁定模式。

4. 实时与轻量化阶段
   - 新增实时摄像头脚本与最新帧优先架构。
   - 新增 performance.json 性能记录。
   - 新增 demo-only、no-save-*、lightweight 等轻量化机制。

## 3. 当前项目进度总结

### 3.1 已完成内容

- 已完成 BoT-SORT / ByteTrack 的复现说明与本地运行方案。
- 已完成离线业务主脚本 [lock_target.py](lock_target.py)。
- 已完成实时摄像头主脚本 [lock_target_realtime.py](lock_target_realtime.py)。
- 已完成统一性能记录模块 [perf_utils.py](perf_utils.py)。
- 已完成输出格式统一：视频、summary、frame_metrics、performance。
- 已完成人脸检测混合方案：OpenCV frontal/profile + MTCNN。
- 已完成基于 YOLO embed 的外观特征抽取与跨 ID 重绑定逻辑。
- 已完成控制层滤波、死区和状态输出设计。
- 已完成 demo-only 和 no-save-* 输出参数化。
- 已完成 lightweight 轻量化运行预设。

### 3.2 已验证结论

- 系统已经不是单纯的 tracker demo，而是具备业务层目标保持与控制量输出能力的原型系统。
- 在离线视频中，系统可以完成目标初始化、跨 ID 延续、锁定状态输出和最终结果保存。
- 在实时摄像头模式下，系统可以稳定运行并主动丢弃旧帧，避免显示链路越积越慢。
- 性能瓶颈已被定位：离线主瓶颈在 collect_candidates，人脸检测和 embedding 是主要重路径。

### 3.3 尚未完成内容

- 尚未实现“输出质量严格不变”的轻量化主链路优化。
- 尚未在 CPU-only 环境达到业务级实时帧率。
- 尚未完成与真实云台执行机构的闭环联调。
- 尚未建立侧脸和快速头部姿态场景下的自动化几何质量评测指标。

## 4. 当前系统架构

### 4.1 离线链路

离线主链路由 [lock_target.py](lock_target.py) 实现，整体流程如下：

1. 使用 YOLO 对视频逐帧执行检测与跟踪。
2. 从 tracker 输出的人体候选中筛选业务候选目标。
3. 在候选人体区域内执行人脸检测。
4. 为可用人脸区域抽取 embedding，用于外观一致性约束。
5. 基于外观、IoU 和中心距离综合选择目标。
6. 更新 TargetState，输出 FACE_LOCK / HEAD_PROXY / LOST 等业务状态。
7. 计算控制中心与控制偏移量。
8. 写出视频、summary、frame_metrics、performance。

### 4.2 实时链路

实时主链路由 [lock_target_realtime.py](lock_target_realtime.py) 实现，架构为：

- camera thread -> latest-frame buffer -> processing thread -> display loop

这样设计的原因是：

- 摄像头采集持续进行，不阻塞处理。
- 处理线程只拿最新帧，不维护待处理队列。
- 显示线程只展示最新处理结果，因此不会产生不断累积的显示延迟。

这是一条“低延迟优先”而不是“全帧保留优先”的实时链路，适合云台视觉前端原型验证。

### 4.3 关键模块职责

- [lock_target.py](lock_target.py)：离线目标锁定、控制量导出、输出保存。
- [lock_target_realtime.py](lock_target_realtime.py)：实时采集、处理、显示和会话保存。
- [perf_utils.py](perf_utils.py)：逐帧性能记录、阶段耗时统计、资源采样。
- [lock_target_change_log.md](lock_target_change_log.md)：关键功能修改与实验记录。

## 5. 核心算法路线

### 5.1 检测与跟踪底座

- 检测模型：YOLO，当前默认使用 yolo26n.pt。
- 跟踪器：BoT-SORT，配置来自 cfg/trackers/botsort.yaml。
- 业务目标并不直接绑定到底层 tracker id，而是额外维护 TargetState。

这是本项目的关键设计点。底层 tracker 只负责候选轨迹，业务系统负责决定“当前哪个轨迹仍然是被锁定目标”。

### 5.2 人脸定位路线

人脸定位采用混合策略：

- OpenCV frontal Haar cascade
- OpenCV profile Haar cascade
- facenet_pytorch 的 MTCNN

策略上优先使用 classical detector，在有需要时由 MTCNN 补充召回，并在部分场景下利用 landmarks 改善脸框几何位置。

### 5.3 身份连续性路线

身份连续性依赖三类信号融合：

- 外观相似度：人脸 embedding 与历史 prototype 的余弦相似度。
- 几何一致性：IoU。
- 运动一致性：中心距离分数。

这一路线的目的不是构建通用多目标 ReID 系统，而是在单目标业务前提下，尽可能提高跨 ID 切换时的连续性。

### 5.4 代理头部框路线

在真实人脸短时不可见时，系统不会直接认为目标丢失，而是基于 face_relative_bbox 与人体框投影出 HEAD_PROXY。这样可以：

- 提高短时遮挡或侧脸场景下的连续性。
- 避免目标状态频繁在 FACE_LOCK 和 LOST 之间跳变。

同时，系统显式输出 lock_mode，区分真实脸锁定与代理头部锁定，避免把代理框误当成真实脸框。

### 5.5 控制输出路线

为了适配云台控制，本项目在视觉层输出以下控制相关量：

- frame_center
- raw_target_center
- filtered_target_center
- offset
- control_offset
- distance_to_center
- control_distance_to_center
- control_state
- deadband_active

这使得系统输出从“可视化框”演进为“可供控制层读取的逐帧观测量”。

## 6. 关键里程碑与结果

### 6.1 里程碑一：人脸锁定链路成型

根据 [lock_target_change_log.md](lock_target_change_log.md)，项目已经完成从人体代理框到真实 face_bbox 的演进，并补齐了 face_hold、LOST、HEAD_PROXY、FACE_LOCK 等业务层机制。

结果上，系统已经具备以下能力：

- 默认绑定 initial_track_id=1 快速开始实验。
- 短时漏检期间保持业务目标连续。
- 遮挡后尝试重绑定。
- 显式区分真实脸锁定与代理头部锁定。

### 6.2 里程碑二：实时摄像头前端成型

实时样例 [runs/lock_target_realtime/camera_20260525-153555/camera_0_summary.json](runs/lock_target_realtime/camera_20260525-153555/camera_0_summary.json) 表明：

- selected_at_frame = 1
- tracker_switches = 2
- reacquired_count = 2
- processed_frames = 138
- session_duration_sec = 48.57
- camera_fps = 30.01
- process_fps = 1.22
- total_dropped_frames = 1139

这说明实时链路已经具备功能完整性，但当前机器上的处理吞吐量远低于摄像头输入速率，因此系统依赖主动丢帧维持低延迟显示。

### 6.3 里程碑三：性能记录体系成型

[perf_utils.py](perf_utils.py) 已把离线与实时统一到同一套性能记录框架中。当前可以自动得到：

- 各阶段耗时
- 每帧总耗时
- embedding 与 MTCNN 调用次数
- CPU 占用与进程内存
- 实时模式下的 source_frame_id 与 dropped_frames_before

这使后续优化工作从“主观体感调参”变成“基于阶段证据的定向优化”。

## 7. 当前性能与质量现状

### 7.1 离线完整版基线

离线基线结果见 [runs/lock_target/offline_run/20260521-120258_summary.json](runs/lock_target/offline_run/20260521-120258_summary.json)：

- processed_frames = 731
- runtime_sec = 675.325
- effective_fps = 1.082
- tracker_switches = 5
- reacquired_count = 3
- face_detected_frames = 551
- total_face_misses = 110

基线性能瓶颈来自 collect_candidates，其中人脸检测与 embedding 占比最高。

### 7.2 离线 lightweight 版本

轻量版结果见 [runs/lock_target/offline_run_light/20260521-120258_summary.json](runs/lock_target/offline_run_light/20260521-120258_summary.json) 和 [runs/lock_target/offline_run_light/20260521-120258_performance.json](runs/lock_target/offline_run_light/20260521-120258_performance.json)：

- runtime_sec = 434.249
- effective_fps = 1.683
- collect_candidates avg_ms = 450.22
- embedding_calls = 166
- face_detect_mtcnn_calls = 355

与完整版相比：

- 总耗时下降约 35.7%。
- 有效 FPS 提升约 55.5%。
- collect_candidates 平均耗时下降约 41.1%。

### 7.3 轻量化的质量代价

虽然 lightweight 版本的 summary 看起来与完整版接近，但逐帧输出已经发生实质变化：

- FACE_LOCK 帧数从 565 降到 546。
- HEAD_PROXY 帧数从 98 升到 117。
- 有 19 帧从 FACE_LOCK 退化为 HEAD_PROXY。
- filtered_target_center 在可见帧上的平均偏移约为 37.88 像素。
- 最大偏移约为 325.05 像素。

这说明当前 lightweight 版本可以作为“速度更高的实验版本”，但不能定义为“输出质量不变”的等价替代版本。

## 8. 当前主要问题

### 8.1 质量问题

- 侧脸、半侧脸、快速转头场景下，真实 face_bbox 仍可能退化为 HEAD_PROXY。
- HEAD_PROXY 几何位置虽优于纯人体框，但仍不等于真实脸框。
- 当前还缺少自动化几何精度指标，很多判断仍依赖关键帧与视频人工检查。

### 8.2 性能问题

- CPU-only 环境下，离线完整模式仅约 1.08 FPS。
- 实时模式在当前机器上仅约 1.22 FPS，远低于 30 FPS 摄像头输入速率。
- 主瓶颈已明确集中在 collect_candidates、face_detect_total 和 embedding 路径。

### 8.3 工程问题

- 实时链路已经可用，但还未与真实云台控制器形成完整闭环。
- 当前输出是视觉前端观测量，不是整机控制系统的最终闭环性能指标。

## 9. 当前项目判断

从研发阶段判断，项目目前处于：

- POC 已完成
- 工程化原型已成型
- 产品化仍未完成

更具体地说：

- 从“算法能否跑通”这个层面，项目已经完成。
- 从“是否具备实验、调参、复盘、实时演示能力”这个层面，项目已经完成。
- 从“是否可以直接作为稳定云台视觉前端投入使用”这个层面，项目还没有完成。

## 10. 建议的后续技术路线

### 路线 A：质量优先

目标：尽量保持或提升几何质量，再优化速度。

建议动作：

- 保留 MTCNN / landmarks 路线的密度，优先只减少 embedding 开销。
- 对侧脸与转头场景建立关键帧自动评测指标。
- 为 FACE_LOCK 与 HEAD_PROXY 建立单独的中心偏移统计。

适用场景：当前最接近业务目标，因为云台前端更怕“框漂”和“控制中心偏移”。

### 路线 B：速度优先

目标：在当前 CPU 机器上继续压缩耗时，接受一定质量损失。

建议动作：

- 进一步减少 embedding 刷新频率。
- 对 face detector 调用做更激进的降频或裁剪。
- 缩小 imgsz、相机分辨率和 display_width。

适用场景：快速演示或资源受限设备验证，但不适合作为“质量不变”的正式方案。

### 路线 C：硬件升级优先

目标：保持当前算法链路能力，用更合适的算力平台满足实时性。

建议动作：

- 从 CPU-only 迁移到具备 CUDA 的平台。
- 为后续 Jetson + MCU + IMU + 编码器 + 电机驱动的云台方案做板级集成。
- 把当前视觉前端与未来控制链通过标准化 JSON / IPC 接口连接。

适用场景：如果业务目标明确要求 30 FPS 或 60 FPS 级闭环，这是必须路线。

## 11. 推荐的下一阶段工作

当前最合理的下一阶段路线是：

1. 先以质量优先方式继续优化离线链路。
2. 把 lightweight 拆分成“只减 embedding”和“减 embedding + 减 MTCNN”两个版本重新对比。
3. 补一套自动化几何质量评测指标，替代仅靠视频肉眼判断。
4. 在确认质量可接受后，再决定是否继续做更激进的轻量化，还是转向硬件升级。

## 12. 结论

截至目前，本项目已经从底层 tracker 复现工作，发展为一套具备以下特征的业务原型系统：

- 能锁定单目标并跨 ID 保持业务连续性。
- 能把目标框收敛到脸部或头部代理区域。
- 能输出适配云台控制的逐帧观测量。
- 能在离线和实时两种模式下运行。
- 能自动记录结构化性能证据。

但项目的关键矛盾已经从“有没有算法”转移为“如何在不牺牲几何质量的前提下获得可用实时性”。

因此，下一阶段不应再泛化地讨论 tracker 或脚本功能是否齐全，而应聚焦两个真正决定成败的问题：

- 如何把 FACE_LOCK 的真实几何稳定性继续提高。
- 如何把当前算法链路迁移到满足业务实时性的计算平台或更高效实现上。