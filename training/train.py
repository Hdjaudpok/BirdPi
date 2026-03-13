"""Train YOLOv8 for bird detection (PC-first, no Pi required)."""

import argparse
import shutil
import sys
from pathlib import Path

DATASET_DIR = Path(__file__).resolve().parent.parent / "dataset"
DATA_YAML = DATASET_DIR / "data.yaml"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "models"


def resolve_device(requested: str) -> str:
    """Resolve training device.

    - "auto": GPU 0 if CUDA is available, else CPU
    - anything else: forwarded as-is to Ultralytics
    """
    if requested != "auto":
        return requested
    try:
        import torch

        return "0" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def main() -> int:
    parser = argparse.ArgumentParser(description="Train YOLO model for birdpi bird detection")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--imgsz", type=int, default=416)
    parser.add_argument("--device", type=str, default="auto",
                        help="auto | cpu | 0 | 0,1 ...")
    parser.add_argument("--model", type=str, default="yolov8n.pt",
                        help="Base checkpoint (default: yolov8n.pt)")
    parser.add_argument("--name", type=str, default="yolov8n_birdpi",
                        help="Run name under ml_pipeline/models/")
    parser.add_argument("--patience", type=int, default=15)
    parser.add_argument("--save-period", type=int, default=5)
    args = parser.parse_args()

    if not DATA_YAML.exists():
        print(f"[ERR] {DATA_YAML} not found. Run prepare_yolo_dataset.py first.")
        return 1

    from ultralytics import YOLO

    device = resolve_device(args.device)
    run_dir = OUTPUT_DIR / args.name

    print("[C2] Training YOLO for birdpi bird detection")
    print(f"  Dataset : {DATA_YAML}")
    print(f"  Model   : {args.model}")
    print(f"  Device  : {device}")
    print(f"  Epochs  : {args.epochs} | Batch: {args.batch} | ImgSz: {args.imgsz}")
    print(f"  Run dir : {run_dir}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model = YOLO(args.model)

    model.train(
        data=str(DATA_YAML),
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=device,
        project=str(OUTPUT_DIR),
        name=args.name,
        exist_ok=True,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        flipud=0.0,
        fliplr=0.5,
        mosaic=1.0,
        mixup=0.0,
        scale=0.5,
        translate=0.1,
        degrees=0.0,
        perspective=0.0,
        lr0=0.01,
        lrf=0.01,
        warmup_epochs=3,
        weight_decay=0.0005,
        patience=args.patience,
        save_period=args.save_period,
        plots=True,
        verbose=True,
    )

    best_pt = run_dir / "weights" / "best.pt"
    if best_pt.exists():
        final_path = OUTPUT_DIR / f"{args.name}_best.pt"
        shutil.copy2(str(best_pt), str(final_path))
        print(f"\n[DONE] Best model copied to: {final_path}")
        return 0

    print("\n[WARN] best.pt not found in training output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
