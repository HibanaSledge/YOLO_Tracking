from __future__ import annotations

import platform
import statistics
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

try:
    import psutil
except ImportError:
    psutil = None

try:
    import torch
except ImportError:
    torch = None


def round_float(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def series_stats(values: list[float]) -> dict:
    if not values:
        return {
            "count": 0,
            "avg_ms": None,
            "min_ms": None,
            "max_ms": None,
            "median_ms": None,
        }
    ordered = sorted(float(v) for v in values)
    return {
        "count": len(ordered),
        "avg_ms": round_float(sum(ordered) / len(ordered)),
        "min_ms": round_float(ordered[0]),
        "max_ms": round_float(ordered[-1]),
        "median_ms": round_float(statistics.median(ordered)),
    }


@dataclass
class FramePerformance:
    frame_index: int
    source_frame_id: int | None = None
    dropped_frames_before: int | None = None
    stage_times_ms: dict[str, float] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    resources: dict[str, float | None] = field(default_factory=dict)


class PerformanceRecorder:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.process = psutil.Process() if psutil is not None else None
        if self.process is not None:
            self.process.cpu_percent(interval=None)
        if psutil is not None:
            psutil.cpu_percent(interval=None)
        self.start_time = time.perf_counter()
        self.frame_records: list[FramePerformance] = []
        self.current_frame: FramePerformance | None = None
        self.stage_samples_ms: dict[str, list[float]] = {}
        self.count_totals: dict[str, int] = {}
        self.count_max: dict[str, int] = {}
        self.resource_samples: dict[str, list[float]] = {}

    def start_frame(self, frame_index: int, source_frame_id: int | None = None, dropped_frames_before: int | None = None) -> None:
        self.current_frame = FramePerformance(
            frame_index=frame_index,
            source_frame_id=source_frame_id,
            dropped_frames_before=dropped_frames_before,
        )

    def end_frame(self) -> None:
        if self.current_frame is None:
            return
        self.frame_records.append(self.current_frame)
        self.current_frame = None

    def add_stage_time(self, name: str, elapsed_ms: float) -> None:
        if self.current_frame is not None:
            self.current_frame.stage_times_ms[name] = self.current_frame.stage_times_ms.get(name, 0.0) + float(elapsed_ms)
        self.stage_samples_ms.setdefault(name, []).append(float(elapsed_ms))

    def increment(self, name: str, value: int = 1) -> None:
        self.count_totals[name] = self.count_totals.get(name, 0) + value
        self.count_max[name] = max(self.count_max.get(name, 0), value)
        if self.current_frame is not None:
            self.current_frame.counts[name] = self.current_frame.counts.get(name, 0) + value

    @contextmanager
    def time_stage(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.add_stage_time(name, (time.perf_counter() - start) * 1000.0)

    def sample_resources(self) -> None:
        sample: dict[str, float | None] = {}
        if psutil is not None and self.process is not None:
            sample["system_cpu_percent"] = float(psutil.cpu_percent(interval=None))
            sample["process_cpu_percent"] = float(self.process.cpu_percent(interval=None))
            sample["process_rss_mb"] = self.process.memory_info().rss / (1024 * 1024)
        if torch is not None and torch.cuda.is_available():
            sample["gpu_memory_allocated_mb"] = float(torch.cuda.memory_allocated() / (1024 * 1024))
            sample["gpu_memory_reserved_mb"] = float(torch.cuda.memory_reserved() / (1024 * 1024))
            sample["gpu_memory_max_allocated_mb"] = float(torch.cuda.max_memory_allocated() / (1024 * 1024))
        if self.current_frame is not None:
            self.current_frame.resources.update({key: round_float(value) for key, value in sample.items()})
        for key, value in sample.items():
            if value is not None:
                self.resource_samples.setdefault(key, []).append(float(value))

    def build_report(self, extra_summary: dict | None = None) -> dict:
        total_duration_sec = time.perf_counter() - self.start_time
        report = {
            "mode": self.mode,
            "runtime": {
                "total_duration_sec": round_float(total_duration_sec, 3),
                "processed_frames": len(self.frame_records),
                "effective_fps": round_float(len(self.frame_records) / total_duration_sec if total_duration_sec > 0 else 0.0, 3),
                "platform": platform.platform(),
                "python_version": sys.version.split()[0],
                "psutil_available": psutil is not None,
                "torch_available": torch is not None,
                "cuda_available": bool(torch is not None and torch.cuda.is_available()),
                "cuda_device_name": torch.cuda.get_device_name(0) if torch is not None and torch.cuda.is_available() else None,
            },
            "stages": {name: series_stats(values) for name, values in self.stage_samples_ms.items()},
            "counts": {
                name: {
                    "total": total,
                    "avg_per_frame": round_float(total / len(self.frame_records)) if self.frame_records else None,
                    "max_per_frame": self.count_max.get(name, 0),
                }
                for name, total in self.count_totals.items()
            },
            "resources": {
                name: {
                    "avg": round_float(sum(values) / len(values)),
                    "max": round_float(max(values)),
                }
                for name, values in self.resource_samples.items()
                if values
            },
            "frame_records": [
                {
                    "frame_index": record.frame_index,
                    "source_frame_id": record.source_frame_id,
                    "dropped_frames_before": record.dropped_frames_before,
                    "stage_times_ms": {key: round_float(value) for key, value in record.stage_times_ms.items()},
                    "counts": record.counts,
                    "resources": record.resources,
                }
                for record in self.frame_records
            ],
        }
        if extra_summary is not None:
            report["summary"] = extra_summary
        return report


class NullPerformanceRecorder:
    def __init__(self, mode: str) -> None:
        self.mode = mode

    def start_frame(self, frame_index: int, source_frame_id: int | None = None, dropped_frames_before: int | None = None) -> None:
        return None

    def end_frame(self) -> None:
        return None

    def add_stage_time(self, name: str, elapsed_ms: float) -> None:
        return None

    def increment(self, name: str, value: int = 1) -> None:
        return None

    @contextmanager
    def time_stage(self, name: str):
        yield

    def sample_resources(self) -> None:
        return None

    def build_report(self, extra_summary: dict | None = None) -> dict:
        report = {
            "mode": self.mode,
            "disabled": True,
        }
        if extra_summary is not None:
            report["summary"] = extra_summary
        return report