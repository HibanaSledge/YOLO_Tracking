from __future__ import annotations

import argparse
import json
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from lock_target import (
    Candidate,
    ROOT,
    TargetState,
    class_name,
    detect_face_in_person,
    draw_candidate,
    draw_control_overlay,
    draw_state,
    extract_embedding,
    largest_face_candidate,
    pick_best_candidate,
    resolve_initial_target,
    resolve_control_state,
    resolve_lock_mode,
    update_control_center,
    frame_metric,
    is_same_tracker_candidate_valid,
)
from ultralytics.perf_utils import NullPerformanceRecorder, PerformanceRecorder
from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run lock_target in realtime from a live RGB camera.")
    parser.add_argument("--camera", type=int, default=0, help="Camera index.")
    parser.add_argument("--camera-backend", default="dshow", choices=["auto", "dshow", "msmf"], help="OpenCV capture backend on Windows.")
    parser.add_argument("--camera-width", type=int, default=1280, help="Requested camera width.")
    parser.add_argument("--camera-height", type=int, default=720, help="Requested camera height.")
    parser.add_argument("--camera-fps", type=int, default=30, help="Requested camera FPS.")
    parser.add_argument("--model", default="yolo26n.pt", help="Detection model path.")
    parser.add_argument("--tracker", default="cfg/trackers/botsort.yaml", help="Tracker YAML path.")
    parser.add_argument("--reid-model", default="yolo26l.pt", help="Model used to extract appearance embeddings.")
    parser.add_argument("--classes", type=int, nargs="*", default=[0], help="Class ids to keep. Default is person only.")
    parser.add_argument("--conf", type=float, default=0.25, help="Detection confidence threshold.")
    parser.add_argument("--iou", type=float, default=0.5, help="NMS IoU threshold.")
    parser.add_argument("--imgsz", type=int, default=640, help="Inference image size for realtime mode.")
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
    parser.add_argument("--save-all-boxes", action="store_true", help="Draw all tracker boxes in the realtime view.")
    parser.add_argument("--face-scale-factor", type=float, default=1.05, help="OpenCV face detector scale factor.")
    parser.add_argument("--face-min-neighbors", type=int, default=3, help="OpenCV face detector minNeighbors.")
    parser.add_argument("--face-hold", type=int, default=6, help="How many frames to keep the last face box when face detection briefly fails.")
    parser.add_argument("--fallback-to-first-face", action="store_true", help="If the requested initial track id is not available, fall back to the first detected face.")
    parser.add_argument("--face-min-confidence", type=float, default=0.30, help="Minimum MTCNN face detection confidence in hybrid mode.")
    parser.add_argument("--control-alpha", type=float, default=0.72, help="Smoothing factor for the control center.")
    parser.add_argument("--control-max-step", type=float, default=40.0, help="Maximum per-frame control-center movement in pixels.")
    parser.add_argument("--control-deadband", type=float, default=12.0, help="Deadband radius in pixels for pan-tilt control output.")
    parser.add_argument("--lightweight", action="store_true", help="Enable lightweight runtime preset for faster processing.")
    parser.add_argument("--reid-interval", type=int, default=8, help="Refresh embeddings every N processed frames while tracking remains stable.")
    parser.add_argument("--mtcnn-interval", type=int, default=3, help="Run MTCNN at most once every N processed frames for the tracked target.")
    parser.add_argument("--display-width", type=int, default=960, help="Resize displayed frame width. Use 0 to keep original size.")
    parser.add_argument("--demo-only", action="store_true", help="Only save the final demo video and skip summary/frame_metrics/performance outputs.")
    parser.add_argument("--no-save-video", action="store_true", help="Do not save the realtime demo video.")
    parser.add_argument("--no-save-summary", action="store_true", help="Do not save summary.json.")
    parser.add_argument("--no-save-frame-metrics", action="store_true", help="Do not save frame_metrics.json.")
    parser.add_argument("--no-save-performance", action="store_true", help="Do not save performance.json or collect performance metrics.")
    parser.add_argument("--save-session", action="store_true", help="Deprecated. Realtime outputs are now saved by default.")
    parser.add_argument("--no-save-session", action="store_true", help="Disable saving video and json outputs after realtime session.")
    parser.add_argument("--project", default="runs/lock_target_realtime", help="Output project directory when saving.")
    parser.add_argument("--name", default="camera", help="Run name when saving.")
    args = parser.parse_args()
    if args.lightweight:
        args.reid_interval = max(args.reid_interval, 8)
        args.mtcnn_interval = max(args.mtcnn_interval, 3)
    return args


