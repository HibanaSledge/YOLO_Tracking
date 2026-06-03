# Lock Target Project

本项目是在 Ultralytics 本地代码仓基础上扩展的一套单目标人脸锁定系统，覆盖离线视频实验、实时摄像头锁定、离线调参复盘、上位机到下位机云台通信和项目文件归档。

## 当前已完成能力

- 离线视频单目标人脸锁定：由 [lock_target.py](lock_target.py) 提供。
- 实时摄像头单目标人脸锁定：由 [lock_target_realtime.py](lock_target_realtime.py) 提供。
- 性能与质量证据输出：summary、frame_metrics、performance 统一落盘。
- 离线调参文档已覆盖 G1-G7、C0-C8、P0-P11 三阶段实验，并提供中文分析报告与指标解释：见 [docs/tuning/](docs/tuning/)。
- 云台 tracking 串口通信协议与上位机发送链路：见 [gimbal/](gimbal/) 和 [docs/gimbal/](docs/gimbal/)。
- 调参脚本、云台脚本、文档和运行产物已按任务分类整理。

## 建议阅读顺序

如果当前目标是快速理解项目现状，建议按下面顺序阅读：

1. 先看 [lock_target_project_report.md](lock_target_project_report.md)，了解项目阶段、核心技术路线、当前瓶颈和下一步建议。
2. 再看 [docs/tuning/offline_tuning_analysis_report.md](docs/tuning/offline_tuning_analysis_report.md)，重点阅读开头的指标解释以及 G1-G7、C0-C8、P0-P11 对比结论。
3. 最后按需回看 [docs/tuning/offline_tuning_progress.md](docs/tuning/offline_tuning_progress.md)、[docs/tuning/corner_case_tuning_progress_corner_20260528_160426.md](docs/tuning/corner_case_tuning_progress_corner_20260528_160426.md)、[docs/tuning/priority_sweep_progress_priority_sweep_20260529.md](docs/tuning/priority_sweep_progress_priority_sweep_20260529.md) 获取执行日志与阶段性结论。

## 目录结构

```text
ultralytics/
├─ docs/
│  ├─ gimbal/                       # 云台协议、闭环验证说明和索引
│  └─ tuning/                       # 调参参数表、进度、结果和最终报告
├─ gimbal/                          # 云台串口协议实现模块
├─ tools/
│  ├─ gimbal/                       # 云台协议测试和验证报告生成脚本
│  └─ tuning/                       # 离线调参和实时进度监控脚本
├─ runs/
│  ├─ gimbal_closed_loop_validation/ # 云台 dry-run 验证产物
│  ├─ lock_target/                  # 离线锁定历史输出
│  ├─ lock_target_realtime/         # 实时锁定历史输出
│  ├─ lock_target_tuning/           # G1-G7 调参实验输出
│  └─ offline_tuning_logs/          # 调参 live log/stdout/stderr
├─ lock_target.py                   # 离线锁定主脚本
├─ lock_target_realtime.py          # 实时摄像头主脚本，已支持可选云台串口输出
├─ perf_utils.py                    # 性能记录模块
├─ lock_target_change_log.md        # 修改记录与证据缺口
└─ lock_target_project_report.md    # 项目进度与技术路线报告
```

## 运行前提

### 1. 工作目录

运行命令前，请先进入项目根目录，也就是包含 [lock_target.py](lock_target.py) 和 [lock_target_realtime.py](lock_target_realtime.py) 的目录。

```powershell
cd path/to/ultralytics
```

### 2. Python 版本

推荐 Python 3.10。

```powershell
py -3.10 lock_target.py --help
```

如果 `python` 命令已经指向正确版本，也可以直接用：

```powershell
python lock_target.py --help
```

### 3. 依赖

运行脚本至少需要以下依赖：

- ultralytics
- opencv-python
- numpy
- torch
- facenet-pytorch
- psutil
- pyserial：真实串口云台通信需要。
- matplotlib：生成云台验证可视化图片需要。

### 4. 模型权重

默认命令依赖以下两个权重文件位于项目根目录：

- yolo26n.pt
- yolo26l.pt

如果权重放在别的目录，需要显式修改 `--model` 和 `--reid-model` 的路径。

## 快速开始

### 离线视频锁定

```powershell
py -3.10 lock_target.py --source "path/to/video.mp4" --model yolo26n.pt --tracker cfg/trackers/botsort.yaml --reid-model yolo26l.pt --classes 0 --conf 0.25 --iou 0.5 --imgsz 960 --initial-track-id 1 --fallback-to-first-face --project runs/lock_target --name offline_run --show --save-all-boxes
```

常用输出目录：

- [runs/lock_target](runs/lock_target)

每次运行会在对应子目录下生成：

- `*_locked.mp4`
- `*_summary.json`
- `*_frame_metrics.json`
- `*_performance.json`

### 实时摄像头锁定

