# Research Scope

## In Scope

- 单目标人脸/头部锁定。
- BoT-SORT / ByteTrack 作为候选跟踪基础。
- 业务层跨 ID 连续性。
- OpenCV + MTCNN / landmarks 人脸定位。
- YOLO embedding 辅助重绑定。
- 云台视觉前端观测量输出。
- 离线实验与实时摄像头低延迟演示。
- 性能/质量 A/B 评估。

## Out of Current Scope Unless Requested

- 完整云台闭环控制器。
- MCU、电机、IMU、编码器板级联调。
- 真实功耗测量。
- 大规模多目标 ReID 产品化。
- 3D 头部姿态完整估计。

## Current Research Question

如何在不显著损伤 FACE_LOCK 几何质量和业务身份连续性的前提下，提高 CPU-only 或未来 GPU 平台上的实时可用性。