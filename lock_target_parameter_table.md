# Lock Target 参数总表与调参路线

## 1. 说明

本文只整理“会影响最终输出质量”的参数，不包含纯输出路径、命名、是否保存文件等不会改变目标选择、脸框几何或控制输出的参数。

表格字段说明：

| 列名 | 含义 |
| --- | --- |
| 参数 | 命令行参数、tracker 配置项或代码内隐含常量 |
| 默认值 | 当前代码或配置中的默认值 |
| 作用阶段 | 该参数主要影响哪一段链路 |
| 影响方向 | 调大或调小后通常会把结果推向什么方向 |
| 风险等级 | 对最终输出质量的影响风险，分为高、中、低 |

补充说明：

- 对于模型规模选择，例如 YOLO26n、YOLO26l、YOLO26x，这里也视为“参数”。
- 对于场景化调参，例如暗光、强抖动、高速运动、强光，本文在后面单独给出场景表，而不是把所有场景建议硬塞进每一行基础参数表里。

## 2. 参数总表

### 2.1 主检测与底层跟踪参数

| 参数 | 默认值 | 作用阶段 | 影响方向 | 风险等级 |
| --- | --- | --- | --- | --- |
| model | yolo26n.pt | 主检测、人框质量、底层跟踪输入 | 更强模型通常提升人框质量和召回，但也可能改变框几何与 track 行为 | 高 |
| tracker | cfg/trackers/botsort.yaml | 底层 track 生成与 ID 连续性 | 换 tracker 配置会直接改变 track id 切换、遮挡恢复和误跟踪 | 高 |
| classes | [0] | 候选筛选 | 改动类别集合会直接改变候选目标集合 | 高 |
| conf | 0.25 | 主检测候选筛选 | 调高更干净但更易漏检，调低召回更高但更易引入误检 | 高 |
| iou | 0.5 | 主检测 NMS | 调高更宽松，调低更严格，会影响人框保留与重叠框处理 | 中 |
| imgsz | 离线 960，实时 640 | 主检测推理分辨率 | 调大通常提升检测细节与小目标质量，调小提升速度但易损失几何细节 | 高 |
| initial-track-id | 1 | 初始化选目标 | 会改变初始绑定对象，从而影响整段输出 | 高 |
| fallback-to-first-face | False | 初始化选目标 | 打开后会在初始 id 不可用时自动回退到第一张脸，改变起始目标选择 | 中 |
| max-lost | 90 | 目标丢失保持 | 调大更保守、更晚宣布丢失；调小更快放弃当前目标 | 高 |

### 2.1.1 YOLO26n / YOLO26l / YOLO26x 模型规模选择表

| 模型参数 | 当前默认 | 主要用途 | 质量倾向 | 速度倾向 | 适用场景 | 风险等级 |
| --- | --- | --- | --- | --- | --- | --- |
| model = YOLO26n | 当前默认主检测模型 | 主检测 | 质量基线最低，但速度最好 | 最快 | 实时优先、算力受限、先跑通链路 | 高 |
| model = YOLO26l | 非当前默认 | 主检测 | 通常比 n 更稳，尤其对小人框、边缘人框、复杂背景更有利 | 明显更慢 | 离线质量优先、需要更稳的人框几何 | 高 |
| model = YOLO26x | 当前仓库未放权重，但应纳入路线 | 主检测 | 理论上三者中最高，尤其在复杂场景下召回和框稳定性更强 | 最慢 | 离线高质量基线、后续硬件升级后验证 | 高 |
| reid-model = YOLO26n | 非当前默认 | 外观 embedding | 更轻，但 embedding 判别力通常较弱 | 最快 | 实时极限轻量实验 | 高 |
| reid-model = YOLO26l | 当前默认 ReID 模型 | 外观 embedding | 当前身份连续性主基线 | 中等 | 当前离线与实时业务基线 | 高 |
| reid-model = YOLO26x | 当前仓库未放权重，但应纳入路线 | 外观 embedding | 理论上外观区分度更强，可能更利于跨 ID 重绑定 | 最慢 | 遮挡重、多人干扰重、离线质量优先 | 高 |

说明：

- 主检测模型变大，通常首先改善的是人框召回和框稳定性，其次才是后续脸检测基础。
- ReID 模型变大，通常首先改善的是跨 ID 重绑定质量，而不是脸框几何本身。
- 如果后续引入 YOLO26x，必须把质量收益和新增耗时一起看，不能只因为它“更大”就默认它一定更优。

### 2.2 业务重绑定与身份连续性参数

| 参数 | 默认值 | 作用阶段 | 影响方向 | 风险等级 |
| --- | --- | --- | --- | --- |
| reid-model | yolo26l.pt | 外观特征提取 | 更强 embedding 模型通常提升跨 ID 连续性，但会改变匹配分布 | 高 |
| appearance-weight | 0.6 | 重绑定综合评分 | 调高更依赖外观，减少几何主导；调低则更依赖位置连续性 | 高 |
| iou-weight | 0.25 | 重绑定综合评分 | 调高更依赖几何重叠，调低更放宽空间一致性 | 高 |
| center-weight | 0.15 | 重绑定综合评分 | 调高更依赖中心运动连续性，调低对突然运动更宽容 | 中 |
| min-appearance | 0.35 | 重绑定门限 | 调高更保守，误绑更少但更易错失重绑定 | 高 |
| min-iou | 0.05 | 重绑定门限 | 调高更严格，调低更容易接受空间偏移较大的候选 | 高 |
| min-center-score | 0.2 | 重绑定门限 | 调高更强调中心一致性，调低更允许运动跳变 | 中 |
| reacquire-thresh | 0.45 | 重绑定总分门限 | 调高更保守，调低更激进 | 高 |
| reid-interval | 离线 1，实时 8 | 同 tracker embedding 刷新频率 | 调大提速但会降低外观更新密度，影响重绑定和同目标确认 | 高 |
| embedding_bank 长度 | 30 | prototype 更新 | 调大更稳定但更迟钝，调小更敏感但更容易漂 | 中 |
| choose_embedding_candidates limit | 3，仅实时 | 实时重绑定候选筛选 | 调大更稳但更慢，调小更快但可能漏掉正确候选 | 中 |

### 2.3 人脸检测与脸框筛选参数

