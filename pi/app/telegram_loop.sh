#!/bin/bash
set -euo pipefail

BASE_DIR="${BIRDPI_DIR:-$HOME/birdpi}"
CONFIG_FILE="${BASE_DIR}/config.env"
EVENT_LOG="${BASE_DIR}/logs/motion_events.log"

if [[ -f "${CONFIG_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${CONFIG_FILE}"
fi

: "${TELEGRAM_EVENT_MESSAGE:=Mouvement en cours dans le birdpi}"

echo "$(date -Is) realtime_loop_online mode=python_persistent" >> "${EVENT_LOG}"
exec /usr/bin/python3 "${BASE_DIR}/telegram_sender.py" --loop "${TELEGRAM_EVENT_MESSAGE}" >> "${EVENT_LOG}" 2>&1
