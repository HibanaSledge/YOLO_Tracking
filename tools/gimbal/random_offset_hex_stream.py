from __future__ import annotations

import argparse
import random
import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gimbal.serial_client import MSG_STOP, MSG_TRACK, STATE_CODES, build_frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate random gimbal TRACK commands and print/send complete serial HEX frames."
    )
    parser.add_argument("--list-ports", action="store_true", help="List available serial ports and exit.")
    parser.add_argument("--port", default=None, help="Serial port, for example COM4. If omitted, only prints HEX frames.")
    parser.add_argument("--mirror-port", action="append", default=[], help="Mirror every frame to another serial port, for example COM10 for VOFA on a virtual COM pair. Can be used multiple times.")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baudrate.")
    parser.add_argument("--mirror-baud", type=int, default=None, help="Mirror serial baudrate. Defaults to --baud.")
    parser.add_argument("--rate", type=float, default=20.0, help="Frame send/print rate in Hz.")
    parser.add_argument("--count", type=int, default=20, help="Number of TRACK frames to generate. Use 0 for infinite.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for repeatable offsets.")
    parser.add_argument("--half-width", type=float, default=360.0, help="Image half width / frame_center.x in pixels.")
    parser.add_argument("--half-height", type=float, default=640.0, help="Image half height / frame_center.y in pixels.")
    parser.add_argument("--max-offset-x", type=int, default=320, help="Maximum absolute random dx in pixels.")
    parser.add_argument("--max-offset-y", type=int, default=560, help="Maximum absolute random dy in pixels.")
    parser.add_argument("--deadband", type=float, default=12.0, help="Deadband radius in pixels.")
    parser.add_argument("--max-speed", type=int, default=500, help="Maximum absolute pan/tilt speed.")
    parser.add_argument("--pan-gain", type=float, default=0.8, help="Pan gain from normalized x offset.")
    parser.add_argument("--tilt-gain", type=float, default=0.8, help="Tilt gain from normalized y offset.")
    parser.add_argument("--invert-pan", action="store_true", help="Invert pan speed direction.")
    parser.add_argument("--invert-tilt", action="store_true", help="Invert tilt speed direction.")
    parser.add_argument("--include-stop", action="store_true", help="Send/print one STOP frame after TRACK frames.")
    parser.add_argument("--hex-only", action="store_true", help="Only print frame HEX, one frame per line.")
    parser.add_argument("--send-hex-text", action="store_true", help="Send ASCII HEX text plus newline instead of binary bytes.")
    parser.add_argument("--mirror-as-hex-text", action="store_true", help="Send ASCII HEX text plus newline to mirror ports only. Keep main port binary unless --send-hex-text is also set.")
    return parser.parse_args()


def clamp_int(value: float, lower: int, upper: int) -> int:
    return int(max(lower, min(upper, round(value))))


def spaced_hex(data: bytes) -> str:
    return data.hex(" ").upper()


def build_track_payload(
    *,
    frame_index: int,
    dx: int,
    dy: int,
    half_width: float,
    half_height: float,
    deadband: float,
    max_speed: int,
    pan_gain: float,
    tilt_gain: float,
    invert_pan: bool,
    invert_tilt: bool,
) -> tuple[bytes, dict]:
    distance = (float(dx) * float(dx) + float(dy) * float(dy)) ** 0.5
    deadband_active = distance <= deadband
    control_active = not deadband_active

    pan = 0.0 if not control_active else float(dx) / max(half_width, 1.0) * max_speed * pan_gain
    tilt = 0.0 if not control_active else float(dy) / max(half_height, 1.0) * max_speed * tilt_gain
    if invert_pan:
        pan = -pan
    if invert_tilt:
        tilt = -tilt

    pan_speed = clamp_int(pan, -max_speed, max_speed)
    tilt_speed = clamp_int(tilt, -max_speed, max_speed)
    dx_px = clamp_int(dx, -32768, 32767)
    dy_px = clamp_int(dy, -32768, 32767)
    distance_px = clamp_int(distance, 0, 65535)

    flags = 0x02 | 0x08  # visible + filtered_center_valid
    if control_active:
        flags |= 0x01
    if deadband_active:
        flags |= 0x04

    payload = struct.pack(
        "<BBIhhhhH",
        STATE_CODES["TRACKING"],
        flags,
        frame_index & 0xFFFFFFFF,
        dx_px,
        dy_px,
        pan_speed,
        tilt_speed,
        distance_px,
    )
    info = {
        "frame_index": frame_index,
        "dx": dx_px,
        "dy": dy_px,
        "distance_px": distance_px,
        "control_active": control_active,
        "deadband_active": deadband_active,
        "flags": flags,
        "pan_speed": pan_speed,
        "tilt_speed": tilt_speed,
    }
    return payload, info


