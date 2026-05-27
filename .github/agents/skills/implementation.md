# Skill: Implementation

## Use When

- 用户已经明确要实现某个代码或文档变更。

## Procedure

1. 读取相关文件，不凭记忆改代码。
2. 先声明影响范围。
3. 做最小改动，保持现有风格。
4. 保留现有 public CLI、输出字段和路径语义，除非用户明确要求变更。
5. 修改后进行可用验证：语法、静态错误、相关测试或最小运行。
6. 对锁定链路的实质修改，追加 `lock_target_change_log.md`。

## Project Guardrails

- `lock_target.py` 是离线主链路，不能引入实时队列积压逻辑。
- `lock_target_realtime.py` 是实时主链路，必须保持 latest-frame 策略。
- `perf_utils.py` 是共享性能记录模块，应保持可选依赖和空记录器逻辑。

## Output

- 改动文件。
- 改动目的。
- 验证结果。
- 未验证项。