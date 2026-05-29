from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from typing import Any

HEADER = b"\xAA\x55"
PROTOCOL_VERSION = 1
MSG_TRACK = 0x01
MSG_STOP = 0x02
MSG_HEARTBEAT = 0x03

STATE_CODES = {
    "SEARCHING": 0,
    "TRACKING": 1,
    "REACQUIRE": 2,
    "HOLD": 3,
    "LOST": 4,
}


def clamp_int(value: float, lower: int, upper: int) -> int:
    return int(max(lower, min(upper, round(value))))


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def build_frame(msg_type: int, sequence: int, payload: bytes = b"") -> bytes:
    if len(payload) > 255:
        raise ValueError("Gimbal serial payload must be <= 255 bytes")
    body = struct.pack("<BBHB", PROTOCOL_VERSION, msg_type & 0xFF, sequence & 0xFFFF, len(payload)) + payload
    checksum = crc16_modbus(body)
    return HEADER + body + struct.pack("<H", checksum)


@dataclass
class GimbalSerialConfig:
    port: str | None = None
    mirror_ports: list[str] | None = None
    baudrate: int = 115200
    mirror_baudrate: int | None = None
    timeout: float = 0.02
    dry_run: bool = False
    mirror_as_hex_text: bool = False
    command_rate_hz: float = 20.0
    max_speed: int = 500
    pan_gain: float = 0.8
    tilt_gain: float = 0.8
    invert_pan: bool = False
    invert_tilt: bool = False


