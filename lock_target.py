from __future__ import annotations

import argparse
import json
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parent
LOCAL_PACKAGE_PARENT = ROOT.parent

if str(LOCAL_PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(LOCAL_PACKAGE_PARENT))

from ultralytics import YOLO  # noqa: E402
from ultralytics.perf_utils import NullPerformanceRecorder, PerformanceRecorder, round_float  # noqa: E402
from gimbal.serial_client import GimbalSerialClient  # noqa: E402


@dataclass
class Candidate:
    bbox: np.ndarray
    track_id: int
    cls: int
    conf: float
    face_bbox: np.ndarray | None = None
    embedding: np.ndarray | None = None

    @property
    def center(self) -> np.ndarray:
        return np.array([(self.bbox[0] + self.bbox[2]) / 2.0, (self.bbox[1] + self.bbox[3]) / 2.0], dtype=np.float32)


@dataclass
class TargetState:
    target_name: str
    tracker_id: int
    bbox: np.ndarray
    face_bbox: np.ndarray | None = None
    embedding_bank: deque[np.ndarray] = field(default_factory=lambda: deque(maxlen=30))
    prototype: np.ndarray | None = None
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(2, dtype=np.float32))
    lost_frames: int = 0
    face_miss_frames: int = 0
    face_detected_frames: int = 0
    total_face_misses: int = 0
    max_face_miss_streak: int = 0
    face_hold_frames: int = 0
    reacquired_count: int = 0
    tracker_switches: int = 0
    total_updates: int = 0
    filtered_center: np.ndarray | None = None
    control_state: str = "SEARCHING"
    reacquire_frames_left: int = 0
    face_relative_bbox: np.ndarray | None = None
    lock_mode: str = "SEARCHING"

    def predicted_bbox(self) -> np.ndarray:
        predicted = self.bbox.copy().astype(np.float32)
        predicted[[0, 2]] += self.velocity[0]
        predicted[[1, 3]] += self.velocity[1]
        return predicted

    def update(self, candidate: Candidate) -> bool:
        previous_bbox = self.bbox.copy().astype(np.float32)
        previous_center = np.array([(self.bbox[0] + self.bbox[2]) / 2.0, (self.bbox[1] + self.bbox[3]) / 2.0], dtype=np.float32)
        switched = candidate.track_id != self.tracker_id
        if switched:
            self.tracker_switches += 1
            if self.lost_frames > 0:
                self.reacquired_count += 1
                self.reacquire_frames_left = 12
        self.velocity = candidate.center - previous_center
        self.tracker_id = candidate.track_id
        self.bbox = candidate.bbox.astype(np.float32)
        self.lost_frames = 0
        self.total_updates += 1
        if candidate.face_bbox is not None:
            if self.face_bbox is None:
                self.face_bbox = candidate.face_bbox.astype(np.float32)
            else:
                self.face_bbox = smooth_bbox(self.face_bbox, candidate.face_bbox.astype(np.float32), alpha=0.75)
            self.face_relative_bbox = face_bbox_to_relative(self.face_bbox, self.bbox)
            self.face_miss_frames = 0
            self.face_detected_frames += 1
            self.lock_mode = "FACE_LOCK"
        else:
            if not switched and self.face_bbox is not None:
                projected_face = project_face_bbox(self.face_relative_bbox, previous_bbox, self.bbox, self.face_bbox)
                if projected_face is not None:
                    self.face_bbox = projected_face
                    self.lock_mode = "HEAD_PROXY"
                else:
                    self.lock_mode = "SEARCHING"
            else:
                self.lock_mode = "SEARCHING"
            self.face_miss_frames += 1
            self.total_face_misses += 1
            self.max_face_miss_streak = max(self.max_face_miss_streak, self.face_miss_frames)
        if candidate.embedding is not None:
            self.embedding_bank.append(candidate.embedding)
            self.prototype = normalize(np.mean(np.stack(self.embedding_bank, axis=0), axis=0))
        return switched


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lock one target across ID switches on top of YOLO tracking.")
    parser.add_argument("--source", required=True, help="Input video path.")
    parser.add_argument("--model", default="yolo26n.pt", help="Detection model path.")
    parser.add_argument("--tracker", default="cfg/trackers/botsort.yaml", help="Tracker YAML path.")
    parser.add_argument("--reid-model", default="yolo26l.pt", help="Model used to extract appearance embeddings.")
    parser.add_argument("--classes", type=int, nargs="*", default=[0], help="Class ids to keep. Default is person only.")
    parser.add_argument("--conf", type=float, default=0.25, help="Detection confidence threshold.")
    parser.add_argument("--iou", type=float, default=0.5, help="NMS IoU threshold.")
    parser.add_argument("--imgsz", type=int, default=960, help="Inference image size.")
    parser.add_argument("--target-name", default="TARGET-1", help="Displayed business target id.")
    parser.add_argument("--initial-track-id", type=int, default=1, help="Bind this tracker id when it appears. Defaults to 1.")
    parser.add_argument("--max-lost", type=int, default=90, help="How many frames to keep searching after target disappears.")
    parser.add_argument("--appearance-weight", type=float, default=0.6, help="Weight of appearance similarity.")
    parser.add_argument("--iou-weight", type=float, default=0.25, help="Weight of IoU consistency.")
    parser.add_argument("--center-weight", type=float, default=0.15, help="Weight of center distance consistency.")
    parser.add_argument("--min-appearance", type=float, default=0.35, help="Minimum cosine similarity for reacquisition.")
    parser.add_argument("--min-iou", type=float, default=0.05, help="Minimum IoU for weak motion gating.")
    parser.add_argument("--min-center-score", type=float, default=0.2, help="Minimum center-distance score for weak motion gating.")
    parser.add_argument("--reacquire-thresh", type=float, default=0.45, help="Minimum final score to accept a new tracker id.")
    parser.add_argument("--project", default="runs/lock_target", help="Output project directory.")
    parser.add_argument("--name", default="exp", help="Run name.")
    parser.add_argument("--show", action="store_true", help="Show live window while processing.")
    parser.add_argument("--save-all-boxes", action="store_true", help="Draw all tracker boxes in the output video.")
    parser.add_argument("--lightweight", action="store_true", help="Enable lightweight runtime preset for faster processing.")
    parser.add_argument("--demo-only", action="store_true", help="Only save the final demo video and skip summary/frame_metrics/performance outputs.")
    parser.add_argument("--no-save-video", action="store_true", help="Do not save the output video.")
    parser.add_argument("--no-save-summary", action="store_true", help="Do not save summary.json.")
    parser.add_argument("--no-save-frame-metrics", action="store_true", help="Do not save frame_metrics.json.")
    parser.add_argument("--no-save-performance", action="store_true", help="Do not save performance.json or collect performance metrics.")
    parser.add_argument("--face-scale-factor", type=float, default=1.05, help="OpenCV face detector scale factor.")
    parser.add_argument("--face-min-neighbors", type=int, default=3, help="OpenCV face detector minNeighbors.")
    parser.add_argument("--face-hold", type=int, default=6, help="How many frames to keep the last face box when face detection briefly fails.")
    parser.add_argument("--fallback-to-first-face", action="store_true", help="If the requested initial track id is not available, fall back to the first detected face.")
    parser.add_argument("--face-min-confidence", type=float, default=0.30, help="Minimum MTCNN face detection confidence in hybrid mode.")
    parser.add_argument("--reid-interval", type=int, default=1, help="Refresh embeddings every N frames for the currently tracked target. 1 means every frame.")
    parser.add_argument("--mtcnn-interval", type=int, default=1, help="Run MTCNN every N frames for the currently tracked target. 1 means every frame.")
    parser.add_argument("--control-alpha", type=float, default=0.72, help="Smoothing factor for the control center. Higher means steadier but slower.")
    parser.add_argument("--control-max-step", type=float, default=40.0, help="Maximum per-frame control-center movement in pixels.")
    parser.add_argument("--control-deadband", type=float, default=12.0, help="Deadband radius in pixels for pan-tilt control output.")
    parser.add_argument("--gimbal-port", default=None, help="Serial port used to send binary gimbal tracking commands, e.g. COM4. Disabled by default.")
    parser.add_argument("--gimbal-mirror-port", action="append", default=[], help="Mirror every gimbal frame to another serial port, e.g. COM10 for VOFA on COM11. Can be used multiple times.")
    parser.add_argument("--gimbal-protocol", choices=("qgimbal", "vision-v1"), default="qgimbal", help="Gimbal serial protocol. qgimbal matches the MCU ReceivePackage 12-byte frame.")
    parser.add_argument("--gimbal-baud", type=int, default=1152000, help="Gimbal serial baudrate.")
    parser.add_argument("--gimbal-mirror-baud", type=int, default=None, help="Mirror serial baudrate. Defaults to --gimbal-baud.")
    parser.add_argument("--gimbal-timeout", type=float, default=0.02, help="Gimbal serial write timeout in seconds.")
    parser.add_argument("--gimbal-dry-run", action="store_true", help="Build gimbal commands without opening a real serial port.")
    parser.add_argument("--gimbal-mirror-as-hex-text", action="store_true", help="Send readable AA 55 ... HEX text to mirror ports for VOFA display.")
    parser.add_argument("--gimbal-command-rate", type=float, default=20.0, help="Maximum gimbal command send rate in Hz.")
    parser.add_argument("--gimbal-max-speed", type=float, default=50.0, help="Maximum absolute yaw/pitch speed sent to the lower controller. QGimbal uses rpm and clamps to +/-50.")
    parser.add_argument("--gimbal-pan-gain", type=float, default=0.8, help="Pan speed gain from normalized x offset to serial command.")
    parser.add_argument("--gimbal-tilt-gain", type=float, default=0.8, help="Tilt speed gain from normalized y offset to serial command.")
    parser.add_argument("--gimbal-invert-pan", action="store_true", help="Invert pan command direction if the lower controller direction is opposite.")
    parser.add_argument("--gimbal-invert-tilt", action="store_true", help="Invert tilt command direction if the lower controller direction is opposite.")
    parser.add_argument("--gimbal-laser", choices=("keep", "on", "off"), default="keep", help="QGimbal laser control field: keep sends 0xFF.")
    parser.add_argument("--gimbal-enabled", choices=("keep", "on", "off"), default="on", help="QGimbal enabled control field. Default on so the MCU can accept speed commands.")
    parser.add_argument("--gimbal-stability", choices=("keep", "on", "off"), default="keep", help="QGimbal stability control field: keep sends 0xFF.")
    args = parser.parse_args()
    if args.lightweight:
        args.reid_interval = max(args.reid_interval, 8)
        args.mtcnn_interval = max(args.mtcnn_interval, 3)
    return args


