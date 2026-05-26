# lock_target.py 修改记录

本文档用于持续记录 lock_target.py 的每一次关键修改。后续每次继续修改该脚本时，都必须追加一节，并至少包含以下内容：

- 新增的内容和功能
- 减少、回退或移除的内容和功能
- 技术细节
- 这次修改的目的
- 有效性证据与指标
- 这次修改后仍然存在的问题

## 记录格式要求

从本次开始，后续每一条记录都必须按如下顺序书写：

### 新增

### 减少或移除

### 技术细节

### 目的

### 有效性证据与指标

至少包含以下三类内容中的两类：

- 运行输出指标：如 selected_at_frame、tracker_switches、reacquired_count、face_detected_frames、total_face_misses、avg_control_distance。
- 对比指标：与上一版或基线版本相比的增减。
- 证据来源：summary.json、frame_metrics.json、视频检查报告、关键帧观察。

### 修改后仍存在的问题

### 证据缺口

如果没有独立实验结果或缺少可比指标，必须明确写出缺口，而不是省略。

---

## 记录 01：初版单目标锁定脚本

### 新增

- 新增 lock_target.py，在 YOLO 检测和 BoT-SORT 跟踪之上实现业务层单目标锁定。
- 新增 TargetState 和 Candidate 数据结构。
- 新增基于外观、IoU 和中心距离的候选匹配逻辑。

### 减少或移除

- 无。

### 技术细节

- 在底层 tracker 输出的 bbox、track_id 之上增加了业务层状态机，而不是直接把 tracker id 当作业务目标 id。
- 候选目标的选择采用三类信号混合评分：外观相似度、IoU、一致性中心距离。
- 这一阶段还没有真实人脸检测，目标框仍更接近人体目标上的业务锁定框。

### 目的

- 不再完全依赖底层 tracker 的单次 ID 分配，尝试在 ID 切换时保持业务目标连续。

### 有效性证据与指标

- 证据来源：[runs/lock_target/demo1/20260521-120258_summary.json](runs/lock_target/demo1/20260521-120258_summary.json)
- selected_at_frame = 3
- tracker_switches = 6
- reacquired_count = 2
- total_updates = 674
- 指标解读：脚本可以完成目标初始化和持续更新，但 tracker_switches 较高，说明早期版本的身份连续性仍然偏弱。

### 修改后仍存在的问题

- 仍以人体框为主，无法满足严格的人脸锁定需求。
- 遮挡后仍可能换 ID 或锁错目标。

### 证据缺口

- 本阶段无逐帧 frame_metrics.json，可用于控制层的指标尚未建立。

## 记录 02：默认绑定 id=1

### 新增

- 新增默认 initial_track_id=1 的启动行为，减少手动选目标步骤。

### 减少或移除

- 降低了对运行时鼠标选择的依赖。

### 技术细节

- 将目标初始化逻辑从“点击选目标”扩展为“优先绑定指定 tracker id，再回退到人工或其他策略”。
- 目标初始化入口从完全交互式改为支持固定实验流程，更适合反复复跑和参数对比。

### 目的

- 让复现实验更快，便于反复调参和重复验证。

### 有效性证据与指标

- 证据来源：[runs/lock_target/demo1/20260521-120258_summary.json](runs/lock_target/demo1/20260521-120258_summary.json) 与 [runs/lock_target/realtime_fix_2/20260521-120258_summary.json](runs/lock_target/realtime_fix_2/20260521-120258_summary.json)
- selected_at_frame：3 -> 1
- 指标解读：默认绑定 id=1 后，目标初始化从第 3 帧提前到第 1 帧，说明初始化交互成本被消除。

### 修改后仍存在的问题

- 只解决交互便利性，不解决侧脸、遮挡和误切换问题。

### 证据缺口

- 该改动与后续多项优化叠加在同一批实验中，无法单独隔离纯粹的初始化收益。

## 记录 03：从人体框收缩到脸部代理框

### 新增

- 新增从人体框估算脸部区域的逻辑，用更小的框替代整个人体框显示目标。

### 减少或移除

