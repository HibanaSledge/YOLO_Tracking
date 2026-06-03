# Codex Experience Playbook

本文档由当前可访问的 Codex/Copilot 对话上下文、执行日志、项目 agent 配置、`lock_target_change_log.md`、`docs/tuning/`、`runs/*_logs/`、`docs/gimbal/serial_protocol.md` 和代表性运行产物复盘整理而成。后续 Codex 会话默认继承本文档，用于减少重复说明、避免重复踩坑，并保持用户偏好一致。

## 1. 复盘范围与证据边界

### 1.1 已检索证据源

- Agent 配置：`.github/agents/agent.md`、`.github/agents/YOLOTracking.agent.md`、`.github/agents/instructions/personal_experience_rules.md`。
- 调参文档：`docs/tuning/offline_tuning_analysis_report.md`、`docs/tuning/offline_tuning_results.md`、`docs/tuning/corner_case_tuning_results_corner_20260528_160426.md`、`docs/tuning/README.md`。
- 执行日志：`runs/offline_tuning_logs/offline_tuning_live.log`、`runs/corner_case_tuning_logs/corner_20260528_160426/corner_case_tuning_live.log`。
- 变更记录：`lock_target_change_log.md`。
- 串口协议：`docs/gimbal/serial_protocol.md`。
- 当前会话上下文：离线 G1-G7 调参、corner case C0-C8、串口协议、VOFA/com0com、算法接入串口发送、环境与命令交互。

### 1.2 证据边界

- 当前可复盘的是仓库内已有日志、文档和本轮对话摘要；如果存在未保存到仓库的历史 Codex 对话，只能通过当前上下文间接归纳。
- 对真实性能、闭环云台控制、人工关键帧结论，只有在已有 `summary.json`、`frame_metrics.json`、`performance.json`、视频复核或用户现场反馈支持时才能写成已验证结论。
- 对串口下位机 ACK / STATUS / ERROR，目前协议已定义，但真实下位机闭环和上位机接收侧解析仍是证据缺口。

## 2. 执行经验总结

### 2.1 会导致问题的做法

1. 只看最终视频或 `summary.json` 就判断优化成功。
   - 问题：summary 接近不代表逐帧行为等价，轻量化可能让 FACE_LOCK 下降、HEAD_PROXY 上升或控制中心轨迹漂移。
   - 正确方式：同时检查 `summary.json`、`frame_metrics.json`、`performance.json`，关键质量结论还要补人工关键帧复核。

2. 把 tracker id 连续性等同于业务目标连续性。
   - 问题：底层 tracker id 可以稳定但业务目标可能误绑，也可能 tracker id 变化但业务目标仍可通过 `TargetState` 恢复。
   - 正确方式：始终区分底层 tracker id 和业务目标身份，使用 appearance、IoU、center continuity、状态机和关键帧共同判断。

3. 把 HEAD_PROXY 当成真实 FACE_LOCK。
   - 问题：HEAD_PROXY 只是代理头部/人体几何，不等同于真实脸框；用于云台控制时可能把控制中心带偏。
   - 正确方式：报告和 UI 必须显式区分 FACE_LOCK、HEAD_PROXY、LOST、SEARCHING、TRACKING、HOLD、REACQUIRE。

4. 为了提速同时改多个质量相关参数。
   - 问题：`imgsz`、`reid-interval`、`mtcnn-interval`、模型规模、ReID 模型和阈值都会影响质量；混合修改会导致无法归因。
   - 正确方式：先同源 baseline，再单变量 A/B；组合实验只能作为后续折中验证，不能作为根因判断。

5. 直接把离线处理结构搬到实时摄像头。
   - 问题：离线逐帧排队、保存视频和累积 JSON 会造成实时显示积压。
   - 正确方式：实时链路采用 camera thread -> latest-frame buffer -> processing thread -> display loop，只处理最新帧并允许丢弃旧帧。

