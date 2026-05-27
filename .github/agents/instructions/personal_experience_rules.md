# Personal Experience Rules

本文档由当前可访问的对话上下文、agent 文件夹、`lock_target_change_log.md`、`lock_target_project_report.md`、`lock_target_parameter_table.md`、代表性 `summary.json` / `performance.json` 和 `debug.log` 复盘整理而成。后续会话默认继承本文档。

## 1. 执行经验总结

### 1.1 已经证明会导致问题的做法

- 只看最终视频观感或 summary 级指标就判断优化成功。
  - 问题：summary 接近不代表逐帧输出等价；lightweight 版本虽然速度提升，但 FACE_LOCK 下降、HEAD_PROXY 上升、中心轨迹发生偏移。
  - 正确方式：必须同时读取 `summary.json`、`frame_metrics.json`、`performance.json`，必要时再做关键帧人工检查。

- 把 tracker id 当成业务目标 id。
  - 问题：底层 tracker id 切换、遮挡恢复、误关联都会让业务目标被换人。
  - 正确方式：始终维护业务层 `TargetState`，用 appearance、IoU、center continuity 综合判断同一业务目标。

- 把 HEAD_PROXY 当成真实 FACE_LOCK。
  - 问题：代理头部框能保持连续性，但几何上不等于真实脸框；云台控制会被错误中心带偏。
  - 正确方式：显式输出并解释 `FACE_LOCK`、`HEAD_PROXY`、`LOST`、`SEARCHING` 等 lock mode。

- 为了速度同时修改多个质量相关参数。
  - 问题：`imgsz`、`reid-interval`、`mtcnn-interval` 都会改变最终质量，同时改动会导致无法归因。
  - 正确方式：轻量化必须做单变量 A/B，先只压 embedding，再单独评估 MTCNN 降频。

- 用离线批处理结构直接跑摄像头。
  - 问题：逐帧排队、写视频和累积 JSON 会造成显示延迟越积越大。
  - 正确方式：实时链路采用 camera thread -> latest-frame buffer -> processing thread -> display loop，只消费最新帧并主动丢弃旧帧。

- 用不稳定统计口径解释实时性能。
  - 问题：旧 `process_fps` 曾与 `process_latency_ms`、`dropped_frames` 矛盾，误导调参。
  - 正确方式：实时吞吐必须与时延口径一致，优先看 `process_latency_ms`、`dropped_frames_before`、`total_dropped_frames` 和 `performance.json` 阶段耗时。

- 修改后不记录证据缺口。
  - 问题：无法区分“已验证收益”和“理论预期”。
  - 正确方式：每次重要修改都必须记录新增、移除、技术细节、目的、有效性证据、仍存在问题和证据缺口。

### 1.2 已经证明正确的执行方式

- 先读仓库真实文件和运行产物，再下结论。
- 区分四类收益：速度提升、锁定质量提升、几何精度提升、工程便利性提升。
- 对实时链路优先处理低延迟和不积压，再讨论完整帧保留。
- 对云台视觉前端优先保护身份连续性、脸/头几何正确性和控制中心稳定性。
- 将功能链路拆成可复盘产物：视频、summary、frame_metrics、performance。
- 当没有运行环境或没有实测结果时，明确标记为静态判断、理论预期或证据缺口。

### 1.3 关键教训

- “更快”不是“更好”；速度收益必须和质量退化一起报告。
- “看起来还能锁住”不是“同一业务目标且几何正确”；必须同时验证身份、几何和控制中心。
- “实时显示不卡”不等于“处理达到实时帧率”；latest-frame 架构解决积压，不解决单帧算法耗时。
- “参数只是性能参数”常常是误判；`imgsz`、`reid-interval`、`mtcnn-interval` 会直接改变输出质量。
- 工程报告要保留证据缺口，否则后续无法复盘。

## 2. 用户偏好与理念提炼

### 2.1 产品理念

- 偏好把算法原型推进到可复盘、可演示、可工程化的系统，而不是停留在 demo。
- 重视业务目标连续性，不接受“底层 tracker 说是同一个 id”就默认业务正确。
- 重视真实控制价值：视觉输出要服务云台控制，而不仅是视频画框。
- 倾向保留完整运行证据，便于后续复盘、对比和报告。