| 参数 | 默认值 | 作用阶段 | 影响方向 | 风险等级 |
| --- | --- | --- | --- | --- |
| face-scale-factor | 1.05 | OpenCV frontal/profile 检测 | 调小通常召回更高但更慢，调大更快但更易漏检 | 高 |
| face-min-neighbors | 3 | OpenCV frontal/profile 检测 | 调高更严格、误检少；调低召回更高但更不稳定 | 高 |
| face-min-confidence | 0.30 | MTCNN 候选过滤 | 调高更保守，调低更激进 | 高 |
| mtcnn-interval | 离线 1，实时 3 | MTCNN 刷新频率 | 调大提速但会降低真实脸框刷新密度，直接影响中心轨迹 | 高 |
| face-hold | 6 | 短时脸丢失保持 | 调大更容易维持 HEAD_PROXY，调小更快进入 SEARCHING 或 LOST | 高 |
| use_mtcnn_landmarks 条件 | face_hint 存在或无 classical face | MTCNN/landmarks 参与逻辑 | 更积极启用 landmarks 会提升复杂姿态定位，但增加开销 | 中 |
| face_hint 选择权重 | 0.7 IoU + 0.3 center | 同目标脸候选排序 | 调高 IoU 会更偏向旧框附近，调高 center 会更偏向整体中心连续性 | 中 |

### 2.4 代理脸框与几何稳定化参数

| 参数 | 默认值 | 作用阶段 | 影响方向 | 风险等级 |
| --- | --- | --- | --- | --- |
| smooth_bbox alpha | 0.75 | 实际 face_bbox 平滑 | 调高更稳但更迟钝，调低更跟手但更抖 | 高 |
| project_face_bbox 平滑 alpha | 0.4 | HEAD_PROXY 投影 | 调高更贴历史，调低更贴当前人体框投影 | 高 |
| stabilize center 混合 | 0.7 previous + 0.3 projected | HEAD_PROXY 几何稳定化 | 更偏历史会更稳，但可能拖尾 | 高 |
| stabilize size 混合 | 0.8 previous + 0.2 projected | HEAD_PROXY 宽高稳定化 | 更偏历史尺寸会更稳，但可能不适应姿态变化 | 中 |
| landmarks box_w 系数 | span_x * 2.8 | landmarks 转脸框 | 调大会放大脸框宽度，调小会收窄 | 中 |
| landmarks box_h 系数 | span_y * 3.4 | landmarks 转脸框 | 调大会放大脸框高度，调小会收窄 | 中 |
| landmarks center_y 偏移 | + span_y * 0.28 | landmarks 转脸框 | 调大会把框往下压，调小会把框往上提 | 中 |
| clamp head_bottom | body_h * 0.68 | 脸框垂直约束 | 调大会允许框下沉，调小会更严格限制在头部上半区 | 高 |
| clamp margin_x | body_w * 0.12 | 脸框水平约束 | 调大会更宽容，调小更严格 | 中 |
| projected width 范围 | [body_w * 0.16, body_w * 0.42] | HEAD_PROXY 宽度范围 | 放宽会让代理框更大更不稳定，收紧会更保守 | 中 |
| projected height 范围 | [body_h * 0.14, body_h * 0.38] | HEAD_PROXY 高度范围 | 同上 | 中 |
| projected center x 范围 | body 左右各留 18% | HEAD_PROXY 中心约束 | 放宽会更灵活但更容易漂 | 中 |
| projected center y 范围 | body_h 12% 到 48% | HEAD_PROXY 中心约束 | 放宽会允许上飘或下沉 | 高 |

### 2.5 控制中心与控制输出参数

| 参数 | 默认值 | 作用阶段 | 影响方向 | 风险等级 |
| --- | --- | --- | --- | --- |
| control-alpha | 0.72 | filtered_target_center 平滑 | 调高更稳但更滞后，调低更灵敏但更抖 | 高 |
| control-max-step | 40.0 | filtered_target_center 限幅 | 调大响应更快，调小更稳但可能跟不上目标 | 高 |
| control-deadband | 12.0 | 控制激活判定 | 调大更不容易触发控制，调小更容易激活 | 中 |
| reacquire_frames_left | 12 | REACQUIRE 持续时长 | 调大让 REACQUIRE 状态持续更久，调小更快回归 TRACKING | 低 |

### 2.6 实时输入链路参数

| 参数 | 默认值 | 作用阶段 | 影响方向 | 风险等级 |
| --- | --- | --- | --- | --- |
| camera-width | 1280 | 实时输入质量 | 调大通常有利于检测与脸框几何，但增加负载 | 高 |
| camera-height | 720 | 实时输入质量 | 同上 | 高 |
| camera-fps | 30 | 实时时间分辨率 | 调高让运动更连续，但如果算力不足会放大丢帧问题 | 中 |
| camera-backend | dshow | 摄像头采集链路 | 会影响取流稳定性、延迟和兼容性 | 低 |

### 2.7 BoT-SORT 配置参数

来源文件：[cfg/trackers/botsort.yaml](cfg/trackers/botsort.yaml)

| 参数 | 默认值 | 作用阶段 | 影响方向 | 风险等级 |
| --- | --- | --- | --- | --- |
| track_high_thresh | 0.25 | 第一阶段匹配 | 调高更干净但更易丢失弱检测，调低召回更高但易漂 | 高 |
| track_low_thresh | 0.1 | 第二阶段低分匹配 | 调高更保守，调低更容易恢复弱目标 | 中 |
| new_track_thresh | 0.25 | 新建轨迹 | 调高减少伪轨迹，调低更容易新建错误轨迹 | 高 |
| track_buffer | 60 | 丢失轨迹保留时长 | 调高更能跨遮挡，但也更可能引入错误延续 | 高 |
| match_thresh | 0.8 | 关联门限 | 调高更严格，调低更容易错配 | 高 |
| fuse_score | True | 分数与关联融合 | 开启通常更稳，关闭可能让弱检测关联方式变化 | 中 |
| gmc_method | sparseOptFlow | 相机运动补偿 | 在移动镜头场景下很关键，关闭或切换方法会改变跟踪稳定性 | 高 |
| with_reid | False | BoT-SORT 内部 ReID | 当前关闭，现阶段对最终质量的直接影响较低 | 低 |
| proximity_thresh | 0.4 | BoT-SORT 内部 ReID | 当前 with_reid=False，现阶段基本不生效 | 低 |
| appearance_thresh | 0.7 | BoT-SORT 内部 ReID | 当前 with_reid=False，现阶段基本不生效 | 低 |
| model | yolo26n.pt | BoT-SORT 内部 ReID 模型 | 当前 with_reid=False，现阶段基本不生效 | 低 |

### 2.8 只影响速度、不列入质量调参主表的参数

