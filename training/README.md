# Training — Custom YOLOv8 Model

This directory contains the tools to train and export a custom YOLOv8-nano model for BirdPi. All training runs on your PC. The Pi only needs the exported `.onnx` file.

---

## Overview

The training pipeline has four stages:

1. Prepare dataset (images + YOLO-format labels)
2. Train YOLOv8-nano
3. Evaluate results
4. Export to ONNX for Pi inference

The bundled pre-trained model (`yolov8n_birdpi_224.onnx`) covers two classes: `bird` and `other_animal`. Training your own model lets you fine-tune on your specific species, camera angle, and lighting conditions.

---

## Requirements

- Python 3.10 or later
- pip packages:

```bash
pip install ultralytics opencv-python numpy
```

CUDA is optional. Training on CPU works but is significantly slower (~10× on a large dataset). A GPU with at least 4 GB VRAM (e.g. RTX 3060 or better) is recommended for training runs over 50 epochs.

---

## 1. Prepare Dataset

### Collect images

Capture frames from your birdhouse camera during actual bird activity. Aim for at least 200–500 labelled images per class for a fine-tuned model. More variety (different lighting, angles, species) improves robustness.

### Label images

Use a YOLO-compatible labelling tool. [LabelImg](https://github.com/HumanSignal/labelImg) is a simple, free option:

```bash
pip install labelImg
labelImg
```

Label each image in **YOLO format** (one `.txt` file per image, same name). Classes should match the order in your `data.yaml`.

### Prepare the dataset structure

```bash
python prepare_dataset.py
```

This script organises your labelled images into the expected directory layout:

```
dataset/
  images/
    train/
    val/
  labels/
    train/
    val/
  data.yaml
```

Edit `prepare_dataset.py` to point to your source image and label directories before running.

---

## 2. Train

```bash
python train.py --epochs 50 --device auto
```

Key arguments:

| Argument | Default | Description |
|---|---|---|
| `--epochs` | 50 | Number of training epochs |
| `--batch` | 8 | Batch size (reduce to 4 if GPU OOM) |
| `--imgsz` | 416 | Training image size |
| `--device` | auto | `auto` selects GPU if available, else CPU |
| `--model` | yolov8n.pt | Base checkpoint to fine-tune from |
| `--name` | yolov8n_birdpi | Run name for output directory |
| `--patience` | 15 | Early stopping patience (epochs) |

The best weights are saved to `models/yolov8n_birdpi_best.pt` when training completes.

---

## 3. Evaluate

```bash
python evaluate.py
```

Prints precision, recall, mAP50, and mAP50-95 on the validation set. Review the confusion matrix and PR curves in the run output directory (`models/yolov8n_birdpi/`).

Reasonable targets for a birdhouse dataset:
- mAP50 > 0.6 is good
- Recall is more important than precision for alerts (missing a bird is worse than a false positive)

---

## 4. Export to ONNX

```bash
python export_onnx.py --imgsz 224
```

This exports the trained model to ONNX at 224×224 resolution, the size expected by the Pi inference pipeline. The export uses opset 12 for maximum compatibility with OpenCV DNN.

Output: `models/yolov8n_birdpi_224.onnx`

The `--imgsz 224` value is the recommended size for Pi 2/3. You can use `--imgsz 320` on Pi 4/5 for slightly better detection quality at the cost of ~50% slower inference.

---

## 5. Deploy to Pi

Copy the ONNX model to your Pi:

```bash
bash ../tools/deploy.sh birdpi.local <username>
```

Or manually:

```bash
scp models/yolov8n_birdpi_224.onnx <username>@birdpi.local:~/birdpi/models/
```

Then update `config.env` on the Pi if the model filename changed:

```bash
TELEGRAM_AI_MODEL=~/birdpi/models/yolov8n_birdpi_224.onnx
TELEGRAM_AI_INPUT_SIZE=224
```

Restart the motion service to pick up the new model:

```bash
sudo systemctl restart motion.service
```

---

## Notes

- Trained `.pt` files and `.onnx` exports are listed in `.gitignore` — do not commit large binary model files to the repository.
- The Pi inference code (`pi/app/telegram_sender.py`) uses `cv2.dnn.readNetFromONNX` and expects a fixed-size input matching `TELEGRAM_AI_INPUT_SIZE`. Always export with the same `--imgsz` you set in `config.env`.
- The model must output predictions in YOLOv8 format (batch × 4+num_classes × num_boxes). The bundled detector handles the transpose and NMS internally.