def session_saving_enabled(args: argparse.Namespace) -> bool:
    return not args.no_save_session and (
        save_video_enabled(args)
        or save_summary_enabled(args)
        or save_frame_metrics_enabled(args)
        or save_performance_enabled(args)
    )


def save_video_enabled(args: argparse.Namespace) -> bool:
    return not args.no_save_video


def save_summary_enabled(args: argparse.Namespace) -> bool:
    return not args.no_save_summary and not args.demo_only


def save_frame_metrics_enabled(args: argparse.Namespace) -> bool:
    return not args.no_save_frame_metrics and not args.demo_only


def save_performance_enabled(args: argparse.Namespace) -> bool:
    return not args.no_save_performance and not args.demo_only


def create_run_dir(args: argparse.Namespace) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_name = f"{args.name}_{stamp}"
    run_dir = ROOT / args.project / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


@dataclass
class SessionPaths:
    run_dir: Path
    output_video: Path
    output_json: Path
    metrics_json: Path
    performance_json: Path


@dataclass
class PerformanceTracker:
    latency_alpha: float = 0.85
    latency_ema_ms: float | None = None
    camera_times: deque[float] = None
    display_times: deque[float] = None

    def __post_init__(self) -> None:
        self.camera_times = deque(maxlen=120)
        self.display_times = deque(maxlen=120)

    def mark_camera(self, now: float) -> float:
        self.camera_times.append(now)
        return self._fps(self.camera_times)

    def mark_display(self, now: float) -> float:
        self.display_times.append(now)
        return self._fps(self.display_times)

    def mark_processing(self, latency_ms: float) -> float:
        if self.latency_ema_ms is None:
            self.latency_ema_ms = latency_ms
        else:
            self.latency_ema_ms = self.latency_alpha * self.latency_ema_ms + (1.0 - self.latency_alpha) * latency_ms
        return 1000.0 / max(self.latency_ema_ms, 1e-3)

    @staticmethod
    def _fps(times: deque[float]) -> float:
        if len(times) < 2:
            return 0.0
        return (len(times) - 1) / max(times[-1] - times[0], 1e-6)


class LatestFrameBuffer:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._frame: np.ndarray | None = None
        self._frame_id = 0
        self._closed = False

    def put(self, frame: np.ndarray) -> int:
        with self._condition:
            if self._closed:
                return self._frame_id
            self._frame = frame
            self._frame_id += 1
            self._condition.notify_all()
            return self._frame_id

    def get_latest(self, last_seen: int, timeout: float = 0.1) -> tuple[int, np.ndarray | None]:
        deadline = time.time() + timeout
        with self._condition:
            while not self._closed and self._frame_id <= last_seen:
                remaining = deadline - time.time()
                if remaining <= 0:
                    return last_seen, None
                self._condition.wait(timeout=remaining)
            if self._frame is None:
                return self._frame_id, None
            return self._frame_id, self._frame.copy()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()


@dataclass
class SharedState:
    stop_event: threading.Event
    raw_frames: LatestFrameBuffer
    processed_frames: LatestFrameBuffer
    metrics_lock: threading.Lock
    latest_metrics: dict
    perf_tracker: PerformanceTracker
    session_paths: SessionPaths | None


def open_camera(args: argparse.Namespace) -> cv2.VideoCapture:
    backend = 0
    if args.camera_backend == "dshow":
        backend = cv2.CAP_DSHOW
    elif args.camera_backend == "msmf":
        backend = cv2.CAP_MSMF
    capture = cv2.VideoCapture(args.camera, backend)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.camera_width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.camera_height)
    capture.set(cv2.CAP_PROP_FPS, args.camera_fps)
    if not capture.isOpened():
        raise RuntimeError(f"Failed to open camera index {args.camera}")
    return capture