下面这些参数通常不改变目标选择、脸框几何或控制输出，只影响保存行为或显示：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| project | runs/lock_target 或 runs/lock_target_realtime | 输出目录 |
| name | exp 或 camera | 运行名 |
| show | False | 是否显示窗口 |
| save-all-boxes | False | 是否绘制全部 tracker 框 |
| demo-only | False | 只保留最终 demo 视频 |
| no-save-video | False | 不保存视频 |
| no-save-summary | False | 不保存 summary |
| no-save-frame-metrics | False | 不保存 frame_metrics |
| no-save-performance | False | 不保存 performance |
| no-save-session | False | 实时模式下关闭整次保存 |
| display-width | 960 | 主要影响显示尺寸，不改变算法主输出 |

### 2.9 场景化参数调整方向表

下面这张表只列最关键、最值得因场景变化而调整的参数。

| 参数 | 暗光 | 强抖动 | 高速运动 | 强光 | 影响说明 |
| --- | --- | --- | --- | --- | --- |
| model | 倾向从 YOLO26n 提升到 YOLO26l 或 YOLO26x | 倾向提升到 YOLO26l 及以上 | 倾向提升到 YOLO26l 及以上 | 倾向维持当前或小幅提升 | 弱纹理、复杂噪声和运动模糊场景下，更大模型通常更稳 |
| reid-model | 倾向提升到 YOLO26l 或 YOLO26x | 倾向提升到 YOLO26l 或 YOLO26x | 倾向提升到 YOLO26l 或 YOLO26x | 一般可维持当前 | 光照差和运动模糊会破坏 embedding 质量，更强模型更能保住身份连续性 |
| imgsz | 倾向调大 | 倾向调大 | 倾向调大或至少不降 | 一般可维持当前 | 暗光和运动模糊下，小脸与边缘脸最先受损，增大 imgsz 常能改善 |
| conf | 倾向略降 | 倾向略降 | 倾向略降 | 倾向略升 | 暗光和高速运动时漏检增多，适当降低 conf 能保住候选；强光误检增多时可略升 |
| iou | 一般维持 | 倾向略升 | 倾向略升 | 一般维持 | 强抖动和高速运动下，适当提高 NMS IoU 往往更有利于保住候选框 |
| track_high_thresh | 倾向略降 | 倾向略降 | 倾向略降 | 一般维持或略升 | 质量差场景下弱检测更多，过高会更容易断轨 |
| track_buffer | 倾向略升 | 倾向升高 | 倾向升高 | 一般维持 | 遮挡和瞬时丢帧增加时，更长缓冲更利于跨短时中断 |
| match_thresh | 一般维持或略降 | 倾向略降 | 倾向略降 | 一般维持 | 强抖动和高速运动会破坏纯几何一致性，过高更容易错失匹配 |
| gmc_method | 倾向保留 | 必须重点关注，必要时试 none、orb、ecc | 倾向保留或换更稳方案 | 一般维持 | 强抖动场景里，全局运动补偿是否适配会直接影响 track 稳定性 |
| face-scale-factor | 倾向调小 | 倾向调小 | 倾向调小 | 一般维持或略升 | 调小通常增加人脸召回，适合弱脸纹理和模糊场景 |
| face-min-neighbors | 倾向调低 | 倾向调低 | 倾向调低 | 倾向调高 | 暗光和模糊下更需要召回，强光高对比场景更需要压误检 |
| face-min-confidence | 倾向调低 | 倾向调低 | 倾向调低 | 倾向略升 | MTCNN 在困难场景置信度会整体下降，阈值过高会直接掉脸 |
| mtcnn-interval | 倾向调小或保持 1 | 倾向调小 | 倾向调小 | 一般可维持当前 | 困难场景里真实脸框刷新频率更重要，间隔过大更容易退到 HEAD_PROXY |
| face-hold | 倾向略升 | 倾向升高 | 倾向升高 | 一般维持 | 在更容易短时丢脸的场景下，适当延长保持时间可提升连续性 |
| min-appearance | 倾向略降 | 倾向略降 | 倾向略降 | 一般维持或略升 | 困难场景 embedding 本身会变差，阈值过高会导致恢复失败 |
| reacquire-thresh | 倾向略降 | 倾向略降 | 倾向略降 | 一般维持 | 复杂场景下总分分布会整体下降，阈值过高会过度保守 |
| appearance-weight | 倾向略降 | 倾向略降 | 倾向略降 | 一般维持 | 光照和模糊会削弱外观可靠性，可适当让位给几何与中心连续性 |
| iou-weight | 一般维持 | 倾向略降 | 倾向略降 | 一般维持 | 强抖动和高速运动会让 IoU 一致性下降，过高更容易错过正确候选 |
| center-weight | 倾向略升 | 倾向略升 | 倾向略升 | 一般维持 | 在外观和 IoU 都不稳定时，中心连续性可以作为更稳的补充信号 |
| control-alpha | 一般维持 | 倾向升高 | 倾向略降或维持 | 一般维持 | 强抖动时需要更稳，高速运动时若过高会拖尾 |
| control-max-step | 一般维持 | 倾向略降 | 倾向升高 | 一般维持 | 强抖动时限制步长有助于抑制乱跳，高速运动时需要更快跟随 |

### 2.10 场景化模型选择表

| 场景 | 主检测模型建议 | ReID 模型建议 | 参数联动重点 | 主要风险 |
| --- | --- | --- | --- | --- |
| 暗光 | YOLO26l 起步，质量优先时试 YOLO26x | YOLO26l 起步，复杂场景试 YOLO26x | imgsz 调大、conf 略降、face-min-confidence 略降 | 速度明显下降 |
| 强抖动 | YOLO26l 更稳，必要时试 YOLO26x | YOLO26l 或 YOLO26x | gmc_method、track_buffer、match_thresh、control-alpha | 若补偿方法不合适，反而会更不稳 |
| 高速运动 | YOLO26l 更稳，必要时试 YOLO26x | YOLO26l 或 YOLO26x | imgsz 不要降太多、track_high_thresh 略降、control-max-step 升高 | 大模型有助于质量，但 CPU-only 下更难实时 |
| 强光 | YOLO26n 或 YOLO26l 通常都可用 | YOLO26l 通常足够 | conf 略升、face-min-neighbors 略升、face-min-confidence 略升 | 过度提阈值会让边缘脸和小脸掉得太多 |

说明：

- 场景越困难，越应该先考虑把主检测模型从 YOLO26n 提升到 YOLO26l，而不是一上来就只压 interval。
- YOLO26x 更适合做离线高质量上限验证，不适合直接当 CPU-only 实时基线。
- 如果后续换到 GPU 平台，YOLO26x 才更有可能进入正式候选链路。

