# QGimbal 与本项目集成说明

## 1. 结论

下位机文档 `QGimbal_Serial_Protocol.md` 描述的是当前真实 MCU 固件协议。本项目原先的 `vision-v1` 协议是上位机侧自定义协议，不能直接被该 MCU 解析。

当前项目已在 `gimbal/serial_client.py` 中支持两种协议：

| 协议 | 参数 | 用途 |
| --- | --- | --- |
| QGimbal | `--gimbal-protocol qgimbal` | 对接真实下位机，默认协议 |
| vision-v1 | `--gimbal-protocol vision-v1` | 保留旧的 `AA 55 + CRC16` 调试协议 |

## 2. QGimbal 协议关键点

### 上位机发送控制帧

本项目向 MCU 发送 12 字节控制帧：

```text
<float yaw_speed_rpm><float pitch_speed_rpm><uint8 laser><uint8 enabled><uint8 stability><uint8 checksum>
```

- 串口：`1152000, 8N1, no flow control`。
- 字节序：little-endian。
- 校验：`sum(byte[0..10]) & 0xFF`。
- 速度单位：rpm。
- MCU 会把速度限幅到 `[-50, 50]` rpm。
- 控制位三态：`0=关闭`，`1=开启`，`0xFF=不操作`。

### MCU 遥测帧

MCU 会以约 1kHz 发送 36 字节遥测帧：

```text
AA FF + padding + imu/motor floats + laser/enabled/stability + checksum
```

本次集成已提供 `parse_qgimbal_telemetry_frame()`，但主算法当前仍只使用视觉偏移下发速度，尚未把遥测闭环接入控制律。

## 3. 视觉偏移到云台速度的映射

本项目仍使用 `frame_metric()` 产生的 `control_offset`：

- `dx > 0`：目标在画面右侧，生成正 `yaw_speed_rpm`。
- `dy > 0`：目标在画面下方，生成正 `pitch_speed_rpm`。
- 如果实际云台方向相反，用 `--gimbal-invert-pan` 或 `--gimbal-invert-tilt` 反向。

速度计算：

```text
yaw_speed_rpm   = clamp(dx / half_width  * gimbal_max_speed * gimbal_pan_gain,  -50, 50)
pitch_speed_rpm = clamp(dy / half_height * gimbal_max_speed * gimbal_tilt_gain, -50, 50)
```

默认：

- `--gimbal-max-speed 50`
- `--gimbal-pan-gain 0.8`
- `--gimbal-tilt-gain 0.8`
- `--gimbal-command-rate 20`

这表示项目默认最多发送约 `±40 rpm`，避免一开始就打满 MCU 的 `±50 rpm` 限幅。

## 4. 推荐运行方式

### 4.1 只验证打包，不打开串口

```powershell
C:/Users/Stuart.Cai/AppData/Local/Programs/Python/Python310/python.exe lock_target_realtime.py --camera 0 --gimbal-dry-run
```

### 4.2 VOFA / 虚拟串口观察 HEX 文本

Python 写 COM10，VOFA 读 COM11：

```powershell
C:/Users/Stuart.Cai/AppData/Local/Programs/Python/Python310/python.exe lock_target_realtime.py --camera 0 --gimbal-mirror-port COM10 --gimbal-mirror-as-hex-text
```

QGimbal 控制帧没有帧头，VOFA 中看到的每行应为 12 字节 HEX，例如：

```text
00 00 00 00 00 00 00 00 FF 01 FF FF
```

### 4.3 连接真实下位机

确认 COM4 未被 VOFA 或其他串口工具占用后：

```powershell
C:/Users/Stuart.Cai/AppData/Local/Programs/Python/Python310/python.exe lock_target_realtime.py --camera 0 --gimbal-port COM4 --gimbal-baud 1152000 --gimbal-command-rate 20 --gimbal-max-speed 30 --gimbal-pan-gain 0.5 --gimbal-tilt-gain 0.5
```

首次上机建议从更小速度开始：

- `--gimbal-max-speed 20` 或 `30`
- `--gimbal-pan-gain 0.3~0.5`
- `--gimbal-tilt-gain 0.3~0.5`

如果方向相反：

```powershell
--gimbal-invert-pan
--gimbal-invert-tilt
```

### 4.4 同时真实下发和 VOFA 镜像

```powershell
C:/Users/Stuart.Cai/AppData/Local/Programs/Python/Python310/python.exe lock_target_realtime.py --camera 0 --gimbal-port COM4 --gimbal-baud 1152000 --gimbal-mirror-port COM10 --gimbal-mirror-as-hex-text
```

注意：VOFA 不能同时打开 COM4。真实下位机走 COM4，观察镜像走 COM10/COM11。

## 5. 安全建议

1. QGimbal MCU 没有 ACK 和重传，也没有超时保护；程序退出时本项目会发送 0 速度帧。
2. 真实上机前先架空云台或断开负载，确认方向与速度范围。
3. 如果云台失控，立即停止 Python 程序并断开使能/电源。
4. 稳定前不要开启激光；默认 `--gimbal-laser keep` 不主动改变激光状态。
5. 默认 `--gimbal-enabled on` 会发送 `enabled=1`，确保 MCU 能执行速度命令；如只想保持 MCU 当前使能状态，使用 `--gimbal-enabled keep`。

## 6. 仍未完成的闭环项

- 尚未把 36 字节遥测帧接入实时 UI 或日志。
- 尚未用遥测角度做 PID/前馈闭环，当前控制仍是视觉偏移到速度的开环比例控制。
- 尚未做真实下位机长时间闭环验证。