from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gimbal.serial_client import GimbalSerialClient, GimbalSerialConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run gimbal protocol/closed-loop validation and generate report figures.")
    parser.add_argument("--port", default=None, help="Optional real serial port, e.g. COM3. If omitted, dry-run is used.")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run even if --port is provided.")
    parser.add_argument("--command-rate", type=float, default=20.0)
    parser.add_argument("--max-speed", type=int, default=150)
    parser.add_argument("--pan-gain", type=float, default=0.8)
    parser.add_argument("--tilt-gain", type=float, default=0.8)
    parser.add_argument("--invert-pan", action="store_true")
    parser.add_argument("--invert-tilt", action="store_true")
    parser.add_argument("--project", default="runs/gimbal_closed_loop_validation")
    parser.add_argument("--name", default="protocol_dry_run")
    return parser.parse_args()


def make_metric(frame_index: int, dx: float, dy: float, active: bool = True, state: str = "TRACKING") -> dict:
    return {
        "frame_index": frame_index,
        "visible": state not in {"SEARCHING", "LOST"},
        "state": state,
        "lock_mode": "FACE_LOCK" if state == "TRACKING" else state,
        "frame_center": {"x": 640.0, "y": 360.0},
        "filtered_target_center": None if state in {"SEARCHING", "LOST"} else {"x": 640.0 + dx, "y": 360.0 + dy},
        "control_offset": None if state in {"SEARCHING", "LOST"} else {"dx": dx, "dy": dy},
        "control_distance_to_center": None if state in {"SEARCHING", "LOST"} else math.sqrt(dx * dx + dy * dy),
        "control_active": active and state in {"TRACKING", "REACQUIRE", "HOLD"},
        "deadband_active": not active,
    }


def validation_sequence() -> list[tuple[str, float, float, bool, str]]:
    points: list[tuple[str, float, float, bool, str]] = []
    for _ in range(6):
        points.append(("SEARCHING stop", 0.0, 0.0, False, "SEARCHING"))
    for label, dx, dy in [
        ("right", 260.0, 0.0),
        ("right_near", 120.0, 0.0),
        ("center", 0.0, 0.0),
        ("down", 0.0, 180.0),
        ("down_near", 0.0, 80.0),
        ("center", 0.0, 0.0),
        ("left", -260.0, 0.0),
        ("left_near", -120.0, 0.0),
        ("center", 0.0, 0.0),
        ("up", 0.0, -180.0),
        ("up_near", 0.0, -80.0),
        ("center", 0.0, 0.0),
    ]:
        active = abs(dx) > 12 or abs(dy) > 12
        repeat = 8 if active else 5
        for _ in range(repeat):
            points.append((label, dx, dy, active, "TRACKING"))
    for _ in range(6):
        points.append(("LOST stop", 0.0, 0.0, False, "LOST"))
    return points


