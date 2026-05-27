# Examples

## Good Comparison Question

用户：比较 `offline_run` 和 `offline_run_light` 是否质量等价。

应做：读取两个 summary、frame_metrics、performance；比较 FACE_LOCK/HEAD_PROXY、中心偏移和阶段耗时；给 pass/conditional/fail。

## Good Realtime Diagnosis

用户：实时画面一卡一卡的。

应做：区分 display 卡顿、process latency、camera fps、dropped frames；优先查 realtime summary/performance。

## Good Feature Request

用户：加一个轻量开关。

应做：说明会影响 embedding/MTCNN 频率；保留默认质量模式；输出性能和质量证据；更新 changelog。

## Bad Answer Pattern

- 只说“降低 imgsz 能提速”。
- 没说明小脸、FACE_LOCK、中心轨迹可能退化。
- 没要求用 performance 和 frame_metrics 验证。