6. 用不稳定或不一致的实时指标解释性能。
   - 问题：单看 `process_fps` 或显示流畅度可能掩盖处理延迟、丢帧和队列积压。
   - 正确方式：实时结论同时看 `process_latency_ms`、`dropped_frames_before`、`total_dropped_frames`、camera fps、display fps 和 `performance.json` 阶段耗时。

7. 跨视频直接比较实验结果。
   - 问题：G1-G7 与 C0-C8 输入源不同，不能把旧视频 baseline 直接当新视频对照。
   - 正确方式：每个新视频必须先建立同源 baseline，例如 C0，再比较 C1-C8。

8. 长实验没有进度监控和落盘日志。
   - 问题：用户无法判断任务是否卡死，失败后也无法复盘到哪一轮。
   - 正确方式：使用 live log、progress md、stdout/stderr log、heartbeat 和 JSON 完整性检查；G1-G7 与 C0-C8 已证明这种方式有效。

9. 串口调试时让 VOFA 和 Python 抢同一个物理 COM 口。
   - 问题：Windows 串口通常独占，VOFA 占用 COM4 后 Python 会报 `PermissionError(13, 拒绝访问)`。
   - 正确方式：真实下位机二进制走 COM4；VOFA 可读 HEX 镜像走虚拟串口对，例如 Python 写 COM10、VOFA 读 COM11。

10. 让 VOFA 直接显示二进制协议帧。
    - 问题：VOFA 文本视图会显示乱码，无法人工核对 `AA 55 ...`。
    - 正确方式：主口保持二进制给下位机，镜像口使用 ASCII HEX 文本给 VOFA。

11. 忽略 Python 环境差异。
    - 问题：在 `.venv` 中运行可能缺少 `cv2` 等依赖，导致 `ModuleNotFoundError`。
    - 正确方式：先确认当前解释器；必要时使用已验证的完整 Python 路径，或给当前环境补齐依赖。

12. 忘记离线窗口需要显式 `--show`。
    - 问题：`lock_target.py` 默认不弹实时窗口，未加 `--show` 会被误认为可视化被串口参数关闭。
    - 正确方式：需要离线实时预览时显式加 `--show`，并提醒它会增加少量耗时。

13. 协议扩展时另起一套接收帧格式。
    - 问题：双向串口若使用不同帧外壳，会增加解析器、CRC、同步和调试复杂度。
    - 正确方式：沿用统一帧格式，通过 `msg_type` 区分 TRACK / STOP / ACK / STATUS / ERROR。

### 2.2 已证明正确的执行方式

- 先构建上下文：读 agent 配置、代码、文档、日志和已有运行产物，再给结论。
- 先建立同源 baseline，再做 A/B；实验名称、参数、输出目录、日志目录都要可追溯。
- 长任务必须有实时进度：live log、progress md、stdout/stderr、heartbeat、完成检测。
- 实验结论必须同时报告速度、质量、几何、控制稳定性和证据缺口。
- 轻量化先试 `reid-interval`，不要优先稀疏化 MTCNN；`mtcnn-interval` 是高风险旋钮。
- 质量线优先细扫人脸召回，尤其 `face-scale-factor`；不要继续优先上探 `imgsz 1152`。
- 云台线要独立看控制指标：`control_distance_to_center`、filtered center 步长、deadband、过冲和滞后。
- 串口链路先用独立脚本验证协议 HEX，再接入算法本体；接入后保留 dry-run、主口、镜像口三种模式。
- 文档变更和代码变更都要说明“已验证内容”和“证据缺口”。

### 2.3 本项目已经沉淀出的关键教训

- 更快不是更好；速度收益必须和质量代价绑定报告。
- 看起来还在跟踪不代表业务目标正确，也不代表脸/头几何正确。
- 实时显示不卡不等于算法达到实时帧率；latest-frame 架构解决积压，不解决单帧计算成本。
- 参数不是纯性能旋钮；很多参数会改变输出质量和控制轨迹。
- VOFA 只是观察工具，不能代替真实下位机闭环验证。
- 串口协议的 `sequence` 成本低但调试价值高，应保留；ACK 中再携带被确认的 `ack_sequence`。

