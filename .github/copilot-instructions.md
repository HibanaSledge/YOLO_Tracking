# Copilot Instructions

本仓库默认使用 [.github/agents/agent.md](agents/agent.md) 作为项目 agent 配置入口，并保留 [.github/agents/YOLOTracking.agent.md](agents/YOLOTracking.agent.md) 作为 VS Code custom-agent 入口。

## Default Behavior

- 遵循 `.github/agents/instructions/` 中的 role、constraints、workflow、context、harness、evaluation、output-format。
- 按 `.github/agents/skills/skills.md` 选择任务 skill。
- 用 `.github/agents/context/` 构建仓库上下文。
- 用 `.github/agents/harness/` 做任务路由、工具使用、验证、恢复和升级。
- 用 `.github/agents/templates/` 保持计划、实现、评审、实验、bug 报告和总结格式一致。

## Repository Rules

- 重要结论必须有证据或明确证据缺口。
- 轻量化、性能、实时性、质量对比必须同时看 summary、frame_metrics、performance。
- 不把 tracker id 连续性等同于业务目标连续性。
- 不把 HEAD_PROXY 当成真实 FACE_LOCK。
- 修改锁定链路后更新 `lock_target_change_log.md`。