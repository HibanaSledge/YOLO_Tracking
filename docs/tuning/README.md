# Offline Tuning Workspace

本目录保存离线单目标锁定调参相关的参数表、进度、结果和最终分析报告。可复用执行脚本统一放在 `tools/tuning/`，运行输出保留在 `runs/` 下。

## 文件说明

- `lock_target_parameter_table.md`：参数优先级、调参路线和 corner case 记录。
- `offline_tuning_progress.md`：最近一次离线调参执行进度和 live log 摘要。
- `offline_tuning_results.md`：baseline 与 G1-G7 的统一指标表，包含速度/质量影响判断。
- `offline_tuning_analysis_report.md`：七轮离线调参中文最终分析报告。

## 可复用脚本

- `tools/tuning/run_offline_tuning.ps1`：从头运行 G1-G7 离线调参。
- `tools/tuning/continue_offline_tuning_after_g1.ps1`：等待 G1 完成后自动续跑 G2-G7。
- `tools/tuning/monitor_manual_offline_experiment.ps1`：监控手动启动的单轮实验进程并更新进度/结果。

三个脚本会从自身位置向上查找 `lock_target.py` 来定位仓库根目录，因此移动到 `tools/tuning/` 后仍可复用。

## 输出目录

- `runs/lock_target_tuning/`：G1-G7 实验输出目录。
- `runs/offline_tuning_logs/`：调参 live log、stdout、stderr 和合并日志。

## 常用入口

在仓库根目录运行：

```powershell
.\tools\tuning\run_offline_tuning.ps1
```

如果 G1 已经手动启动，需要自动续跑后续实验：

```powershell
.\tools\tuning\continue_offline_tuning_after_g1.ps1 -StartAfterId G1
```

如果需要监控手动启动的实验进程：

```powershell
.\tools\tuning\monitor_manual_offline_experiment.ps1 -ProcessId <PID> -ExperimentId G1 -ExperimentName detect_img1152 -ParamsText "--imgsz 1152"
```
