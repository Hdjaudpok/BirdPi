#!/bin/bash
set -euo pipefail
# BirdPi - Motion event end hook
# Pi 2: force-kill avec fallback si YOLO inference bloque le processus

BASE_DIR="${BIRDPI_DIR:-$HOME/birdpi}"
LOG_DIR="${BASE_DIR}/logs"
EVENT_LOG="${LOG_DIR}/motion_events.log"
EVENT_ACTIVE_FILE="${BASE_DIR}/.event_active"
REALTIME_PID_FILE="${BASE_DIR}/.telegram_realtime.pid"

mkdir -p "${LOG_DIR}"
echo "$(date -Is) event_end" >> "${EVENT_LOG}"

rm -f "${EVENT_ACTIVE_FILE}"

if [[ -f "${REALTIME_PID_FILE}" ]]; then
  RT_PID="$(cat "${REALTIME_PID_FILE}" 2>/dev/null || echo "")"
  if [[ -n "${RT_PID}" ]] && kill -0 "${RT_PID}" 2>/dev/null; then
    kill "${RT_PID}" 2>/dev/null || true
    # Wait up to 12s for YOLO inference to finish gracefully
    for i in $(seq 1 12); do
      kill -0 "${RT_PID}" 2>/dev/null || break
      sleep 1
    done
    # Force kill if still alive (stuck in OpenCV C code)
    if kill -0 "${RT_PID}" 2>/dev/null; then
      kill -9 "${RT_PID}" 2>/dev/null || true
      echo "$(date -Is) realtime_loop_force_killed pid=${RT_PID}" >> "${EVENT_LOG}"
    else
      echo "$(date -Is) realtime_loop_stopped pid=${RT_PID}" >> "${EVENT_LOG}"
    fi
  fi
  rm -f "${REALTIME_PID_FILE}"
fi
