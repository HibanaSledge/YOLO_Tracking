from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gimbal.serial_client import GimbalSerialClient, GimbalSerialConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send deterministic gimbal serial commands for lower-controller validation.")
    parser.add_argument("--port", default=None, help="Serial port, e.g. COM3.")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baudrate.")
    parser.add_argument("--dry-run", action="store_true", help="Build commands without opening a real serial port.")
    parser.add_argument("--rate", type=float, default=10.0, help="Command rate in Hz.")
    parser.add_argument("--max-speed", type=int, default=500, help="Maximum speed command.")
    parser.add_argument("--pan-gain", type=float, default=0.8, help="Pan gain.")
    parser.add_argument("--tilt-gain", type=float, default=0.8, help="Tilt gain.")
    parser.add_argument("--invert-pan", action="store_true", help="Invert pan command.")
    parser.add_argument("--invert-tilt", action="store_true", help="Invert tilt command.")
    parser.add_argument("--mode", choices=["center", "pan", "tilt", "box", "stop"], default="box", help="Validation pattern.")
    parser.add_argument("--cycles", type=int, default=2, help="Number of pattern cycles.")
    parser.add_argument("--hold-sec", type=float, default=1.0, help="Hold duration for each test point.")
    return parser.parse_args()


def make_metric(frame_index: int, dx: float, dy: float, active: bool = True) -> dict:
    return {
        "frame_index": frame_index,
        "visible": True,
        "state": "TRACKING",
        "frame_center": {"x": 640.0, "y": 360.0},
        "filtered_target_center": {"x": 640.0 + dx, "y": 360.0 + dy},
        "control_offset": {"dx": dx, "dy": dy},
        "control_distance_to_center": (dx * dx + dy * dy) ** 0.5,
        "control_active": active,
        "deadband_active": not active,
    }


def pattern_points(mode: str) -> list[tuple[float, float, bool, str]]:
    if mode == "center":
        return [(0.0, 0.0, False, "center idle")]
    if mode == "pan":
        return [(240.0, 0.0, True, "pan right"), (-240.0, 0.0, True, "pan left")]
    if mode == "tilt":
        return [(0.0, 160.0, True, "tilt down"), (0.0, -160.0, True, "tilt up")]
    if mode == "stop":
        return []
    return [
        (240.0, 0.0, True, "pan right"),
        (0.0, 160.0, True, "tilt down"),
        (-240.0, 0.0, True, "pan left"),
        (0.0, -160.0, True, "tilt up"),
        (0.0, 0.0, False, "center idle"),
    ]


def main() -> None:
    args = parse_args()
    client = GimbalSerialClient(
        GimbalSerialConfig(
            port=args.port,
            baudrate=args.baud,
            dry_run=args.dry_run,
            command_rate_hz=args.rate,
            max_speed=args.max_speed,
            pan_gain=args.pan_gain,
            tilt_gain=args.tilt_gain,
            invert_pan=args.invert_pan,
            invert_tilt=args.invert_tilt,
        )
    )
    if not client.enabled:
        raise RuntimeError(f"Gimbal serial client is not enabled: {client.summary()}")

    frame_index = 0
    try:
        if args.mode == "stop":
            print(client.send_stop(reason="LOST", min_interval_sec=0.0))
            return

        interval = 1.0 / max(args.rate, 1.0)
        repeats = max(1, int(args.hold_sec / interval))
        for _ in range(args.cycles):
            for dx, dy, active, label in pattern_points(args.mode):
                print(f"pattern: {label} dx={dx} dy={dy} active={active}")
                for _ in range(repeats):
                    frame_index += 1
                    command = client.send_metric(make_metric(frame_index, dx, dy, active))
                    if command is not None:
                        print(command)
                    time.sleep(interval)
        print(client.send_stop(reason="LOST", min_interval_sec=0.0))
    finally:
        client.close()
        print(client.summary())


if __name__ == "__main__":
    main()