## 3. 最值得优先调的 10 个参数

### 3.1 前 10 优先级列表

| 排名 | 参数 | 默认值 | 优先原因 | 主要风险 |
| --- | --- | --- | --- | --- |
| 1 | imgsz | 离线 960，实时 640 | 同时影响主检测质量、几何细节和速度，是最强的一阶参数 | 调低后小脸和边缘脸框最容易退化 |
| 2 | conf | 0.25 | 直接决定人框保留质量，影响后续所有链路 | 过高漏人，过低误检 |
| 3 | face-min-confidence | 0.30 | 直接决定 MTCNN 候选是否进入最终脸框集合 | 过高掉脸，过低引入假脸 |
| 4 | face-scale-factor | 1.05 | OpenCV 脸检测最核心的召回/稳定平衡参数 | 调得过小会慢且误检增加 |
| 5 | face-min-neighbors | 3 | 决定 classical face 的严格度 | 调得过低会抖，过高会漏 |
| 6 | min-appearance | 0.35 | 直接决定跨 ID 重绑定是否足够保守 | 过低误绑，过高错失恢复 |
| 7 | reacquire-thresh | 0.45 | 是重绑定综合总闸门 | 过低激进，过高保守 |
| 8 | appearance-weight | 0.6 | 决定重绑定更偏脸特征还是更偏几何 | 与 min-appearance 强耦合 |
| 9 | mtcnn-interval | 离线 1，实时 3 | 当前轻量化质量退化的直接来源之一 | 调大后中心轨迹更容易偏 |
| 10 | control-alpha | 0.72 | 直接影响 filtered_target_center 的控制观感 | 调大拖尾，调小抖动 |

说明：

- 如果目标是“提升身份连续性”，优先调 6、7、8。
- 如果目标是“提升脸框几何质量”，优先调 1、3、4、5、9。
- 如果目标是“提升云台控制观感”，优先调 10，并搭配 control-max-step。

补充：

- 如果你允许切换模型规模，那么 model 和 reid-model 应当被视为“0 号优先参数”，因为它们会先决定整个参数空间的上限。

## 4. 调参路线

### 4.1 总原则

调参顺序不要混乱，建议按下面的固定顺序推进：

1. 先稳主检测。
2. 再稳人脸检测。
3. 再稳重绑定。
4. 最后再调控制中心和平滑。
5. 轻量化参数最后再碰，不要一开始就动。

### 4.2 第一阶段：先锁住主检测质量

目标：让 person 框尽量稳定，避免后续所有问题都被主检测质量污染。

优先调：

| 参数 | 当前默认 | 建议试验点 |
| --- | --- | --- |
| imgsz | 960 / 640 | 离线试 960、1152；实时试 512、640、768 |
| conf | 0.25 | 0.20、0.25、0.30 |
| iou | 0.5 | 0.45、0.50、0.55 |
| track_high_thresh | 0.25 | 0.25、0.30、0.35 |
| match_thresh | 0.8 | 0.75、0.80、0.85 |

判断标准：

- 人框是否更稳。
- 目标是否更少掉出候选集合。
- tracker_switches 和 reacquired_count 是否改善。

### 4.3 第二阶段：再锁住脸框质量

目标：提高 FACE_LOCK 占比，减少 HEAD_PROXY 和假脸框。

优先调：

| 参数 | 当前默认 | 建议试验点 |
| --- | --- | --- |
| face-scale-factor | 1.05 | 1.03、1.05、1.08 |
| face-min-neighbors | 3 | 2、3、4 |
| face-min-confidence | 0.30 | 0.25、0.30、0.35 |
| mtcnn-interval | 1 / 3 | 离线固定 1；实时试 2、3、4 |
| face-hold | 6 | 4、6、8 |

判断标准：

- FACE_LOCK 帧数是否上升。
- HEAD_PROXY 帧数是否下降。
- 关键帧中脸框是否还会偏到头顶、耳侧或后脑。

### 4.4 第三阶段：重绑定参数单独调

目标：在遮挡、转头、换 ID 后，尽量保持还是同一个业务目标。

优先调：

| 参数 | 当前默认 | 建议试验点 |
| --- | --- | --- |
| appearance-weight | 0.6 | 0.5、0.6、0.7 |
| iou-weight | 0.25 | 0.2、0.25、0.3 |
| center-weight | 0.15 | 0.1、0.15、0.2 |
| min-appearance | 0.35 | 0.30、0.35、0.40 |
| reacquire-thresh | 0.45 | 0.40、0.45、0.50 |

判断标准：

- tracker_switches 是否减少。
- reacquired_count 是否合理，不要只看少，还要看是不是恢复成功。
- 视频中是否出现“换绑到别的人”的情况。

### 4.5 第四阶段：最后调控制观感

目标：让 filtered_target_center 更适合控制，不因为视觉抖动而输出剧烈波动。

优先调：

| 参数 | 当前默认 | 建议试验点 |
| --- | --- | --- |
| control-alpha | 0.72 | 0.60、0.72、0.82 |
| control-max-step | 40.0 | 25、40、60 |
| control-deadband | 12.0 | 8、12、16 |

判断标准：

- filtered_target_center 的轨迹是否更平滑。
- control_active 是否过于频繁或过于迟钝。
- 云台控制需求是“更稳”还是“更跟手”，两者不能同时极致。

### 4.6 第五阶段：轻量化参数单独做 A/B

目标：确认哪些轻量化改动是“可接受退化”，哪些会明显损伤输出质量。

建议顺序：

1. 先只调 reid-interval，不动 mtcnn-interval。
2. 再单独调 mtcnn-interval。
3. 不要同时改两个再下结论。

建议试验点：

| 参数 | 当前默认 | 建议试验点 |
| --- | --- | --- |
| reid-interval | 离线 1，实时 8 | 离线试 1、2、4；实时试 4、8、12 |
| mtcnn-interval | 离线 1，实时 3 | 离线试 1、2；实时试 2、3、4 |

判断标准：

- performance.json 中 collect_candidates_ms、embedding_ms、face_detect_mtcnn_ms 是否下降。
- FACE_LOCK 是否下降。
- filtered_target_center 的平均偏移和最大偏移是否明显恶化。

## 5. 推荐的首轮调参组合

如果现在要开始正式调参，建议先跑下面 3 组，而不是一次改很多项。

### 组合 A：质量优先基线

| 参数 | 建议值 |
| --- | --- |
| imgsz | 离线 960，实时 640 |
| conf | 0.25 |
| face-scale-factor | 1.05 |
| face-min-neighbors | 3 |
| face-min-confidence | 0.30 |
| reid-interval | 离线 1，实时 8 |
| mtcnn-interval | 离线 1，实时 3 |