```powershell
py -3.10 lock_target_realtime.py --camera 0 --camera-width 960 --camera-height 540 --camera-fps 30 --imgsz 512 --display-width 800 --reid-interval 10 --mtcnn-interval 4 --initial-track-id 1 --fallback-to-first-face --project runs/lock_target_realtime --name camera
```

常用输出目录：

- [runs/lock_target_realtime](runs/lock_target_realtime)

实时模式结束后会输出：

- `*_locked.mp4`
- `*_summary.json`
- `*_frame_metrics.json`
- `*_performance.json`

实时窗口中按 `q` 退出。

## 新任务 1：云台 tracking 串口通信

已完成上位机 camera tracking 到下位机云台控制的通信出口。实时脚本会把 `frame_metric` 中的 `control_offset` 转换为云台 `pan_speed` 和 `tilt_speed`，通过串口协议发给下位机。

### 关键文件

- [gimbal/serial_client.py](gimbal/serial_client.py)：串口协议打包、CRC、TRACK/STOP 发送、dry-run 支持。
- [docs/gimbal/serial_protocol.md](docs/gimbal/serial_protocol.md)：上位机到下位机串口通信协议。
- [docs/gimbal/closed_loop_validation.md](docs/gimbal/closed_loop_validation.md)：下位机固件闭环验证步骤。
- [docs/gimbal/README.md](docs/gimbal/README.md)：云台任务索引。
- [tools/gimbal/test_serial.py](tools/gimbal/test_serial.py)：固定命令串口测试脚本。
- [tools/gimbal/run_closed_loop_validation.py](tools/gimbal/run_closed_loop_validation.py)：闭环验证报告与可视化图片生成脚本。

### 协议摘要

- 帧头：`0xAA 0x55`
- 版本：`0x01`
- 消息类型：TRACK、STOP、HEARTBEAT 预留
- 校验：CRC16-Modbus
- TRACK payload：state、flags、frame_index、dx_px、dy_px、pan_speed、tilt_speed、distance_px
- STOP payload：reason

### 实时 tracking 接云台示例

真实串口：

```powershell
py -3.10 lock_target_realtime.py --camera 0 --camera-width 960 --camera-height 540 --camera-fps 30 --imgsz 512 --display-width 800 --initial-track-id 1 --fallback-to-first-face --project runs/lock_target_realtime --name camera_gimbal --gimbal-port COM3 --gimbal-baud 115200 --gimbal-command-rate 20 --gimbal-max-speed 150
```

无硬件 dry-run：

```powershell
py -3.10 lock_target_realtime.py --camera 0 --camera-width 960 --camera-height 540 --camera-fps 30 --imgsz 512 --display-width 800 --initial-track-id 1 --fallback-to-first-face --project runs/lock_target_realtime --name camera_gimbal_dry --gimbal-dry-run
```

### 云台验证结果

已完成无硬件 dry-run 协议闭环验证，结果保存在：

- [runs/gimbal_closed_loop_validation/protocol_dry_run_20260528-113713](runs/gimbal_closed_loop_validation/protocol_dry_run_20260528-113713)

该目录包含：

- `validation_report.md`
- `validation_summary.json`
- `validation_commands.csv`
- `command_timeseries.png`
- `offset_speed_mapping.png`
- `validation_checks.png`

证据缺口：本机当时只检测到 COM1，未检测到真实下位机控制板串口，因此真实电机闭环、稳态误差、响应延迟、过冲和丢包恢复仍需接入实际硬件后验证。

## 新任务 2：离线调参脚本与结果归档

已将离线调参任务产生的脚本、实时进度监控脚本、参数表、结果表和分析报告按用途归档，当前文档同时覆盖早期 G1-G7、后续 C0-C8 corner case，以及最新 P0-P11 priority sweep，后续调参实验可以继续复用这套入口。

### 调参脚本

调参脚本统一放在 [tools/tuning/](tools/tuning/)：

- [tools/tuning/run_offline_tuning.ps1](tools/tuning/run_offline_tuning.ps1)：从头运行 G1-G7。
- [tools/tuning/continue_offline_tuning_after_g1.ps1](tools/tuning/continue_offline_tuning_after_g1.ps1)：等待指定前置实验完成后续跑后续实验。
- [tools/tuning/monitor_manual_offline_experiment.ps1](tools/tuning/monitor_manual_offline_experiment.ps1)：监控手动启动的实验 PID，并更新进度/结果。

三个脚本已改为从自身路径向上查找 [lock_target.py](lock_target.py) 来定位仓库根目录，因此移动到 [tools/tuning/](tools/tuning/) 后仍可复用。

### 调参文档

调参文档统一放在 [docs/tuning/](docs/tuning/)：

- [docs/tuning/README.md](docs/tuning/README.md)：调参任务索引和常用命令。
- [docs/tuning/lock_target_parameter_table.md](docs/tuning/lock_target_parameter_table.md)：参数优先级、调参路线和 corner case。
- [docs/tuning/offline_tuning_progress.md](docs/tuning/offline_tuning_progress.md)：最近调参进度和 live log 摘要。
- [docs/tuning/offline_tuning_results.md](docs/tuning/offline_tuning_results.md)：baseline 与 G1-G7 的统一指标表。
- [docs/tuning/offline_tuning_analysis_report.md](docs/tuning/offline_tuning_analysis_report.md)：主调参分析报告，已汇总 G1-G7、C0-C8、P0-P11，并补充 `FACE_LOCK` / `HEAD_PROXY` 等指标解释、观感映射和人工关键帧复核建议。