def run_validation(args: argparse.Namespace, run_dir: Path) -> dict:
    use_dry_run = args.dry_run or not args.port
    client = GimbalSerialClient(
        GimbalSerialConfig(
            port=args.port,
            baudrate=args.baud,
            dry_run=use_dry_run,
            command_rate_hz=args.command_rate,
            max_speed=args.max_speed,
            pan_gain=args.pan_gain,
            tilt_gain=args.tilt_gain,
            invert_pan=args.invert_pan,
            invert_tilt=args.invert_tilt,
        )
    )
    if not client.enabled:
        raise RuntimeError(f"Gimbal client is not enabled: {client.summary()}")

    rows: list[dict] = []
    sequence = validation_sequence()
    try:
        for index, (label, dx, dy, active, state) in enumerate(sequence, start=1):
            metric = make_metric(index, dx, dy, active, state)
            command = client.send_metric(metric)
            if command is None:
                command = {"sent": False, "msg_type": "RATE_LIMIT", "state": state, "pan_speed": 0, "tilt_speed": 0}
            distance = metric.get("control_distance_to_center")
            rows.append(
                {
                    "frame_index": index,
                    "label": label,
                    "state": state,
                    "dx_px": dx,
                    "dy_px": dy,
                    "distance_px": 0.0 if distance is None else float(distance),
                    "control_active": metric["control_active"],
                    "deadband_active": metric["deadband_active"],
                    "msg_type": command.get("msg_type"),
                    "sent": bool(command.get("sent", False)),
                    "pan_speed": int(command.get("pan_speed", 0)),
                    "tilt_speed": int(command.get("tilt_speed", 0)),
                    "flags": int(command.get("flags", 0) or 0),
                }
            )
            time.sleep(1.0 / max(args.command_rate, 1.0))
        stop = client.send_stop(reason="LOST", min_interval_sec=0.0)
        rows.append(
            {
                "frame_index": len(rows) + 1,
                "label": "explicit STOP",
                "state": "LOST",
                "dx_px": 0.0,
                "dy_px": 0.0,
                "distance_px": 0.0,
                "control_active": False,
                "deadband_active": True,
                "msg_type": None if stop is None else stop.get("msg_type"),
                "sent": False if stop is None else bool(stop.get("sent", False)),
                "pan_speed": 0,
                "tilt_speed": 0,
                "flags": 0,
            }
        )
    finally:
        client.close()

    summary = {
        "run_dir": str(run_dir),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "dry_run" if use_dry_run else "serial_send",
        "serial": client.summary(),
        "total_rows": len(rows),
        "track_packets": sum(1 for row in rows if row["msg_type"] == "TRACK"),
        "stop_packets": sum(1 for row in rows if row["msg_type"] == "STOP"),
        "sent_packets_recorded": sum(1 for row in rows if row["sent"]),
        "failed_packets": client.failed_packets,
        "direction_checks": direction_checks(rows),
        "hardware_closed_loop_completed": bool(args.port and not use_dry_run),
        "evidence_gap": None if args.port and not use_dry_run else "未连接可识别的下位机反馈/真实云台画面闭环；本次为上位机协议 dry-run 验证。",
    }
    write_outputs(run_dir, rows, summary)
    return summary


def direction_checks(rows: list[dict]) -> dict:
    checks = {
        "right_pan_positive": any(row["dx_px"] > 0 and row["pan_speed"] > 0 for row in rows),
        "left_pan_negative": any(row["dx_px"] < 0 and row["pan_speed"] < 0 for row in rows),
        "down_tilt_positive": any(row["dy_px"] > 0 and row["tilt_speed"] > 0 for row in rows),
        "up_tilt_negative": any(row["dy_px"] < 0 and row["tilt_speed"] < 0 for row in rows),
        "center_zero_speed": any(row["label"] == "center" and row["pan_speed"] == 0 and row["tilt_speed"] == 0 for row in rows),
        "lost_stop": any(row["state"] == "LOST" and row["msg_type"] == "STOP" for row in rows),
    }
    checks["all_passed"] = all(checks.values())
    return checks


def write_outputs(run_dir: Path, rows: list[dict], summary: dict) -> None:
    (run_dir / "validation_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    csv_path = run_dir / "validation_commands.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    plot_command_timeseries(run_dir, rows)
    plot_offset_speed_map(run_dir, rows)
    plot_validation_summary(run_dir, summary)
    write_report(run_dir, summary)


def plot_command_timeseries(run_dir: Path, rows: list[dict]) -> None:
    x = [row["frame_index"] for row in rows]
    pan = [row["pan_speed"] for row in rows]
    tilt = [row["tilt_speed"] for row in rows]
    distance = [row["distance_px"] for row in rows]
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    axes[0].plot(x, pan, label="pan_speed", color="#1f77b4")
    axes[0].plot(x, tilt, label="tilt_speed", color="#ff7f0e")
    axes[0].axhline(0, color="black", linewidth=0.8)
    axes[0].set_ylabel("speed command")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    axes[1].plot(x, distance, label="distance_px", color="#2ca02c")
    axes[1].set_xlabel("frame index")
    axes[1].set_ylabel("offset distance (px)")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    fig.suptitle("Gimbal command time series")
    fig.tight_layout()
    fig.savefig(run_dir / "command_timeseries.png", dpi=150)
    plt.close(fig)


def plot_offset_speed_map(run_dir: Path, rows: list[dict]) -> None:
    active_rows = [row for row in rows if row["msg_type"] == "TRACK"]
    dx = [row["dx_px"] for row in active_rows]
    dy = [row["dy_px"] for row in active_rows]
    pan = [row["pan_speed"] for row in active_rows]
    tilt = [row["tilt_speed"] for row in active_rows]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    axes[0].scatter(dx, pan, c=pan, cmap="coolwarm", s=45)
    axes[0].axhline(0, color="black", linewidth=0.8)
    axes[0].axvline(0, color="black", linewidth=0.8)
    axes[0].set_xlabel("dx_px")
    axes[0].set_ylabel("pan_speed")
    axes[0].set_title("x offset -> pan")
    axes[0].grid(True, alpha=0.3)
    axes[1].scatter(dy, tilt, c=tilt, cmap="coolwarm", s=45)
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].axvline(0, color="black", linewidth=0.8)
    axes[1].set_xlabel("dy_px")
    axes[1].set_ylabel("tilt_speed")
    axes[1].set_title("y offset -> tilt")
    axes[1].grid(True, alpha=0.3)
    fig.suptitle("Offset to speed mapping")
    fig.tight_layout()
    fig.savefig(run_dir / "offset_speed_mapping.png", dpi=150)
    plt.close(fig)


