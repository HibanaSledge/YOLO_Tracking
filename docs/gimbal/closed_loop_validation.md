# 云台 tracking 闭环验证指南

## 1. 闭环验证目标

闭环验证不是只看串口有没有字节，而是确认完整链路成立：

camera -> 上位机视觉 tracking -> `control_offset` -> 串口协议 -> 下位机解析 -> 云台 yaw/pitch 运动 -> 画面中心误差收敛

本指南分三步推进：

1. 不接电机，只验证下位机能正确解析协议帧。
2. 接电机但不跑视觉，只用固定测试脚本验证方向、速度和 STOP。
3. 跑实时 camera tracking，验证目标偏离画面中心后云台能自动跟随并减小偏差。

## 2. 硬件连接

### 2.1 USB 转串口接法

| 上位机 USB-TTL | 下位机 UART |
| --- | --- |
| TX | RX |
| RX | TX |
| GND | GND |

注意：

- 必须共地。
- 电平要匹配，常见 USB-TTL 是 3.3V 或 5V，下位机 UART 不能接错电平。
- 先不接电机或断开电机使能，确认协议解析正确后再上电机。

### 2.2 默认串口参数

| 项目 | 值 |
| --- | --- |
| 波特率 | 115200 |
| 数据位 | 8 |
| 停止位 | 1 |
| 校验 | None |
| 流控 | None |

## 3. 下位机固件需要实现的内容

下位机最少要实现：

1. UART 字节流接收。
2. 搜索帧头 `0xAA 0x55`。
3. 读取 version、msg_type、sequence、payload_len。
4. 读取 payload 和 crc16。
5. 计算 CRC16-Modbus 并校验。
6. 解析 TRACK / STOP。
7. 超时保护：超过 300 ms 没收到有效 TRACK，自动 STOP。

## 4. 下位机解析伪代码

```c
#define HEADER0 0xAA
#define HEADER1 0x55
#define MSG_TRACK 0x01
#define MSG_STOP  0x02
#define PROTOCOL_VERSION 0x01

#pragma pack(push, 1)
typedef struct {
    uint8_t state_code;
    uint8_t flags;
    uint32_t frame_index;
    int16_t dx_px;
    int16_t dy_px;
    int16_t pan_speed;
    int16_t tilt_speed;
    uint16_t distance_px;
} TrackPayload;
#pragma pack(pop)

void on_valid_frame(uint8_t msg_type, uint8_t *payload, uint8_t payload_len) {
    if (msg_type == MSG_TRACK && payload_len == sizeof(TrackPayload)) {
        TrackPayload cmd;
        memcpy(&cmd, payload, sizeof(TrackPayload));

        bool control_active = (cmd.flags & 0x01) != 0;
        bool visible = (cmd.flags & 0x02) != 0;
        bool deadband_active = (cmd.flags & 0x04) != 0;

        if (!visible || !control_active || deadband_active) {
            set_gimbal_speed(0, 0);
            return;
        }

        set_gimbal_speed(cmd.pan_speed, cmd.tilt_speed);
        last_track_ms = millis();
        return;
    }

    if (msg_type == MSG_STOP && payload_len == 1) {
        set_gimbal_speed(0, 0);
        return;
    }
}

void loop_safety_check(void) {
    if (millis() - last_track_ms > 300) {
        set_gimbal_speed(0, 0);
    }
}
```

下位机要注意 little-endian。如果 MCU 是常见 ARM / STM32，一般天然是 little-endian。如果不是，需要手动组装字段。

## 5. PC 侧分阶段验证

### 5.1 阶段 A：不接电机，只看解析日志

下位机先把解析到的字段打印到调试口或屏幕，例如：

```text
TRACK seq=12 state=1 dx=240 dy=0 pan=150 tilt=0 flags=0x0B
STOP state=4
```

上位机运行：

```powershell
python tools/gimbal/test_serial.py --port COM3 --mode box --cycles 1
```

期望：

- 下位机能连续解析 TRACK。
- CRC 错误计数为 0。
- 最后能收到 STOP。
- `pan_speed`、`tilt_speed` 随测试方向变化。

### 5.2 阶段 B：接电机，验证方向

先低速测试：

