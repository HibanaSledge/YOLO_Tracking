# Context Engineering

## Purpose

上下文工程不是额外写一个 skill 文件，而是 agent 的默认工作方式：把用户要求、仓库代码、运行产物、对话经验、执行日志和项目文档组织成可执行上下文。

## Mandatory Context Sources

按优先级读取：

1. 当前用户请求与当前编辑文件。
2. [instructions/personal_experience_rules.md](personal_experience_rules.md)。
3. [context/repo-map.md](../context/repo-map.md)、[context/architecture.md](../context/architecture.md)、[context/conventions.md](../context/conventions.md)。
4. 核心代码：`lock_target.py`、`lock_target_realtime.py`、`perf_utils.py`。
5. 项目文档：`lock_target_change_log.md`、`lock_target_project_report.md`、`docs/tuning/lock_target_parameter_table.md`。
6. 运行产物：`runs/lock_target/**`、`runs/lock_target_realtime/**` 下的 summary、frame_metrics、performance。
7. 执行日志和现场反馈，例如 `debug.log` 或用户描述的实时窗口现象。

## Context Classification

- Fact：文件中存在、运行产物中可读、用户明确给出的内容。
- Inference：基于事实的判断，例如瓶颈来源、质量退化原因。
- Gap：没有同源 A/B、没有逐帧指标、没有性能文件、没有端到端实测。

## Required Distinctions

- 离线批处理 vs 实时 latest-frame 低延迟链路。
- tracker id 连续 vs 业务目标连续。
- FACE_LOCK 真实脸框 vs HEAD_PROXY 代理头部框。
- 速度提升 vs 几何质量提升 vs 工程便利性提升。
- 显示流畅 vs 处理吞吐达标。

## Context Output Rule

当任务复杂或结论依赖多个来源时，输出中必须包含：使用了哪些上下文、哪些是事实、哪些是推断、哪些仍缺证据。