## 3. 用户偏好与理念提炼

### 3.1 代码要求

- 偏好最小改动、局部修改、保持现有 CLI 和输出格式兼容。
- 新功能要优先复用共享模块，例如串口协议统一放在 `gimbal/serial_client.py`，离线和实时入口只接参数和调用。
- 修改锁定链路、串口链路、调参脚本或重要输出时，要同步更新相关文档或变更记录。
- 代码必须可运行、可验证，不接受只给理论方案；必要时先提供独立验证脚本，再接入主算法。
- 命令要能直接从仓库根目录执行；当环境有坑时，给完整 Python 路径或明确环境选择。

### 3.2 输入输出标准

- 输入需求如果不完整，先问关键选择题；一旦用户确认，agent 应主动实施。
- 输出应结论先行，再给证据、风险、命令或下一步。
- 涉及性能、质量、实时性、轻量化、锁定准确性时，必须绑定文件、指标或明确证据缺口。
- 报告和文档应结构化，区分已完成、已验证、待验证、证据缺口。
- 命令输出应给完整可复制版本；如果有“安全验证版”和“真实硬件版”，应分别列出。

### 3.3 交互原则

- 用户期望 agent 主动检索、执行、修改和验证，而不是只给建议。
- 遇到长任务，用户偏好实时记录和监控，不希望黑盒等待。
- 遇到报错，先定位根因，再给最短可行修复路径；不要让用户在多个猜测中试错。
- 用户接受必要的澄清问题，但偏好少问、问关键点、选项化。
- 用户重视可复盘工程流程，偏好把经验沉淀为文档和 agent 默认规则。

### 3.4 产品与工程理念

- 目标不是单纯 YOLO demo，而是可演示、可复盘、可接云台前端的系统。
- 业务目标身份连续性优先于 tracker id 表面连续性。
- FACE_LOCK / HEAD_PROXY 几何正确性优先于单纯框存在。
- 控制中心稳定性、低延迟显示和串口可解释性是云台前端可用性的关键。
- 所有“优化”都必须能被复盘：有运行产物、有日志、有指标、有风险说明。

## 4. 可复用规则清单

### 4.1 通用行为规则

1. 处理任务前先判断任务类型：离线、实时、串口、调参、报告、agent 配置、环境问题。
2. 不要基于记忆直接下结论；优先检索真实文件、日志和运行产物。
3. 做任何性能/质量结论时，必须引用或读取 `summary.json`、`frame_metrics.json`、`performance.json` 中至少一种；证据不足时明确写出。
4. 不要把 HEAD_PROXY 当 FACE_LOCK；不要把 tracker id 当业务目标。
5. 不要把跨视频结果直接比较；新视频先建同源 baseline。
6. 长实验必须可监控、可恢复、可复盘。
7. 给用户命令时，优先给完整命令；必要时同时给安全验证版和真实硬件版。
8. 遇到 Windows PowerShell 命令，注意反引号续行、串口独占和完整 Python 路径。
9. 修改代码后运行语法检查或最小验证；如果无法端到端验证，说明原因。
10. 对已有工作流进行扩展时，优先复用旧脚本和旧监控方式，不要重新造一套不兼容流程。

### 4.2 调参规则

1. 调参按同源 baseline -> 单变量实验 -> 组合实验 -> 报告归纳执行。
2. 质量优先线：优先 `face-scale-factor` 局部细扫，再考虑 `face-min-neighbors`，谨慎使用 `face-min-confidence`。
3. 速度优先线：优先继续测试 `reid-interval` 的安全上限，例如 4 / 6 / 8 / 10。
4. 不优先继续投入 `imgsz 1152`，除非新视频明确有人框漏检、小人/边缘人明显失败。
5. 不优先调整 reacquire 阈值，除非出现遮挡后找不回、多人交错误绑或 tracker/reacquire 异常。
6. 不优先稀疏化 MTCNN；`mtcnn-interval` 增大会降低 FACE_LOCK、增加 HEAD_PROXY 的风险已被 G6/G7/C8 支持。
7. 模型规模 `--model` 和 `--reid-model` 属于 0 号优先参数，但必须单独 A/B；当前默认仍建议 `--model yolo26n.pt --reid-model yolo26l.pt`。
8. 云台控制参数单独成线，不能只按 FACE_LOCK 排名；必须看控制中心距离、中心步长、deadband 和闭环响应。