def save_video_enabled(args: argparse.Namespace) -> bool:
    return not args.no_save_video


def save_summary_enabled(args: argparse.Namespace) -> bool:
    return not args.no_save_summary and not args.demo_only


def save_frame_metrics_enabled(args: argparse.Namespace) -> bool:
    return not args.no_save_frame_metrics and not args.demo_only


def save_performance_enabled(args: argparse.Namespace) -> bool:
    return not args.no_save_performance and not args.demo_only


def normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        return vector.astype(np.float32)
    return (vector / norm).astype(np.float32)


def cosine_similarity(lhs: np.ndarray | None, rhs: np.ndarray | None) -> float:
    if lhs is None or rhs is None:
        return 0.0
    return float(np.dot(normalize(lhs), normalize(rhs)))


def iou_xyxy(lhs: np.ndarray, rhs: np.ndarray) -> float:
    x1 = max(float(lhs[0]), float(rhs[0]))
    y1 = max(float(lhs[1]), float(rhs[1]))
    x2 = min(float(lhs[2]), float(rhs[2]))
    y2 = min(float(lhs[3]), float(rhs[3]))
    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    intersection = inter_w * inter_h
    lhs_area = max(0.0, float(lhs[2] - lhs[0])) * max(0.0, float(lhs[3] - lhs[1]))
    rhs_area = max(0.0, float(rhs[2] - rhs[0])) * max(0.0, float(rhs[3] - rhs[1]))
    union = lhs_area + rhs_area - intersection
    return 0.0 if union <= 0.0 else intersection / union


def center_score(lhs: np.ndarray, rhs: np.ndarray, image_shape: tuple[int, int, int]) -> float:
    lhs_center = np.array([(lhs[0] + lhs[2]) / 2.0, (lhs[1] + lhs[3]) / 2.0], dtype=np.float32)
    rhs_center = np.array([(rhs[0] + rhs[2]) / 2.0, (rhs[1] + rhs[3]) / 2.0], dtype=np.float32)
    diagonal = float(np.hypot(image_shape[1], image_shape[0]))
    if diagonal <= 0.0:
        return 0.0
    distance = float(np.linalg.norm(lhs_center - rhs_center))
    return max(0.0, 1.0 - distance / diagonal)