class GimbalSerialClient:
    def __init__(self, config: GimbalSerialConfig) -> None:
        self.config = config
        self.mirror_ports = list(config.mirror_ports or [])
        self.enabled = bool(config.port) or bool(self.mirror_ports) or config.dry_run
        self.sequence = 0
        self.serial_port: Any | None = None
        self.mirror_serial_ports: list[Any] = []
        self.sent_packets = 0
        self.failed_packets = 0
        self.last_send_time = 0.0
        self.last_stop_time = 0.0
        self.open_error: str | None = None
        if self.enabled and not config.dry_run and config.port:
            self._open_serial()
        if not config.dry_run and self.mirror_ports:
            self._open_mirror_serials()

    @classmethod
    def from_args(cls, args: Any) -> "GimbalSerialClient":
        return cls(
            GimbalSerialConfig(
                port=getattr(args, "gimbal_port", None),
                mirror_ports=list(getattr(args, "gimbal_mirror_port", None) or []),
                baudrate=int(getattr(args, "gimbal_baud", 115200)),
                mirror_baudrate=getattr(args, "gimbal_mirror_baud", None),
                timeout=float(getattr(args, "gimbal_timeout", 0.02)),
                dry_run=bool(getattr(args, "gimbal_dry_run", False)),
                mirror_as_hex_text=bool(getattr(args, "gimbal_mirror_as_hex_text", False)),
                command_rate_hz=float(getattr(args, "gimbal_command_rate", 20.0)),
                max_speed=int(getattr(args, "gimbal_max_speed", 500)),
                pan_gain=float(getattr(args, "gimbal_pan_gain", 0.8)),
                tilt_gain=float(getattr(args, "gimbal_tilt_gain", 0.8)),
                invert_pan=bool(getattr(args, "gimbal_invert_pan", False)),
                invert_tilt=bool(getattr(args, "gimbal_invert_tilt", False)),
            )
        )

    def _open_serial(self) -> None:
        try:
            import serial  # type: ignore

            self.serial_port = serial.Serial(
                self.config.port,
                baudrate=self.config.baudrate,
                timeout=self.config.timeout,
                write_timeout=self.config.timeout,
            )
        except Exception as exc:  # pragma: no cover - depends on local serial hardware/package
            self.open_error = str(exc)
            self.enabled = bool(self.mirror_ports) or self.config.dry_run
            self.serial_port = None

    def _open_mirror_serials(self) -> None:
        try:
            import serial  # type: ignore

            mirror_baudrate = self.config.mirror_baudrate or self.config.baudrate
            for port in self.mirror_ports:
                self.mirror_serial_ports.append(
                    serial.Serial(
                        port,
                        baudrate=mirror_baudrate,
                        timeout=self.config.timeout,
                        write_timeout=self.config.timeout,
                    )
                )
        except Exception as exc:  # pragma: no cover - depends on local serial hardware/package
            self.open_error = str(exc)
            self.enabled = bool(self.serial_port) or self.config.dry_run
            for mirror_port in self.mirror_serial_ports:
                try:
                    mirror_port.close()
                except Exception:
                    pass
            self.mirror_serial_ports = []

    def _next_sequence(self) -> int:
        self.sequence = (self.sequence + 1) & 0xFFFF
        return self.sequence

    def _write_frame(self, msg_type: int, payload: bytes = b"") -> bool:
        if not self.enabled:
            return False
        frame = build_frame(msg_type, self._next_sequence(), payload)
        wrote_any = False
        try:
            if self.serial_port is not None:
                self.serial_port.write(frame)
                wrote_any = True
            for mirror_port in self.mirror_serial_ports:
                if self.config.mirror_as_hex_text:
                    mirror_port.write((frame.hex(" ").upper() + "\n").encode("ascii"))
                else:
                    mirror_port.write(frame)
                wrote_any = True
            if self.config.dry_run:
                wrote_any = True
            if wrote_any:
                self.sent_packets += 1
                return True
            return False
        except Exception as exc:  # pragma: no cover - depends on serial hardware
            self.failed_packets += 1
            self.open_error = str(exc)
            return False

    def send_stop(self, reason: str = "STOP", min_interval_sec: float = 0.5) -> dict | None:
        if not self.enabled:
            return None
        now = time.perf_counter()
        if now - self.last_stop_time < min_interval_sec:
            return None
        self.last_stop_time = now
        state_code = STATE_CODES.get(reason, STATE_CODES.get("LOST", 4))
        payload = struct.pack("<B", state_code)
        ok = self._write_frame(MSG_STOP, payload)
        return {
            "sent": ok,
            "msg_type": "STOP",
            "state": reason,
            "pan_speed": 0,
            "tilt_speed": 0,
        }

    def send_metric(self, metric: dict) -> dict | None:
        if not self.enabled:
            return None
        now = time.perf_counter()
        min_interval = 1.0 / max(self.config.command_rate_hz, 1.0)
        if now - self.last_send_time < min_interval:
            return None

        state = str(metric.get("state", "SEARCHING"))
        offset = metric.get("control_offset")
        frame_center = metric.get("frame_center")
        visible = bool(metric.get("visible", False))
        control_active = bool(metric.get("control_active", False))
        deadband_active = bool(metric.get("deadband_active", False))
        frame_index = int(metric.get("frame_index", 0) or 0)

        if not visible or offset is None or frame_center is None or state in {"SEARCHING", "LOST"}:
            return self.send_stop(reason=state)

        dx = float(offset.get("dx", 0.0))
        dy = float(offset.get("dy", 0.0))
        half_width = max(float(frame_center.get("x", 1.0)), 1.0)
        half_height = max(float(frame_center.get("y", 1.0)), 1.0)
        pan = dx / half_width * self.config.max_speed * self.config.pan_gain
        tilt = dy / half_height * self.config.max_speed * self.config.tilt_gain
        if self.config.invert_pan:
            pan = -pan
        if self.config.invert_tilt:
            tilt = -tilt
        if not control_active:
            pan = 0.0
            tilt = 0.0

        pan_speed = clamp_int(pan, -self.config.max_speed, self.config.max_speed)
        tilt_speed = clamp_int(tilt, -self.config.max_speed, self.config.max_speed)
        dx_px = clamp_int(dx, -32768, 32767)
        dy_px = clamp_int(dy, -32768, 32767)
        distance = clamp_int(float(metric.get("control_distance_to_center", 0.0) or 0.0), 0, 65535)
        flags = 0
        if control_active:
            flags |= 0x01
        if visible:
            flags |= 0x02
        if deadband_active:
            flags |= 0x04
        if metric.get("filtered_target_center") is not None:
            flags |= 0x08

        payload = struct.pack(
            "<BBIhhhhH",
            STATE_CODES.get(state, 0),
            flags,
            frame_index & 0xFFFFFFFF,
            dx_px,
            dy_px,
            pan_speed,
            tilt_speed,
            distance,
        )
        self.last_send_time = now
        ok = self._write_frame(MSG_TRACK, payload)
        return {
            "sent": ok,
            "msg_type": "TRACK",
            "state": state,
            "flags": flags,
            "pan_speed": pan_speed,
            "tilt_speed": tilt_speed,
            "dx_px": dx_px,
            "dy_px": dy_px,
            "distance_px": distance,
        }

    def close(self) -> None:
        if self.enabled:
            self.send_stop(reason="LOST", min_interval_sec=0.0)
        if self.serial_port is not None:
            try:
                self.serial_port.close()
            except Exception:  # pragma: no cover - depends on serial hardware
                pass
            self.serial_port = None
        for mirror_port in self.mirror_serial_ports:
            try:
                mirror_port.close()
            except Exception:  # pragma: no cover - depends on serial hardware
                pass
        self.mirror_serial_ports = []

    def summary(self) -> dict:
        return {
            "enabled": self.enabled,
            "port": self.config.port,
            "mirror_ports": self.mirror_ports,
            "baudrate": self.config.baudrate,
            "mirror_baudrate": self.config.mirror_baudrate or self.config.baudrate,
            "dry_run": self.config.dry_run,
            "mirror_as_hex_text": self.config.mirror_as_hex_text,
            "command_rate_hz": self.config.command_rate_hz,
            "max_speed": self.config.max_speed,
            "pan_gain": self.config.pan_gain,
            "tilt_gain": self.config.tilt_gain,
            "invert_pan": self.config.invert_pan,
            "invert_tilt": self.config.invert_tilt,
            "sent_packets": self.sent_packets,
            "failed_packets": self.failed_packets,
            "open_error": self.open_error,
        }