建议模型：

- 主检测模型优先保持 YOLO26n 作为速度基线。
- ReID 模型保持 YOLO26l。

### 组合 B：只压 embedding，不压脸框刷新

| 参数 | 建议值 |
| --- | --- |
| reid-interval | 离线 2 或 4，实时 8 或 10 |
| mtcnn-interval | 保持不变 |
| 其他质量参数 | 保持基线 |

用途：优先验证是否能在不明显损害 FACE_LOCK 的前提下，先拿到一部分速度收益。

建议模型：

- 主检测模型不变。
- ReID 模型不变。

### 组合 C：轻量化实验版

| 参数 | 建议值 |
| --- | --- |
| reid-interval | 离线 4，实时 10 |
| mtcnn-interval | 离线 2，实时 4 |
| imgsz | 实时 512 |

用途：用于验证速度上限，不用于定义“质量不变”。

建议模型：

- 主检测模型保持 YOLO26n。
- ReID 模型可在 YOLO26l 和 YOLO26n 之间做极限轻量实验，但必须单独做 A/B。

### 组合 D：复杂场景高质量版

| 参数 | 建议值 |
| --- | --- |
| model | YOLO26l，必要时试 YOLO26x |
| reid-model | YOLO26l，必要时试 YOLO26x |
| imgsz | 离线 1152，实时 640 或 768 |
| conf | 0.20 到 0.25 |
| face-min-confidence | 0.25 到 0.30 |
| mtcnn-interval | 尽量小，离线保持 1，实时试 2 |

用途：

- 用于暗光、强抖动、高速运动等困难场景下验证质量上限。
- 不作为 CPU-only 实时性能基线。

## 6. 最后建议

当前这套系统里，最容易被误当成“只是性能参数”，但实际上会直接改输出质量的参数只有 3 个：

| 参数 | 原因 |
| --- | --- |
| imgsz | 会直接改变主检测质量与小脸可见性 |
| reid-interval | 会直接改变 embedding 刷新密度和身份连续性 |
| mtcnn-interval | 会直接改变真实脸框刷新密度和控制中心轨迹 |

所以后续所有轻量化实验，必须把这 3 个和 FACE_LOCK、HEAD_PROXY、filtered_target_center 偏移一起看，不能只看 FPS。

## 7. Corner Case 极端场景清单与调参方向

本节整理所有目前能预见、且可能影响算法最终输出质量的 corner case。这里的“输出质量”包括：

- 是否仍锁定同一个业务目标。
- FACE_LOCK 是否真实可靠。
- HEAD_PROXY 是否仍在合理头部区域。
- filtered_target_center 是否稳定且适合控制。
- 实时模式是否因为处理延迟或丢帧导致输出失真。

### 7.1 光照类 Corner Case

| Corner Case | 典型表现 | 对算法质量的影响 | 优先调整参数 | 调整方向 | 可能副作用 | 风险等级 |
| --- | --- | --- | --- | --- | --- | --- |
| 暗光 | 人脸纹理弱、噪声大、人框置信度低 | person 漏检、face_bbox 漏检、embedding 不稳定 | model、reid-model、imgsz、conf、face-min-confidence、face-scale-factor、face-min-neighbors | model/reid-model 升到 YOLO26l 或 YOLO26x；imgsz 调大；conf 略降；face-min-confidence 略降；face-scale-factor 调小；face-min-neighbors 调低 | 速度下降，误检增加 | 高 |
| 极暗光 | 人脸几乎不可见，只剩轮廓 | FACE_LOCK 大量退化为 HEAD_PROXY，甚至 LOST | model、imgsz、conf、face-hold、max-lost、track_buffer | 优先提升模型和 imgsz；降低 conf；增大 face-hold、max-lost、track_buffer | 可能长时间保持错误目标或旧位置 | 高 |
| 强光过曝 | 脸部高光，五官细节消失 | MTCNN 和 cascade 都可能误检或漏检 | conf、face-min-confidence、face-min-neighbors、face-scale-factor | conf 略升；face-min-confidence 略升；face-min-neighbors 略升；face-scale-factor 可略升 | 过度调高会漏掉小脸和边缘脸 | 高 |
| 逆光 | 人体可见但脸部黑，脸框不稳定 | 人框可能还在，但 face_bbox 丢失，HEAD_PROXY 增多 | imgsz、face-min-confidence、face-hold、mtcnn-interval、control-alpha | imgsz 调大；face-min-confidence 略降；face-hold 略升；mtcnn-interval 调小；control-alpha 略升 | 速度下降，HEAD_PROXY 保持更久 | 高 |
| 光照快速变化 | 自动曝光跳变，画面忽明忽暗 | track 抖动、embedding 前后不一致 | conf、track_buffer、min-appearance、reacquire-thresh、control-alpha | conf 略降；track_buffer 略升；min-appearance 略降；reacquire-thresh 略降；control-alpha 略升 | 更容易接受低质量候选 | 中 |
| 彩色灯光/偏色 | 脸色异常，embedding 质量下降 | 外观相似度不稳定，重绑定可能失败 | reid-model、min-appearance、appearance-weight、center-weight | reid-model 升级；min-appearance 略降；appearance-weight 略降；center-weight 略升 | 可能让几何信号过度主导 | 中 |

### 7.2 运动与相机抖动类 Corner Case

