#!/bin/bash
set -euo pipefail

LOG_FILE="/var/log/birdpi-bootstrap.log"
exec > >(tee -a "${LOG_FILE}") 2>&1

MARKER="/etc/birdpi-bootstrap.done"
if [[ -f "${MARKER}" ]]; then
  echo "[birdpi] deja configure"
  exit 0
fi

BOOT_DIR="/boot"
if [[ -d "/boot/firmware" ]]; then
  BOOT_DIR="/boot/firmware"
fi
SRC_DIR="${BOOT_DIR}/birdpi"

if [[ -f "${SRC_DIR}/bootstrap.env" ]]; then
  # shellcheck disable=SC1090,SC1091
  set -a
  source "${SRC_DIR}/bootstrap.env"
  set +a
fi

PI_USER="${PI_USER:-pi}"
PI_PASSWORD="${PI_PASSWORD:-PiN1ch0ir!2026}"
HOSTNAME_VALUE="${HOSTNAME_VALUE:-birdpi}"

echo "[birdpi] creation/utilisateur ${PI_USER}"
if ! id "${PI_USER}" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "${PI_USER}"
fi
echo "${PI_USER}:${PI_PASSWORD}" | chpasswd
usermod -aG sudo,video,dialout,gpio,i2c,plugdev "${PI_USER}"

echo "[birdpi] hostname ${HOSTNAME_VALUE}"
echo "${HOSTNAME_VALUE}" > /etc/hostname
if grep -q '^127\.0\.1\.1' /etc/hosts; then
  sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t${HOSTNAME_VALUE}/" /etc/hosts
else
  echo -e "127.0.1.1\t${HOSTNAME_VALUE}" >> /etc/hosts
fi

echo "[birdpi] apt install"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  ffmpeg \
  git \
  python3-pip \
  python3-opencv \
  python3-numpy \
  libcamera-apps \
  i2c-tools \
  motion \
  python3-serial \
  python3-gpiozero \
  logrotate \
  curl \
  ca-certificates

if command -v raspi-config >/dev/null 2>&1; then
  echo "[birdpi] raspi-config interfaces"
  raspi-config nonint do_ssh 0 || true
  raspi-config nonint do_camera 0 || true
  raspi-config nonint do_serial_hw 0 || true
  raspi-config nonint do_serial_cons 1 || true
fi

CONFIG_TXT="${BOOT_DIR}/config.txt"
if [[ -f "${CONFIG_TXT}" ]]; then
  add_line() {
    local line="$1"
    grep -qxF "${line}" "${CONFIG_TXT}" || echo "${line}" >> "${CONFIG_TXT}"
  }
  add_line "camera_auto_detect=1"
  add_line "enable_uart=1"
  add_line "dtoverlay=disable-bt"
  add_line "hdmi_blanking=2"
fi

CMDLINE_TXT="${BOOT_DIR}/cmdline.txt"
if [[ -f "${CMDLINE_TXT}" ]]; then
  sed -i 's/console=serial0,[0-9]\+ //g' "${CMDLINE_TXT}"
fi

echo "[birdpi] deployment /home/${PI_USER}/birdpi"
install -d -m 0750 -o "${PI_USER}" -g "${PI_USER}" "/home/${PI_USER}/birdpi"
install -d -m 0750 -o "${PI_USER}" -g "${PI_USER}" "/home/${PI_USER}/birdpi/logs"
install -d -m 0750 -o "${PI_USER}" -g "${PI_USER}" "/home/${PI_USER}/birdpi/recordings"
install -d -m 0750 -o "${PI_USER}" -g "${PI_USER}" "/home/${PI_USER}/birdpi/models"

install -m 0750 -o "${PI_USER}" -g "${PI_USER}" "${SRC_DIR}/app/camera_stream.sh" "/home/${PI_USER}/birdpi/camera_stream.sh"
install -m 0750 -o "${PI_USER}" -g "${PI_USER}" "${SRC_DIR}/app/telegram_sender.py" "/home/${PI_USER}/birdpi/telegram_sender.py"
install -m 0750 -o "${PI_USER}" -g "${PI_USER}" "${SRC_DIR}/app/telegram_loop.sh" "/home/${PI_USER}/birdpi/telegram_loop.sh"
install -m 0750 -o "${PI_USER}" -g "${PI_USER}" "${SRC_DIR}/scripts/install_model.sh" "/home/${PI_USER}/birdpi/install_model.sh"
install -m 0750 -o "${PI_USER}" -g "${PI_USER}" "${SRC_DIR}/app/battery_monitor.py" "/home/${PI_USER}/birdpi/battery_monitor.py"
install -m 0750 -o "${PI_USER}" -g "${PI_USER}" "${SRC_DIR}/app/on_event_start.sh" "/home/${PI_USER}/birdpi/on_event_start.sh"
install -m 0750 -o "${PI_USER}" -g "${PI_USER}" "${SRC_DIR}/app/on_event_end.sh" "/home/${PI_USER}/birdpi/on_event_end.sh"
install -m 0640 -o "${PI_USER}" -g "${PI_USER}" "${SRC_DIR}/app/config.env" "/home/${PI_USER}/birdpi/config.env"
chmod 0600 "/home/${PI_USER}/birdpi/config.env"