- 减少了整个人体框作为业务目标框的使用。

### 技术细节

- 根据人体框的上半部分比例估算头部区域，将业务目标框从全身框收缩为近似头部框。
- 本质上属于规则驱动的 face proxy，不依赖真实脸检测模型。

### 目的

- 让锁定框更接近真正控制需要的头部区域，而不是整个人体区域。

### 有效性证据与指标

- 证据来源：代码阶段演进和后续视频问题反馈。
- 指标证据：当前仓库无该阶段的独立 summary.json 留存。
- 观察证据：后续用户多次反馈“框变小了，但会漂移”，说明这一步实现了框缩小，但未解决几何准确性。

### 修改后仍存在的问题

- 本质上仍是代理框，不是真实人脸检测结果。
- 头部姿态变化时容易漂移。

### 证据缺口

- 无独立留档的定量指标，无法单独量化代理框阶段的收益。

## 记录 04：接入真实人脸检测

### 新增

- 新增真实人脸检测器，改为优先使用 face_bbox 做显示和重识别。

### 减少或移除

- 弱化了纯人体框推测脸框的做法。

### 技术细节

- 目标锁定主体从人体业务框切换为真实 face_bbox。
- 人脸区域用于显示、匹配和外观特征抽取，不再只用于视觉展示。
- 这一步为后续 ReID 和更精细控制量输出奠定了基础。

### 目的

- 提高业务目标框的几何准确性，让橙框更接近真正人脸。

### 有效性证据与指标

- 证据来源：[runs/lock_target/demo1/20260521-120258_summary.json](runs/lock_target/demo1/20260521-120258_summary.json) 与 [runs/lock_target/realtime_fix_2/20260521-120258_summary.json](runs/lock_target/realtime_fix_2/20260521-120258_summary.json)
- tracker_switches：6 -> 1
- reacquired_count：2 -> 1
- selected_at_frame：3 -> 1
- 指标解读：虽然这些收益不完全由“真实人脸检测”单独贡献，但整体链路从 demo1 到 realtime_fix_2 的身份稳定性明显提升。

### 修改后仍存在的问题

- 检测器在侧脸、遮挡和快速转头场景下仍会漏检。

### 证据缺口

- 没有该阶段的单独 A/B 版本留档，无法完全分离“真实脸检测”对比“代理脸框”的净收益。

## 记录 05：修复视频提前结束与遮挡消失

### 新增

- 新增 LOST 和 face_hold 相关逻辑。
- 新增在短时漏检期间保留目标框的行为。

### 减少或移除

- 移除了目标长时间丢失后直接提前结束主循环的行为。

### 技术细节

- 主循环不再因目标丢失直接 break，而是区分“短时可保留”和“真正丢失”。
- 新增 face_hold_frames，允许目标在短时漏检期间仍保留业务状态和可视化。

### 目的

- 保证输出视频长度正常，并让遮挡期间的目标状态更连贯。

### 有效性证据与指标

- 证据来源：[runs/lock_target/realtime_fix_3/20260521-120258_summary.json](runs/lock_target/realtime_fix_3/20260521-120258_summary.json)
- total_updates = 604
- face_detected_frames = 246
- total_face_misses = 358
- max_face_miss_streak = 44
- 指标解读：这一阶段说明系统已经能跨越较长漏检区间继续运行并输出结果，否则不会出现大段持续统计。

### 修改后仍存在的问题

- 保留下来的框不一定是准确脸框，可能只是停留在旧位置。

### 证据缺口

- 该阶段缺少与“提前结束版本”的同视频同参数对照 summary。

## 记录 06：混合人脸检测器

### 新增

- 新增 OpenCV 正脸/侧脸检测与 MTCNN 的混合人脸检测策略。

### 减少或移除

- 不再单纯依赖单一人脸检测器。

### 技术细节

- 检测顺序调整为：优先 classical cascade，失败时再用 MTCNN 兜底。
- 混合策略同时兼顾初始化速度和复杂姿态下的补充召回率。

### 目的

- 尽量兼顾初始化速度和较复杂姿态下的补充检测能力。

