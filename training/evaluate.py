"""Evaluate YOLO models for bird detection on val/test splits."""

import argparse
import json
import sys
from pathlib import Path

DATASET_DIR = Path(__file__).resolve().parent.parent / "dataset"
DATA_YAML = DATASET_DIR / "data.yaml"
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def resolve_device(requested: str) -> str:
    if requested != "auto":
        return requested
    try:
        import torch

        return "0" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def evaluate_model(model_path, data_yaml, name, device="auto", split="test"):
    """Run YOLO validation and return metrics."""
    from ultralytics import YOLO

    device = resolve_device(device)
    print(f"\n[EVAL] {name}: {model_path} (split={split}, device={device})")
    model = YOLO(str(model_path))

    results = model.val(
        data=str(data_yaml),
        split=split,
        device=device,
        verbose=True,
        plots=True,
        save_json=True,
        project=str(RESULTS_DIR),
        name=name,
        exist_ok=True,
    )

    metrics = {
        "model": name,
        "model_path": str(model_path),
        "split": split,
        "device": device,
        "mAP50": float(results.box.map50),
        "mAP50_95": float(results.box.map),
        "precision": float(results.box.mp),
        "recall": float(results.box.mr),
    }

    if hasattr(results.box, "ap_class_index"):
        class_names = results.names
        for i, cls_idx in enumerate(results.box.ap_class_index):
            cls_name = class_names[int(cls_idx)]
            metrics[f"AP50_{cls_name}"] = float(results.box.ap50[i])

    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate models on val/test set")
    parser.add_argument("--model", type=str, default=None,
                        help="Path to fine-tuned model (default: auto-detect)")
    parser.add_argument("--device", type=str, default="auto",
                        help="auto | cpu | 0 | 0,1 ...")
    parser.add_argument("--split", type=str, default="test",
                        choices=["train", "val", "test"])
    parser.add_argument("--no-baseline", action="store_true",
                        help="Skip COCO baseline evaluation")
    args = parser.parse_args()

    if not DATA_YAML.exists():
        print(f"[ERR] {DATA_YAML} not found")
        return 1

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    all_metrics = []

    if not args.no_baseline:
        print("=" * 60)
        print("Evaluating COCO pretrained YOLOv8n (baseline)")
        print("=" * 60)
        baseline_metrics = evaluate_model(
            "yolov8n.pt",
            DATA_YAML,
            "baseline_coco",
            device=args.device,
            split=args.split,
        )
        all_metrics.append(baseline_metrics)
    else:
        baseline_metrics = None

    finetuned_path = Path(args.model) if args.model else MODELS_DIR / "yolov8n_birdpi_best.pt"

    if finetuned_path.exists():
        print("=" * 60)
        print("Evaluating fine-tuned YOLOv8n birdpi")
        print("=" * 60)
        finetuned_metrics = evaluate_model(
            finetuned_path,
            DATA_YAML,
            "finetuned_birdpi",
            device=args.device,
            split=args.split,
        )
        all_metrics.append(finetuned_metrics)

        if baseline_metrics is not None:
            print("\n" + "=" * 60)
            print("COMPARISON")
            print("=" * 60)
            print(f"{'Metric':<20} {'COCO baseline':>15} {'Fine-tuned':>15} {'Delta':>10}")
            print("-" * 60)
            for key in ["mAP50", "mAP50_95", "precision", "recall"]:
                b = baseline_metrics[key]
                f = finetuned_metrics[key]
                delta = f - b
                sign = "+" if delta >= 0 else ""
                print(f"{key:<20} {b:>14.3f} {f:>14.3f} {sign}{delta:>9.3f}")
    else:
        print(f"\n[SKIP] Fine-tuned model not found: {finetuned_path}")
        print("  Run train_yolov8_nano.py first")

    results_path = RESULTS_DIR / "evaluation_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, indent=2)
    print(f"\n  Results saved: {results_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
