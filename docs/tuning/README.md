# Offline Tuning Workspace

本目录保存离线单目标锁定调参相关的参数表、进度、结果和最终分析报告。当前文档体系已经覆盖三类实验：早期 G1-G7 离线调参、后续 C0-C8 corner case 补充实验，以及最新 P0-P11 priority sweep。可复用执行脚本统一放在 `tools/tuning/`，运行输出保留在 `runs/` 下。

## 文件说明

- `lock_target_parameter_table.md`：参数优先级、调参路线和 corner case 记录。
- `offline_tuning_progress.md`：最近一次离线调参执行进度和 live log 摘要。
- `offline_tuning_results.md`：baseline 与 G1-G7 的统一指标表，包含速度/质量影响判断。
- `offline_tuning_analysis_report.md`：主分析报告，已汇总 G1-G7、C0-C8 和 P0-P11，并补充主要指标解释、观感映射和人工关键帧复核建议。
- `corner_case_experiment_plan_20260528_160426.md`：针对 `Q:\20260528-160426.mp4` 的 C0-C8 corner case 调参计划。
- `corner_case_tuning_progress_<RunId>.md`：corner case 调参执行进度，脚本运行后生成。
- `corner_case_tuning_results_<RunId>.md`：corner case 调参统一指标表，脚本运行后生成。

## 建议阅读顺序

1. 先看 `offline_tuning_analysis_report.md` 第 1.1 节，理解 `FACE_LOCK`、`HEAD_PROXY`、`LOST`、`SEARCHING`、`Tracker Switches` 等指标的真实含义，以及这些指标在画面观感上的对应关系。
2. 再看 `offline_tuning_results.md` 或各轮结果表，快速比较速度、质量、连续性指标的变化趋势。
3. 最后回到 `offline_tuning_analysis_report.md` 中对应实验章节，确认结论是否建立在 `summary.json`、`frame_metrics.json`、`performance.json` 和人工关键帧复核之上。

## 判读原则

- 不把 tracker id 连续性直接等同于业务目标身份连续性。
- 不把 `HEAD_PROXY` 当作真实 `FACE_LOCK` 成功。
- 看到 `FACE_LOCK` 增加时，仍要结合关键帧人工复核，确认是否真的锁在目标脸上，而不是旁人脸、误检脸或后脑代理。
- 涉及轻量化或实时性结论时，必须同时看 `FPS`、`Runtime Sec`、各阶段平均耗时，以及质量指标是否同步恶化。

## 可复用脚本

- `tools/tuning/run_offline_tuning.ps1`：从头运行 G1-G7 离线调参。
- `tools/tuning/continue_offline_tuning_after_g1.ps1`：等待 G1 完成后自动续跑 G2-G7。
- `tools/tuning/monitor_manual_offline_experiment.ps1`：监控手动启动的单轮实验进程并更新进度/结果。
- `tools/tuning/run_corner_case_tuning.ps1`：对新输入 `Q:\20260528-160426.mp4` 运行 C0-C8 corner case 调参。

这些脚本会从自身位置向上查找 `lock_target.py` 来定位仓库根目录，因此移动到 `tools/tuning/` 后仍可复用。

## 输出目录

- `runs/lock_target_tuning/`：G1-G7 实验输出目录。
- `runs/offline_tuning_logs/`：调参 live log、stdout、stderr 和合并日志。
- `runs/lock_target_corner_cases/<RunId>/`：corner case C0-C8 实验输出目录。
- `runs/corner_case_tuning_logs/<RunId>/`：corner case live log、stdout 和 stderr。

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

如果需要运行新视频 corner case 调参：

```powershell
.\tools\tuning\run_corner_case_tuning.ps1 -SourceVideo "Q:\20260528-160426.mp4" -RunId corner_20260528_160426
```

如果需要覆盖已有同名输出：

```powershell
.\tools\tuning\run_corner_case_tuning.ps1 -SourceVideo "Q:\20260528-160426.mp4" -RunId corner_20260528_160426 -Force
```
