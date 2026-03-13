#!/bin/bash
set -euo pipefail
# BirdPi - Stream YouTube permanent
# Optimise pour Raspberry Pi 2 Model B (ARMv7, 1GB RAM)
#
# Budget CPU Pi 2: Motion ~15-20%, ffmpeg ~25-35%, YOLO ~30% (burst)
# Total idle: ~45%. Total motion event: ~80%. Marge: 20%.

BASE_DIR="${BIRDPI_DIR:-$HOME/birdpi}"
CONFIG_FILE="${BASE_DIR}/config.env"
LOG_DIR="${BASE_DIR}/logs"

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "config.env introuvable: ${CONFIG_FILE}" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${CONFIG_FILE}"

mkdir -p "${LOG_DIR}"

STREAM_URL="${RTMP_URL/\$STREAM_KEY/${STREAM_KEY}}"
MOTION_PORT="${MOTION_STREAM_PORT:-8081}"

# Pi 2: single thread encoding (640x480@10fps baseline ultrafast ne necessite pas
# plus d'un thread, et evite le cache-line bouncing sur BCM2836 ARM)
export FFMPEG_THREADS=1

echo "demarrage stream Pi2 vers ${STREAM_URL} (source: :${MOTION_PORT}, fps=${CAM_FPS}, bitrate=${CAM_BITRATE})"

exec nice -n 5 ffmpeg \
  -hide_banner \
  -loglevel warning \
  -threads "${FFMPEG_THREADS}" \
  -use_wallclock_as_timestamps 1 \
  -f mjpeg -i "http://localhost:${MOTION_PORT}" \
  -f lavfi -i anullsrc=r=44100:cl=mono \
  -c:v libx264 -preset ultrafast -tune zerolatency \
  -profile:v baseline -level 3.0 \
  -b:v "${CAM_BITRATE}" \
  -maxrate "${CAM_BITRATE}" \
  -bufsize "$((CAM_BITRATE * 2))" \
  -pix_fmt yuv420p \
  -vf "fps=${CAM_FPS}" \
  -g "$((CAM_FPS * 2))" \
  -c:a aac \
  -b:a 64k \
  -ac 1 \
  -f flv "${STREAM_URL}"
