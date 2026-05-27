# Quality Standards

## Target Identity

- 不能只看 tracker id。
- 必须关注是否仍是同一个业务目标。
- 多人交叉、遮挡、相似外观是高风险场景。

## Face / Head Geometry

- FACE_LOCK 应尽可能是真实脸框。
- HEAD_PROXY 可以维持连续性，但不能当作真实脸框质量。
- 假 FACE_LOCK 比 HEAD_PROXY 更危险，因为统计好看但控制会偏。

## Control Quality

- filtered center 应稳定但不能过度拖尾。
- 控制死区、平滑和最大步长需要按场景取舍。

## Performance Quality

- 速度提升必须绑定质量影响。
- `demo-only` 主要减少输出负担，不等于算法变快。
- CPU-only 实时低 FPS 是当前已知限制。

## Evidence Standard

- 最低：summary。
- 合格：summary + frame_metrics。
- 性能合格：summary + frame_metrics + performance。
- 质量关键结论：还需要关键帧或视频检查。