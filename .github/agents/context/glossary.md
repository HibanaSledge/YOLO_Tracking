# Glossary

- `TargetState`：业务层目标状态，不等于 tracker id。
- `Candidate`：从 tracker 输出构造的候选目标。
- `FACE_LOCK`：真实脸框可用，当前锁定基于 face bbox。
- `HEAD_PROXY`：真实脸暂不可用，使用头部代理框维持连续性。
- `LOST`：业务目标不可可靠输出。
- `SEARCHING`：尚未建立稳定目标。
- `TRACKING`：控制状态中可跟踪。
- `HOLD`：短时保持旧位置或代理状态。
- `REACQUIRE`：遮挡或 ID 切换后重新绑定。
- `frame_metrics`：逐帧输出，记录 lock mode、control state、中心点和偏移。
- `performance`：阶段耗时与资源统计。
- `latest-frame`：实时链路只保留最新帧的低延迟设计。
- `lightweight`：通过降低 embedding/MTCNN 刷新频率等方式提速，可能改变质量。