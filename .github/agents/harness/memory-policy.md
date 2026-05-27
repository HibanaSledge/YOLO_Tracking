# Memory Policy

## What To Persist

- 用户稳定偏好：结构化、结论先行、证据导向、最小改动。
- 仓库级事实：脚本职责、运行命令、输出字段、验证口径。
- 常见错误：只看 summary、混淆 FACE_LOCK/HEAD_PROXY、把 tracker id 当业务目标。

## Where To Persist

- 本仓库 agent 文档：`.github/agents/**`。
- 项目历史：`lock_target_change_log.md`。
- 长期用户偏好：必要时写入持久 memory。

## What Not To Persist

- 未验证猜测。
- 临时 run 的偶然现象，除非有产物支撑。
- 机器特定绝对路径，除非用户明确要求。

## Update Rule

如果新证据推翻旧经验，必须更新或删除旧规则，不保留冲突结论。