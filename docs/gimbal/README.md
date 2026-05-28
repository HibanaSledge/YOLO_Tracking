# 云台 tracking 文件索引

## 代码模块

| 文件 | 用途 |
| --- | --- |
| `gimbal/serial_client.py` | 上位机串口协议打包、CRC16、TRACK/STOP 发送、速度映射。 |
| `gimbal/__init__.py` | 云台模块导出入口。 |

## 联调脚本

| 文件 | 用途 |
| --- | --- |
| `tools/gimbal/test_serial.py` | 不跑 camera，只发送固定方向命令，用于下位机协议、方向和 STOP 验证。 |
| `tools/gimbal/run_closed_loop_validation.py` | 运行协议 dry-run 或真实串口验证，并生成 CSV、JSON、报告和 PNG 图。 |

## 文档

| 文件 | 用途 |
| --- | --- |
| `docs/gimbal/serial_protocol.md` | 云台串口通信协议 v1。 |
| `docs/gimbal/closed_loop_validation.md` | 下位机固件接入和闭环验证步骤。 |

## 验证输出

| 目录 | 用途 |
| --- | --- |
| `runs/gimbal_closed_loop_validation/` | 保存每次云台验证的报告、图片、CSV、JSON。 |

## 常用命令

协议方向测试：

```powershell
python tools/gimbal/test_serial.py --port COM3 --mode box --cycles 1
```

生成验证报告和图片：

```powershell
python tools/gimbal/run_closed_loop_validation.py --dry-run
```

真实串口闭环验证：

```powershell
python tools/gimbal/run_closed_loop_validation.py --port COM3
```

实时 camera tracking 接云台：

```powershell
python lock_target_realtime.py --camera 0 --gimbal-port COM3 --gimbal-baud 115200 --gimbal-max-speed 150
```
