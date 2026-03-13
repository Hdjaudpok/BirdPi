#!/bin/bash
set -euo pipefail
# BirdPi - Install custom YOLOv8-nano ONNX model
# Replaces v1 YOLOv4-tiny (37MB, 80 COCO classes) with
# custom-trained YOLOv8-nano (11.6MB, 2 classes: bird, other_animal)

BASE_DIR="${BIRDPI_DIR:-$HOME/birdpi}"
CONFIG_FILE="${BASE_DIR}/config.env"
MODELS_DIR="${BASE_DIR}/models"
BOOT_DIR="/boot"

if [[ -d "/boot/firmware" ]]; then
  BOOT_DIR="/boot/firmware"
fi

if [[ -f "${CONFIG_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${CONFIG_FILE}"
fi

MODEL_PATH="${TELEGRAM_AI_MODEL:-${MODELS_DIR}/yolov8n_birdpi_224.onnx}"
MODEL_NAME="$(basename "${MODEL_PATH}")"

mkdir -p "${MODELS_DIR}"

# Strategy 1: Copy from boot partition (bundled with SD card)
BOOT_MODEL="${BOOT_DIR}/birdpi/models/${MODEL_NAME}"
if [[ -s "${BOOT_MODEL}" ]] && [[ ! -s "${MODEL_PATH}" ]]; then
  echo "[model] copying bundled model from boot partition"
  cp "${BOOT_MODEL}" "${MODEL_PATH}"
  echo "[model] installed: ${MODEL_PATH} ($(du -h "${MODEL_PATH}" | cut -f1))"
fi

# Strategy 2: Model already in place
if [[ -s "${MODEL_PATH}" ]]; then
  echo "[model] already present: ${MODEL_PATH} ($(du -h "${MODEL_PATH}" | cut -f1))"
  exit 0
fi

echo "[model] ERROR: model not found at ${MODEL_PATH}" >&2
echo "[model] Please copy ${MODEL_NAME} to ${MODELS_DIR}/ manually" >&2
echo "[model] Or re-flash the SD card with the updated bundle" >&2
exit 1
