# Recovery

## When Patch Fails

1. 重新读取目标文件。
2. 缩小 patch 范围。
3. 保留用户最新修改。
4. 不用终端强行覆盖。

## When Validation Fails

1. 判断是否由本次修改引入。
2. 优先修复与任务相关的问题。
3. 同一文件最多尝试三轮。
4. 第三轮仍失败，给出错误、已尝试方案和下一步选择。

## When Evidence Is Missing

- 明确标记 `inconclusive`。
- 给出最小补证命令或检查清单。
- 不把理论预期写成已验证。

## When Runtime Is Too Expensive

- 先做静态检查或小样本验证。
- 建议用户运行完整视频实验。
- 明确完整验证需要哪些产物。