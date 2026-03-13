"""Phase C4: Export fine-tuned YOLOv8-nano to ONNX for Pi deployment.

Exports the trained model to ONNX format for use with
cv2.dnn.readNetFromONNX on Raspberry Pi 2.

Compatible with the YoloTinyDetector class in telegram_sender.py.

Usage:
    python export_for_pi.py [--model path/to/best.pt] [--imgsz 224]
"""

import argparse
import shutil
import sys
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


def main():
    parser = argparse.ArgumentParser(description="Export model for Pi deployment")
    parser.add_argument("--model", type=str, default=None,
                        help="Path to trained .pt model")
    parser.add_argument("--imgsz", type=int, default=224,
                        help="Input size for Pi inference (default: 224)")
    args = parser.parse_args()

    model_path = args.model
    if model_path is None:
        model_path = MODELS_DIR / "yolov8n_birdpi_best.pt"

    if not Path(model_path).exists():
        print(f"[ERR] Model not found: {model_path}")
        print("  Run train_yolov8_nano.py first")
        sys.exit(1)

    from ultralytics import YOLO

    print(f"[C4] Exporting model for Raspberry Pi 2")
    print(f"  Source: {model_path}")
    print(f"  Input size: {args.imgsz}x{args.imgsz}")

    model = YOLO(str(model_path))

    # Export to ONNX (primary format for cv2.dnn on Pi)
    print("\n  Exporting ONNX...")
    onnx_path = model.export(
        format="onnx",
        imgsz=args.imgsz,
        simplify=True,
        opset=12,  # Good compatibility with OpenCV DNN
        dynamic=False,  # Fixed input size for Pi
    )
    print(f"  ONNX exported: {onnx_path}")

    # Copy to standard location
    final_onnx = MODELS_DIR / f"yolov8n_birdpi_{args.imgsz}.onnx"
    shutil.copy2(str(onnx_path), str(final_onnx))
    print(f"  Final: {final_onnx}")

    # Print deployment instructions
    print(f"""
[DEPLOY] To use on Raspberry Pi 2:

1. Copy {final_onnx.name} to ~/birdpi/models/

2. Update config.env:
   TELEGRAM_AI_MODEL=~/birdpi/models/{final_onnx.name}
   TELEGRAM_AI_INPUT_SIZE={args.imgsz}

3. The YoloTinyDetector in telegram_sender.py will auto-detect
   the ONNX model and use cv2.dnn.readNetFromONNX.

Model info:
  - Input: {args.imgsz}x{args.imgsz} RGB
  - Classes: bird (0), other_animal (1)
  - Framework: OpenCV DNN (no PyTorch needed on Pi)
""")


if __name__ == "__main__":
    main()