| Corner Case | 典型表现 | 对算法质量的影响 | 优先调整参数 | 调整方向 | 可能副作用 | 风险等级 |
| --- | --- | --- | --- | --- | --- | --- |
| 强相机抖动 | 整帧快速晃动，背景和目标都跳 | BoT-SORT 关联失败、tracker id 切换、控制中心乱跳 | gmc_method、track_buffer、match_thresh、track_high_thresh、control-alpha、control-max-step | 重点测试 gmc_method；track_buffer 升高；match_thresh 略降；track_high_thresh 略降；control-alpha 升高；control-max-step 降低 | 过度平滑会拖尾，match_thresh 过低会错配 | 高 |
| 持续移动镜头 | 目标和背景都有全局运动 | GMC 不合适会造成漂移或错配 | gmc_method、match_thresh、track_buffer、center-weight | 保留 sparseOptFlow 作为基线，必要时对比 none/orb/ecc；track_buffer 略升；center-weight 略升 | 不同视频最优 GMC 可能不同 | 高 |
| 高速目标运动 | 人脸快速穿过画面，运动模糊 | 人框和脸框漏检，filtered_center 跟不上 | model、imgsz、conf、track_high_thresh、max-lost、control-max-step、control-alpha | model 升级；imgsz 不要降；conf 略降；track_high_thresh 略降；max-lost 略升；control-max-step 升高；control-alpha 降低或维持 | 控制输出更敏感，抖动可能增加 | 高 |
| 突然加速/急停 | 中心位置突然大幅变化 | 中心平滑滞后，云台指令慢半拍 | control-alpha、control-max-step、center-weight | control-alpha 降低；control-max-step 升高；center-weight 略升 | 抗抖能力下降 | 中 |
| 运动模糊 | 脸部边缘糊，五官不可分 | face_bbox 和 embedding 同时变差 | model、reid-model、imgsz、face-min-confidence、min-appearance、reacquire-thresh | model/reid-model 升级；imgsz 调大；face-min-confidence 略降；min-appearance 略降；reacquire-thresh 略降 | 更容易引入低质量脸候选 | 高 |
| 低帧率输入 | 相邻帧位移大 | IoU 和中心连续性下降，重绑定困难 | match_thresh、min-iou、min-center-score、center-weight、max-lost | match_thresh 降低；min-iou 降低；min-center-score 降低；center-weight 略升；max-lost 升高 | 容易接受错误候选 | 中 |

### 7.3 遮挡与目标姿态类 Corner Case

| Corner Case | 典型表现 | 对算法质量的影响 | 优先调整参数 | 调整方向 | 可能副作用 | 风险等级 |
| --- | --- | --- | --- | --- | --- | --- |
| 短时遮挡 | 目标脸消失几帧后恢复 | FACE_LOCK 变 HEAD_PROXY 或 HOLD | face-hold、max-lost、track_buffer、reacquire-thresh | face-hold 升高；max-lost 升高；track_buffer 升高；reacquire-thresh 可略降 | 遮挡期间可能保持旧位置过久 | 高 |
| 长时间遮挡 | 目标长时间不可见 | 可能 LOST 或误重绑定到别人 | max-lost、track_buffer、min-appearance、reacquire-thresh | max-lost 和 track_buffer 适度升高；min-appearance 和 reacquire-thresh 不宜过低 | 太激进会误绑，太保守会找不回 | 高 |
| 部分脸遮挡 | 口罩、手挡脸、帽檐 | face_bbox 漏检，embedding 质量下降 | face-min-confidence、face-min-neighbors、reid-model、face-hold | face-min-confidence 略降；face-min-neighbors 略降；reid-model 升级；face-hold 略升 | 假脸和错误候选增加 | 高 |
| 侧脸/背头 | 正脸不可见，耳侧或后脑显著 | FACE_LOCK 下降，HEAD_PROXY 增加，假 FACE_LOCK 风险 | mtcnn-interval、face-scale-factor、face-min-neighbors、landmarks 几何常量、clamp head_bottom | mtcnn-interval 调小；face-scale-factor 调小；face-min-neighbors 调低；必要时收紧 landmarks 和 clamp 几何 | 速度下降，几何常量调错会框偏 | 高 |
| 低头/抬头 | 五官位置变化，脸框上下漂 | 脸框可能偏到头顶或下巴 | landmarks center_y、landmarks box_h、clamp head_bottom、projected center y 范围 | 根据视频观察微调 center_y 和 box_h；收紧或放宽 projected center y | 属于强几何调参，泛化风险高 | 高 |
| 人脸很小 | 远距离目标，脸部像素少 | 人脸检测失败，embedding 不可靠 | model、imgsz、face-min-confidence、min_face 隐含规则、camera-width/height | model 升级；imgsz 调大；face-min-confidence 略降；实时提高输入分辨率 | 计算量显著上升 | 高 |
| 人体框只包含上半身/半身 | body_bbox 高宽比例异常 | face_relative_bbox 和 HEAD_PROXY 投影失真 | clamp 几何常量、projected width/height 范围、face-hold | 收紧 projected width/height 和 center y；face-hold 不宜过大 | 可能更快 LOST | 中 |
| 目标突然转身 | 从脸到后脑 | FACE_LOCK 直接退化，embedding 断档 | face-hold、max-lost、mtcnn-interval、reid-interval | face-hold 升高；max-lost 升高；mtcnn-interval 调小；reid-interval 调小 | 速度下降，旧身份保持时间更长 | 高 |

### 7.4 多人、交互和背景干扰类 Corner Case

| Corner Case | 典型表现 | 对算法质量的影响 | 优先调整参数 | 调整方向 | 可能副作用 | 风险等级 |
| --- | --- | --- | --- | --- | --- | --- |
| 多人近距离交叉 | 两个人重叠、擦肩而过 | tracker id 切换，业务目标可能换人 | reid-model、min-appearance、appearance-weight、reacquire-thresh、track_buffer | reid-model 升级；min-appearance 升高；appearance-weight 升高；reacquire-thresh 升高；track_buffer 适度升高 | 可能导致正确重绑定变慢 | 高 |
| 多人相似外观 | 脸或衣着相似 | embedding 区分度下降，误绑风险高 | reid-model、min-appearance、reacquire-thresh、center-weight、min-center-score | reid-model 升级；min-appearance 升高；reacquire-thresh 升高；center-weight 略升；min-center-score 升高 | 过保守会找不回目标 | 高 |
| 目标被其他人遮挡后出现 | 遮挡后候选很多 | 重绑定可能选错 | appearance-weight、min-appearance、reacquire-thresh、choose_embedding_candidates limit | appearance-weight 升高；min-appearance 升高；reacquire-thresh 升高；实时 limit 可升高 | 速度下降，重绑定变慢 | 高 |
| 背景中有人脸照片/海报 | 非真实人脸被检测到 | false face 进入候选，可能扰乱初始化或重绑定 | classes、face-min-confidence、face-min-neighbors、reacquire-thresh | face-min-confidence 升高；face-min-neighbors 升高；reacquire-thresh 升高 | 小脸召回下降 | 中 |
| 镜子/玻璃反射 | 反射中出现同一人或其他人脸 | 可能锁到反射目标 | min-appearance、min-iou、min-center-score、center-weight | 提高几何约束：min-iou、min-center-score、center-weight；不要只靠 appearance | 大位移真实恢复可能受阻 | 高 |
| 目标出画又入画 | 完全离开画面后回来 | 可能 LOST，或者重新绑定错误对象 | max-lost、track_buffer、min-appearance、reacquire-thresh | max-lost 升高；track_buffer 升高；min-appearance 不宜太低；reacquire-thresh 维持或略升 | 长时间保留可能误认其他人 | 高 |
| 初始帧 id=1 不是目标 | initial-track-id 默认选错 | 整段都锁错业务目标 | initial-track-id、fallback-to-first-face、choose_by_click | 改 initial-track-id；必要时关闭自动回退，改为人工点击选择 | 操作复杂度上升 | 高 |

