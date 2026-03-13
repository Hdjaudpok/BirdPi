#!/bin/bash
set -euo pipefail

# BirdPi - Interactive Setup
# Run this on your Raspberry Pi after cloning the repo.
# It generates config.env and optionally downloads the AI model.

BIRDPI_DIR="${BIRDPI_DIR:-$HOME/birdpi}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="${BIRDPI_DIR}/config.env"
CONFIG_EXAMPLE="${REPO_DIR}/config.env.example"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

info()  { echo -e "${GREEN}[BirdPi]${NC} $*"; }
warn()  { echo -e "${YELLOW}[BirdPi]${NC} $*"; }
error() { echo -e "${RED}[BirdPi]${NC} $*" >&2; }
ask()   { echo -en "${CYAN}[BirdPi]${NC} $* "; }

echo ""
echo -e "${BOLD}Welcome to BirdPi Setup!${NC}"
echo ""
echo "This script will configure BirdPi on your Raspberry Pi."
echo "Press Enter to accept default values shown in [brackets]."
echo ""

# --- Step 1: Telegram (required) ---
echo -e "${BOLD}[1/6] Telegram Configuration (required)${NC}"
echo ""
echo "You need a Telegram bot. Create one at https://t.me/BotFather"
echo "Then get your chat ID at https://t.me/userinfobot"
echo ""

ask "Bot token:"
read -r TELEGRAM_BOT_TOKEN
if [[ -z "${TELEGRAM_BOT_TOKEN}" ]]; then
  error "Bot token is required. Aborting."
  exit 1
fi

ask "Chat ID:"
read -r TELEGRAM_CHAT_ID
if [[ -z "${TELEGRAM_CHAT_ID}" ]]; then
  error "Chat ID is required. Aborting."
  exit 1
fi

# Test Telegram
info "Testing Telegram connection..."
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" \
  -d "text=BirdPi setup test - connection OK!" 2>/dev/null || echo "000")

if [[ "${RESPONSE}" == "200" ]]; then
  info "Telegram test message sent! Check your phone."
else
  warn "Telegram test failed (HTTP ${RESPONSE}). Check your token and chat ID."
  ask "Continue anyway? [y/N]:"
  read -r CONTINUE
  if [[ "${CONTINUE}" != "y" && "${CONTINUE}" != "Y" ]]; then
    exit 1
  fi
fi
echo ""

# --- Step 2: YouTube Live (optional) ---
echo -e "${BOLD}[2/6] YouTube Live Streaming (optional)${NC}"
echo ""
ask "Enable YouTube streaming? [y/N]:"
read -r ENABLE_YT

STREAM_KEY="your_youtube_stream_key_here"
if [[ "${ENABLE_YT}" == "y" || "${ENABLE_YT}" == "Y" ]]; then
  ask "YouTube stream key:"
  read -r STREAM_KEY
  if [[ -z "${STREAM_KEY}" ]]; then
    warn "No stream key provided, YouTube streaming disabled."
    STREAM_KEY="your_youtube_stream_key_here"
  fi
fi
echo ""

# --- Step 3: Camera ---
echo -e "${BOLD}[3/6] Camera Settings${NC}"
echo ""
if [[ -e /dev/video0 ]]; then
  info "Camera detected at /dev/video0"
else
  warn "No camera detected at /dev/video0. You can still configure and connect later."
fi

ask "Resolution [640x480]:"
read -r CAM_RES
CAM_RES="${CAM_RES:-640x480}"
CAM_WIDTH="${CAM_RES%x*}"
CAM_HEIGHT="${CAM_RES#*x}"

ask "FPS [10]:"
read -r CAM_FPS
CAM_FPS="${CAM_FPS:-10}"

ask "Bitrate [400000]:"
read -r CAM_BITRATE
CAM_BITRATE="${CAM_BITRATE:-400000}"
echo ""