### 2.2 交互原则

- 默认希望 agent 主动检索文件、日志和产物，不要只给抽象建议。
- 输出应结构化、结论先行、少废话。
- 需要把不确定性、风险和证据缺口直接写出来。
- 给命令或方案时要可复现、可落地，优先从项目根目录可执行。
- 需要在“完整分析模式”和“轻量演示模式”之间保持清晰切换。

### 2.3 UI / 可视化偏好

- 偏好界面和输出能直观看到系统状态：`FACE_LOCK`、`HEAD_PROXY`、`TRACKING`、`HOLD`、`LOST`、`REACQUIRE`。
- 偏好实时覆盖层显示关键性能：camera fps、process fps、display fps、latency、dropped frames。
- 偏好把性能和质量指标外显，避免只凭主观体感判断。
- 对云台前端而言，稳定、可解释、低延迟优先于花哨展示。

### 2.4 工程风格偏好

- 最小改动、可验证、可回滚。
- 保持现有 CLI 和输出格式兼容，除非明确要求重构。
- 重要变更必须更新变更记录。
- 先建立基线，再做 A/B；不要一次混入多个无关变量。
- 用数据证明收益，用关键帧解释质量风险。

## 3. 可复用规则清单

### 3.1 默认行为规则

1. 回答前先确认任务属于离线、实时、共享工具、文档、评估还是 agent 配置。
2. 涉及仓库事实时，优先读取真实文件和运行产物。
3. 涉及性能时，必须查 `performance.json` 或明确说明没有性能证据。
4. 涉及质量时，必须查 `frame_metrics.json` 或明确说明缺少逐帧证据。
5. 涉及轻量化时，必须报告速度收益和质量代价。
6. 涉及实时性时，必须区分低延迟显示、处理 FPS、相机 FPS、丢帧和保存视频时长。
7. 涉及云台前端时，优先关注控制中心稳定性和几何正确性。
8. 任何修改都尽量最小化，并保留现有接口。
9. 无法实测时，不得写成已验证结论。
10. 输出应先给结论，再给证据、风险和下一步。

### 3.2 质量判断规则

- `tracker_switches` 少不一定代表业务质量好，还要看是否误绑和是否成功恢复。
- `reacquired_count` 少不一定代表好，可能是恢复失败或过度保守。
- `FACE_LOCK` 高不一定代表真实几何正确，要防假 FACE_LOCK。
- `HEAD_PROXY` 增加通常意味着真实脸框质量下降，需要解释对控制中心的影响。
- 轻量化等价替代必须通过逐帧中心偏移、lock mode 分布和关键帧检查共同确认。

### 3.3 参数与实验规则

- 调参顺序：主检测 -> 人脸检测 -> 重绑定 -> 控制平滑 -> 轻量化。
- 轻量化顺序：先只调 `reid-interval`，再单独调 `mtcnn-interval`，最后才组合。
- 不要把 `imgsz`、模型规模、ReID 模型、MTCNN 频率和重绑定阈值混在一次实验里同时解释。
- 每个实验名称必须表达场景和关键参数，如 `profile_mtcnn1_faceconf025`、`rt_512_reid10_mtcnn4`。

### 3.4 文档规则

- 重要代码变更后，更新 `lock_target_change_log.md`。
- 报告必须区分：已完成、已验证、尚未完成、证据缺口。
- 引用文件时优先引用仓库内实际存在的文档和产物。
- 不得虚构路径、函数、指标或实测数据。

## 4. 默认证据源优先级

1. 代码文件：`lock_target.py`、`lock_target_realtime.py`、`perf_utils.py`。
2. 项目复盘：`lock_target_change_log.md`、`lock_target_project_report.md`、`lock_target_parameter_table.md`。
3. 运行摘要：`runs/lock_target/**/_summary.json`、`runs/lock_target_realtime/**/_summary.json`。
4. 逐帧质量：`runs/**/_frame_metrics.json`。
5. 性能证据：`runs/**/_performance.json`。
6. 仅当结构化证据不足时，再使用视频观察、截图或用户现场反馈。