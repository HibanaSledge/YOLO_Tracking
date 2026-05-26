from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch

from ultralytics.utils import LOGGER

_NMS_DEBUG = {"enabled": False, "prefix": ""}


def debug_enabled(args: Any) -> bool:
    """Return True when debug visualization is enabled."""
    return bool(getattr(args, "visualize", False))


def ensure_debug_dir(save_dir: str | Path, *parts: str) -> Path:
    """Create and return a debug output directory under the run save_dir."""
    path = Path(save_dir) / "debug"
    for part in parts:
        path /= str(part)
    path.mkdir(parents=True, exist_ok=True)
    return path


def debug_file_prefix(stage: str, batch_i: int, epoch: int | None = None) -> str:
    """Build a stable file prefix for debug artifacts."""
    if epoch is None:
        return f"{stage}_batch{batch_i:04d}"
    return f"{stage}_epoch{epoch:03d}_batch{batch_i:04d}"


def should_save_debug(batch_i: int | None, limit: int = 3) -> bool:
    """Limit debug artifact generation to the first few batches."""
    return batch_i is not None and batch_i < limit


def save_tensor_npy(tensor: torch.Tensor | np.ndarray, path: str | Path) -> None:
    """Save a tensor or ndarray to .npy."""
    array = tensor.detach().float().cpu().numpy() if isinstance(tensor, torch.Tensor) else np.asarray(tensor)
    np.save(str(path), array)


def tensor_to_image(tensor: torch.Tensor | np.ndarray) -> np.ndarray:
    """Convert a BCHW/CHW tensor or ndarray to an RGB uint8 image."""
    if isinstance(tensor, torch.Tensor):
        array = tensor.detach().float().cpu().numpy()
    else:
        array = np.asarray(tensor)

    if array.ndim == 4:
        array = array[0]
    if array.ndim == 3 and array.shape[0] in {1, 3}:
        array = np.transpose(array, (1, 2, 0))
    if array.ndim == 2:
        array = array[..., None]
    if array.shape[-1] == 1:
        array = np.repeat(array, 3, axis=-1)
    if array.max() <= 1.0:
        array = array * 255.0
    return np.ascontiguousarray(np.clip(array, 0, 255).astype(np.uint8))


