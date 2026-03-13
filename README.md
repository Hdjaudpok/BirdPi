# BirdPi

**Smart birdhouse with AI-powered bird detection and real-time Telegram alerts — runs entirely on a Raspberry Pi, no cloud required.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Pi Compatible](https://img.shields.io/badge/Raspberry%20Pi-2%2F3%2F4%2F5-red)](docs/pi-compatibility.md)

<!-- TODO: Add photo of birdhouse with detection overlay -->

---

## What it does

- Detects birds in real time using a YOLOv8-nano model running on-device (ONNX via OpenCV DNN)
- Sends annotated Telegram photos the moment a bird is confirmed
- Eliminates false positives with a temporal tracker (multi-frame confirmation)
- Enhances low-light IR camera footage with CLAHE preprocessing
- Classifies bird activity: entry, exit, feeding, resting, transit
- Streams 24/7 live video to YouTube via ffmpeg
- Monitors battery voltage (placeholder ADC, ready for solar setups)
- Runs headless and autonomously from first boot

---

## Quick Start

1. **Flash Raspberry Pi OS Lite** (64-bit recommended) with [Raspberry Pi Imager](https://www.raspberrypi.com/software/). Enable SSH in the imager settings.
2. **Clone this repo** on the Pi:
   ```bash
   git clone https://github.com/Hdjaudpok/BirdPi.git ~/BirdPi
   ```
3. **Run setup** (interactive — configures Telegram, camera, AI settings):
   ```bash
   bash ~/BirdPi/tools/setup.sh
   sudo bash ~/BirdPi/pi/scripts/bootstrap.sh
   ```
4. **Reboot** — BirdPi starts automatically on every boot.

See [docs/installation.md](docs/installation.md) for the full walkthrough.

---

## Features

| Feature | Description |
|---|---|
| YOLOv8-nano AI | Bird detection via ONNX model, no PyTorch needed on Pi |
| Temporal tracker | Requires N consecutive frames before firing an alert |
| CLAHE enhancement | Contrast-limited adaptive histogram equalization for IR/night cameras |
| Activity classifier | Identifies entry, exit, feeding, resting, and transit behaviours |
| Telegram alerts | Annotated JPEG with detection boxes sent to your phone |
| YouTube streaming | 24/7 live stream via ffmpeg RTMP |
| Battery monitor | Voltage tracking via ADC (optional, extensible) |
| Headless boot | All services managed by systemd, no keyboard or monitor needed |
| SD card protection | zram swap, tmpfs for recordings, volatile journald — no SD writes for runtime data |

---

## Hardware

| Part | Minimum | Recommended |
|---|---|---|
| Raspberry Pi | Pi 2 Model B | Pi 3B+ or Pi 4 |
| Camera | Any USB webcam | Wide-angle USB cam or IR Pi Camera Module |
| microSD | 8 GB | 16 GB Class 10 / A1 |
| Power supply | 5V 2.5A micro-USB | 5V 3A USB-C (Pi 4/5) |
| Birdhouse | Any enclosure with camera hole | Weatherproof wooden box |

Estimated cost: ~40 EUR minimum. See [docs/hardware.md](docs/hardware.md) for details.

---

## How it works

```
USB camera
    │
    ▼
Motion (motion detection daemon)
    │ on_event_start.sh / on_event_end.sh
    ▼
telegram_sender.py
    ├── CLAHE (IR enhancement)
    ├── YOLOv8-nano ONNX (bird detection)
    ├── Temporal tracker (multi-frame confirmation)
    ├── Activity classifier
    └── Telegram bot API → your phone

camera_stream.sh (ffmpeg) → YouTube RTMP → 24/7 live stream
```

Motion triggers the AI pipeline. The temporal tracker waits for N consecutive detections before sending an alert, cutting false positives from shadows and insects. All inference runs locally on the Pi.

---

## Train Your Own Model

The bundled model (YOLOv8-nano, 224×224) is trained on a birdhouse dataset. You can fine-tune it on your own species or camera angle.

```bash
cd training/
python train.py --epochs 50 --device auto
python export_onnx.py --imgsz 224
```

See [training/README.md](training/README.md) for the full pipeline.

---

## Pi Compatibility

| Pi Model | AI Detection | YouTube Stream | Notes |
|---|---|---|---|
| Pi 2 Model B | ~6–10 s/frame | Works (400 kbps) | Slow but functional, zram required |
| Pi 3B+ | ~2–4 s/frame | Works (800 kbps) | Recommended minimum |
| Pi 4 (2 GB+) | ~1–2 s/frame | Works (2 Mbps) | Best experience |
| Pi 5 | <1 s/frame | Works (4 Mbps) | Overkill but great |
| Pi Zero 2W | ~8–12 s/frame | Marginal | Experimental |

See [docs/pi-compatibility.md](docs/pi-compatibility.md) for tuning details.

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get started.

---

## License

MIT — see [LICENSE](LICENSE).