def put_perf_overlay(frame: np.ndarray, perf: dict) -> None:
    lines = [
        f"CAM:{perf.get('camera_fps', 0.0):.1f} FPS  PROC:{perf.get('process_fps', 0.0):.1f} FPS  DISP:{perf.get('display_fps', 0.0):.1f} FPS",
        f"PROC_LAT:{perf.get('process_latency_ms', 0.0):.1f} ms  DROPPED:{int(perf.get('dropped_frames', 0))}",
    ]
    y = frame.shape[0] - 44
    for line in lines:
        cv2.putText(frame, line, (18, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        y += 24


def choose_embedding_candidates(candidates: list[Candidate], limit: int = 3) -> list[Candidate]:
    face_candidates = [candidate for candidate in candidates if candidate.face_bbox is not None]
    face_candidates.sort(key=lambda candidate: float((candidate.face_bbox[2] - candidate.face_bbox[0]) * (candidate.face_bbox[3] - candidate.face_bbox[1])), reverse=True)
    return face_candidates[:limit]


def collect_candidates_realtime(
    result,
    frame: np.ndarray,
    embed_model: YOLO,
    face_detectors: dict,
    classes: set[int],
    args: argparse.Namespace,
    tracked_state: TargetState | None,
    processed_index: int,
    perf: PerformanceRecorder | None = None,
) -> list[Candidate]:
    boxes = result.boxes
    if boxes is None or not boxes.is_track or len(boxes) == 0:
        return []

    xyxy = boxes.xyxy.cpu().numpy()
    track_ids = boxes.id.int().cpu().tolist()
    clss = boxes.cls.int().cpu().tolist()
    confs = boxes.conf.cpu().tolist()
    candidates: list[Candidate] = []
    tracked_candidate: Candidate | None = None

    for bbox, track_id, cls, conf in zip(xyxy, track_ids, clss, confs):
        if classes and cls not in classes:
            continue
        if perf is not None:
            perf.increment("candidate_count")
            perf.increment("face_detect_calls")
        face_hint = None
        enable_mtcnn = False
        if tracked_state is not None and int(track_id) == tracked_state.tracker_id and tracked_state.face_bbox is not None:
            face_hint = tracked_state.face_bbox
            enable_mtcnn = processed_index % max(1, args.mtcnn_interval) == 0
        face_start = time.perf_counter() if perf is not None else None
        face_bbox = detect_face_in_person(
            frame,
            np.asarray(bbox, dtype=np.float32),
            {
                "frontal": face_detectors["frontal"],
                "profile": face_detectors["profile"],
                "mtcnn": face_detectors["mtcnn"] if enable_mtcnn or face_hint is None else None,
            },
            args.face_scale_factor,
            args.face_min_neighbors,
            args.face_min_confidence,
            face_hint,
            perf,
        )
        if perf is not None and face_start is not None:
            perf.add_stage_time("face_detect_total_ms", (time.perf_counter() - face_start) * 1000.0)
        candidate = Candidate(
            bbox=np.asarray(bbox, dtype=np.float32),
            track_id=int(track_id),
            cls=int(cls),
            conf=float(conf),
            face_bbox=face_bbox,
            embedding=None,
        )
        if tracked_state is not None and candidate.track_id == tracked_state.tracker_id:
            tracked_candidate = candidate
        candidates.append(candidate)

    if tracked_state is None:
        return candidates

    if tracked_candidate is not None and is_same_tracker_candidate_valid(tracked_state, tracked_candidate, frame.shape, args):
        should_refresh = processed_index % max(1, args.reid_interval) == 0 and tracked_candidate.face_bbox is not None
        if should_refresh:
            if perf is not None:
                perf.increment("embedding_calls")
            embedding_start = time.perf_counter() if perf is not None else None
            tracked_candidate.embedding = extract_embedding(embed_model, frame, tracked_candidate.face_bbox)
            if perf is not None and embedding_start is not None:
                perf.add_stage_time("embedding_ms", (time.perf_counter() - embedding_start) * 1000.0)
        return candidates

    for candidate in choose_embedding_candidates(candidates):
        if perf is not None:
            perf.increment("embedding_calls")
        embedding_start = time.perf_counter() if perf is not None else None
        candidate.embedding = extract_embedding(embed_model, frame, candidate.face_bbox)
        if perf is not None and embedding_start is not None:
            perf.add_stage_time("embedding_ms", (time.perf_counter() - embedding_start) * 1000.0)
    return candidates


def camera_worker(capture: cv2.VideoCapture, shared: SharedState) -> None:
    while not shared.stop_event.is_set():
        ok, frame = capture.read()
        if not ok:
            time.sleep(0.01)
            continue
        shared.raw_frames.put(frame)
        now = time.perf_counter()
        camera_fps = shared.perf_tracker.mark_camera(now)
        with shared.metrics_lock:
            shared.latest_metrics["camera_fps"] = camera_fps
    capture.release()
    shared.raw_frames.close()


def processing_worker(args: argparse.Namespace, shared: SharedState) -> None:
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

    classes = set(args.classes)
    names = detect_model.names if hasattr(detect_model, "names") else {}
    state: TargetState | None = None
    processed_index = 0
    selected_at_frame: int | None = None
    last_score: float | None = None
    input_frame_id = 0
    writer = None
    frame_metrics: list[dict] = []
    total_dropped_frames = 0
    max_dropped_frames = 0
    session_start = time.perf_counter()
    perf = PerformanceRecorder(mode="realtime") if save_performance_enabled(args) else NullPerformanceRecorder(mode="realtime")

    while not shared.stop_event.is_set():
        next_frame_id, frame = shared.raw_frames.get_latest(input_frame_id, timeout=0.1)
        if frame is None:
            continue
        dropped_frames = max(0, next_frame_id - input_frame_id - 1)
        total_dropped_frames += dropped_frames
        max_dropped_frames = max(max_dropped_frames, dropped_frames)
        input_frame_id = next_frame_id
        processed_index += 1
        perf.start_frame(processed_index, source_frame_id=next_frame_id, dropped_frames_before=dropped_frames)
        tick = time.perf_counter()

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
                candidates = collect_candidates_realtime(result, frame, embed_model, face_detectors, classes, args, state, processed_index, perf)
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
                    if candidate is None and args.fallback_to_first_face:
                        candidate = largest_face_candidate(candidates)
                    if candidate is not None:
                        if candidate.face_bbox is not None and candidate.embedding is None:
                            perf.increment("embedding_calls")
                            embedding_start = time.perf_counter()
                            candidate.embedding = extract_embedding(embed_model, frame, candidate.face_bbox)
                            perf.add_stage_time("embedding_ms", (time.perf_counter() - embedding_start) * 1000.0)
                        state = TargetState(target_name=args.target_name, tracker_id=candidate.track_id, bbox=candidate.bbox.copy())
                        state.face_hold_frames = args.face_hold
                        state.update(candidate)
                        selected_at_frame = processed_index
                        last_score = 1.0
                else:
                    tracked_candidate = next((candidate for candidate in candidates if candidate.track_id == state.tracker_id), None)
                    if tracked_candidate is not None and is_same_tracker_candidate_valid(state, tracked_candidate, frame.shape, args):
                        last_score = 1.0
                        state.update(tracked_candidate)
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

                metric = frame_metric(processed_index, max(1.0, float(getattr(args, "output_fps", args.camera_fps))), frame.shape, state, args.control_deadband)
                metric["source_frame_id"] = next_frame_id
                metric["dropped_frames_before"] = dropped_frames
                draw_control_overlay(display_frame, metric)
                if save_frame_metrics_enabled(args):
                    frame_metrics.append(metric)

            with perf.time_stage("copy_output_frame_ms"):
                output_frame = display_frame.copy()

            if save_video_enabled(args) and session_saving_enabled(args):
                if writer is None:
                    assert shared.session_paths is not None
                    writer = cv2.VideoWriter(
                        str(shared.session_paths.output_video),
                        cv2.VideoWriter_fourcc(*"mp4v"),
                        max(1.0, float(getattr(args, "output_fps", args.camera_fps))),
                        (output_frame.shape[1], output_frame.shape[0]),
                    )
                with perf.time_stage("write_video_ms"):
                    writer.write(output_frame)

        process_latency_ms = (time.perf_counter() - tick) * 1000.0
        process_fps = shared.perf_tracker.mark_processing(process_latency_ms)
        with shared.metrics_lock:
            shared.latest_metrics.update(
                {
                    "process_latency_ms": process_latency_ms,
                    "process_fps": process_fps,
                    "dropped_frames": dropped_frames,
                    "dropped_frames_total": total_dropped_frames,
                    "max_dropped_frames": max_dropped_frames,
                    "selected_at_frame": selected_at_frame,
                    "final_lock_mode": resolve_lock_mode(state),
                    "tracker_id": None if state is None else state.tracker_id,
                }
            )
            overlay_perf = dict(shared.latest_metrics)

        perf.sample_resources()
        perf.end_frame()
        put_perf_overlay(display_frame, overlay_perf)

        if args.display_width > 0 and display_frame.shape[1] > args.display_width:
            scale = args.display_width / display_frame.shape[1]
            display_frame = cv2.resize(display_frame, (args.display_width, int(display_frame.shape[0] * scale)), interpolation=cv2.INTER_LINEAR)

        shared.processed_frames.put(display_frame)

    if writer is not None:
        writer.release()

    if session_saving_enabled(args) and shared.session_paths is not None:
        session_duration = time.perf_counter() - session_start
        summary = {
            "source": f"camera:{args.camera}",
            "output_video": str(shared.session_paths.output_video) if save_video_enabled(args) else None,
            "frame_metrics_json": str(shared.session_paths.metrics_json) if save_frame_metrics_enabled(args) else None,
            "performance_json": str(shared.session_paths.performance_json) if save_performance_enabled(args) else None,
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
            "processed_frames": processed_index,
            "session_duration_sec": round(float(session_duration), 2),
            "requested_camera_fps": args.camera_fps,
            "output_fps": round(float(getattr(args, "output_fps", args.camera_fps)), 2),
            "camera_fps": round(float(shared.latest_metrics.get("camera_fps", 0.0)), 2),
            "process_fps": round(float(shared.latest_metrics.get("process_fps", 0.0)), 2),
            "display_fps": round(float(shared.latest_metrics.get("display_fps", 0.0)), 2),
            "process_latency_ms": round(float(shared.latest_metrics.get("process_latency_ms", 0.0)), 2),
            "total_dropped_frames": total_dropped_frames,
            "max_dropped_frames": max_dropped_frames,
        }
        if save_performance_enabled(args):
            performance_report = perf.build_report(summary)
            shared.session_paths.performance_json.write_text(json.dumps(performance_report, ensure_ascii=False, indent=2), encoding="utf-8")
        if save_frame_metrics_enabled(args):
            shared.session_paths.metrics_json.write_text(json.dumps(frame_metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        if save_summary_enabled(args):
            shared.session_paths.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    shared.processed_frames.close()


def display_loop(args: argparse.Namespace, shared: SharedState) -> None:
    cv2.namedWindow("Lock Target Realtime", cv2.WINDOW_NORMAL)
    last_frame_id = 0
    last_frame: np.ndarray | None = None
    display_times: deque[float] = deque(maxlen=60)

    while not shared.stop_event.is_set():
        next_frame_id, frame = shared.processed_frames.get_latest(last_frame_id, timeout=0.01)
        if frame is not None:
            last_frame = frame
            last_frame_id = next_frame_id
        if last_frame is not None:
            display_fps = shared.perf_tracker.mark_display(time.perf_counter())
            with shared.metrics_lock:
                shared.latest_metrics["display_fps"] = display_fps
            cv2.imshow("Lock Target Realtime", last_frame)

        key = cv2.waitKey(1) & 0xFF
        if key in {27, ord("q")}:
            shared.stop_event.set()
            break
    cv2.destroyAllWindows()


def main() -> None:
    args = parse_args()
    capture = open_camera(args)
    args.output_fps = capture.get(cv2.CAP_PROP_FPS) or float(args.camera_fps)
    session_paths = None
    if session_saving_enabled(args):
        run_dir = create_run_dir(args)
        session_paths = SessionPaths(
            run_dir=run_dir,
            output_video=run_dir / f"camera_{args.camera}_locked.mp4",
            output_json=run_dir / f"camera_{args.camera}_summary.json",
            metrics_json=run_dir / f"camera_{args.camera}_frame_metrics.json",
            performance_json=run_dir / f"camera_{args.camera}_performance.json",
        )
    shared = SharedState(
        stop_event=threading.Event(),
        raw_frames=LatestFrameBuffer(),
        processed_frames=LatestFrameBuffer(),
        metrics_lock=threading.Lock(),
        latest_metrics={"camera_fps": 0.0, "process_fps": 0.0, "display_fps": 0.0, "process_latency_ms": 0.0, "dropped_frames": 0, "dropped_frames_total": 0, "max_dropped_frames": 0},
        perf_tracker=PerformanceTracker(),
        session_paths=session_paths,
    )

    camera_thread = threading.Thread(target=camera_worker, args=(capture, shared), daemon=True)
    processor_thread = threading.Thread(target=processing_worker, args=(args, shared), daemon=True)
    camera_thread.start()
    processor_thread.start()

    try:
        display_loop(args, shared)
    finally:
        shared.stop_event.set()
        shared.raw_frames.close()
        shared.processed_frames.close()
        camera_thread.join(timeout=2.0)
        processor_thread.join(timeout=2.0)


if __name__ == "__main__":
    main()