def add_banner(image: np.ndarray, title: str, lines: list[str] | None = None, color: tuple[int, int, int] = (40, 180, 240)) -> np.ndarray:
    """Add a banner and optional info lines above an RGB image."""
    lines = lines or []
    img = image.copy()
    if img.ndim == 2:
        img = np.repeat(img[..., None], 3, axis=-1)
    banner_h = 52 + 24 * len(lines)
    canvas = np.full((img.shape[0] + banner_h, img.shape[1], 3), 245, dtype=np.uint8)
    canvas[:banner_h] = np.array(color, dtype=np.uint8)
    canvas[banner_h:] = img
    cv2.putText(canvas, title, (16, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
    for i, line in enumerate(lines):
        cv2.putText(
            canvas,
            line,
            (16, 58 + i * 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return canvas


def save_rgb_image(image: np.ndarray, path: str | Path, title: str | None = None, lines: list[str] | None = None) -> None:
    """Save an RGB image, optionally with a title banner."""
    img = np.ascontiguousarray(image.copy())
    if title:
        img = add_banner(img, title, lines)
    cv2.imwrite(str(path), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))


def save_tensor_image(
    tensor: torch.Tensor | np.ndarray, path: str | Path, title: str | None = None, lines: list[str] | None = None
) -> None:
    """Save the first image from a BCHW/CHW tensor or ndarray with optional title banner."""
    save_rgb_image(tensor_to_image(tensor), path, title=title, lines=lines)


def annotate_image_file(
    path: str | Path, title: str, lines: list[str] | None = None, color: tuple[int, int, int] = (40, 180, 240)
) -> None:
    """Add a title banner to an already saved image file."""
    path = Path(path)
    if not path.exists():
        LOGGER.warning(f"[debug] skip annotate missing image: {path}")
        return
    image = cv2.imread(str(path))
    if image is None:
        return
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = add_banner(image, title, lines, color=color)
    cv2.imwrite(str(path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))


def save_feature_heatmap(
    tensor: torch.Tensor | np.ndarray,
    path: str | Path,
    title: str,
    mode: str = "mean",
    line: str | None = None,
) -> None:
    """Save a feature tensor as a color heatmap."""
    if isinstance(tensor, torch.Tensor):
        array = tensor.detach().float().cpu().numpy()
    else:
        array = np.asarray(tensor)
    if array.ndim == 4:
        array = array[0]
    if array.ndim == 3:
        if mode == "max":
            array = array.max(axis=0)
        else:
            array = array.mean(axis=0)
    array = array.astype(np.float32)
    lo, hi = np.percentile(array, (1, 99))
    if hi <= lo:
        lo, hi = float(array.min()), float(array.max()) if float(array.max()) > float(array.min()) else (0.0, 1.0)
    array = np.clip((array - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
    array = (array * 255).astype(np.uint8)
    heat = cv2.applyColorMap(array, cv2.COLORMAP_TURBO)
    heat = cv2.cvtColor(heat, cv2.COLOR_BGR2RGB)
    h, w = heat.shape[:2]
    max_dim = max(h, w)
    if max_dim < 640:
        scale = 640 / max_dim
        heat = cv2.resize(
            heat,
            (max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
            interpolation=cv2.INTER_NEAREST,
        )
    save_rgb_image(heat, path, title=title, lines=[line] if line else None)


def save_matrix_heatmap(
    matrix: torch.Tensor | np.ndarray,
    path: str | Path,
    title: str,
    line: str | None = None,
    min_size: tuple[int, int] = (960, 480),
) -> None:
    """Save a 2D matrix heatmap with readable output size."""
    if isinstance(matrix, torch.Tensor):
        array = matrix.detach().float().cpu().numpy()
    else:
        array = np.asarray(matrix)
    if array.ndim != 2:
        array = np.squeeze(array)
    array = array.astype(np.float32)
    lo, hi = np.percentile(array, (1, 99))
    if hi <= lo:
        lo = float(array.min())
        hi = float(array.max())
        if hi <= lo:
            hi = lo + 1.0
    array = np.clip((array - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
    heat = cv2.applyColorMap((array * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
    heat = cv2.cvtColor(heat, cv2.COLOR_BGR2RGB)
    target_w, target_h = min_size
    heat = cv2.resize(heat, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
    save_rgb_image(heat, path, title=title, lines=[line] if line else None)


def save_boxes_overlay(
    image: torch.Tensor | np.ndarray,
    boxes: torch.Tensor | np.ndarray,
    path: str | Path,
    title: str,
    scores: torch.Tensor | np.ndarray | None = None,
    box_format: str = "xyxy",
    max_boxes: int = 50,
) -> None:
    """Draw boxes on an image and save with a title banner."""
    img = np.ascontiguousarray(tensor_to_image(image).copy())
    h, w = img.shape[:2]
    boxes_np = boxes.detach().float().cpu().numpy() if isinstance(boxes, torch.Tensor) else np.asarray(boxes)
    if boxes_np.ndim == 3:
        boxes_np = boxes_np[0]
    scores_np = None
    if scores is not None:
        scores_np = scores.detach().float().cpu().numpy() if isinstance(scores, torch.Tensor) else np.asarray(scores)
        if scores_np.ndim > 1:
            scores_np = scores_np.reshape(-1)
    count = min(len(boxes_np), max_boxes)
    for i in range(count):
        box = boxes_np[i].copy()
        if box_format == "xywh":
            cx, cy, bw, bh = box[:4]
            box = np.array([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], dtype=np.float32)
        x1, y1, x2, y2 = box[:4].astype(int)
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(0, min(x2, w - 1))
        y2 = max(0, min(y2, h - 1))
        color = (255, 80, 80) if i < 10 else (255, 210, 80)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        if scores_np is not None and i < len(scores_np):
            cv2.putText(
                img,
                f"{scores_np[i]:.3f}",
                (x1, max(18, y1 + 18)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
                cv2.LINE_AA,
            )
    save_rgb_image(img, path, title=title, lines=[f"boxes_shown={count}", f"image_size={w}x{h}"])


def log_tensor_stats(name: str, tensor: torch.Tensor | np.ndarray) -> None:
    """Log concise tensor statistics for debug tracing."""
    if isinstance(tensor, torch.Tensor):
        t = tensor.detach()
        LOGGER.info(
            f"[debug] {name}: shape={tuple(t.shape)} dtype={t.dtype} device={t.device} "
            f"min={float(t.min()):.4f} max={float(t.max()):.4f}"
        )
    else:
        a = np.asarray(tensor)
        LOGGER.info(
            f"[debug] {name}: shape={a.shape} dtype={a.dtype} min={float(a.min()):.4f} max={float(a.max()):.4f}"
        )


def set_debug_context(model: Any, save_dir: str | Path, stage: str, batch_i: int, epoch: int | None = None) -> dict:
    """Attach per-batch debug context to the model and detection head."""
    module = model.module if hasattr(model, "module") else model
    if hasattr(module, "model") and hasattr(module.model, "model"):
        base_model = module.model
    elif hasattr(module, "model") and isinstance(module.model, torch.nn.Sequential):
        base_model = module
    else:
        base_model = module
    context = {"enabled": True, "save_dir": Path(save_dir), "stage": stage, "batch_i": batch_i, "epoch": epoch}
    setattr(base_model, "_debug_context", context)
    head = None
    if hasattr(base_model, "model") and len(base_model.model):
        head = base_model.model[-1]
    if head is not None:
        setattr(head, "_debug_context", context)
    return context


def get_debug_context(module: Any) -> dict | None:
    """Fetch a previously attached debug context."""
    return getattr(module, "_debug_context", None)


def set_nms_debug(enabled: bool, prefix: str = "") -> None:
    """Set module-level NMS debug logging state."""
    _NMS_DEBUG["enabled"] = enabled
    _NMS_DEBUG["prefix"] = prefix


def get_nms_debug() -> dict[str, Any]:
    """Return current NMS debug state."""
    return _NMS_DEBUG
