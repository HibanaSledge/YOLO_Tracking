# Skill: Literature Alignment

## Use When

- 用户要求把论文、算法路线或外部方法与当前项目对齐。
- 用户比较 BoT-SORT、ByteTrack、ReID、MTCNN、头部姿态估计或轻量化方案。

## Procedure

1. 先说明当前仓库已实现的对应能力。
2. 区分外部方法的理论目标与本项目业务目标。
3. 给出可落地改造点。
4. 设计最小实验验证，而不是直接替换主链路。

## Project Alignment Rules

- ByteTrack/BoT-SORT 是底层候选轨迹来源，不等于业务目标状态。
- ReID 主要服务跨 ID 身份连续性，不直接提升脸框几何。
- MTCNN/landmarks 主要服务真实脸框定位，但成本影响实时性。
- 头部姿态或关键点方案应先作为几何质量实验接入，不应直接替换全部状态机。

## Output

- 外部方法要解决的问题。
- 当前仓库已有能力。
- 差距。
- 最小实验方案。