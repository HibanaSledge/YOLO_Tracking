from __future__ import annotations

import argparse
import json
import sys
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

    def predicted_bbox(self) -> np.ndarray:
        predicted = self.bbox.copy().astype(np.float32)
        predicted[[0, 2]] += self.velocity[0]
        predicted[[1, 3]] += self.velocity[1]
        return predicted

    def update(self, candidate: Candidate) -> bool:
        previous_center = np.array([(self.bbox[0] + self.bbox[2]) / 2.0, (self.bbox[1] + self.bbox[3]) / 2.0], dtype=np.float32)
        switched = candidate.track_id != self.tracker_id
        if switched:
            self.tracker_switches += 1
            if self.lost_frames > 0:
                self.reacquired_count += 1
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
            self.face_miss_frames = 0
            self.face_detected_frames += 1
        else:
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
    parser.add_argument("--face-scale-factor", type=float, default=1.05, help="OpenCV face detector scale factor.")
    parser.add_argument("--face-min-neighbors", type=int, default=3, help="OpenCV face detector minNeighbors.")
    parser.add_argument("--face-hold", type=int, default=6, help="How many frames to keep the last face box when face detection briefly fails.")
    parser.add_argument("--fallback-to-first-face", action="store_true", help="If the requested initial track id is not available, fall back to the first detected face.")
    parser.add_argument("--face-min-confidence", type=float, default=0.30, help="Minimum MTCNN face detection confidence in hybrid mode.")
    return parser.parse_args()


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


def bbox_area(bbox: np.ndarray | None) -> float:
    if bbox is None:
        return 0.0
    return max(0.0, float(bbox[2] - bbox[0])) * max(0.0, float(bbox[3] - bbox[1]))


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
    if frontal is not None and not frontal.empty():
        faces = frontal.detectMultiScale(
            gray,
            scaleFactor=scale_factor,
            minNeighbors=min_neighbors,
            minSize=(min_face, min_face),
        )
        for fx, fy, fw, fh in faces:
            absolute_faces.append(
                np.array([x1 + fx, y1 + fy, x1 + fx + fw, y1 + fy + fh], dtype=np.float32)
            )

    profile = face_detectors.get("profile")
    if profile is not None and not profile.empty():
        left_faces = profile.detectMultiScale(
            gray,
            scaleFactor=max(1.03, scale_factor),
            minNeighbors=max(2, min_neighbors - 1),
            minSize=(min_face, min_face),
        )
        for fx, fy, fw, fh in left_faces:
            absolute_faces.append(
                np.array([x1 + fx, y1 + fy, x1 + fx + fw, y1 + fy + fh], dtype=np.float32)
            )
        flipped = cv2.flip(gray, 1)
        right_faces = profile.detectMultiScale(
            flipped,
            scaleFactor=max(1.03, scale_factor),
            minNeighbors=max(2, min_neighbors - 1),
            minSize=(min_face, min_face),
        )
        for fx, fy, fw, fh in right_faces:
            rx = gray.shape[1] - fx - fw
            absolute_faces.append(
                np.array([x1 + rx, y1 + fy, x1 + rx + fw, y1 + fy + fh], dtype=np.float32)
            )

    mtcnn = face_detectors.get("mtcnn")
    if mtcnn is not None:
        rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
        boxes, probs = mtcnn.detect(rgb)
        if boxes is not None and probs is not None:
            for box, prob in zip(boxes, probs):
                if box is None or prob is None or float(prob) < min_confidence:
                    continue
                fx1, fy1, fx2, fy2 = box.tolist()
                absolute_faces.append(np.array([x1 + fx1, y1 + fy1, x1 + fx2, y1 + fy2], dtype=np.float32))

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
        face_hint = None
        if tracked_state is not None and track_id == tracked_state.tracker_id and tracked_state.face_bbox is not None:
            face_hint = tracked_state.face_bbox
        face_bbox = detect_face_in_person(
            frame,
            np.asarray(bbox, dtype=np.float32),
            face_detectors,
            args.face_scale_factor,
            args.face_min_neighbors,
            args.face_min_confidence,
            face_hint,
        )
        candidates.append(
            Candidate(
                bbox=np.asarray(bbox, dtype=np.float32),
                track_id=int(track_id),
                cls=int(cls),
                conf=float(conf),
                face_bbox=face_bbox,
                embedding=None if face_bbox is None else extract_embedding(embed_model, frame, face_bbox),
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
    color = (0, 80, 255) if state.face_miss_frames == 0 else (0, 180, 255)
    label = f"{state.target_name} tid:{state.tracker_id}"
    if score is not None and score < 1.0:
        label += f" score:{score:.2f}"
    if state.face_miss_frames > 0:
        label += f" face-hold:{state.face_miss_frames}"
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 4)
    cv2.putText(frame, label, (x1, max(24, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)


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
    writer = cv2.VideoWriter(str(output_video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

    names = detect_model.names if hasattr(detect_model, "names") else {}
    state: TargetState | None = None
    frame_index = 0
    classes = set(args.classes)
    selected_at_frame = None
    last_score = None

    while True:
        success, frame = capture.read()
        if not success:
            break
        frame_index += 1
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

        candidates = collect_candidates(result, frame, embed_model, face_detectors, classes, args, state)
        display_frame = result.plot(conf=True, labels=True) if args.save_all_boxes else frame.copy()

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

        writer.write(display_frame)
        if args.show:
            cv2.imshow("Lock Target", display_frame)
            key = cv2.waitKey(1) & 0xFF
            if key in {27, ord("q")}:
                break

    capture.release()
    writer.release()
    cv2.destroyAllWindows()

    summary = {
        "source": str(source),
        "output_video": str(output_video),
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
    }
    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()