for file in \
  "/home/${PI_USER}/birdpi/camera_stream.sh" \
  "/home/${PI_USER}/birdpi/telegram_sender.py" \
  "/home/${PI_USER}/birdpi/telegram_loop.sh" \
  "/home/${PI_USER}/birdpi/install_model.sh" \
  "/home/${PI_USER}/birdpi/battery_monitor.py" \
  "/home/${PI_USER}/birdpi/on_event_start.sh" \
  "/home/${PI_USER}/birdpi/on_event_end.sh"; do
  sed -i "s#/home/pi/#/home/${PI_USER}/#g" "${file}"
done

# Copy bundled ONNX model from boot partition
echo "[birdpi] installing YOLOv8-nano ONNX model"
if [[ -d "${SRC_DIR}/models" ]]; then
  cp -v "${SRC_DIR}/models/"*.onnx "/home/${PI_USER}/birdpi/models/" 2>/dev/null || true
  chown -R "${PI_USER}:${PI_USER}" "/home/${PI_USER}/birdpi/models/"
fi
sudo -u "${PI_USER}" "/home/${PI_USER}/birdpi/install_model.sh" || true

echo "[birdpi] motion.conf -> /etc/motion/motion.conf"
install -d -m 0755 /etc/motion
install -m 0644 "${SRC_DIR}/motion/motion.conf" /etc/motion/motion.conf
sed -i "s#/home/pi/#/home/${PI_USER}/#g" /etc/motion/motion.conf

echo "[birdpi] services install"
install -m 0644 "${SRC_DIR}/services/motion.service" /etc/systemd/system/motion.service
install -m 0644 "${SRC_DIR}/services/camera_stream.service" /etc/systemd/system/camera_stream.service
install -m 0644 "${SRC_DIR}/services/battery_monitor.service" /etc/systemd/system/battery_monitor.service
install -m 0644 "${SRC_DIR}/services/disable-hdmi.service" /etc/systemd/system/disable-hdmi.service
install -m 0644 "${SRC_DIR}/services/logrotate-birdpi" /etc/logrotate.d/birdpi

sed -i "s/__PI_USER__/${PI_USER}/g" /etc/systemd/system/motion.service
sed -i "s/__PI_USER__/${PI_USER}/g" /etc/systemd/system/camera_stream.service
sed -i "s/__PI_USER__/${PI_USER}/g" /etc/systemd/system/battery_monitor.service
sed -i "s#/home/pi/#/home/${PI_USER}/#g" /etc/logrotate.d/birdpi
sed -i "s#su pi pi#su ${PI_USER} ${PI_USER}#g" /etc/logrotate.d/birdpi

echo "[birdpi] sudoers shutdown"
cat > /etc/sudoers.d/birdpi-shutdown <<EOF
${PI_USER} ALL=(root) NOPASSWD:/sbin/shutdown
EOF
chmod 0440 /etc/sudoers.d/birdpi-shutdown

echo "[birdpi] hardening ssh/root"
mkdir -p /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/99-birdpi-hardening.conf <<'EOF'
PermitRootLogin no
ChallengeResponseAuthentication no
EOF
passwd -l root || true
systemctl restart ssh || true

echo "[birdpi] Pi 2 performance tuning"

# --- zram swap (compressed RAM swap - zero SD writes, critical for SD longevity) ---
# Pi 2: 1GB RAM is tight. zram compresses swap in RAM (lz4, ~2:1 ratio)
# giving ~1.3-1.5GB effective memory without ANY SD card writes.
# NEVER use file-based swap on microSD (kills the card in months).
echo "[birdpi] configuring zram swap (256MB compressed -> ~512MB effective)"

