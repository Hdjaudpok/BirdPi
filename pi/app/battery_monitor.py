#!/usr/bin/env python3
import logging
import os
import subprocess
import time
from pathlib import Path

BASE_DIR = Path(os.environ.get("BIRDPI_DIR", Path.home() / "birdpi"))
CONFIG_PATH = BASE_DIR / "config.env"
LOG_PATH = BASE_DIR / "logs" / "battery_monitor.log"


def load_env(path: Path) -> dict:
    values = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def read_battery_voltage() -> float | None:
    # Placeholder: remplacer par lecture ADC/HAT (PiJuice, MCP3008, etc.)
    return None


def main() -> int:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
    )

    cfg = load_env(CONFIG_PATH)
    low_voltage = float(cfg.get("LOW_BATTERY_VOLTAGE", "3.30"))
    interval_sec = int(cfg.get("BATTERY_CHECK_INTERVAL_SEC", "60"))

    logging.info("battery monitor demarre (seuil=%.2fV, interval=%ss)", low_voltage, interval_sec)

    while True:
        voltage = read_battery_voltage()
        if voltage is None:
            logging.info("lecture batterie indisponible (placeholder)")
        else:
            logging.info("tension batterie: %.3fV", voltage)
            if voltage <= low_voltage:
                logging.warning("batterie faible (%.3fV <= %.3fV), extinction", voltage, low_voltage)
                subprocess.run(["sudo", "/sbin/shutdown", "-h", "now"], check=False)  # noqa: S603
                return 0
        time.sleep(interval_sec)


if __name__ == "__main__":
    raise SystemExit(main())