```powershell
python tools/gimbal/test_serial.py --port COM3 --mode pan --max-speed 100 --cycles 2
python tools/gimbal/test_serial.py --port COM3 --mode tilt --max-speed 100 --cycles 2
```

方向判断：

| 测试点 | 上位机命令含义 | 期望云台动作 |
| --- | --- | --- |
| pan right | 目标在画面右侧 | 云台向右追 |
| pan left | 目标在画面左侧 | 云台向左追 |
| tilt down | 目标在画面下方 | 云台向下追 |
| tilt up | 目标在画面上方 | 云台向上追 |

如果方向反了：

- pan 反了：实时运行时加 `--gimbal-invert-pan`。
- tilt 反了：实时运行时加 `--gimbal-invert-tilt`。

测试 STOP：

```powershell
python tools/gimbal/test_serial.py --port COM3 --mode stop
```

期望：云台立即停。

### 5.3 阶段 C：上位机 camera tracking 闭环

确认方向正确后，启动实时 tracking：

```powershell
python lock_target_realtime.py --camera 0 --gimbal-port COM3 --gimbal-baud 115200 --gimbal-max-speed 150 --gimbal-command-rate 20
```

如果方向反了：

```powershell
python lock_target_realtime.py --camera 0 --gimbal-port COM3 --gimbal-invert-pan --gimbal-invert-tilt --gimbal-max-speed 150
```

初次上机建议：

- `--gimbal-max-speed` 从 100 或 150 开始。
- 不要一开始用 500。
- 先让目标缓慢左右移动，观察画面中心误差是否变小。

## 6. 闭环通过标准

### 6.1 协议层通过标准

- 下位机能稳定同步帧头。
- CRC 校验通过率接近 100%。
- TRACK payload 字段解析正确。
- STOP 能立即清零速度。
- 上位机断开或停止发送后，下位机 300 ms 内自动停机。

### 6.2 控制方向通过标准

- 目标在画面右侧时，云台向右追。
- 目标在画面左侧时，云台向左追。
- 目标在画面下方时，云台向下追。
- 目标在画面上方时，云台向上追。
- 目标回到死区内时，速度变 0。

### 6.3 tracking 闭环通过标准

观察实时画面和保存的 frame_metrics：

- `control_distance_to_center` 应该整体下降或维持在死区附近。
- `control_active` 不应一直高频抖动。
- LOST / SEARCHING 时云台应停止。
- HOLD 阶段是否继续动要谨慎观察；如果 HOLD 中使用 HEAD_PROXY 导致误动，后续可增加只允许 FACE_LOCK 控制的安全模式。

## 7. 常见问题排查

### 7.1 下位机收不到数据

检查：

- COM 口是否正确。
- TX/RX 是否交叉。
- GND 是否共地。
- 波特率是否一致。
- 串口是否被其他软件占用。

### 7.2 能收到字节但解析失败

检查：

- 是否按 little-endian 解析。
- CRC 是否只覆盖 version 到 payload，不包含 header。
- payload_len 是否按 1 字节读取。
- `TrackPayload` 是否被编译器填充对齐；C 里要使用 pack。

### 7.3 云台方向反了

不用改固件，优先通过上位机参数处理：

- `--gimbal-invert-pan`
- `--gimbal-invert-tilt`

### 7.4 云台震荡

先降低：

- `--gimbal-max-speed`
- `--gimbal-pan-gain`
- `--gimbal-tilt-gain`

再考虑加大：

- `--control-deadband`
- `--control-alpha`

### 7.5 目标丢失后云台还在动

下位机必须实现超时 STOP。上位机也会发送 STOP，但闭环安全不能只依赖上位机正常退出。

## 8. 建议的首次联调顺序

1. 下位机只打印解析结果，不驱动电机。
2. PC 运行 `python tools/gimbal/test_serial.py --port COM3 --mode box --cycles 1`。
3. 确认 TRACK / STOP / CRC 全部正确。
4. 接电机低速运行 pan / tilt 测试。
5. 修正方向。
6. 运行 `lock_target_realtime.py`，先用低 `gimbal-max-speed`。
7. 记录一次 realtime summary 和 frame_metrics。
8. 根据误差和抖动再调 `gimbal_max_speed`、`gimbal_pan_gain`、`gimbal_tilt_gain`、`control_deadband`。
