# 云台串口通信协议 v1

## 1. 目标

本协议用于上位机实时 camera tracking 程序向下位机发送云台控制命令。上位机负责视觉检测、目标锁定和控制偏移计算；下位机负责根据串口命令驱动云台 yaw/pitch 电机。

当前协议的帧格式是统一串口帧格式。上位机发送命令和下位机回传状态应沿用同一套帧外壳，通过 `msg_type` 区分消息方向和消息语义，不需要为接收帧重新设计一套独立帧格式。

协议设计目标：

- 低延迟：每帧只发送当前最新控制量，不要求下位机缓存历史帧。
- 可恢复：每帧带固定帧头、长度和 CRC16，丢包或错位后可重新同步。
- 安全：目标丢失、未初始化或程序退出时发送 STOP。
- 可解释：保留下发时的目标状态、像素偏移、速度命令和距离。

## 2. 串口默认参数

| 项目 | 默认值 |
| --- | --- |
| 波特率 | 115200 |
| 数据位 | 8 |
| 停止位 | 1 |
| 校验位 | None |
| 流控 | None |
| 默认发送频率 | 20 Hz |

## 3. 数据帧格式

所有多字节整数均为 little-endian。

| 字段 | 长度 | 类型 | 说明 |
| --- | --- | --- | --- |
| header | 2 | uint8[2] | 固定 `0xAA 0x55` |
| version | 1 | uint8 | 当前为 `0x01` |
| msg_type | 1 | uint8 | 消息类型 |
| sequence | 2 | uint16 | 上位机递增序号，溢出回绕 |
| payload_len | 1 | uint8 | payload 字节数，最大 255 |
| payload | N | bytes | 消息体 |
| crc16 | 2 | uint16 | CRC16-Modbus，覆盖 `version` 到 `payload` |

CRC 不包含 `header`，但包含 `version`、`msg_type`、`sequence`、`payload_len` 和 `payload`。

## 4. 消息类型

| msg_type | 名称 | 方向 | 说明 |
| --- | --- | --- | --- |
| `0x01` | TRACK | 上位机 -> 下位机 | 当前 tracking 控制命令 |
| `0x02` | STOP | 上位机 -> 下位机 | 停止云台运动 |
| `0x03` | HEARTBEAT | 双向或保留 | 当前代码暂未主动发送 |
| `0x81` | ACK | 下位机 -> 上位机 | 确认收到某条上位机命令 |
| `0x82` | STATUS | 下位机 -> 上位机 | 回传云台当前状态 |
| `0x83` | ERROR | 下位机 -> 上位机 | 回传下位机错误码 |

## 5. TRACK payload

格式：`<BBIhhhhH`，总长度 16 字节。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| state_code | uint8 | tracking 状态码 |
| flags | uint8 | 状态标志位 |
| frame_index | uint32 | 上位机处理帧序号 |
| dx_px | int16 | 目标控制中心相对画面中心的 x 偏移，右为正 |
| dy_px | int16 | 目标控制中心相对画面中心的 y 偏移，下为正 |
| pan_speed | int16 | yaw 速度命令，默认右转为正 |
| tilt_speed | int16 | pitch 速度命令，默认下转为正 |
| distance_px | uint16 | 控制中心到画面中心的像素距离 |

### 5.1 state_code

| state_code | 状态 | 说明 |
| --- | --- | --- |
| 0 | SEARCHING | 尚未锁定目标 |
| 1 | TRACKING | 正常跟踪 |
| 2 | REACQUIRE | 重绑定后短时恢复状态 |
| 3 | HOLD | 短时丢脸或短时丢检测，仍保持目标 |
| 4 | LOST | 目标丢失 |

### 5.2 flags

| bit | 名称 | 说明 |
| --- | --- | --- |
| 0 | control_active | 偏移超过死区，云台应运动 |
| 1 | visible | 当前存在可用目标框或保持框 |
| 2 | deadband_active | 偏移在死区内，速度应为 0 |
| 3 | filtered_center_valid | filtered_target_center 有效 |

## 6. STOP payload

格式：`<B`，总长度 1 字节。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| state_code | uint8 | 触发 STOP 时的状态码，通常为 SEARCHING 或 LOST |

下位机收到 STOP 后应立即将 yaw/pitch 速度置 0。

## 7. 上位机速度计算规则

上位机使用实时脚本中的 `control_offset` 生成速度：

- `dx_px > 0`：目标在画面右侧，默认 `pan_speed > 0`。
- `dy_px > 0`：目标在画面下方，默认 `tilt_speed > 0`。
- 如果机械方向相反，上位机启动时使用 `--gimbal-invert-pan` 或 `--gimbal-invert-tilt` 反向。
- 如果 `control_active=false` 或 `deadband_active=true`，速度命令为 0。

速度计算公式：

```text
pan_speed  = clamp(dx_px / half_width  * max_speed * pan_gain,  -max_speed, max_speed)
tilt_speed = clamp(dy_px / half_height * max_speed * tilt_gain, -max_speed, max_speed)
```