def smooth_bbox(previous: np.ndarray, current: np.ndarray, alpha: float = 0.75) -> np.ndarray:
    return (alpha * previous + (1.0 - alpha) * current).astype(np.float32)


def smooth_center(previous: np.ndarray | None, current: np.ndarray, alpha: float, max_step: float) -> np.ndarray:
    if previous is None:
        return current.astype(np.float32)
    step = current.astype(np.float32) - previous.astype(np.float32)
    step_norm = float(np.linalg.norm(step))
    if max_step > 0.0 and step_norm > max_step:
        step = step / max(step_norm, 1e-6) * max_step
        current = previous.astype(np.float32) + step
    return (alpha * previous.astype(np.float32) + (1.0 - alpha) * current.astype(np.float32)).astype(np.float32)


def bbox_center(bbox: np.ndarray) -> np.ndarray:
    return np.array([(bbox[0] + bbox[2]) * 0.5, (bbox[1] + bbox[3]) * 0.5], dtype=np.float32)


def bbox_area(bbox: np.ndarray | None) -> float:
    if bbox is None:
        return 0.0
    return max(0.0, float(bbox[2] - bbox[0])) * max(0.0, float(bbox[3] - bbox[1]))


def face_bbox_to_relative(face_bbox: np.ndarray | None, body_bbox: np.ndarray | None) -> np.ndarray | None:
    if face_bbox is None or body_bbox is None:
        return None
    body_w = float(body_bbox[2] - body_bbox[0])
    body_h = float(body_bbox[3] - body_bbox[1])
    if body_w <= 1e-6 or body_h <= 1e-6:
        return None
    return np.array(
        [
            (face_bbox[0] - body_bbox[0]) / body_w,
            (face_bbox[1] - body_bbox[1]) / body_h,
            (face_bbox[2] - body_bbox[0]) / body_w,
            (face_bbox[3] - body_bbox[1]) / body_h,
        ],
        dtype=np.float32,
    )


def relative_face_to_bbox(relative_face: np.ndarray | None, body_bbox: np.ndarray | None) -> np.ndarray | None:
    if relative_face is None or body_bbox is None:
        return None
    body_w = float(body_bbox[2] - body_bbox[0])
    body_h = float(body_bbox[3] - body_bbox[1])
    if body_w <= 1e-6 or body_h <= 1e-6:
        return None
    return np.array(
        [
            body_bbox[0] + relative_face[0] * body_w,
            body_bbox[1] + relative_face[1] * body_h,
            body_bbox[0] + relative_face[2] * body_w,
            body_bbox[1] + relative_face[3] * body_h,
        ],
        dtype=np.float32,
    )


def landmarks_to_face_bbox(
    landmarks: np.ndarray | None,
    roi_origin: tuple[int, int],
    body_bbox: np.ndarray,
    image_shape: tuple[int, int, int],
) -> np.ndarray | None:
    if landmarks is None:
        return None
    points = np.asarray(landmarks, dtype=np.float32)
    if points.ndim != 2 or points.shape[0] < 3 or points.shape[1] != 2:
        return None
    valid = np.isfinite(points).all(axis=1)
    points = points[valid]
    if len(points) < 3:
        return None

    origin_x, origin_y = roi_origin
    absolute_points = points.copy()
    absolute_points[:, 0] += float(origin_x)
    absolute_points[:, 1] += float(origin_y)

    x_min = float(np.min(absolute_points[:, 0]))
    x_max = float(np.max(absolute_points[:, 0]))
    y_min = float(np.min(absolute_points[:, 1]))
    y_max = float(np.max(absolute_points[:, 1]))
    span_x = max(1.0, x_max - x_min)
    span_y = max(1.0, y_max - y_min)

    body_w = max(1.0, float(body_bbox[2] - body_bbox[0]))
    body_h = max(1.0, float(body_bbox[3] - body_bbox[1]))

    center_x = float(np.mean(absolute_points[:, 0]))
    center_y = float(np.mean(absolute_points[:, 1])) + span_y * 0.28
    box_w = min(max(span_x * 2.8, body_w * 0.16), body_w * 0.52)
    box_h = min(max(span_y * 3.4, body_h * 0.16), body_h * 0.46)

    candidate = np.array(
        [
            center_x - box_w * 0.5,
            center_y - box_h * 0.58,
            center_x + box_w * 0.5,
            center_y + box_h * 0.42,
        ],
        dtype=np.float32,
    )
    candidate = clamp_face_bbox_to_body(candidate, body_bbox)
    if candidate is None:
        return None
    candidate[0] = max(0.0, candidate[0])
    candidate[1] = max(0.0, candidate[1])
    candidate[2] = min(float(image_shape[1] - 1), candidate[2])
    candidate[3] = min(float(image_shape[0] - 1), candidate[3])
    if candidate[2] <= candidate[0] or candidate[3] <= candidate[1]:
        return None
    return candidate


def clamp_face_bbox_to_body(face_bbox: np.ndarray | None, body_bbox: np.ndarray) -> np.ndarray | None:
    if face_bbox is None:
        return None
    body_x1, body_y1, body_x2, body_y2 = body_bbox.astype(np.float32)
    body_w = max(1.0, float(body_x2 - body_x1))
    body_h = max(1.0, float(body_y2 - body_y1))
    head_bottom = body_y1 + body_h * 0.68
    margin_x = body_w * 0.12
    x1 = max(body_x1 - margin_x, float(face_bbox[0]))
    y1 = max(body_y1 + body_h * 0.02, float(face_bbox[1]))
    x2 = min(body_x2 + margin_x, float(face_bbox[2]))
    y2 = min(head_bottom, float(face_bbox[3]))
    if x2 <= x1 or y2 <= y1:
        return None
    return np.array([x1, y1, x2, y2], dtype=np.float32)