# --- Step 4: AI Model ---
echo -e "${BOLD}[4/6] AI Model${NC}"
echo ""
MODEL_DIR="${BIRDPI_DIR}/models"
MODEL_PATH="${MODEL_DIR}/yolov8n_birdpi_224.onnx"

if [[ -f "${MODEL_PATH}" ]]; then
  info "Model already present: ${MODEL_PATH}"
else
  info "Model not found. Attempting download from GitHub..."
  mkdir -p "${MODEL_DIR}"
  RELEASE_URL="https://github.com/Hdjaudpok/BirdPi/releases/latest/download/yolov8n_birdpi_224.onnx"
  if curl -fSL -o "${MODEL_PATH}" "${RELEASE_URL}" 2>/dev/null; then
    info "Model downloaded successfully ($(du -h "${MODEL_PATH}" | cut -f1))"
  else
    warn "Download failed. You can add the model manually later."
    warn "Place it at: ${MODEL_PATH}"
    rm -f "${MODEL_PATH}"
  fi
fi
echo ""

# --- Step 5: AI Settings (optional) ---
echo -e "${BOLD}[5/6] AI Settings (optional)${NC}"
echo ""
ask "AI confidence threshold [0.35]:"
read -r AI_CONF
AI_CONF="${AI_CONF:-0.35}"

ask "Enable temporal tracker (multi-frame confirmation)? [Y/n]:"
read -r TRACKER
TRACKER_ENABLED=1
if [[ "${TRACKER}" == "n" || "${TRACKER}" == "N" ]]; then
  TRACKER_ENABLED=0
fi

ask "Enable CLAHE night vision enhancement? [Y/n]:"
read -r CLAHE
CLAHE_ENABLED=1
if [[ "${CLAHE}" == "n" || "${CLAHE}" == "N" ]]; then
  CLAHE_ENABLED=0
fi
echo ""

# --- Step 6: Generate config.env ---
echo -e "${BOLD}[6/6] Generating configuration${NC}"
echo ""

mkdir -p "${BIRDPI_DIR}"

# Start from example and substitute values
cp "${CONFIG_EXAMPLE}" "${CONFIG_FILE}"
sed -i "s|TELEGRAM_BOT_TOKEN=.*|TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}|" "${CONFIG_FILE}"
sed -i "s|TELEGRAM_CHAT_ID=.*|TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}|" "${CONFIG_FILE}"
sed -i "s|STREAM_KEY=.*|STREAM_KEY=${STREAM_KEY}|" "${CONFIG_FILE}"
sed -i "s|CAM_FPS=.*|CAM_FPS=${CAM_FPS}|" "${CONFIG_FILE}"
sed -i "s|CAM_BITRATE=.*|CAM_BITRATE=${CAM_BITRATE}|" "${CONFIG_FILE}"
sed -i "s|TELEGRAM_AI_CONFIDENCE=.*|TELEGRAM_AI_CONFIDENCE=${AI_CONF}|" "${CONFIG_FILE}"
sed -i "s|TELEGRAM_TRACKER_ENABLED=.*|TELEGRAM_TRACKER_ENABLED=${TRACKER_ENABLED}|" "${CONFIG_FILE}"
sed -i "s|TELEGRAM_CLAHE_ENABLED=.*|TELEGRAM_CLAHE_ENABLED=${CLAHE_ENABLED}|" "${CONFIG_FILE}"
chmod 600 "${CONFIG_FILE}"

info "config.env written to ${CONFIG_FILE}"
echo ""

echo -e "${BOLD}Setup complete!${NC}"
echo ""
info "Next steps:"
info "  1. Run: sudo bash pi/scripts/bootstrap.sh"
info "     (installs packages, configures services, reboots)"
info "  2. After reboot, BirdPi runs automatically."
info "  3. Check Telegram for alerts when motion is detected!"
echo ""
info "Docs: https://github.com/Hdjaudpok/BirdPi"
echo ""
