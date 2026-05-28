# Repo Map

## Root Files

- `lock_target.py`：离线视频单目标人脸锁定主脚本。
- `lock_target_realtime.py`：实时摄像头单目标锁定主脚本。
- `perf_utils.py`：离线与实时共享性能记录。
- `lock_target_change_log.md`：每次关键修改的证据化记录。
- `lock_target_project_report.md`：项目进度与技术路线报告。
- `docs/tuning/lock_target_parameter_table.md`：质量相关参数、调参路线和 corner case。
- `README.md`：运行说明。
- `yolo26n.pt`、`yolo26l.pt`：当前可用权重。

## Important Directories

- `cfg/trackers/`：BoT-SORT / ByteTrack 配置。
- `runs/lock_target/`：离线运行结果。
- `runs/lock_target_realtime/`：实时运行结果。
- `trackers/`：Ultralytics tracker 实现。
- `engine/`、`models/`、`nn/`、`utils/`：Ultralytics 基础框架。
- `.github/agents/`：本 agent 的指令、技能、上下文、harness 和模板。

## Evidence Files

- `*_summary.json`：运行摘要。
- `*_frame_metrics.json`：逐帧质量、状态与控制量。
- `*_performance.json`：阶段耗时和资源统计。
- `*_locked.mp4`：视频结果，用于人工检查几何问题。