def stabilize_projected_face_bbox(
    projected_bbox: np.ndarray | None,
    previous_face_bbox: np.ndarray | None,
    body_bbox: np.ndarray,
) -> np.ndarray | None:
    if projected_bbox is None:
        return None

    body_x1, body_y1, body_x2, body_y2 = body_bbox.astype(np.float32)
    body_w = max(1.0, float(body_x2 - body_x1))
    body_h = max(1.0, float(body_y2 - body_y1))

    projected_center = bbox_center(projected_bbox)
    projected_w = max(1.0, float(projected_bbox[2] - projected_bbox[0]))
    projected_h = max(1.0, float(projected_bbox[3] - projected_bbox[1]))

    if previous_face_bbox is not None:
        previous_center = bbox_center(previous_face_bbox)
        previous_w = max(1.0, float(previous_face_bbox[2] - previous_face_bbox[0]))
        previous_h = max(1.0, float(previous_face_bbox[3] - previous_face_bbox[1]))
        center = 0.7 * previous_center + 0.3 * projected_center
        width = 0.8 * previous_w + 0.2 * projected_w
        height = 0.8 * previous_h + 0.2 * projected_h
    else:
        center = projected_center
        width = projected_w
        height = projected_h

    width = min(max(width, body_w * 0.16), body_w * 0.42)
    height = min(max(height, body_h * 0.14), body_h * 0.38)

    cx = float(np.clip(center[0], body_x1 + body_w * 0.18, body_x2 - body_w * 0.18))
    cy = float(np.clip(center[1], body_y1 + body_h * 0.12, body_y1 + body_h * 0.48))

    stabilized = np.array(
        [cx - width * 0.5, cy - height * 0.5, cx + width * 0.5, cy + height * 0.5],
        dtype=np.float32,
    )
    return clamp_face_bbox_to_body(stabilized, body_bbox)


def project_face_bbox(
    relative_face: np.ndarray | None,
    previous_body_bbox: np.ndarray,
    current_body_bbox: np.ndarray,
    previous_face_bbox: np.ndarray | None,
) -> np.ndarray | None:
    body_shift = bbox_center(current_body_bbox) - bbox_center(previous_body_bbox)
    shifted_previous = None
    if previous_face_bbox is not None:
        shifted_previous = previous_face_bbox.astype(np.float32).copy()
        shifted_previous[[0, 2]] += body_shift[0]
        shifted_previous[[1, 3]] += body_shift[1]

    relative_projected = relative_face_to_bbox(relative_face, current_body_bbox)
    if relative_projected is not None and shifted_previous is not None:
        projected = smooth_bbox(shifted_previous, relative_projected, alpha=0.4)
    else:
        projected = relative_projected if relative_projected is not None else shifted_previous

    return stabilize_projected_face_bbox(projected, previous_face_bbox, current_body_bbox)


def largest_face_candidate(candidates: list[Candidate]) -> Candidate | None:
    face_candidates = [candidate for candidate in candidates if candidate.face_bbox is not None]
    if not face_candidates:
        return None
    return max(face_candidates, key=lambda candidate: bbox_area(candidate.face_bbox))


def detect_face_in_person(
    image: np.ndarray,
    person_bbox: np.ndarray,
    face_detectors: dict,
    scale_factor: float,
    min_neighbors: int,
    min_confidence: float,
    face_hint: np.ndarray | None = None,
    perf: PerformanceRecorder | None = None,
) -> np.ndarray | None:
    """Detect a face inside the upper region of a person box and return absolute xyxy coordinates."""
    x1, y1, x2, y2 = person_bbox.astype(int)
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(image.shape[1], x2)
    y2 = min(image.shape[0], y2)
    if x2 <= x1 or y2 <= y1:
        return None

    body_w = x2 - x1
    body_h = y2 - y1
    expand_x = int(body_w * 0.12)
    expand_top = int(body_h * 0.08)
    head_y2 = min(image.shape[0], y1 + max(1, int(body_h * 0.78)))
    x1 = max(0, x1 - expand_x)
    x2 = min(image.shape[1], x2 + expand_x)
    y1 = max(0, y1 - expand_top)
    if head_y2 <= y1:
        return None

    roi = image[y1:head_y2, x1:x2]
    if roi.size == 0:
        return None

    absolute_faces: list[np.ndarray] = []
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    min_face = max(16, int(min(body_w, body_h) * 0.10))

    frontal = face_detectors.get("frontal")
    classical_faces: list[np.ndarray] = []
    if frontal is not None and not frontal.empty():
        classical_start = time.perf_counter() if perf is not None else None
        faces = frontal.detectMultiScale(
            gray,
            scaleFactor=scale_factor,
            minNeighbors=min_neighbors,
            minSize=(min_face, min_face),
        )
        if perf is not None and classical_start is not None:
            perf.add_stage_time("face_detect_classical_ms", (time.perf_counter() - classical_start) * 1000.0)
        for fx, fy, fw, fh in faces:
            classical_faces.append(
                np.array([x1 + fx, y1 + fy, x1 + fx + fw, y1 + fy + fh], dtype=np.float32)
            )

    profile = face_detectors.get("profile")
    if profile is not None and not profile.empty():
        profile_start = time.perf_counter() if perf is not None else None
        left_faces = profile.detectMultiScale(
            gray,
            scaleFactor=max(1.03, scale_factor),
            minNeighbors=max(2, min_neighbors - 1),
            minSize=(min_face, min_face),
        )
        for fx, fy, fw, fh in left_faces:
            classical_faces.append(
                np.array([x1 + fx, y1 + fy, x1 + fx + fw, y1 + fy + fh], dtype=np.float32)
            )
        flipped = cv2.flip(gray, 1)
        right_faces = profile.detectMultiScale(
            flipped,
            scaleFactor=max(1.03, scale_factor),
            minNeighbors=max(2, min_neighbors - 1),
            minSize=(min_face, min_face),
        )
        if perf is not None and profile_start is not None:
            perf.add_stage_time("face_detect_profile_ms", (time.perf_counter() - profile_start) * 1000.0)
        for fx, fy, fw, fh in right_faces:
            rx = gray.shape[1] - fx - fw
            classical_faces.append(
                np.array([x1 + rx, y1 + fy, x1 + rx + fw, y1 + fy + fh], dtype=np.float32)
            )

    absolute_faces.extend(classical_faces)

    mtcnn = face_detectors.get("mtcnn")
    use_mtcnn_landmarks = mtcnn is not None and (face_hint is not None or not classical_faces)
    if use_mtcnn_landmarks:
        rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
        mtcnn_start = time.perf_counter() if perf is not None else None
        try:
            boxes, probs, landmarks = mtcnn.detect(rgb, landmarks=True)
        except RuntimeError as exc:
            # facenet-pytorch may throw on empty proposals in some edge cases.
            if "torch.cat(): expected a non-empty list of Tensors" in str(exc):
                boxes, probs, landmarks = None, None, None
            else:
                raise
        if perf is not None and mtcnn_start is not None:
            perf.add_stage_time("face_detect_mtcnn_ms", (time.perf_counter() - mtcnn_start) * 1000.0)
            perf.increment("face_detect_mtcnn_calls")
        if boxes is not None and probs is not None:
            for idx, (box, prob) in enumerate(zip(boxes, probs)):
                if box is None or prob is None or float(prob) < min_confidence:
                    continue
                fx1, fy1, fx2, fy2 = box.tolist()
                absolute_faces.append(np.array([x1 + fx1, y1 + fy1, x1 + fx2, y1 + fy2], dtype=np.float32))
                landmark_box = None
                if landmarks is not None and idx < len(landmarks):
                    landmark_box = landmarks_to_face_bbox(
                        landmarks[idx],
                        (x1, y1),
                        person_bbox.astype(np.float32),
                        image.shape,
                    )
                if landmark_box is not None:
                    absolute_faces.append(landmark_box)

    filtered_faces: list[np.ndarray] = []
    for face_bbox in absolute_faces:
        pad_w = int(max(0.0, face_bbox[2] - face_bbox[0]) * 0.08)
        pad_h = int(max(0.0, face_bbox[3] - face_bbox[1]) * 0.12)
        face_bbox = np.array(
            [
                max(0, int(face_bbox[0] - pad_w)),
                max(0, int(face_bbox[1] - pad_h)),
                min(image.shape[1] - 1, int(face_bbox[2] + pad_w)),
                min(image.shape[0] - 1, int(face_bbox[3] + pad_h)),
            ],
            dtype=np.float32,
        )
        face_w = face_bbox[2] - face_bbox[0]
        face_h = face_bbox[3] - face_bbox[1]
        face_cx = (face_bbox[0] + face_bbox[2]) * 0.5
        face_cy = (face_bbox[1] + face_bbox[3]) * 0.5
        width_ratio = face_w / max(1.0, float(body_w))
        height_ratio = face_h / max(1.0, float(body_h))
        upper_bound = y1 + body_h * 0.78
        horizontal_margin = body_w * 0.25
        if not (0.10 <= width_ratio <= 0.9):
            continue
        if not (0.08 <= height_ratio <= 0.7):
            continue
        if face_cy > upper_bound:
            continue
        if face_cx < x1 - horizontal_margin or face_cx > x2 + horizontal_margin:
            continue
        filtered_faces.append(face_bbox)

    absolute_faces = filtered_faces
    if not absolute_faces:
        return None
    if face_hint is None:
        return max(absolute_faces, key=bbox_area)

    return max(
        absolute_faces,
        key=lambda face_bbox: 0.7 * iou_xyxy(face_hint, face_bbox) + 0.3 * center_score(face_hint, face_bbox, image.shape),
    )


