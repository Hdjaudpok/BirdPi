#!/bin/bash
set -euo pipefail
# ============================================================
# BirdPi - Deploy to running Raspberry Pi via SSH
# ============================================================
# Usage:
#   bash deploy.sh [PI_HOST] [PI_USER]
#
# Examples:
#   bash deploy.sh                    # defaults: birdpi.local / pi
#   bash deploy.sh 192.168.1.42       # custom IP
#   bash deploy.sh 192.168.1.42 jules # custom IP + user
#
# What this script does:
#   1. Stops motion & telegram services
#   2. Backs up current files on Pi
#   3. Uploads new telegram_sender.py v2
#   4. Uploads new config.env
#   5. Uploads YOLOv8-nano ONNX model (11.6MB)
#   6. Removes old YOLOv4-tiny files
#   7. Restarts services
# ============================================================

PI_HOST="${1:-birdpi.local}"
PI_USER="${2:-pi}"
PI_DIR="/home/${PI_USER}/birdpi"

# Resolve script directory for file paths
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PI_SRC_DIR="$(dirname "${SCRIPT_DIR}")/pi"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()  { echo -e "${YELLOW}[deploy]${NC} $*"; }
error() { echo -e "${RED}[deploy]${NC} $*" >&2; }

# Verify files exist locally
check_file() {
  if [[ ! -f "$1" ]]; then
    error "Fichier manquant: $1"
    exit 1
  fi
}

info "=== BirdPi - Deploiement ==="
info "Cible: ${PI_USER}@${PI_HOST}"
info ""

# Check local files
check_file "${PI_SRC_DIR}/app/telegram_sender.py"
check_file "${PI_SRC_DIR}/app/config.env"
check_file "${PI_SRC_DIR}/scripts/install_model.sh"

info "Fichiers locaux OK"

# Test SSH connectivity
info "Test connexion SSH..."
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "${PI_USER}@${PI_HOST}" "echo ok" >/dev/null 2>&1; then
  error "Impossible de se connecter a ${PI_USER}@${PI_HOST}"
  error "Verifiez:"
  error "  - Le Pi est allume et connecte au WiFi"
  error "  - SSH est active"
  error "  - Votre cle SSH est configuree"
  error "  - L'adresse ${PI_HOST} est correcte"
  exit 1
fi
info "Connexion SSH OK"

# Step 1: Stop services
info "Arret des services..."
ssh "${PI_USER}@${PI_HOST}" "
  sudo systemctl stop motion.service 2>/dev/null || true
  # Kill any running telegram loop
  if [[ -f ${PI_DIR}/.telegram_realtime.pid ]]; then
    PID=\$(cat ${PI_DIR}/.telegram_realtime.pid 2>/dev/null || echo '')
    [[ -n \"\${PID}\" ]] && kill \${PID} 2>/dev/null || true
    rm -f ${PI_DIR}/.telegram_realtime.pid
  fi
  rm -f ${PI_DIR}/.event_active
  echo 'Services arretes'
"

# Step 2: Backup current files
info "Sauvegarde des fichiers actuels..."
BACKUP_TS=$(date +%Y%m%d_%H%M%S)
ssh "${PI_USER}@${PI_HOST}" "
  mkdir -p ${PI_DIR}/backups/${BACKUP_TS}
  cp -f ${PI_DIR}/telegram_sender.py ${PI_DIR}/backups/${BACKUP_TS}/ 2>/dev/null || true
  cp -f ${PI_DIR}/config.env ${PI_DIR}/backups/${BACKUP_TS}/ 2>/dev/null || true
  cp -f ${PI_DIR}/install_model.sh ${PI_DIR}/backups/${BACKUP_TS}/ 2>/dev/null || true
  echo 'Backup: ${PI_DIR}/backups/${BACKUP_TS}/'
"

# Step 3: Upload new files
info "Upload telegram_sender.py v2..."
scp -q "${PI_SRC_DIR}/app/telegram_sender.py" "${PI_USER}@${PI_HOST}:${PI_DIR}/telegram_sender.py"

info "Upload config.env..."
scp -q "${PI_SRC_DIR}/app/config.env" "${PI_USER}@${PI_HOST}:${PI_DIR}/config.env"

info "Upload install_model.sh..."
scp -q "${PI_SRC_DIR}/scripts/install_model.sh" "${PI_USER}@${PI_HOST}:${PI_DIR}/install_model.sh"

# Step 4: Upload ONNX model (if present)
ONNX_MODEL="$(dirname "${SCRIPT_DIR}")/models/yolov8n_birdpi_224.onnx"
if [[ -f "${ONNX_MODEL}" ]]; then
  info "Upload modele YOLOv8-nano ONNX (11.6MB)..."
  ssh "${PI_USER}@${PI_HOST}" "mkdir -p ${PI_DIR}/models"
  scp -q "${ONNX_MODEL}" "${PI_USER}@${PI_HOST}:${PI_DIR}/models/yolov8n_birdpi_224.onnx"
else
  warn "Modele ONNX non trouve localement: ${ONNX_MODEL}"
  warn "  Executez training/export_onnx.py d'abord"
fi

# Step 5: Set permissions
info "Permissions..."
ssh "${PI_USER}@${PI_HOST}" "
  chmod 0750 ${PI_DIR}/telegram_sender.py
  chmod 0600 ${PI_DIR}/config.env
  chmod 0750 ${PI_DIR}/install_model.sh
"

# Step 6: Clean old YOLOv4-tiny files (if present)
info "Nettoyage ancien modele YOLOv4-tiny..."
ssh "${PI_USER}@${PI_HOST}" "
  rm -f ${PI_DIR}/models/yolov4-tiny.cfg 2>/dev/null || true
  rm -f ${PI_DIR}/models/yolov4-tiny.weights 2>/dev/null || true
  rm -f ${PI_DIR}/models/coco.names 2>/dev/null || true
  echo 'Ancien modele supprime'
"

# Step 7: Restart services
info "Redemarrage des services..."
ssh "${PI_USER}@${PI_HOST}" "
  sudo systemctl start motion.service
  echo 'Motion redemarre'
"

# Step 8: Verify
info "Verification..."
ssh "${PI_USER}@${PI_HOST}" "
  echo ''
  echo '=== Etat du deploiement ==='
  echo ''
  echo 'Modele ONNX:'
  ls -lh ${PI_DIR}/models/yolov8n_birdpi_224.onnx 2>/dev/null || echo '  MANQUANT!'
  echo ''
  echo 'telegram_sender.py:'
  head -3 ${PI_DIR}/telegram_sender.py | grep -o 'v[0-9]' || echo '  version inconnue'
  echo ''
  echo 'Services:'
  systemctl is-active motion.service 2>/dev/null || echo '  motion: inactif'
  echo ''
  echo 'RAM disponible:'
  free -h | grep Mem
  echo ''
  echo 'Espace disque:'
  df -h / | tail -1
"

info ""
info "=== Deploiement v2 termine! ==="
info ""
info "Nouveautes deployees:"
info "  - YOLOv8-nano ONNX custom (bird detection, 11.6MB)"
info "  - CLAHE preprocessing (contraste IR/nuit)"
info "  - Tracker temporel (confirmation 3 frames)"
info "  - Classificateur comportement (entree/sortie/repos/alimentation)"
info ""
info "Pour tester manuellement:"
info "  ssh ${PI_USER}@${PI_HOST}"
info "  python3 ${PI_DIR}/telegram_sender.py 'Test detection v2'"
info ""
