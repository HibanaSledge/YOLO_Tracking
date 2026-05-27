# Workflow

## Default Loop

1. Intake：复述任务目标，识别任务类型和影响范围。
2. Context：读取必要的代码、文档、运行产物和历史规则。
3. Route：按 [harness/routing.md](../harness/routing.md) 选择 skill 和验证路径。
4. Plan：给出最小步骤，复杂任务维护待办。
5. Execute：实现、分析、比较或写文档。
6. Validate：按 [harness/validation.md](../harness/validation.md) 验证。
7. Report：按 [instructions/output-format.md](output-format.md) 输出结论、证据、风险和下一步。

## Project-Specific Workflow

- 代码修改：先定位入口，再做最小改动，再验证语法/运行/指标，再更新变更记录。
- 实验对比：先固定 baseline 和 candidate，再比较 summary、frame_metrics、performance。
- 实时问题：先判断是否是积压延迟、算法吞吐、摄像头采集、显示开销或保存开销。
- 质量问题：先判断身份连续性，再判断 FACE_LOCK/HEAD_PROXY，再判断控制中心偏移。
- 文档复盘：必须把已验证事实、理论推断、证据缺口分开写。

## Stop Conditions

- 任务目标已完成，并已说明验证结果。
- 缺少必要文件、运行环境或用户输入，且无法通过现有上下文继续推进。
- 第三次同类修复仍无法消除同一问题，必须升级给用户决策。