### 7.5 摄像头、画质和输入源类 Corner Case

| Corner Case | 典型表现 | 对算法质量的影响 | 优先调整参数 | 调整方向 | 可能副作用 | 风险等级 |
| --- | --- | --- | --- | --- | --- | --- |
| 摄像头分辨率过低 | 小脸像素不足 | face_bbox 和 embedding 同时退化 | camera-width、camera-height、imgsz、model | 提高 camera-width/height；提高 imgsz；model 升级 | 实时吞吐下降，丢帧增加 | 高 |
| 摄像头自动曝光跳变 | 画面亮度突变 | 检测和 embedding 分布波动 | conf、face-min-confidence、control-alpha、track_buffer | conf 和 face-min-confidence 适度放宽；control-alpha 升高；track_buffer 升高 | 稳定性与响应速度冲突 | 中 |
| 摄像头延迟大 | 画面显示滞后 | 控制输出对真实目标位置滞后 | camera-backend、camera-fps、camera-width/height、imgsz | 降低输入分辨率；尝试 dshow/msmf；降低 imgsz | 画质下降 | 高 |
| 压缩噪声/码流块效应 | 视频块状、边缘断裂 | 小脸检测变差 | model、imgsz、face-scale-factor、face-min-confidence | model 升级；imgsz 调大；face-scale-factor 调小；face-min-confidence 略降 | 速度下降，误检上升 | 中 |
| 滚动快门畸变 | 快速运动时目标形变 | bbox 几何异常，控制中心偏移 | control-alpha、control-max-step、match_thresh、center-weight | control-alpha 升高；control-max-step 降低；match_thresh 降低；center-weight 略升 | 高速跟随变慢 | 中 |
| 帧率不稳定 | processed_index 间隔不均 | 实时丢帧、控制输出不连续 | camera-fps、imgsz、reid-interval、mtcnn-interval | 降低 imgsz；提高 reid/mtcnn interval；降低 camera-fps | 质量下降，脸框刷新变稀 | 高 |

### 7.6 底层 tracker 和 ReID 类 Corner Case

| Corner Case | 典型表现 | 对算法质量的影响 | 优先调整参数 | 调整方向 | 可能副作用 | 风险等级 |
| --- | --- | --- | --- | --- | --- | --- |
| tracker id 频繁切换 | 同一目标反复换 id | 业务层频繁重绑定，输出抖动 | track_buffer、match_thresh、gmc_method、reid-model、reacquire-thresh | track_buffer 升高；match_thresh 调整；测试 gmc_method；reid-model 升级；reacquire-thresh 合理提高 | 重绑定可能变慢 | 高 |
| tracker 长时间保持错误 id | 底层轨迹漂到别人身上 | 业务层可能误以为还是同一目标 | min-appearance、reacquire-thresh、is_same_tracker 几何阈值、appearance-weight | min-appearance 升高；reacquire-thresh 升高；appearance-weight 升高；收紧同 tracker 几何阈值 | 遮挡恢复更困难 | 高 |
| embedding 质量突然下降 | 外观相似度异常低 | 正确目标也无法通过重绑定 | reid-model、min-appearance、appearance-weight、reid-interval | reid-model 升级；min-appearance 略降；appearance-weight 略降；reid-interval 调小 | 误绑风险上升 | 高 |
| embedding 刷新过稀 | 轻量化后 prototype 落后 | 中间帧身份确认变弱 | reid-interval、embedding_bank 长度 | reid-interval 调小；embedding_bank 长度可适度缩短 | 速度下降，prototype 更敏感 | 中 |
| BoT-SORT 内部 ReID 打开 | with_reid=True 后双 ReID 体系并存 | 底层 tracker 行为改变，业务层结果也变 | with_reid、proximity_thresh、appearance_thresh、model | 必须单独 A/B，不要和业务 ReID 参数同时改 | 影响来源难以归因 | 高 |

### 7.7 人脸检测与几何框类 Corner Case

| Corner Case | 典型表现 | 对算法质量的影响 | 优先调整参数 | 调整方向 | 可能副作用 | 风险等级 |
| --- | --- | --- | --- | --- | --- | --- |
| 假 FACE_LOCK | 标签显示 FACE_LOCK，但框在耳朵、后脑或头顶 | 统计好看但几何错误，云台会跟偏 | landmarks 几何常量、clamp head_bottom、face-min-confidence、face-min-neighbors | 收紧几何约束；face-min-confidence 升高；face-min-neighbors 升高 | 召回下降，HEAD_PROXY 增多 | 高 |
| HEAD_PROXY 长时间存在 | 真实脸检测持续失败 | 控制中心基于代理框，可能慢慢漂 | mtcnn-interval、face-hold、face-scale-factor、face-min-confidence | mtcnn-interval 调小；face-hold 不宜过大；face-scale-factor 调小；face-min-confidence 适度降低 | 速度下降，误检增加 | 高 |
| 脸框忽大忽小 | cascade/MTCNN 候选不稳定 | filtered_target_center 抖动，控制输出抖 | smooth_bbox alpha、face_hint 权重、landmarks box_w/h | smooth_bbox alpha 升高；更偏 face_hint；收紧 box_w/h 范围 | 响应变慢 | 中 |
| 脸框过大包含背景 | bbox 包住头肩或背景 | embedding 被污染，中心偏移 | landmarks box_w/h、pad_w/h、width_ratio/height_ratio | 减小 box_w/h；减小 padding；收紧 ratio 上限 | 可能裁掉部分脸 | 中 |
| 脸框过小只框五官局部 | bbox 不完整 | embedding 不稳定，控制中心偏局部 | landmarks box_w/h、pad_w/h、ratio 下限 | 增大 box_w/h；增大 padding；放宽 ratio 下限 | 可能引入背景 | 中 |
| 多个人脸在同一人体框附近 | 候选排序可能选错脸 | 误 FACE_LOCK 或错误 embedding | face_hint 选择权重、min-appearance、center-weight | 更偏 face_hint；提高 min-appearance；提高 center-weight | 快速姿态变化时可能保守 | 高 |

### 7.8 实时链路与性能类 Corner Case