# Disable any existing file swap to protect SD card
swapoff -a 2>/dev/null || true
if [[ -f /swapfile ]]; then
  rm -f /swapfile
  sed -i '/swapfile/d' /etc/fstab
  echo "[birdpi] removed old file swap (SD protection)"
fi

# Disable Raspbian's default dphys-swapfile (file-based swap)
systemctl disable --now dphys-swapfile.service 2>/dev/null || true
apt-get remove -y dphys-swapfile 2>/dev/null || true

# Create zram swap service
cat > /etc/systemd/system/zram-swap.service <<'ZRAMEOF'
[Unit]
Description=zram compressed swap (Pi 2 memory extension)
After=local-fs.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c '\
  modprobe zram num_devices=1 && \
  echo lz4 > /sys/block/zram0/comp_algorithm && \
  echo 256M > /sys/block/zram0/disksize && \
  mkswap /dev/zram0 && \
  swapon -p 100 /dev/zram0'
ExecStop=/bin/sh -c 'swapoff /dev/zram0 2>/dev/null; echo 1 > /sys/block/zram0/reset'

[Install]
WantedBy=multi-user.target
ZRAMEOF

# zram-swap.service is enabled in the bulk enable below

# Low swappiness: only swap under real pressure
echo "vm.swappiness=10" > /etc/sysctl.d/99-birdpi-swap.conf

# --- CPU governor: performance mode for consistent inference times ---
echo "[birdpi] CPU governor -> performance"
cat > /etc/systemd/system/cpu-performance.service <<'CPUEOF'
[Unit]
Description=Set CPU governor to performance
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'test -d /sys/devices/system/cpu/cpu0/cpufreq && echo performance | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor || echo "cpufreq not available"'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
CPUEOF

# --- Memory optimizations for Pi 2 ---
echo "[birdpi] memory optimizations"
cat > /etc/sysctl.d/99-birdpi-memory.conf <<'EOF'
# Reduce filesystem cache pressure (more RAM for apps)
vm.vfs_cache_pressure=200
# Reduce dirty page ratio (write to SD sooner, free RAM faster)
vm.dirty_ratio=10
vm.dirty_background_ratio=5
# Reduce minimum free memory (Pi 2 needs every MB)
vm.min_free_kbytes=8192
EOF

# --- GPU memory split: minimum for headless Pi 2 ---
# 16MB = minimum. OK for USB cameras. If using CSI camera (Pi Camera Module),
# change to gpu_mem=64 or the camera will fail to initialize.
CONFIG_TXT="${BOOT_DIR}/config.txt"
if [[ -f "${CONFIG_TXT}" ]]; then
  if ! grep -q "gpu_mem=" "${CONFIG_TXT}"; then
    echo "gpu_mem=16" >> "${CONFIG_TXT}"
    echo "[birdpi] GPU memory reduced to 16MB (headless, USB camera only)"
  fi
fi

# --- Disable unnecessary services ---
echo "[birdpi] disabling unnecessary services"
systemctl disable --now bluetooth.service hciuart.service || true
systemctl disable --now avahi-daemon.service || true
systemctl disable --now triggerhappy.service || true
systemctl disable --now ModemManager.service || true
systemctl set-default multi-user.target

# --- Journald: volatile to reduce SD wear ---
mkdir -p /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/99-birdpi.conf <<'EOF'
[Journal]
Storage=volatile
RuntimeMaxUse=20M
SystemMaxUse=30M
MaxRetentionSec=3day
RateLimitIntervalSec=30s
RateLimitBurst=200
EOF
systemctl restart systemd-journald || true

# --- tmpfs for recordings (avoid SD wear, data is streamed to YouTube anyway) ---
echo "[birdpi] tmpfs for recordings"
mkdir -p "/home/${PI_USER}/birdpi/recordings"
echo "tmpfs /home/${PI_USER}/birdpi/recordings tmpfs nodev,nosuid,size=50M,uid=$(id -u "${PI_USER}"),gid=$(id -g "${PI_USER}") 0 0" >> /etc/fstab

# --- Enable services ---
systemctl daemon-reload
systemctl enable disable-hdmi.service motion.service camera_stream.service battery_monitor.service cpu-performance.service zram-swap.service
systemctl restart motion.service || true
systemctl restart camera_stream.service || true
systemctl disable birdpi-bootstrap.service

# --- Apply sysctl now ---
sysctl --system || true

touch "${MARKER}"
sync

echo "[birdpi] termine, reboot"
reboot