def match_score(
    state: TargetState,
    candidate: Candidate,
    image_shape: tuple[int, int, int],
    args: argparse.Namespace,
) -> tuple[float, float, float, float]:
    reference_bbox = state.face_bbox if state.face_bbox is not None else state.predicted_bbox()
    candidate_bbox = candidate.face_bbox if candidate.face_bbox is not None else candidate.bbox
    appearance = cosine_similarity(state.prototype, candidate.embedding)
    overlap = iou_xyxy(reference_bbox, candidate_bbox)
    center = center_score(reference_bbox, candidate_bbox, image_shape)
    score = args.appearance_weight * appearance + args.iou_weight * overlap + args.center_weight * center
    return score, appearance, overlap, center


def is_same_tracker_candidate_valid(
    state: TargetState,
    candidate: Candidate,
    image_shape: tuple[int, int, int],
    args: argparse.Namespace,
) -> bool:
    score, appearance, overlap, center = match_score(state, candidate, image_shape, args)
    if candidate.face_bbox is None:
        return overlap >= max(0.1, args.min_iou) or center >= max(0.35, args.min_center_score)
    if candidate.embedding is None:
        return overlap >= max(0.12, args.min_iou * 1.5) or center >= max(0.35, args.min_center_score * 1.5)
    if state.prototype is None:
        return overlap >= max(0.08, args.min_iou) or center >= max(0.3, args.min_center_score)
    return score >= max(args.reacquire_thresh * 0.8, 0.35) and (
        appearance >= max(args.min_appearance * 0.8, 0.2) or overlap >= max(args.min_iou * 1.5, 0.1)
    )


def crop_box(image: np.ndarray, bbox: np.ndarray) -> np.ndarray | None:
    x1, y1, x2, y2 = bbox.astype(int)
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(image.shape[1], x2)
    y2 = min(image.shape[0], y2)
    if x2 <= x1 or y2 <= y1:
        return None
    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    return crop.copy()


def extract_embedding(embed_model: YOLO, image: np.ndarray, bbox: np.ndarray) -> np.ndarray | None:
    crop = crop_box(image, bbox)
    if crop is None:
        return None
    embedding = embed_model.embed(crop, verbose=False)[0]
    if hasattr(embedding, "cpu"):
        embedding = embedding.cpu().numpy()
    embedding = np.asarray(embedding, dtype=np.float32).reshape(-1)
    return normalize(embedding)


def class_name(names, class_id: int) -> str:
    if isinstance(names, dict):
        return str(names.get(class_id, class_id))
    if isinstance(names, (list, tuple)) and 0 <= class_id < len(names):
        return str(names[class_id])
    return str(class_id)