### 有效性证据与指标

- 证据来源：[runs/lock_target/realtime_fix_2/20260521-120258_summary.json](runs/lock_target/realtime_fix_2/20260521-120258_summary.json)、[runs/lock_target/hybrid_fix_1_0522/20260521-120258_summary.json](runs/lock_target/hybrid_fix_1_0522/20260521-120258_summary.json)、[runs/lock_target/hybrid_fix_2/20260521-120258_summary.json](runs/lock_target/hybrid_fix_2/20260521-120258_summary.json)
- face_detected_frames：481 -> 555 -> 551
- total_face_misses：在 hybrid_fix_1/2 分别为 109 / 113
- max_face_miss_streak：13
- 指标解读：混合检测阶段的人脸命中帧数显著高于 realtime_fix_2，说明召回率确实提升。

### 修改后仍存在的问题

- 侧脸检测仍不稳定，尤其在画质一般或头部转动较快时。

### 证据缺口

- 没有对每种检测器单独做完整 A/B 统计，仍以阶段性 summary 为主。

## 记录 07：新增每帧控制量 JSON

### 新增

- 新增 frame_metrics.json 输出。
- 新增 frame_center、target_center、offset、distance_to_center 等字段。

### 减少或移除

- 无。

### 技术细节

- 将视觉结果从“只在视频里画框”扩展为“逐帧导出控制观测量”。
- 每一帧可输出目标中心、画面中心、偏移向量和距离，为云台控制接口预留数据源。

### 目的

- 为后续云台控制提供逐帧偏移量和目标中心信息。

### 有效性证据与指标

- 证据来源：[runs/lock_target/hybrid_fix_2/20260521-120258_summary.json](runs/lock_target/hybrid_fix_2/20260521-120258_summary.json) 和 [runs/lock_target/hybrid_fix_2/20260521-120258_frame_metrics.json](runs/lock_target/hybrid_fix_2/20260521-120258_frame_metrics.json)
- frame_metrics_json 字段已存在于 summary 中。
- total_frames = 731（由 frame_metrics 统计）
- 指标解读：说明逐帧 JSON 已完整生成，可支撑后续控制链路读取。

### 修改后仍存在的问题

- 输出的是观测量，不代表目标已经被控制到中心。

### 证据缺口

- 该阶段尚未和真实云台控制程序闭环联动，因此没有控制效果指标。

## 记录 08：控制层滤波与状态机

### 新增

- 新增 filtered_center、control_state。
- 新增 TRACKING、HOLD、LOST、REACQUIRE 相关状态输出。
- 新增 control_offset、control_distance_to_center、deadband_active 等字段。

### 减少或移除

- 减少了直接使用原始检测中心作为控制输入的做法。

### 技术细节

- 在业务层增加控制中心滤波，而不是直接使用 raw_target_center。
- 将状态拆分为 TRACKING / HOLD / LOST / REACQUIRE，避免“有框”与“可控”混为一谈。
- deadband 用于表示控制上可以暂时不动作的近中心区域。

### 目的

- 让视觉输出更适合云台控制，而不是把检测抖动直接传给控制系统。

### 有效性证据与指标

- 证据来源：[runs/lock_target/hybrid_fix_2/20260521-120258_frame_metrics.json](runs/lock_target/hybrid_fix_2/20260521-120258_frame_metrics.json)
- total_frames = 731
- state 分布：TRACKING 540，HOLD 126，LOST 54，REACQUIRE 11
- avg_raw_distance = 168.6
- avg_control_distance = 152.01
- 指标解读：控制层滤波确实降低了平均控制偏差，但仍然不能把目标维持在中心附近。

### 修改后仍存在的问题

- 控制层平滑会掩盖一部分真实快速偏移，可能影响响应及时性。

### 证据缺口

- 没有真实云台执行后的误差闭环数据，当前仍是纯视觉侧指标。

## 记录 09：严格跨 ID 重绑定尝试

### 新增

- 新增跨 ID 重绑定的连续确认帧数和更高阈值限制。

### 减少或移除