| Corner Case | 典型表现 | 对算法质量的影响 | 优先调整参数 | 调整方向 | 可能副作用 | 风险等级 |
| --- | --- | --- | --- | --- | --- | --- |
| process_fps 远低于 camera_fps | 丢帧很多，但显示不积压 | 处理帧稀疏，运动连续性差 | imgsz、model、reid-interval、mtcnn-interval、camera-width/height | 降低 imgsz；model 用 YOLO26n；增大 reid/mtcnn interval；降低相机分辨率 | 输出质量下降 | 高 |
| dropped_frames 突然升高 | 镜头一动就丢很多帧 | 目标可能跳变，重绑定困难 | imgsz、mtcnn-interval、reid-interval、camera-fps、camera-width/height | 降低分辨率和 imgsz；增大 interval；必要时降低 camera-fps | 脸框质量下降 | 高 |
| 保存视频时长短于真实会话 | 实时输出只包含处理帧 | 复盘视频不等于完整时间轴 | output_fps、保存策略、process_fps | 当前设计保留处理帧；若要完整时间轴需改保存逻辑 | 文件更大，逻辑更复杂 | 中 |
| show 窗口卡顿 | 显示慢但算法可能还在跑 | 误判性能瓶颈 | display-width、show、save-all-boxes | display-width 降低；关闭 save-all-boxes；必要时不 show | 可视化信息减少 | 低 |
| CPU 占满 | 单帧延迟大 | 实时输出稀疏，控制滞后 | model、imgsz、mtcnn-interval、reid-interval | 用小模型；降低 imgsz；增大 interval | 质量下降 | 高 |

### 7.9 控制输出类 Corner Case

| Corner Case | 典型表现 | 对算法质量的影响 | 优先调整参数 | 调整方向 | 可能副作用 | 风险等级 |
| --- | --- | --- | --- | --- | --- | --- |
| 控制中心抖动 | filtered_target_center 小幅高频震荡 | 云台会来回抖 | control-alpha、control-max-step、control-deadband、smooth_bbox alpha | control-alpha 升高；control-max-step 降低；control-deadband 升高；smooth_bbox alpha 升高 | 响应变慢 | 高 |
| 控制中心拖尾 | 目标移动后中心跟不上 | 云台慢半拍 | control-alpha、control-max-step | control-alpha 降低；control-max-step 升高 | 抖动增加 | 高 |
| 控制死区过大 | 目标偏了但 control_active 不触发 | 目标不容易回到画面中心 | control-deadband | control-deadband 降低 | 控制更频繁，可能抖 | 中 |
| 控制死区过小 | 一点偏差就触发控制 | 云台可能频繁微调 | control-deadband、control-alpha | control-deadband 升高；control-alpha 升高 | 响应迟钝 | 中 |
| LOST/HOLD 状态切换频繁 | 控制输出断续 | 云台动作不连续 | face-hold、max-lost、control-alpha | face-hold 升高；max-lost 升高；control-alpha 升高 | 可能保持错误目标更久 | 高 |

### 7.10 Corner Case 调参优先级总表

| 优先级 | 场景类别 | 第一优先参数 | 第二优先参数 | 不建议一开始动的参数 | 原因 |
| --- | --- | --- | --- | --- | --- |
| 1 | 暗光/极暗光 | model、imgsz、conf | face-min-confidence、face-scale-factor、face-min-neighbors | control-alpha | 先解决看不见和检测不到，再谈控制平滑 |
| 2 | 强抖动 | gmc_method、track_buffer、match_thresh | control-alpha、control-max-step | face 几何硬编码 | 先判断是不是底层跟踪/GMC 问题 |
| 3 | 高速运动 | imgsz、conf、track_high_thresh | control-max-step、control-alpha、max-lost | face 几何硬编码 | 先保住候选，再处理控制响应 |
| 4 | 多人交叉 | reid-model、min-appearance、reacquire-thresh | appearance-weight、center-weight、track_buffer | mtcnn-interval | 本质是身份连续性问题，不是先压速度 |
| 5 | 侧脸/转身 | mtcnn-interval、face-scale-factor、face-min-confidence | landmarks 几何常量、face-hold | reid-interval | 本质是脸框几何和真实脸召回问题 |
| 6 | 实时掉帧 | imgsz、model、camera-width/height | reid-interval、mtcnn-interval | min-appearance、reacquire-thresh | 先解决吞吐，再判断质量参数 |
| 7 | 控制抖动 | control-alpha、control-max-step、control-deadband | smooth_bbox alpha | model | 如果检测已经稳定，才调控制层 |

## 8. Corner Case 实验命名建议

为了让后续结果可追溯，建议每个极端场景实验都在 `--name` 里写清楚场景和主要参数变化。

| 场景 | 命名示例 | 含义 |
| --- | --- | --- |
| 暗光 | dark_img1152_conf020 | 暗光，imgsz=1152，conf=0.20 |
| 强抖动 | shake_gmc_orb_buf90 | 强抖动，gmc_method=orb，track_buffer=90 |
| 高速运动 | fast_conf020_step60 | 高速运动，conf=0.20，control-max-step=60 |
| 多人交叉 | crowd_app040_reacq050 | 多人交叉，min-appearance=0.40，reacquire-thresh=0.50 |
| 侧脸 | profile_mtcnn1_faceconf025 | 侧脸，mtcnn-interval=1，face-min-confidence=0.25 |
| 实时掉帧 | rt_512_reid10_mtcnn4 | 实时，imgsz=512，reid-interval=10，mtcnn-interval=4 |

## 9. Corner Case 判断指标

每次极端场景实验至少看下面这些指标，不要只看最终视频观感。

| 指标 | 来源文件 | 判断意义 |
| --- | --- | --- |
| effective_fps | summary.json / performance.json | 速度是否可接受 |
| tracker_switches | summary.json | 底层 ID 连续性是否恶化 |
| reacquired_count | summary.json | 重绑定是否频繁 |
| face_detected_frames | summary.json | 真实脸检测是否改善 |
| total_face_misses | summary.json | 脸漏检是否增加 |
| max_face_miss_streak | summary.json | 是否有长时间脸丢失 |
| FACE_LOCK / HEAD_PROXY / LOST 分布 | frame_metrics.json | 锁定模式是否退化 |
| filtered_target_center 偏移 | frame_metrics.json | 控制中心是否变差 |
| collect_candidates_ms | performance.json | 候选构建是否仍是瓶颈 |
| embedding_ms | performance.json | ReID 成本是否过高 |
| face_detect_mtcnn_ms | performance.json | MTCNN 成本是否过高 |
| dropped_frames_before | 实时 frame_metrics.json | 实时丢帧是否影响连续性 |