def plot_validation_summary(run_dir: Path, summary: dict) -> None:
    checks = summary["direction_checks"]
    labels = [key for key in checks if key != "all_passed"]
    values = [1 if checks[key] else 0 for key in labels]
    colors = ["#2ca02c" if value else "#d62728" for value in values]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.barh(labels, values, color=colors)
    ax.set_xlim(0, 1.1)
    ax.set_xlabel("pass = 1")
    ax.set_title("Validation checks")
    for i, value in enumerate(values):
        ax.text(1.02, i, "PASS" if value else "FAIL", va="center")
    fig.tight_layout()
    fig.savefig(run_dir / "validation_checks.png", dpi=150)
    plt.close(fig)


def write_report(run_dir: Path, summary: dict) -> None:
    checks = summary["direction_checks"]
    lines = [
        "# 云台闭环验证报告",
        "",
        "## 1. 验证结论",
        "",
        f"- 验证模式：{summary['mode']}",
        f"- TRACK 包数量：{summary['track_packets']}",
        f"- STOP 包数量：{summary['stop_packets']}",
        f"- 记录到的成功发送包：{summary['sent_packets_recorded']}",
        f"- 失败发送包：{summary['failed_packets']}",
        f"- 方向与 STOP 检查：{'通过' if checks['all_passed'] else '未通过'}",
        f"- 真实硬件闭环：{'已执行串口发送' if summary['hardware_closed_loop_completed'] else '未完成'}",
        "",
    ]
    if summary.get("evidence_gap"):
        lines += ["## 2. 证据缺口", "", f"- {summary['evidence_gap']}", ""]
    lines += [
        "## 3. 检查项",
        "",
        "| 检查项 | 结果 |",
        "| --- | --- |",
    ]
    for key, value in checks.items():
        if key == "all_passed":
            continue
        lines.append(f"| {key} | {'PASS' if value else 'FAIL'} |")
    lines += [
        "",
        "## 4. 可视化",
        "",
        "![命令时间序列](command_timeseries.png)",
        "",
        "![偏移到速度映射](offset_speed_mapping.png)",
        "",
        "![验证检查项](validation_checks.png)",
        "",
        "## 5. 解读",
        "",
        "- `command_timeseries.png` 用于观察 pan/tilt 命令是否随模拟目标偏移变化，并在居中或 LOST 时归零。",
        "- `offset_speed_mapping.png` 用于确认 dx 与 pan、dy 与 tilt 的符号关系是否正确。",
        "- `validation_checks.png` 汇总方向、居中归零、LOST STOP 等基础检查是否通过。",
        "",
        "## 6. 下一步真实闭环要求",
        "",
        "1. 接入真实下位机串口，不使用 dry-run。",
        "2. 下位机打印解析日志，确认 CRC、TRACK、STOP 正常。",
        "3. 低速接入电机，确认 pan/tilt 方向。",
        "4. 启动 `lock_target_realtime.py --gimbal-port COMx`，观察 `control_distance_to_center` 是否随云台运动下降。",
    ]
    (run_dir / "validation_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = ROOT / args.project / f"{args.name}_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    summary = run_validation(args, run_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