- 减少了目标完全丢失时立刻跳到新目标的概率。

### 技术细节

- 跨 ID 重绑定不再单帧决定，而是需要连续多帧指向同一个新 track id。
- 同时提高 appearance 和总分阈值，防止低质量候选进入切换流程。

### 目的

- 避免目标短时丢失后过快切到其他人的脸上。

### 有效性证据与指标

- 证据来源：[runs/lock_target/hybrid_fix_2/20260521-120258_frame_metrics.json](runs/lock_target/hybrid_fix_2/20260521-120258_frame_metrics.json) 与 hybrid_fix_3 同阶段 summary / frame_metrics 统计
- hybrid_fix_2：TRACKING 540，LOST 54，avg_control_distance 152.01
- hybrid_fix_3：TRACKING 538，LOST 56，avg_control_distance 154.25，avg_raw_distance 174.24
- 指标解读：严格切换虽然更保守，但整体效果略差，没有成为更优版本。

### 修改后仍存在的问题

- 恢复速度下降，整体效果比预期更保守，实测不优于上一版。

### 证据缺口

- 没有对“误切换次数”做单独字段统计，当前仍通过整体状态分布和视频观察间接判断。

## 记录 10：回退重绑定策略，保留人脸框跟随人体预测

### 新增

- 新增 face_relative_bbox 驱动的人脸预测框逻辑。
- 新增对预测框的头部区域裁剪，避免明显跑出头部范围。

### 减少或移除

- 回退了严格跨 ID 连续确认策略，恢复到更接近 hybrid_fix_2 的重绑定行为。

### 技术细节

- 用 face_relative_bbox 记录人脸框相对于人体框的位置。
- 当同一人体轨迹仍存在但真实脸检测失败时，使用当前人体框投影出新的代理人脸框。
- 预测框会被限制在头部区域内，避免飞到背景里。

### 目的

- 保持原有恢复速度，同时改善侧脸短时漏检时的框漂移。

### 有效性证据与指标

- 证据来源：[runs/lock_target/hybrid_fix_4/20260521-120258_summary.json](runs/lock_target/hybrid_fix_4/20260521-120258_summary.json) 与视频 inspection_report 观察
- 指标回到接近 hybrid_fix_2：TRACKING 540，LOST 54，avg_control_distance 154.38
- 视频证据：在 LOST 帧观察中，橙框未再明显挂到其他目标上；侧脸阶段橙框仍在头部附近而非完全漂到背景。
- 指标解读：该版本成功恢复了响应速度，并减少了明显误锁，但几何精度仍不足。

### 修改后仍存在的问题

- 预测框仍然更像头部代理框，不是真实侧脸框。

### 证据缺口

- 尚未把“误锁人数”做成显式可比指标，仍主要依赖关键帧观察。

## 记录 11：进一步收紧侧脸预测框几何约束

### 新增

- 新增 stabilize_projected_face_bbox，使预测框更贴近上一帧真实脸框的中心和尺寸。
- 进一步收紧预测框在头部区域内的活动边界。

### 减少或移除

- 减少了预测框上飘到头顶区域的自由度。

### 技术细节

- 对 projected face bbox 增加几何稳定化步骤：优先继承上一帧真实脸框的尺寸和垂直位置，再吸收当前人体投影结果。
- 预测框中心和宽高都会被裁剪到人体上半部分的合理范围内。

### 目的

- 改善侧脸和短时漏检阶段的预测框几何位置，避免看起来像错误的小框。

### 有效性证据与指标

- 证据来源：[runs/lock_target/hybrid_fix_4/20260521-120258_frame_metrics.json](runs/lock_target/hybrid_fix_4/20260521-120258_frame_metrics.json)、[runs/lock_target/hybrid_fix_5/20260521-120258_summary.json](runs/lock_target/hybrid_fix_5/20260521-120258_summary.json)、[runs/lock_target/hybrid_fix_5/inspection_report.html](runs/lock_target/hybrid_fix_5/inspection_report.html)
- avg_raw_distance：174.61 -> 171.9
- max_raw_distance：471.63 -> 455.04
- REACQUIRE 首帧关键观察：Frame 510 的 raw_dist 从 335.66 降到 254.88
- 指标解读：重绑定恢复段的首帧落点更合理，但侧脸阶段的 HEAD_PROXY 仍然没有达到真实脸框精度。