def collect_candidates(
    result,
    frame: np.ndarray,
    embed_model: YOLO,
    face_detectors: dict,
    classes: set[int],
    args: argparse.Namespace,
    tracked_state: TargetState | None = None,
    perf: PerformanceRecorder | None = None,
    frame_index: int = 0,
) -> list[Candidate]:
    boxes = result.boxes
    if boxes is None or not boxes.is_track or len(boxes) == 0:
        return []
    xyxy = boxes.xyxy.cpu().numpy()
    track_ids = boxes.id.int().cpu().tolist()
    clss = boxes.cls.int().cpu().tolist()
    confs = boxes.conf.cpu().tolist()
    candidates: list[Candidate] = []
    for bbox, track_id, cls, conf in zip(xyxy, track_ids, clss, confs):
        if classes and cls not in classes:
            continue
        if perf is not None:
            perf.increment("candidate_count")
            perf.increment("face_detect_calls")
        face_hint = None
        is_tracked_candidate = False
        face_detectors_for_candidate = face_detectors
        if tracked_state is not None and track_id == tracked_state.tracker_id and tracked_state.face_bbox is not None:
            face_hint = tracked_state.face_bbox
            is_tracked_candidate = True
            if args.mtcnn_interval > 1 and frame_index % args.mtcnn_interval != 0:
                face_detectors_for_candidate = {
                    "frontal": face_detectors.get("frontal"),
                    "profile": face_detectors.get("profile"),
                    "mtcnn": None,
                }
        face_start = time.perf_counter() if perf is not None else None
        face_bbox = detect_face_in_person(
            frame,
            np.asarray(bbox, dtype=np.float32),
            face_detectors_for_candidate,
            args.face_scale_factor,
            args.face_min_neighbors,
            args.face_min_confidence,
            face_hint,
            perf,
        )
        if perf is not None and face_start is not None:
            perf.add_stage_time("face_detect_total_ms", (time.perf_counter() - face_start) * 1000.0)
        embedding = None
        if face_bbox is not None:
            should_refresh_embedding = (not is_tracked_candidate) or args.reid_interval <= 1 or frame_index % args.reid_interval == 0
            if should_refresh_embedding:
                if perf is not None:
                    perf.increment("embedding_calls")
                embedding_start = time.perf_counter() if perf is not None else None
                embedding = extract_embedding(embed_model, frame, face_bbox)
                if perf is not None and embedding_start is not None:
                    perf.add_stage_time("embedding_ms", (time.perf_counter() - embedding_start) * 1000.0)
        candidates.append(
            Candidate(
                bbox=np.asarray(bbox, dtype=np.float32),
                track_id=int(track_id),
                cls=int(cls),
                conf=float(conf),
                face_bbox=face_bbox,
                embedding=embedding,
            )
        )
    return candidates


def choose_by_click(frame: np.ndarray, candidates: list[Candidate], names) -> Candidate | None:
    selected_point: dict[str, tuple[int, int] | None] = {"point": None}
    window_name = "Select Target"

    def on_mouse(event, x, y, _flags, _userdata):
        if event == cv2.EVENT_LBUTTONDOWN:
            selected_point["point"] = (x, y)

    preview = frame.copy()
    for candidate in candidates:
        x1, y1, x2, y2 = candidate.bbox.astype(int)
        label = f"tid:{candidate.track_id} {class_name(names, candidate.cls)}"
        cv2.rectangle(preview, (x1, y1), (x2, y2), (0, 255, 255), 2)
        cv2.putText(preview, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window_name, on_mouse)
    while True:
        cv2.imshow(window_name, preview)
        key = cv2.waitKey(20) & 0xFF
        point = selected_point["point"]
        if point is not None:
            x, y = point
            inside = [candidate for candidate in candidates if candidate.bbox[0] <= x <= candidate.bbox[2] and candidate.bbox[1] <= y <= candidate.bbox[3]]
            if inside:
                inside.sort(key=lambda candidate: (candidate.bbox[2] - candidate.bbox[0]) * (candidate.bbox[3] - candidate.bbox[1]))
                cv2.destroyWindow(window_name)
                return inside[0]
            selected_point["point"] = None
        if key in {27, ord("q")}:
            cv2.destroyWindow(window_name)
            return None


def resolve_initial_target(
    frame: np.ndarray,
    candidates: list[Candidate],
    names,
    initial_track_id: int | None,
    fallback_to_first_face: bool,
) -> Candidate | None:
    if initial_track_id is not None:
        for candidate in candidates:
            if candidate.track_id == initial_track_id and candidate.face_bbox is not None:
                return candidate
        if not fallback_to_first_face:
            return None
        return largest_face_candidate(candidates)
    return choose_by_click(frame, [candidate for candidate in candidates if candidate.face_bbox is not None], names)


def pick_best_candidate(
    state: TargetState,
    candidates: list[Candidate],
    image_shape: tuple[int, int, int],
    args: argparse.Namespace,
) -> tuple[Candidate | None, float]:
    same_tracker = next((candidate for candidate in candidates if candidate.track_id == state.tracker_id), None)
    if same_tracker is not None and is_same_tracker_candidate_valid(state, same_tracker, image_shape, args):
        return same_tracker, 1.0

    best_candidate = None
    best_score = -1.0
    for candidate in candidates:
        if candidate.face_bbox is None or candidate.embedding is None:
            continue
        score, appearance, overlap, center = match_score(state, candidate, image_shape, args)
        if appearance < args.min_appearance and overlap < args.min_iou and center < args.min_center_score:
            continue
        if score > best_score:
            best_score = score
            best_candidate = candidate
    if best_score < args.reacquire_thresh:
        return None, best_score
    return best_candidate, best_score


def draw_candidate(frame: np.ndarray, candidate: Candidate, label: str, color: tuple[int, int, int], thickness: int) -> None:
    x1, y1, x2, y2 = candidate.bbox.astype(int)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
    cv2.putText(frame, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)


