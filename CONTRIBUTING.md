# Contributing

Contributions are welcome — bug fixes, new features, documentation improvements, and hardware experiments all help.

---

## How to Contribute

1. **Fork** the repository on GitHub.
2. **Create a branch** for your change:
   ```bash
   git checkout -b fix/telegram-reconnect
   ```
3. Make your changes, test them (see below), and commit with a clear message.
4. **Open a pull request** against the `main` branch.
   - Describe what the change does and why.
   - If it fixes a reported issue, reference it with `Fixes #123`.

For large changes or new features, open an issue first to discuss the design before writing code.

---

## Development Setup

### On a real Pi (recommended for anything touching services or hardware)

```bash
git clone https://github.com/Hdjaudpok/BirdPi.git ~/BirdPi
bash ~/BirdPi/tools/setup.sh
sudo bash ~/BirdPi/pi/scripts/bootstrap.sh
```

After bootstrap, edit files directly in the repo under `~/BirdPi/pi/app/` or `~/BirdPi/pi/scripts/` and restart the relevant service to test:

```bash
sudo systemctl restart motion.service
```

### On a PC (for training, tools, and non-Pi code)

```bash
git clone https://github.com/Hdjaudpok/BirdPi.git
cd BirdPi/training
pip install ultralytics opencv-python numpy
```

The `tools/deploy.sh` script can push updated files to a Pi over SSH during development — useful to avoid editing files twice.

---

## Code Style

### Shell scripts (`pi/scripts/`, `tools/`)

- All scripts must pass [ShellCheck](https://www.shellcheck.net/) with no errors.
  ```bash
  shellcheck tools/setup.sh
  shellcheck pi/scripts/bootstrap.sh
  ```
- Use `set -euo pipefail` at the top of every script.
- Quote all variable expansions unless deliberately word-splitting.
- Avoid bashisms that are not available on Debian's `/bin/sh` when writing scripts that could run as `sh`.

### Python (`pi/app/`, `training/`)

- Pi-side Python (`pi/app/`) must use the standard library and packages installable via `apt` (`python3-opencv`, `python3-numpy`). Do not add PyPI dependencies to Pi-side code without a very good reason — the Pi may not have pip or internet access.
- PC-side training code (`training/`) may use `ultralytics`, `torch`, etc.
- Follow PEP 8. A line length of 100 characters is acceptable.
- No type annotations are required but are appreciated.
- Prefer clarity over cleverness, especially in the Pi-side code where debugging is harder.

---

## Reporting Issues

When opening a bug report, include:

- **Pi model** (e.g. Raspberry Pi 3B+)
- **OS version**: `cat /etc/os-release`
- **Python version**: `python3 --version`
- **OpenCV version**: `python3 -c "import cv2; print(cv2.__version__)"`
- **Relevant logs**: `journalctl -u motion.service -n 50`
- A clear description of what you expected versus what happened

Feature requests are also welcome. Describe the use case, not just the implementation.

---

## Testing

### On Pi

There is no automated test suite for Pi-side code (the hardware dependency makes it impractical). Manual testing steps:

1. Trigger a motion event manually by waving in front of the camera.
2. Confirm a Telegram alert arrives with an annotated image.
3. Check service status: `systemctl status motion.service camera_stream.service`
4. Check logs: `journalctl -u motion.service -f`

### Training pipeline (PC)

After changes to `training/`:

```bash
cd training/
python prepare_dataset.py   # verify dataset structure
python train.py --epochs 2 --device cpu  # quick smoke test
python evaluate.py
python export_onnx.py --imgsz 224
```

A 2-epoch training run on a small dataset (even 10 images) is sufficient to verify the pipeline does not crash.

### Shell scripts

Run ShellCheck before opening a PR:

```bash
shellcheck tools/setup.sh tools/deploy.sh pi/scripts/bootstrap.sh pi/scripts/install_model.sh
```