### 修改后仍存在的问题

- REACQUIRE 恢复段有一定改善，但侧脸阶段仍难以稳定输出真实脸框。

### 证据缺口

- 对 Frame 48 / 51 这种典型侧脸问题帧，还没有形成可自动统计的几何偏移指标，仍依赖人工视频检查。

## 记录 12：FACE_LOCK / HEAD_PROXY 双模式输出

### 新增

- 新增 lock_mode 概念，明确区分 FACE_LOCK、HEAD_PROXY、SEARCHING、LOST。
- 在视频标签中显示当前锁定模式。
- 在 frame_metrics.json 和 summary.json 中新增 lock_mode 输出字段。

### 减少或移除

- 减少了“预测框看起来像真实脸框”的语义混淆。

### 技术细节

- 当真实 face_bbox 可用且当前 face_miss_frames = 0 时，标记为 FACE_LOCK。
- 当真实脸检测暂时失败，但仍依赖 face_relative_bbox 和人体轨迹生成代理框时，标记为 HEAD_PROXY。
- summary 中新增 final_lock_mode，frame_metrics 中逐帧新增 lock_mode，视频标签也同步显示模式。

### 目的

- 明确告诉后续控制平台当前拿到的究竟是真实脸锁定，还是头部代理框锁定。

### 有效性证据与指标