阅读这些调参文档时，建议先看 [docs/tuning/offline_tuning_analysis_report.md](docs/tuning/offline_tuning_analysis_report.md) 开头的指标解释，再回看结果表。这里的原则是：不能把 tracker id 连续性直接当成业务目标连续性，也不能把 `HEAD_PROXY` 视为真实的人脸锁定成功；所有质量结论都需要结合关键帧人工复核。

### 调参输出

- [runs/lock_target_tuning](runs/lock_target_tuning)：G1-G7 实验输出。
- [runs/offline_tuning_logs](runs/offline_tuning_logs)：live log、stdout、stderr 和合并日志。

### 常用调参入口

从头运行 G1-G7：

```powershell
.\tools\tuning\run_offline_tuning.ps1
```

从 G1 之后续跑：

```powershell
.\tools\tuning\continue_offline_tuning_after_g1.ps1 -StartAfterId G1
```

监控手动实验进程：

```powershell
.\tools\tuning\monitor_manual_offline_experiment.ps1 -ProcessId <PID> -ExperimentId G1 -ExperimentName detect_img1152 -ParamsText "--imgsz 1152"
```

## 轻量模式

如果想快速切到轻量模式，可以使用 `--lightweight`。

### 离线轻量模式

```powershell
py -3.10 lock_target.py --source "path/to/video.mp4" --model yolo26n.pt --tracker cfg/trackers/botsort.yaml --reid-model yolo26l.pt --classes 0 --conf 0.25 --iou 0.5 --imgsz 960 --initial-track-id 1 --fallback-to-first-face --project runs/lock_target --name offline_run_light --show --save-all-boxes --lightweight
```

### 实时轻量模式

```powershell
py -3.10 lock_target_realtime.py --camera 0 --camera-width 960 --camera-height 540 --camera-fps 30 --imgsz 512 --display-width 800 --initial-track-id 1 --fallback-to-first-face --project runs/lock_target_realtime --name camera_light --lightweight
```

说明：

- `--lightweight` 当前会提升 `reid_interval` 和 `mtcnn_interval`，优先降低稳定跟踪阶段的计算开销。
- 轻量模式可以提升速度，但当前不能保证和完整版逐帧输出完全一致。

## 只生成最终 Demo 视频

如果只想保留最终视频，不写出 summary、frame_metrics、performance，可以使用 `--demo-only`。

```powershell
py -3.10 lock_target.py --source "path/to/video.mp4" --model yolo26n.pt --tracker cfg/trackers/botsort.yaml --reid-model yolo26l.pt --classes 0 --conf 0.25 --iou 0.5 --imgsz 960 --initial-track-id 1 --fallback-to-first-face --project runs/lock_target --name offline_demo --show --save-all-boxes --demo-only
```

## 常见问题

### 1. 为什么命令里不再使用绝对路径

README 中使用的是跨机器可复用写法，前提是：

- 你已经进入项目根目录。
- 你的 Python 环境已经装好依赖。
- 权重文件位置与命令里的相对路径一致。

### 2. 为什么我的机器上 `python` 不能用

请优先尝试：

```powershell
py -3.10 lock_target.py --help
```

如果还是不行，说明 Python 3.10 没有加入启动器或环境变量，需要先修正本机 Python 环境。

### 3. 为什么实时模式帧率很低

当前算法链路在人脸检测、MTCNN 和 embedding 提取上开销较大。在 CPU-only 环境下，实时模式更像低延迟演示系统，而不是高帧率实时系统。

### 4. 为什么轻量模式和完整版结果不完全一致

因为轻量模式会减少 embedding 和 MTCNN 的刷新频率，这会影响部分帧的人脸框更新和中心轨迹。当前它适合做提速实验，不适合定义为“质量完全等价”的替代模式。

### 5. 为什么云台 dry-run 通过仍不能等同真实闭环通过

dry-run 只证明上位机协议打包、方向映射、STOP 行为和报告生成链路可用；真实云台还需要下位机固件解析、串口收发、电机方向、速度标定和相机画面误差收敛验证。

## 参考文档

- [lock_target_change_log.md](lock_target_change_log.md)
- [lock_target_project_report.md](lock_target_project_report.md)
- [docs/tuning/README.md](docs/tuning/README.md)
- [docs/tuning/offline_tuning_analysis_report.md](docs/tuning/offline_tuning_analysis_report.md)
- [docs/gimbal/README.md](docs/gimbal/README.md)
- [docs/gimbal/serial_protocol.md](docs/gimbal/serial_protocol.md)
- [docs/gimbal/closed_loop_validation.md](docs/gimbal/closed_loop_validation.md)