默认：

- `max_speed = 500`
- `pan_gain = 0.8`
- `tilt_gain = 0.8`

## 8. 下位机解析建议

下位机接收侧建议按以下流程实现：

1. 在串口字节流中搜索帧头 `0xAA 0x55`。
2. 读取固定头部：version、msg_type、sequence、payload_len。
3. 按 payload_len 读取 payload 和 crc16。
4. 对 `version` 到 `payload` 重新计算 CRC16-Modbus。
5. CRC 错误则丢弃当前帧，继续搜索下一帧头。
6. 如果连续超过 300 ms 未收到有效 TRACK，可自动执行 STOP。
7. 收到 STOP 后立即清零电机速度。

## 9. 下位机回传消息

下位机回传消息沿用第 3 节定义的统一帧格式：`header + version + msg_type + sequence + payload_len + payload + crc16`。

建议约定：

- 上位机发送帧使用上位机自己的递增 `sequence`。
- 下位机回传帧使用下位机自己的递增 `sequence`。
- 如果下位机需要确认某条上位机命令，应在 ACK payload 中携带被确认命令的 `ack_sequence`。
- 上位机接收侧先按统一帧格式完成帧头搜索、长度读取和 CRC 校验，再根据 `msg_type` 分发处理。

### 9.1 ACK payload

ACK 用于确认下位机已经收到并解析某条上位机命令。

格式：`<BHB`，总长度 4 字节。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| ack_msg_type | uint8 | 被确认的上位机消息类型，例如 `0x01` TRACK 或 `0x02` STOP |
| ack_sequence | uint16 | 被确认的上位机命令序号 |
| status_code | uint8 | 确认状态，`0` 表示 OK，非 `0` 表示异常 |

建议 `status_code`：

| status_code | 名称 | 说明 |
| --- | --- | --- |
| 0 | OK | 命令已接收并通过校验 |
| 1 | UNSUPPORTED_MSG | 不支持的消息类型 |
| 2 | BAD_PAYLOAD_LEN | payload 长度不符合该消息类型定义 |
| 3 | BUSY | 下位机忙，命令未执行或延迟执行 |

### 9.2 STATUS payload

STATUS 用于下位机周期性或按需回传云台状态，便于上位机和 VOFA/日志对齐实际执行情况。

格式：`<hhBBH`，总长度 8 字节。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| yaw_speed | int16 | 当前 yaw 实际速度或最近一次目标速度 |
| pitch_speed | int16 | 当前 pitch 实际速度或最近一次目标速度 |
| mode | uint8 | 下位机当前工作模式 |
| error_code | uint8 | 当前错误码，`0` 表示无错误 |
| voltage_mv | uint16 | 电源电压，单位 mV；无法获取时填 `0` |

建议 `mode`：

| mode | 名称 | 说明 |
| --- | --- | --- |
| 0 | IDLE | 空闲或未运动 |
| 1 | TRACKING | 正在按 TRACK 命令运动 |
| 2 | STOP | 已执行停止 |
| 3 | ERROR | 下位机处于错误状态 |

### 9.3 ERROR payload

ERROR 用于下位机主动上报异常。

格式：`<BH`，总长度 3 字节。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| error_code | uint8 | 错误码 |
| related_sequence | uint16 | 相关的上位机命令序号；如果无关联命令则填 `0` |

建议 `error_code`：

| error_code | 名称 | 说明 |
| --- | --- | --- |
| 0 | NONE | 无错误，通常不需要发送 ERROR |
| 1 | CRC_ERROR | 收到的帧 CRC 错误 |
| 2 | PAYLOAD_ERROR | payload 解析失败或长度异常 |
| 3 | MOTOR_FAULT | 电机或驱动故障 |
| 4 | TIMEOUT_STOP | 超时未收到有效 TRACK，已自动 STOP |
| 5 | VOLTAGE_LOW | 电压过低 |

## 10. 上位机启动示例

只打开 camera tracking，不启用串口：

```powershell
python lock_target_realtime.py --camera 0
```

启用真实串口：

```powershell
python lock_target_realtime.py --camera 0 --gimbal-port COM3 --gimbal-baud 115200
```

只测试协议打包和 tracking 链路，不打开真实串口：

```powershell
python lock_target_realtime.py --camera 0 --gimbal-dry-run
```

如果云台方向相反：

```powershell
python lock_target_realtime.py --camera 0 --gimbal-port COM3 --gimbal-invert-pan --gimbal-invert-tilt
```

## 11. 当前证据缺口

- 已定义上位机发送协议和代码接入点。
- 已定义下位机回传帧应复用统一帧格式，并通过 `0x81` ACK、`0x82` STATUS、`0x83` ERROR 区分回传消息。
- 尚未拿真实下位机固件做闭环验证。
- 尚未实现上位机接收侧对 ACK / STATUS / ERROR 的完整解析和日志记录。
- 尚未标定不同云台电机的速度单位，因此 `max_speed`、`pan_gain`、`tilt_gain` 需要上机后实测调整。