- 证据来源：当前代码实现与运行校验；脚本已通过 --help 启动校验。
- 指标状态：尚未基于引入 lock_mode 的版本完成独立复跑，因此还没有 FACE_LOCK / HEAD_PROXY 帧数分布统计。
- 代码落点：[lock_target.py](lock_target.py#L59)、[lock_target.py](lock_target.py#L730)、[lock_target.py](lock_target.py#L788)、[lock_target.py](lock_target.py#L814)、[lock_target.py](lock_target.py#L969)

### 修改后仍存在的问题

- HEAD_PROXY 模式下的几何位置仍不等于真实脸框，只是更诚实地表达当前状态。
- 若要真正提升侧脸表现，仍需要更强的侧脸检测或头部关键点方案。

### 证据缺口

- 尚未对引入 lock_mode 后的实际视频结果做独立统计，下一轮复跑后应补充 FACE_LOCK / HEAD_PROXY / LOST 的分布数据。

## 记录 13：引入基于 landmarks 的侧脸 / 头部关键点定位

### 新增

- 新增 landmarks_to_face_bbox，将 MTCNN 返回的 5 点 landmarks 转换为更稳定的人脸框。
- 新增对同一目标优先启用 MTCNN landmarks 的逻辑，即使 classical face 已有候选，也会额外尝试关键点检测。
- 新增关键点驱动的人脸框作为 detect_face_in_person 的额外候选来源。

### 减少或移除

- 减少了对纯 classical frontal/profile 框直接作为最终脸框的依赖。

### 技术细节

- 对当前正在跟踪的目标，当存在 face_hint 时，MTCNN 不再只做“无 classical 候选时的兜底”，而是显式运行 detect(..., landmarks=True)。
- 将 landmarks 的点集转换为绝对坐标后，按关键点跨度生成一个更贴近头脸结构的框，而不是直接使用模型返回原框。
- 生成的人脸框会继续经过 clamp_face_bbox_to_body 约束，避免关键点框直接跑出头部区域。

### 目的

- 提高侧脸、半侧脸和快速转头场景下的真实脸定位能力，减少 HEAD_PROXY 仅靠人体轨迹预测时的几何误差。

### 有效性证据与指标

- 证据来源：代码实现与运行校验。
- 技术证据：当前环境中的 facenet-pytorch MTCNN 已确认支持 detect(img, landmarks=True)。
- 运行证据：本次修改完成后需基于新复跑结果补充 FACE_LOCK / HEAD_PROXY 分布变化，以及侧脸关键帧对比截图。

### 修改后仍存在的问题

- 若 MTCNN 在极端侧脸上仍不给出有效 landmarks，则系统仍会退化到 HEAD_PROXY。
- 该方案仍属于 2D 关键点驱动，不包含真正的 3D 头部姿态估计。

### 证据缺口

- 目前尚无本次修改后的独立 summary.json / frame_metrics.json 和视频检查报告，无法给出量化收益，需在下一轮复跑后补录。

## 记录 14：新增实时摄像头锁定脚本

### 新增

- 新增 lock_target_realtime.py，用于直接读取本机 RGB 摄像头并实时显示带目标锁定框的结果。
- 新增最新帧缓冲结构，采集线程持续读相机，处理线程只消费最新帧，显示线程只展示最新的处理结果。
- 新增实时性能覆盖层，实时显示 camera_fps、process_fps、display_fps、process_latency_ms、dropped_frames。
- 新增针对实时模式的轻量化策略参数：imgsz 默认降到 640、reid_interval、mtcnn_interval、display_width、save_session。

### 减少或移除

- 不再沿用离线脚本默认的整段 output_video 写盘和整份 frame_metrics.json 内存累积路径。
- 不再让显示循环等待历史帧顺序消费，旧帧会被主动丢弃，避免屏幕越跑越慢。

### 技术细节

- 现有 lock_target.py 的主循环本质是离线批处理结构：读取一帧、完整推理、写视频、追加 JSON、再显示。这种结构用于摄像头时会形成处理积压，最终看到的是越来越滞后的画面，而不是实时画面。
- 新脚本将链路拆为三个阶段：camera_worker 负责采集，processing_worker 负责跟踪和锁定，display_loop 负责 GUI 显示。三个阶段之间只共享“最新一帧”，不维护等待队列，因此处理速度一旦低于采集速度，系统会主动丢掉旧帧而不是把延迟越积越大。
- 为了保留现有锁定逻辑但降低实时负担，新脚本复用了 TargetState、pick_best_candidate、draw_state、draw_control_overlay 等核心逻辑，但把候选收集改成 realtime 版：
- 同 tracker 稳定跟踪阶段不再给所有候选每帧都跑 embedding。
- 只有在需要重绑定或按 reid_interval 刷新时才抽取 embedding。
- 对已锁定目标只按 mtcnn_interval 限制 MTCNN 的调用频率，避免 face_hint 存在时每帧都跑 CPU 版 MTCNN。
- 相机打开时显式设置了 CAP_PROP_BUFFERSIZE=1、MJPG、目标宽高和目标 FPS，减少 Windows 摄像头缓冲导致的历史帧积压。

### 目的

- 在不继续做算法方向优化的前提下，先把现有锁定系统改造成可直接用于本机 RGB 摄像头的实时前端，并把卡顿来源从“排队延迟”转为“当前这帧真实处理耗时”。

### 有效性证据与指标

- 证据来源：代码结构变更，实时脚本参数设计，以及屏幕性能覆盖层的可视化输出。
- 运行输出指标：新增了 camera_fps、process_fps、display_fps、process_latency_ms、dropped_frames 五类实时指标，可直接在窗口下方观察。
- 对比证据：旧版 lock_target.py 会在主循环内持续 writer.write 和 frame_metrics.append，实时版已默认移除这两条重路径，并通过 latest-frame 丢帧模式避免相机画面因历史帧堆积而越来越卡。

### 修改后仍存在的问题

- 如果单帧算法耗时本身仍显著高于 33 ms，那么屏幕会保持“实时但处理帧率较低”，不会再累积延迟，但也不可能凭空达到 30 FPS。
- facenet_pytorch 的 MTCNN 仍在 CPU 上运行；如果摄像头分辨率过高、光照复杂或目标很多，process_fps 仍可能成为瓶颈。
- 当前实时脚本默认仍沿用 initial_track_id=1 的初始化方式，更适合单目标演示；如果要支持运行中鼠标点选，需要再补一个交互式初始化入口。

### 证据缺口

- 这次改动尚未在当前机器上完成真实摄像头实测，所以还没有独立的 process_fps、dropped_frames 和窗口流畅度截图留档。
- 由于当前工作区 Python 环境缺少 cv2、ultralytics、facenet_pytorch 的完整运行依赖，现阶段只能完成静态实现和语法级校验，无法在本轮对真实摄像头做端到端复跑。

## 记录 15：修正实时性能统计并默认保存完整输出

### 新增

- 新增实时会话默认保存行为：每次结束后自动输出完整的 locked.mp4、frame_metrics.json、summary.json。
- 新增基于时间戳的独立运行目录，避免多次实时测试互相覆盖。
- 新增 total_dropped_frames、max_dropped_frames、processed_frames、session_duration_sec、output_fps 等会话级摘要字段。
- 新增 frame_metrics 中的 source_frame_id 和 dropped_frames_before 字段，用于还原实时丢帧情况。

### 减少或移除

- 移除了 process_fps 依赖短时间戳窗口直接推算的统计方式，避免出现与 process_latency_ms 矛盾的异常高值。
- 不再需要显式传入 save-session 才能保存输出，实时模式默认会保存结果；只有在明确传入 no-save-session 时才关闭。

### 技术细节

- 用户现场反馈表明，镜头移动时 process_fps 会异常跳到 1000+，同时 process_latency_ms 和 dropped_frames 又显示系统实际上变慢了，这说明旧统计口径不稳定，不能作为真实吞吐量依据。
- 新实现将 process_fps 改为基于单帧处理时延的平滑倒数计算，即先对 process_latency_ms 做 EMA 平滑，再使用 $fps = 1000 / latency\_ema\_ms$ 生成实时 process_fps。这一口径会和时延保持一致，不会在高时延阶段反向飙升。
- 实时会话输出改为在 processing_worker 结束时一次性写出 summary 和 frame_metrics，而视频仍在处理过程中持续写入，避免运行中频繁重写 summary.json。
- 为了兼容此前离线脚本的产物格式，summary 字段延续了 output_video、frame_metrics_json、selected_at_frame、tracker_switches、reacquired_count、final_lock_mode 等主字段，并在此基础上增加了实时链路特有的丢帧和吞吐量指标。

### 目的

- 让实时窗口中的性能数字和实际观感一致，避免误导调参。
- 满足“每次实时结束后都要像离线脚本一样完整保存输出”的使用要求，便于后续复盘和对比。

### 有效性证据与指标

- 证据来源：用户现场反馈与代码修正。
- 现场证据：用户报告镜头静止时 dropped_frames = 0，而镜头移动时 dropped_frames 最高到 20；同时旧版 process_fps 曾异常升到 1000+。这一组合与 331.5 ms 的 process_latency_ms 明显矛盾，证明旧 process_fps 统计口径不可靠。
- 结构性证据：新版本已将输出路径固定为每次独立 run_dir，并在结束时写出完整的 output_video、frame_metrics_json、summary 三件套，与此前离线脚本格式对齐。

### 修改后仍存在的问题

- 如果镜头快速移动导致真实单帧处理延迟显著上升，那么 process_fps 现在会如实下降，说明瓶颈仍在算法本身，而不是仅仅显示链路。
- 实时输出视频目前按相机输出 fps 写入；当处理中主动丢帧较多时，保存下来的视频时长可能短于真实会话时长，但内容仍和实时窗口看到的处理结果一致。

### 证据缺口

- 这次修正后的版本还没有拿到新的 summary.json 和 frame_metrics.json 实测样本，因此 total_dropped_frames、max_dropped_frames、修正后的 process_fps 曲线仍需要下一轮复跑后补录。

## 后续维护要求

- 每次修改 lock_target.py 后，都必须在本文档追加新的记录小节。
- 每次新增记录时，保持相同结构：新增、减少或移除、技术细节、目的、有效性证据与指标、修改后仍存在的问题、证据缺口。
- 如果某次修改没有独立实验结果，必须明确写出证据缺口，并在后续复跑后补录指标。