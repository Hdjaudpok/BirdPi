# Pi Compatibility

BirdPi officially supports all Raspberry Pi models from the Pi 2 onward. Performance varies significantly by model; this page explains what to expect and how the system adapts.

---

## Performance Table

| Pi Model | AI Detection | YouTube Stream | RAM | Notes |
|---|---|---|---|---|
| Pi 2 Model B | ~6–10 s/frame | Works (400 kbps) | 1 GB | Slow but fully functional; zram is critical |
| Pi 3B / 3B+ | ~2–4 s/frame | Works (800 kbps) | 1 GB | Recommended minimum for comfortable use |
| Pi 4 (2 GB+) | ~1–2 s/frame | Works (2 Mbps) | 2–8 GB | Best balance of cost and performance |
| Pi 5 | <1 s/frame | Works (4 Mbps) | 4–8 GB | Fastest; most of the margin goes unused |
| Pi Zero 2W | ~8–12 s/frame | Marginal | 512 MB | Experimental; RAM is very tight |

"AI detection" is the time between motion trigger and Telegram alert, dominated by ONNX inference on a 224×224 frame.

---

## What bootstrap.sh Optimises

`pi/scripts/bootstrap.sh` applies a set of tunings that are applied once on first boot regardless of Pi model. They are most impactful on Pi 2 and Pi 3.

### zram swap

File-based swap on a microSD card kills the card within months and is too slow to be useful. BirdPi replaces it with zram:

- Allocates 256 MB of compressed RAM swap using the lz4 algorithm
- Effective capacity is ~512 MB (roughly 2:1 compression ratio on typical data)
- Zero SD card writes during runtime
- `dphys-swapfile` (Raspberry Pi OS default file swap) is disabled and removed

This is what keeps the Pi 2 (1 GB RAM) stable under load with Python, OpenCV, and motion running simultaneously.

### CPU governor

Sets the CPU scaling governor to `performance` via a dedicated systemd service. This locks the CPU at maximum frequency and eliminates inference latency spikes caused by on-demand frequency ramp-up.

On Pi 2/3 this meaningfully reduces worst-case detection time.

### GPU memory split

Sets `gpu_mem=16` in `config.txt`. This is the minimum safe value for headless operation with a USB camera, freeing 48–112 MB of RAM compared to the default.

> If you are using a CSI Pi Camera Module instead of a USB webcam, change this to `gpu_mem=64` in `/boot/firmware/config.txt`, otherwise the camera will fail to initialise.

### Memory pressure tuning

Writes to `/etc/sysctl.d/99-birdpi-memory.conf`:

| Parameter | Value | Effect |
|---|---|---|
| `vm.vfs_cache_pressure` | 200 | Reduces filesystem cache, frees RAM for apps |
| `vm.dirty_ratio` | 10 | Flushes dirty pages sooner |
| `vm.dirty_background_ratio` | 5 | Background flush starts earlier |
| `vm.min_free_kbytes` | 8192 | Keeps a small reserve to avoid OOM stalls |
| `vm.swappiness` | 10 | Only swaps under real memory pressure |

### tmpfs for recordings

Motion detection event recordings are written to a 50 MB tmpfs mount at `~/birdpi/recordings`. This means:
- Zero SD wear from recordings (video is streamed live to YouTube anyway)
- Faster write throughput
- Recordings are lost on reboot (by design — they are ephemeral)

### Journald volatile storage

Systemd journal is set to `Storage=volatile` with a 20 MB runtime cap. Logs live in RAM only and do not survive a reboot. Use `journalctl -u motion.service` to read them while the system is running.

### Disabled services

The following services are stopped and disabled as they are unnecessary for a headless birdhouse:

- `bluetooth.service` / `hciuart.service`
- `avahi-daemon.service`
- `triggerhappy.service`
- `ModemManager.service`

The default boot target is set to `multi-user.target` (no graphical session).

---

## Pi 2 Specific Notes

The Pi 2 is the most constrained supported platform. With all optimisations applied:

- AI inference: ~6–10 seconds per analysed frame (YOLOv8-nano, 224×224, cv2.dnn)
- YouTube streaming: stable at 400 kbps, 10 FPS, 640×480
- Idle RAM after boot: ~200–250 MB free with all services running
- SD card writes: near zero during normal operation

The detection latency means some fast bird events may generate only one or two analysed frames. The temporal tracker's confirmation threshold (`TELEGRAM_TRACKER_CONFIRM_FRAMES`) is set to 3 by default; you may want to lower it to 2 on Pi 2 to avoid missing short visits.

## Pi Zero 2W Notes

The Pi Zero 2W has the same CPU cores as the Pi 3 but only 512 MB of RAM. With motion, OpenCV, and Python all running:

- RAM is very tight (< 50 MB free in typical load)
- YouTube streaming may drop frames or stall under AI load
- Increase zram size to 192 MB (edit the zram-swap.service after bootstrap, change `256M` to `192M` and disable YouTube streaming)

BirdPi will run, but the Pi Zero 2W is not recommended for production use.
