# Conventions

## Code Conventions

- 最小改动，保持现有风格。
- 不随意更改 public CLI 参数。
- 不随意改变 `summary.json`、`frame_metrics.json`、`performance.json` 字段语义。
- 性能记录逻辑保持可选依赖，不因缺少资源采样依赖阻断主流程。

## Documentation Conventions

- 重要锁定链路变更必须更新 `lock_target_change_log.md`。
- 记录格式：新增、减少或移除、技术细节、目的、有效性证据与指标、仍存在问题、证据缺口。
- 没有实测就写“证据缺口”，不要省略。

## Experiment Naming

- 名称包含场景和关键参数。
- 示例：`dark_img1152_conf020`、`profile_mtcnn1_faceconf025`、`rt_512_reid10_mtcnn4`。

## Command Conventions

- 优先使用项目根目录相对路径。
- 不默认写入机器专属绝对路径。
- 输出目录使用 `runs/lock_target` 或 `runs/lock_target_realtime`。