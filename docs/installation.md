# Installation

This guide walks you through setting up BirdPi on a Raspberry Pi from scratch.

---

## Prerequisites

- Raspberry Pi 2, 3, 4, or 5 (Pi Zero 2W is experimental)
- microSD card, 8 GB minimum (16 GB+ recommended)
- USB webcam or Pi Camera Module
- Internet connection (Wi-Fi or Ethernet)
- A Telegram account and a bot token ([create one at BotFather](https://t.me/BotFather))
- A computer to flash the SD card

---

## 1. Flash Raspberry Pi OS Lite

1. Download and install [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Select **Raspberry Pi OS Lite (64-bit)** as the operating system.
3. Click the settings gear icon before writing:
   - Set hostname (e.g. `birdpi`)
   - Enable SSH
   - Set username and password
   - Configure your Wi-Fi network
4. Flash the card, insert it into the Pi, and power on.

> Pi 2 users: use the 32-bit Lite image. The 64-bit image requires ARMv8 (Pi 3+).

---

## 2. Connect via SSH

Find the Pi on your network (check your router, or use `ping birdpi.local`) and connect:

```bash
ssh <your-username>@birdpi.local
```

Install your SSH key so you can connect without a password:

```bash
ssh-copy-id <your-username>@birdpi.local
```

---

## 3. Install BirdPi

### Clone the repository

```bash
git clone https://github.com/Hdjaudpok/BirdPi.git ~/BirdPi
```

### Run the interactive setup

```bash
bash ~/BirdPi/tools/setup.sh
```

The setup script will:
- Ask for your Telegram bot token and chat ID
- Test the Telegram connection (sends a test message)
- Optionally configure YouTube live streaming
- Set camera resolution, FPS, and bitrate
- Download the pre-trained YOLOv8-nano ONNX model from the latest GitHub release
- Tune AI confidence, tracker, and CLAHE settings
- Write `~/birdpi/config.env`

### Run bootstrap (as root)

```bash
sudo bash ~/BirdPi/pi/scripts/bootstrap.sh
```

Bootstrap installs all system packages (ffmpeg, motion, python3-opencv, etc.), configures systemd services, applies Pi performance tuning (zram, CPU governor, tmpfs), and reboots automatically.

> This step requires internet access and takes several minutes on first run.

---

## 4. Verify

After reboot, check that all services are running:

```bash
systemctl status motion.service
systemctl status camera_stream.service
systemctl status battery_monitor.service
```

Each should show `active (running)`.

Check Telegram: trigger some motion in front of the camera. Within seconds you should receive an annotated photo alert on your phone.

You can also view the motion live stream locally at `http://birdpi.local:8081`.

---

## Troubleshooting

### Camera not detected

```
No camera detected at /dev/video0
```

- Confirm the USB camera is plugged in: `ls /dev/video*`
- Try a different USB port
- For Pi Camera Module (CSI ribbon cable): ensure `camera_auto_detect=1` is in `/boot/firmware/config.txt` (bootstrap sets this automatically) and run `libcamera-hello` to test
- Check kernel logs: `dmesg | grep -i camera`

### Telegram alerts not arriving

- Verify your bot token: `curl "https://api.telegram.org/bot<TOKEN>/getMe"`
- Verify your chat ID: send a message to your bot, then check `https://api.telegram.org/bot<TOKEN>/getUpdates`
- Check the telegram sender log: `journalctl -u motion.service -n 50`
- Ensure the Pi has internet access: `ping -c 3 api.telegram.org`

### Motion service not starting

```bash
sudo journalctl -u motion.service -n 30
```

Common causes:
- Camera not found (`/dev/video0` absent) — motion will not start without a camera
- Port 8081 already in use — check `ss -tlnp | grep 8081`
- Bad motion.conf — reinstall with `sudo bash ~/BirdPi/pi/scripts/bootstrap.sh`

### AI model missing

If setup could not download the model automatically:

```bash
bash ~/birdpi/install_model.sh
```

Or download manually from the [latest release](https://github.com/Hdjaudpok/BirdPi/releases/latest) and place the `.onnx` file at `~/birdpi/models/yolov8n_birdpi_224.onnx`.