### 4.3 串口与云台规则

1. 串口协议默认 115200、8N1、20 Hz；帧格式为 `AA 55 + version + msg_type + sequence + payload_len + payload + crc16`。
2. `sequence` 保留，用于丢包、重复、乱序和日志对齐；`uint16` 溢出回绕。
3. 上位机发送和下位机回传沿用统一帧外壳，通过 `msg_type` 区分方向和语义。
4. 主口给下位机发真实二进制；VOFA 镜像口发 ASCII HEX 文本。
5. COM4 等物理串口不能被 VOFA 和 Python 同时打开；观察链路用 com0com 虚拟串口对。
6. 推荐本机观察配置：Python 写 COM10，VOFA 读 COM11；真实下位机二进制可另走 COM4。
7. 先用 `tools/gimbal/random_offset_hex_stream.py` 做协议与端口验证，再接入 `lock_target.py` / `lock_target_realtime.py`。
8. 下位机闭环未验证前，不得声称云台实际跟踪已稳定，只能说明上位机协议帧已生成/发送。

### 4.4 环境与命令规则

1. 如果 `.venv` 缺少 `cv2`，可退出 `.venv` 并使用已验证 Python 3.10 完整路径运行；退出虚拟环境不会影响代码、模型、输出目录或串口。
2. 离线脚本默认不显示窗口；需要实时可视化必须加 `--show`。
3. `--show` 会增加一点耗时，性能实验默认不加；人工观察和演示时可加。
4. 需要 VOFA 验证时，优先运行不占用 COM4 的安全命令：只加 `--gimbal-mirror-port COM10 --gimbal-mirror-as-hex-text`。
5. 真实硬件联调时再加 `--gimbal-port COM4`，并确认 COM4 未被 VOFA 或其他串口工具占用。

### 4.5 文档与 agent 配置规则

1. 新经验应写入独立可引用文档，而不是只留在聊天里。
2. agent 默认加载文档应在 `.github/agents/agent.md` 和 VS Code custom-agent 入口中同时引用。
3. 文档要区分“规则”“证据”“证据缺口”，避免把推测固化为已验证事实。
4. 配置文件更新后要检查 Markdown/YAML frontmatter 基本有效性。

## 5. 未来 Codex 默认执行模板

### 5.1 分析类任务

1. 读取相关 agent/context/skill 文档。
2. 搜索代码、文档、日志、运行产物。
3. 建立证据表：哪些已验证、哪些未验证。
4. 输出结论：结论、证据、风险、证据缺口、下一步。

### 5.2 实现类任务

1. 先确认入口脚本和共享模块。
2. 优先改共享模块，再给离线/实时入口接参数。
3. 保持默认行为不变，新增功能默认关闭或显式参数启用。
4. 运行语法检查、最小 dry-run 或 CLI help 验证。
5. 给用户可直接运行的完整命令。

### 5.3 实验类任务

1. 先设计实验矩阵，固定同源 baseline。
2. 每轮只改变一个核心变量。
3. 自动写 progress/results/live log。
4. 完成后聚合 summary、frame_metrics、performance。
5. 报告同时看速度、质量、几何、控制稳定性和证据缺口。

### 5.4 串口/硬件类任务

1. 先明确端口占用关系和观察链路。
2. 先跑独立协议脚本，再接入算法。
3. 区分二进制主口和 HEX 文本镜像口。
4. 明确哪些是上位机 dry-run 证据，哪些是真实硬件闭环证据。
5. 如果没有下位机 ACK / STATUS / ERROR，不能宣称闭环已完成。