# Architecture

## Offline Pipeline

`lock_target.py` 的典型流程：

1. 读取视频帧。
2. YOLO 检测与 BoT-SORT 跟踪。
3. 从 person tracks 构造候选。
4. 在人体框内做人脸检测：OpenCV frontal/profile + MTCNN。
5. 计算或复用 embedding。
6. 使用 appearance、IoU、center continuity 更新业务目标 `TargetState`。
7. 输出 FACE_LOCK / HEAD_PROXY / LOST 等 lock mode。
8. 更新 filtered control center。
9. 写出 video、summary、frame_metrics、performance。

## Realtime Pipeline

`lock_target_realtime.py` 的核心架构：

camera thread -> latest-frame buffer -> processing thread -> display loop

设计目标是低延迟，不保留每一帧。处理低于采集速率时，系统主动丢弃旧帧，避免显示积压。

## Shared Performance Layer

`perf_utils.py` 提供统一性能记录：阶段耗时、帧总耗时、候选数量、embedding/MTCNN 次数、CPU/内存/CUDA 信息。无 `psutil` 或 CUDA 时不阻断主流程。

## Core Design Choice

业务目标不直接等于 tracker id。底层 tracker 可能换 id 或漂移，业务层必须用 `TargetState` 和重绑定逻辑维护“同一个目标”。