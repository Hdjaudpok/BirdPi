#!/bin/bash
set -euo pipefail
# BirdPi - Motion event start hook
# Optimise Pi 2: UN SEUL processus Python/YOLO a la fois (anti-OOM)

BASE_DIR="${BIRDPI_DIR:-$HOME/birdpi}"
CONFIG_FILE="${BASE_DIR}/config.env"
LOG_DIR="${BASE_DIR}/logs"
EVENT_LOG="${LOG_DIR}/motion_events.log"
LAST_ALERT_FILE="${BASE_DIR}/.last_alert_ts"
EVENT_ACTIVE_FILE="${BASE_DIR}/.event_active"
REALTIME_PID_FILE="${BASE_DIR}/.telegram_realtime.pid"
REALTIME_SCRIPT="${BASE_DIR}/telegram_loop.sh"

mkdir -p "${LOG_DIR}" "${BASE_DIR}/recordings"

if [[ -f "${CONFIG_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${CONFIG_FILE}"
fi

: "${MOTION_DEBOUNCE_SEC:=30}"
: "${TELEGRAM_START_ALERT:=1}"
: "${TELEGRAM_REALTIME_MODE:=1}"
: "${TELEGRAM_START_MESSAGE:=Mouvement detecte dans le birdpi}"

echo "$(date -Is) event_start" >> "${EVENT_LOG}"
touch "${EVENT_ACTIVE_FILE}"

# Debounce check
NOW_TS="$(date +%s)"
LAST_TS=0
if [[ -f "${LAST_ALERT_FILE}" ]]; then
  LAST_TS="$(cat "${LAST_ALERT_FILE}" 2>/dev/null || echo 0)"
fi

if (( NOW_TS - LAST_TS < MOTION_DEBOUNCE_SEC )); then
  echo "$(date -Is) telegram_skip_debounce=${MOTION_DEBOUNCE_SEC}" >> "${EVENT_LOG}"
  exit 0
fi

echo "${NOW_TS}" > "${LAST_ALERT_FILE}"

# Pi 2 CRITICAL: ne JAMAIS lancer 2 processus Python/YOLO en parallele.
# 2x YOLO = ~450MB RAM = OOM sur 1GB.
# Solution: tout passe par le realtime loop (premiere iteration = alerte initiale)

if [[ "${TELEGRAM_REALTIME_MODE}" == "1" ]]; then
  # Kill any stale realtime loop from previous event
  if [[ -f "${REALTIME_PID_FILE}" ]]; then
    RT_PID="$(cat "${REALTIME_PID_FILE}" 2>/dev/null || echo "")"
    if [[ -n "${RT_PID}" ]] && kill -0 "${RT_PID}" 2>/dev/null; then
      echo "$(date -Is) killing_stale_realtime pid=${RT_PID}" >> "${EVENT_LOG}"
      kill "${RT_PID}" 2>/dev/null || true
      # Wait up to 12s for YOLO inference to finish before force kill
      for _ in $(seq 1 12); do
        kill -0 "${RT_PID}" 2>/dev/null || break
        sleep 1
      done
      kill -9 "${RT_PID}" 2>/dev/null || true
    fi
    rm -f "${REALTIME_PID_FILE}"
  fi

  if [[ -x "${REALTIME_SCRIPT}" ]]; then
    (
      /usr/bin/nice -n 10 /bin/bash "${REALTIME_SCRIPT}" >> "${EVENT_LOG}" 2>&1
    ) &
    echo $! > "${REALTIME_PID_FILE}"
    echo "$(date -Is) realtime_loop_started pid=$(cat "${REALTIME_PID_FILE}")" >> "${EVENT_LOG}"
  else
    echo "$(date -Is) realtime_loop_missing ${REALTIME_SCRIPT}" >> "${EVENT_LOG}"
  fi
elif [[ "${TELEGRAM_START_ALERT}" == "1" ]]; then
  # Fallback: single alert (non-blocking) if realtime mode disabled
  (
    /usr/bin/nice -n 10 /usr/bin/python3 "${BASE_DIR}/telegram_sender.py" "${TELEGRAM_START_MESSAGE}" >> "${EVENT_LOG}" 2>&1 || true
  ) &
  echo "$(date -Is) single_alert_sent_bg" >> "${EVENT_LOG}"
fi