def draw_state(frame: np.ndarray, state: TargetState, score: float | None = None) -> None:
    if state.face_bbox is None:
        return
    if state.lost_frames > 0:
        if state.lost_frames > state.face_hold_frames:
            return
        bbox = state.face_bbox.astype(int)
        x1, y1, x2, y2 = bbox
        color = (0, 180, 255)
        label = f"{state.target_name} LOST:{state.lost_frames}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
        cv2.putText(frame, label, (x1, max(24, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        return
    if state.face_miss_frames > 0 and state.face_miss_frames > state.face_hold_frames:
        return
    bbox = state.face_bbox.astype(int)
    x1, y1, x2, y2 = bbox
    mode = resolve_lock_mode(state)
    color = (0, 80, 255) if mode == "FACE_LOCK" else (0, 200, 255)
    label = f"{state.target_name} {mode} tid:{state.tracker_id}"
    if score is not None and score < 1.0:
        label += f" score:{score:.2f}"
    if state.face_miss_frames > 0:
        label += f" face-hold:{state.face_miss_frames}"
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 4)
    cv2.putText(frame, label, (x1, max(24, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)


def draw_control_overlay(frame: np.ndarray, metric: dict) -> None:
    frame_center = metric["frame_center"]
    fc = (int(frame_center["x"]), int(frame_center["y"]))
    cv2.drawMarker(frame, fc, (255, 255, 255), cv2.MARKER_CROSS, 18, 2)

    filtered_center = metric.get("filtered_target_center")
    if filtered_center is not None:
        tc = (int(filtered_center["x"]), int(filtered_center["y"]))
        color = (0, 80, 255) if metric.get("control_active") else (0, 180, 255)
        cv2.circle(frame, tc, 6, color, -1)
        cv2.line(frame, fc, tc, color, 2)

    state_text = metric.get("state", "SEARCHING")
    control_text = "ACTIVE" if metric.get("control_active") else "IDLE"
    deadband_text = "ON" if metric.get("deadband_active") else "OFF"
    cv2.putText(
        frame,
        f"STATE:{state_text} CTRL:{control_text} DEADBAND:{deadband_text}",
        (20, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
    )


def active_target_bbox(state: TargetState | None) -> np.ndarray | None:
    if state is None or state.face_bbox is None:
        return None
    if state.lost_frames > 0:
        if state.lost_frames > state.face_hold_frames:
            return None
        return state.face_bbox
    if state.face_miss_frames > 0 and state.face_miss_frames > state.face_hold_frames:
        return None
    return state.face_bbox


def active_control_center(state: TargetState | None) -> np.ndarray | None:
    if state is None or state.filtered_center is None:
        return None
    if state.control_state == "LOST":
        return None
    if state.face_bbox is None and state.control_state not in {"HOLD", "REACQUIRE", "TRACKING"}:
        return None
    return state.filtered_center


def resolve_lock_mode(state: TargetState | None) -> str:
    if state is None:
        return "SEARCHING"
    if state.lost_frames > state.face_hold_frames:
        return "LOST"
    if state.face_bbox is None:
        return "SEARCHING"
    if state.face_miss_frames == 0:
        return "FACE_LOCK"
    if state.face_miss_frames <= state.face_hold_frames:
        return "HEAD_PROXY"
    return "SEARCHING"


def resolve_control_state(state: TargetState | None) -> str:
    if state is None:
        return "SEARCHING"
    if state.lost_frames > 0:
        return "HOLD" if state.lost_frames <= state.face_hold_frames else "LOST"
    if state.face_miss_frames > 0:
        return "HOLD" if state.face_miss_frames <= state.face_hold_frames else "LOST"
    if state.reacquire_frames_left > 0:
        return "REACQUIRE"
    return "TRACKING"


def update_control_center(state: TargetState | None, args: argparse.Namespace) -> None:
    if state is None:
        return
    active_bbox = active_target_bbox(state)
    if active_bbox is None:
        state.control_state = resolve_control_state(state)
        return
    raw_center = bbox_center(active_bbox)
    state.filtered_center = smooth_center(state.filtered_center, raw_center, args.control_alpha, args.control_max_step)
    state.control_state = resolve_control_state(state)
    if state.reacquire_frames_left > 0 and state.control_state == "REACQUIRE":
        state.reacquire_frames_left -= 1


def frame_metric(
    frame_index: int,
    fps: float,
    frame_shape: tuple[int, int, int],
    state: TargetState | None,
    control_deadband: float,
) -> dict:
    frame_center = np.array([frame_shape[1] * 0.5, frame_shape[0] * 0.5], dtype=np.float32)
    active_bbox = active_target_bbox(state)
    control_center = active_control_center(state)
    state_name = resolve_control_state(state)
    lock_mode = resolve_lock_mode(state)
    if active_bbox is None or control_center is None:
        return {
            "frame_index": frame_index,
            "timestamp_sec": round(frame_index / fps, 4) if fps > 0 else None,
            "visible": False,
            "state": state_name,
            "lock_mode": lock_mode,
            "frame_center": {"x": round(float(frame_center[0]), 2), "y": round(float(frame_center[1]), 2)},
            "raw_target_center": None,
            "filtered_target_center": None,
            "target_center": None,
            "offset": None,
            "distance_to_center": None,
            "control_offset": None,
            "control_distance_to_center": None,
            "control_active": False,
            "deadband_active": False,
            "tracker_id": None if state is None else state.tracker_id,
        }

    raw_target_center = bbox_center(active_bbox)
    offset = raw_target_center - frame_center
    distance = float(np.linalg.norm(offset))
    control_offset = control_center - frame_center
    control_distance = float(np.linalg.norm(control_offset))
    deadband_active = control_distance <= control_deadband
    control_active = not deadband_active and state_name in {"TRACKING", "REACQUIRE", "HOLD"}
    return {
        "frame_index": frame_index,
        "timestamp_sec": round(frame_index / fps, 4) if fps > 0 else None,
        "visible": True,
        "state": state_name,
        "lock_mode": lock_mode,
        "frame_center": {"x": round(float(frame_center[0]), 2), "y": round(float(frame_center[1]), 2)},
        "raw_target_center": {"x": round(float(raw_target_center[0]), 2), "y": round(float(raw_target_center[1]), 2)},
        "filtered_target_center": {"x": round(float(control_center[0]), 2), "y": round(float(control_center[1]), 2)},
        "target_center": {"x": round(float(control_center[0]), 2), "y": round(float(control_center[1]), 2)},
        "offset": {"dx": round(float(offset[0]), 2), "dy": round(float(offset[1]), 2)},
        "distance_to_center": round(distance, 2),
        "control_offset": {"dx": round(float(control_offset[0]), 2), "dy": round(float(control_offset[1]), 2)},
        "control_distance_to_center": round(control_distance, 2),
        "control_active": control_active,
        "deadband_active": deadband_active,
        "tracker_id": None if state is None else state.tracker_id,
    }


def ensure_output_dir(project: str, name: str) -> Path:
    run_dir = ROOT / project / name
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def main() -> None:
    args = parse_args()
    source = Path(args.source)
    if not source.exists():
        raise FileNotFoundError(f"Video not found: {source}")

    run_dir = ensure_output_dir(args.project, args.name)
    output_video = run_dir / f"{source.stem}_locked.mp4"
    output_json = run_dir / f"{source.stem}_summary.json"
    metrics_json = run_dir / f"{source.stem}_frame_metrics.json"
    performance_json = run_dir / f"{source.stem}_performance.json"

    from facenet_pytorch import MTCNN

    detect_model = YOLO(args.model)
    embed_model = YOLO(args.reid_model)
    cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    frontal_detector = cv2.CascadeClassifier(str(cascade_path))
    profile_path = Path(cv2.data.haarcascades) / "haarcascade_profileface.xml"
    profile_detector = cv2.CascadeClassifier(str(profile_path)) if profile_path.exists() else None
    face_detectors = {
        "frontal": frontal_detector,
        "profile": profile_detector,
        "mtcnn": MTCNN(keep_all=True, device="cpu", post_process=False),
    }

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"Failed to open video: {source}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = None
    if save_video_enabled(args):
        writer = cv2.VideoWriter(str(output_video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

    names = detect_model.names if hasattr(detect_model, "names") else {}
    state: TargetState | None = None
    frame_index = 0
    classes = set(args.classes)
    selected_at_frame = None
    last_score = None
    frame_metrics: list[dict] = []
    perf = PerformanceRecorder(mode="offline") if save_performance_enabled(args) else NullPerformanceRecorder(mode="offline")
    gimbal = GimbalSerialClient.from_args(args)
    run_start = time.perf_counter()

    while True:
        success, frame = capture.read()
        if not success:
            break
        frame_index += 1
        perf.start_frame(frame_index)
        with perf.time_stage("frame_total_ms"):
            with perf.time_stage("detect_track_ms"):
                result = detect_model.track(
                    frame,
                    persist=True,
                    tracker=args.tracker,
                    classes=args.classes,
                    conf=args.conf,
                    iou=args.iou,
                    imgsz=args.imgsz,
                    verbose=False,
                )[0]

            with perf.time_stage("collect_candidates_ms"):
                candidates = collect_candidates(result, frame, embed_model, face_detectors, classes, args, state, perf, frame_index)
            with perf.time_stage("plot_base_ms"):
                display_frame = result.plot(conf=True, labels=True) if args.save_all_boxes else frame.copy()

            with perf.time_stage("state_update_ms"):
                if state is None:
                    candidate = resolve_initial_target(
                        display_frame.copy(),
                        candidates,
                        names,
                        args.initial_track_id,
                        args.fallback_to_first_face,
                    )
                    if candidate is not None:
                        state = TargetState(target_name=args.target_name, tracker_id=candidate.track_id, bbox=candidate.bbox.copy())
                        state.face_hold_frames = args.face_hold
                        state.update(candidate)
                        selected_at_frame = frame_index
                        last_score = 1.0
                else:
                    best_candidate, best_score = pick_best_candidate(state, candidates, frame.shape, args)
                    last_score = best_score if best_candidate is not None else None
                    if best_candidate is not None:
                        state.update(best_candidate)
                    else:
                        state.lost_frames += 1
                        if state.lost_frames > args.max_lost:
                            state.face_bbox = None

            with perf.time_stage("control_update_ms"):
                update_control_center(state, args)

            with perf.time_stage("draw_overlay_ms"):
                if args.save_all_boxes:
                    for candidate in candidates:
                        if state is not None and candidate.track_id == state.tracker_id and state.lost_frames == 0:
                            continue
                        draw_candidate(
                            display_frame,
                            candidate,
                            f"tid:{candidate.track_id} {class_name(names, candidate.cls)} {candidate.conf:.2f}",
                            (0, 200, 0),
                            2,
                        )

                if state is not None:
                    draw_state(display_frame, state, last_score)

                metric = frame_metric(frame_index, fps, frame.shape, state, args.control_deadband)
                with perf.time_stage("gimbal_serial_ms"):
                    gimbal_command = gimbal.send_metric(metric)
                if gimbal_command is not None:
                    metric["gimbal_command"] = gimbal_command
                if save_frame_metrics_enabled(args):
                    frame_metrics.append(metric)
                draw_control_overlay(display_frame, metric)

            if writer is not None:
                with perf.time_stage("write_video_ms"):
                    writer.write(display_frame)

            if args.show:
                show_start = time.perf_counter()
                cv2.imshow("Lock Target", display_frame)
                key = cv2.waitKey(1) & 0xFF
                perf.add_stage_time("show_ms", (time.perf_counter() - show_start) * 1000.0)
                if key in {27, ord("q")}:
                    perf.sample_resources()
                    perf.end_frame()
                    break

            perf.sample_resources()
        perf.end_frame()

    capture.release()
    if writer is not None:
        writer.release()
    cv2.destroyAllWindows()
    gimbal.close()

    total_runtime_sec = time.perf_counter() - run_start

    summary = {
        "source": str(source),
        "output_video": str(output_video) if save_video_enabled(args) else None,
        "frame_metrics_json": str(metrics_json) if save_frame_metrics_enabled(args) else None,
        "performance_json": str(performance_json) if save_performance_enabled(args) else None,
        "selected_at_frame": selected_at_frame,
        "target_initialized": state is not None,
        "target_name": args.target_name,
        "final_tracker_id": None if state is None else state.tracker_id,
        "tracker_switches": 0 if state is None else state.tracker_switches,
        "reacquired_count": 0 if state is None else state.reacquired_count,
        "lost_frames": 0 if state is None else state.lost_frames,
        "face_detected_frames": 0 if state is None else state.face_detected_frames,
        "face_miss_frames": 0 if state is None else state.face_miss_frames,
        "total_face_misses": 0 if state is None else state.total_face_misses,
        "max_face_miss_streak": 0 if state is None else state.max_face_miss_streak,
        "total_updates": 0 if state is None else state.total_updates,
        "final_control_state": resolve_control_state(state),
        "final_lock_mode": resolve_lock_mode(state),
        "final_filtered_target_center": None
        if state is None or state.filtered_center is None
        else {"x": round(float(state.filtered_center[0]), 2), "y": round(float(state.filtered_center[1]), 2)},
        "control_alpha": args.control_alpha,
        "control_max_step": args.control_max_step,
        "control_deadband": args.control_deadband,
        "processed_frames": frame_index,
        "runtime_sec": round_float(total_runtime_sec, 3),
        "effective_fps": round_float(frame_index / total_runtime_sec if total_runtime_sec > 0 else 0.0, 3),
        "gimbal_serial": gimbal.summary(),
    }
    if save_performance_enabled(args):
        performance_report = perf.build_report(summary)
        performance_json.write_text(json.dumps(performance_report, ensure_ascii=False, indent=2), encoding="utf-8")
    if save_frame_metrics_enabled(args):
        metrics_json.write_text(json.dumps(frame_metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    if save_summary_enabled(args):
        output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()