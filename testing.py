from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
LOCAL_PACKAGE_PARENT = ROOT.parent

if str(LOCAL_PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(LOCAL_PACKAGE_PARENT))

from ultralytics import YOLO  # noqa: E402
import ultralytics  # noqa: E402


DEFAULT_MODEL = "yolo26n.yaml"
DEFAULT_DATA = "datasets/offline_demo.yaml"
DEFAULT_PROJECT = "outputs"
DEFAULT_NAME = "train"


def model_arg_was_provided(argv: list[str] | None = None) -> bool:
    argv = sys.argv[1:] if argv is None else argv
    return any(arg == "--model" or arg.startswith("--model=") for arg in argv)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train and validate a YOLO detection model on the offline demo dataset."
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Model YAML or weights path. Explicit existing .pt weights are validated without training.",
    )
    parser.add_argument("--data", default=DEFAULT_DATA, help="Dataset YAML path.")
    parser.add_argument("--epochs", type=int, default=10, help="Number of training epochs.")
    parser.add_argument("--project", default=DEFAULT_PROJECT, help="Output project directory.")
    parser.add_argument("--name", default=DEFAULT_NAME, help="Run name under the project directory.")
    parser.add_argument("--imgsz", type=int, default=640, help="Input image size.")
    parser.add_argument("--batch", type=int, default=16, help="Training batch size.")
    parser.add_argument("--workers", type=int, default=8, help="DataLoader worker count.")
    parser.add_argument("--device", default=None, help="Device, for example 'cpu', '0', or '0,1'.")
    parser.add_argument("--seed", type=int, default=0, help="Random seed.")
    parser.add_argument("--patience", type=int, default=100, help="Early stopping patience.")
    parser.add_argument("--conf", type=float, default=None, help="Validation confidence threshold.")
    parser.add_argument("--iou", type=float, default=0.7, help="Validation NMS IoU threshold.")
    parser.add_argument("--split", default="val", help="Dataset split used for validation.")
    parser.add_argument("--resume", action="store_true", help="Resume an unfinished training run when possible.")
    parser.add_argument("--skip-train", action="store_true", help="Skip training and run validation only.")
    parser.add_argument("--skip-val", action="store_true", help="Skip validation after training.")
    parser.add_argument(
        "--use-best-for-val",
        action="store_true",
        help="Validate the best.pt checkpoint from the current run when it exists.",
    )
    parser.add_argument(
        "--exist-ok",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Allow reusing an existing output directory.",
    )
    parser.add_argument(
        "--plots",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Save training and validation plots.",
    )
    parser.add_argument(
        "--visualize",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Save feature/debug visualizations supported by the local Ultralytics code.",
    )
    parser.add_argument("--save-json", action="store_true", help="Save validation predictions as JSON when supported.")
    parser.add_argument("--save-txt", action="store_true", help="Save validation predictions as YOLO txt labels.")
    parser.add_argument("--save-conf", action="store_true", help="Include confidence scores in saved txt labels.")
    return parser.parse_args()


def resolve_existing_file(path: str, description: str) -> str:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    if not candidate.exists():
        raise FileNotFoundError(f"{description} not found: {candidate}")
    return str(candidate)


def compact_kwargs(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def run_training(model: YOLO, args: argparse.Namespace) -> Any:
    train_args = compact_kwargs(
        {
            "data": args.data,
            "epochs": args.epochs,
            "project": args.project,
            "name": args.name,
            "exist_ok": args.exist_ok,
            "plots": args.plots,
            "visualize": args.visualize,
            "imgsz": args.imgsz,
            "batch": args.batch,
            "workers": args.workers,
            "device": args.device,
            "seed": args.seed,
            "patience": args.patience,
            "resume": args.resume,
        }
    )
    print("Training with arguments:", train_args)
    return model.train(**train_args)


def find_best_checkpoint(model: YOLO, args: argparse.Namespace) -> Path | None:
    trainer = getattr(model, "trainer", None)
    if trainer is not None:
        best = getattr(trainer, "best", None)
        if best and Path(best).exists():
            return Path(best)

    candidate = ROOT / "runs" / "detect" / args.project / args.name / "weights" / "best.pt"
    return candidate if candidate.exists() else None


def run_validation(model: YOLO, args: argparse.Namespace) -> Any:
    val_args = compact_kwargs(
        {
            "data": args.data,
            "plots": args.plots,
            "visualize": args.visualize,
            "imgsz": args.imgsz,
            "batch": args.batch,
            "workers": args.workers,
            "device": args.device,
            "split": args.split,
            "conf": args.conf,
            "iou": args.iou,
            "save_json": args.save_json,
            "save_txt": args.save_txt,
            "save_conf": args.save_conf,
        }
    )
    print("Validating with arguments:", val_args)
    return model.val(**val_args)


def main() -> None:
    args = parse_args()
    model_was_provided = model_arg_was_provided()
    os.chdir(ROOT)

    args.data = resolve_existing_file(args.data, "Dataset YAML")
    model_path = Path(args.model)
    if model_path.suffix in {".pt", ".yaml", ".yml"} and not model_path.is_absolute() and (ROOT / model_path).exists():
        model_path = ROOT / model_path
        args.model = str(model_path)

    print("ultralytics from:", ultralytics.__file__)
    print("working directory:", Path.cwd())

    model = YOLO(args.model)

    existing_weights_for_eval = model_was_provided and model_path.suffix == ".pt" and model_path.exists()
    if existing_weights_for_eval:
        print("Existing model weights were provided; skipping training and running validation only.")

    if not args.skip_train and not existing_weights_for_eval:
        run_training(model, args)

    if args.skip_val:
        return

    if args.use_best_for_val:
        best = find_best_checkpoint(model, args)
        if best is not None:
            print("Loading best checkpoint for validation:", best)
            model = YOLO(str(best))
        else:
            print("best.pt was not found; validating the current model object instead.")

    run_validation(model, args)


if __name__ == "__main__":
    main()