def open_serial(port: str | None, baud: int):
    if not port:
        return None
    import serial  # type: ignore

    return serial.Serial(port, baudrate=baud, timeout=0.02, write_timeout=0.02)


def open_serial_or_exit(port: str | None, baud: int, label: str):
    try:
        return open_serial(port, baud)
    except Exception as exc:
        message = str(exc)
        if port and ("PermissionError" in message or "Access is denied" in message or "拒绝访问" in message):
            raise SystemExit(
                f"Failed to open {label} {port}: access denied.\n"
                "Most likely another program is already using this COM port, such as VOFA, a serial monitor, "
                "Arduino IDE, another Python process, or the lower-controller debugger.\n"
                "Fix: close/disconnect that program first. For mirror mode, Python must open the writer side "
                "of the virtual COM pair, and VOFA must open the other side."
            ) from exc
        raise


def write_frame(serial_port, frame: bytes, hex_text: str, send_hex_text: bool) -> None:
    if serial_port is None:
        return
    if send_hex_text:
        serial_port.write((hex_text + "\n").encode("ascii"))
    else:
        serial_port.write(frame)


def list_serial_ports() -> None:
    try:
        from serial.tools import list_ports  # type: ignore
    except Exception as exc:
        raise RuntimeError("pyserial is required to list serial ports. Install it with: pip install pyserial") from exc

    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found.")
        return
    for port in ports:
        print(f"{port.device}\t{port.description}\t{port.hwid}")


def main() -> None:
    args = parse_args()
    if args.list_ports:
        list_serial_ports()
        return

    rng = random.Random(args.seed)
    serial_port = open_serial_or_exit(args.port, args.baud, "main port")
    mirror_baud = args.mirror_baud if args.mirror_baud is not None else args.baud
    mirror_ports = [open_serial_or_exit(port, mirror_baud, "mirror port") for port in args.mirror_port]
    interval = 1.0 / max(args.rate, 1.0)
    frame_index = 0
    sequence = 0

    try:
        while args.count <= 0 or frame_index < args.count:
            frame_index += 1
            sequence = (sequence + 1) & 0xFFFF
            dx = rng.randint(-abs(args.max_offset_x), abs(args.max_offset_x))
            dy = rng.randint(-abs(args.max_offset_y), abs(args.max_offset_y))
            payload, info = build_track_payload(
                frame_index=frame_index,
                dx=dx,
                dy=dy,
                half_width=args.half_width,
                half_height=args.half_height,
                deadband=args.deadband,
                max_speed=args.max_speed,
                pan_gain=args.pan_gain,
                tilt_gain=args.tilt_gain,
                invert_pan=args.invert_pan,
                invert_tilt=args.invert_tilt,
            )
            frame = build_frame(MSG_TRACK, sequence, payload)
            frame_hex = spaced_hex(frame)
            write_frame(serial_port, frame, frame_hex, args.send_hex_text)
            for mirror_port in mirror_ports:
                write_frame(mirror_port, frame, frame_hex, args.mirror_as_hex_text)

            if args.hex_only:
                print(frame_hex, flush=True)
            else:
                print(
                    " ".join(
                        [
                            f"seq={sequence}",
                            f"frame={frame_index}",
                            f"dx={info['dx']}",
                            f"dy={info['dy']}",
                            f"dist={info['distance_px']}",
                            f"active={int(info['control_active'])}",
                            f"flags=0x{info['flags']:02X}",
                            f"pan={info['pan_speed']}",
                            f"tilt={info['tilt_speed']}",
                            f"hex={frame_hex}",
                        ]
                    ),
                    flush=True,
                )
            time.sleep(interval)

        if args.include_stop:
            sequence = (sequence + 1) & 0xFFFF
            payload = struct.pack("<B", STATE_CODES["LOST"])
            frame = build_frame(MSG_STOP, sequence, payload)
            frame_hex = spaced_hex(frame)
            write_frame(serial_port, frame, frame_hex, args.send_hex_text)
            for mirror_port in mirror_ports:
                write_frame(mirror_port, frame, frame_hex, args.mirror_as_hex_text)
            print(frame_hex if args.hex_only else f"seq={sequence} stop=1 hex={frame_hex}", flush=True)
    finally:
        if serial_port is not None:
            serial_port.close()
        for mirror_port in mirror_ports:
            mirror_port.close()


if __name__ == "__main__":
    main()