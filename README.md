# Lock Target Project

本项目是在 Ultralytics 本地代码仓基础上扩展的一套单目标人脸锁定系统，支持两种运行模式：

- 离线视频锁定
- 实时摄像头锁定

项目根目录下的核心脚本如下：

- [lock_target.py](lock_target.py)：离线锁定主脚本
- [lock_target_realtime.py](lock_target_realtime.py)：实时摄像头主脚本
- [perf_utils.py](perf_utils.py)：性能记录模块
- [lock_target_change_log.md](lock_target_change_log.md)：修改记录
- [lock_target_project_report.md](lock_target_project_report.md)：项目进度与技术路线报告

## 运行前提

### 1. 工作目录

运行命令前，请先进入项目根目录，也就是包含 [lock_target.py](lock_target.py) 和 [lock_target_realtime.py](lock_target_realtime.py) 的目录。

示例：

```powershell
cd path/to/ultralytics
```

在 Windows PowerShell 中，如果你当前就在项目根目录，可以直接执行 README 下面的命令。

### 2. Python 版本

推荐 Python 3.10。

如果你的机器装了多个 Python 版本，优先使用下面这种写法：

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

如果需要在新机器上补齐依赖，可以先按你的环境管理方式安装这些包。

### 4. 模型权重

默认命令依赖以下两个权重文件位于项目根目录：

- yolo26n.pt
- yolo26l.pt

如果你把权重放在别的目录，需要显式修改 `--model` 和 `--reid-model` 的路径。

## 快速开始

### 离线视频锁定

下面这条命令用于处理一段本地视频，并输出锁定结果：

```powershell
py -3.10 lock_target.py --source "path/to/video.mp4" --model yolo26n.pt --tracker cfg/trackers/botsort.yaml --reid-model yolo26l.pt --classes 0 --conf 0.25 --iou 0.5 --imgsz 960 --initial-track-id 1 --fallback-to-first-face --project runs/lock_target --name offline_run --show --save-all-boxes
```

参数说明：

- `--source`：输入视频路径，需要替换成你自己的视频文件。
- `--model`：主检测模型。
- `--tracker`：BoT-SORT 配置文件。
- `--reid-model`：用于提取外观特征的模型。
- `--classes 0`：仅保留 person 类别。
- `--initial-track-id 1`：优先锁定 tracker id 1。
- `--fallback-to-first-face`：当初始 id 不可用时，回退到第一张检测到的人脸。
- `--show`：处理时显示窗口。
- `--save-all-boxes`：输出视频时绘制所有 tracker 框。

输出目录默认位于：

- [runs/lock_target](runs/lock_target)

每次运行会在对应子目录下生成：

- `*_locked.mp4`
- `*_summary.json`
- `*_frame_metrics.json`
- `*_performance.json`

### 实时摄像头锁定

下面这条命令用于打开本机摄像头做实时锁定：

```powershell
py -3.10 lock_target_realtime.py --camera 0 --camera-width 960 --camera-height 540 --camera-fps 30 --imgsz 512 --display-width 800 --reid-interval 10 --mtcnn-interval 4 --initial-track-id 1 --fallback-to-first-face --project runs/lock_target_realtime --name camera
```

参数说明：

- `--camera 0`：使用默认摄像头。
- `--camera-width`、`--camera-height`：请求摄像头分辨率。
- `--camera-fps`：请求摄像头帧率。
- `--imgsz`：实时推理尺寸。
- `--display-width`：显示窗口缩放宽度。
- `--reid-interval`：稳定跟踪时 embedding 刷新间隔。
- `--mtcnn-interval`：稳定跟踪时 MTCNN 刷新间隔。

输出目录默认位于：

- [runs/lock_target_realtime](runs/lock_target_realtime)

实时模式结束后会输出：

- `*_locked.mp4`
- `*_summary.json`
- `*_frame_metrics.json`
- `*_performance.json`

实时窗口中按 `q` 退出。

## 轻量模式

如果你想快速切到轻量模式，可以使用 `--lightweight`。

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
- 轻量模式可以提升速度，但当前并不能保证和完整版逐帧输出完全一致。

## 只生成最终 Demo 视频

如果你只想保留最终视频，不想写出 summary、frame_metrics、performance，可以使用 `--demo-only`。

示例：

```powershell
py -3.10 lock_target.py --source "path/to/video.mp4" --model yolo26n.pt --tracker cfg/trackers/botsort.yaml --reid-model yolo26l.pt --classes 0 --conf 0.25 --iou 0.5 --imgsz 960 --initial-track-id 1 --fallback-to-first-face --project runs/lock_target --name offline_demo --show --save-all-boxes --demo-only
```

## 常见问题

### 1. 为什么命令里不再使用绝对路径

README 中使用的是跨机器可复用写法，前提是：

- 你已经进入项目根目录。
- 你的 Python 环境已经装好依赖。
- 权重文件位置与命令里的相对路径一致。

这样命令才能在不同机器上复用，而不是绑定某一台机器上的固定目录。

### 2. 为什么我的机器上 `python` 不能用

请优先尝试：

```powershell
py -3.10 lock_target.py --help
```

如果还是不行，说明你的 Python 3.10 没有加入启动器或环境变量，需要先修正本机 Python 环境。

### 3. 为什么实时模式帧率很低

当前算法链路在人脸检测、MTCNN 和 embedding 提取上开销较大。在 CPU-only 环境下，实时模式更像低延迟演示系统，而不是高帧率实时系统。

### 4. 为什么轻量模式和完整版结果不完全一致

因为轻量模式会减少 embedding 和 MTCNN 的刷新频率，这会影响部分帧的人脸框更新和中心轨迹。当前它适合做提速实验，不适合定义为“质量完全等价”的替代模式。

## 参考文档

- [lock_target_change_log.md](lock_target_change_log.md)
- [lock_target_project_report.md](lock_target_project_report.md)