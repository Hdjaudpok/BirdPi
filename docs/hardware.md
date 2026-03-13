# Hardware

BirdPi is designed to work with inexpensive, widely-available hardware. This page lists what you need, what is recommended, and optional additions for advanced setups.

---

## Minimum Hardware

| Component | Specification | Notes |
|---|---|---|
| Raspberry Pi | Any model (2, 3, 4, 5) | Pi 2 is the minimum — slow but functional |
| USB webcam | Any UVC-compatible webcam | Most standard webcams work out of the box |
| microSD card | 8 GB, Class 10 or A1 | 16 GB+ recommended for headroom |
| Power supply | 5V 2.5A (Pi 2/3), 5V 3A USB-C (Pi 4/5) | Underpowered supply causes random crashes |
| Internet | Wi-Fi or Ethernet | Required for Telegram alerts and YouTube streaming |

A basic setup can be assembled for around **40 EUR**.

---

## Recommended Hardware

| Component | Recommendation | Why |
|---|---|---|
| Raspberry Pi | Pi 3B+ or Pi 4 (2 GB+) | 2–4× faster AI inference than Pi 2 |
| Camera | Wide-angle USB webcam (100°+) | Covers more of the birdhouse interior |
| Camera (night) | IR USB camera with built-in LED ring | Works in darkness; CLAHE enhancement is built in |
| microSD | 16–32 GB, A2-rated | Better sustained write speed for motion recordings |
| Case | Weatherproof enclosure | Required for outdoor installation |

---

## Optional: Battery and Solar

BirdPi includes a `battery_monitor.py` service for reading cell voltage. It is pre-wired for an ADC (analog-to-digital converter) on the I2C bus.

| Component | Notes |
|---|---|
| LiPo or LiFePO4 battery | 3.7V–12V depending on buck converter |
| DC-DC buck converter | Regulates battery voltage to 5V for the Pi |
| ADC module (e.g. ADS1115) | Reads battery voltage via I2C (address 0x48) |
| Solar panel | 5W–10W panel is sufficient for Pi 3/4 in direct sunlight |

The battery monitor logs voltage and sends a Telegram alert when voltage drops below the `LOW_BATTERY_VOLTAGE` threshold in `config.env`. Without an ADC connected, the service runs as a placeholder and logs only.

---

## Birdhouse

BirdPi does not require a specific birdhouse design, but a few guidelines help:

**Interior dimensions**

| Bird type | Floor (W × D) | Hole diameter |
|---|---|---|
| Blue tit / Coal tit | 10 × 10 cm | 28–32 mm |
| Great tit / Nuthatch | 12 × 12 cm | 32 mm |
| Sparrow | 12 × 15 cm | 32–35 mm |
| Starling | 15 × 15 cm | 45 mm |

**Camera placement**

- Mount the camera on the ceiling of the birdhouse, angled slightly down toward the nest cup.
- Aim for a 40–60 cm working distance to the nest.
- For IR cameras, ensure the IR LED ring has line of sight to the nest area; avoid pointing it directly at the entrance hole (reflections degrade detection quality).
- Drill a small cable exit hole in the back wall and seal it with silicone after routing the USB cable.

**Weatherproofing**

- Use untreated wood 18–20 mm thick for insulation and durability.
- Apply exterior varnish or wood stain on all outer surfaces.
- Route the USB and power cables through conduit or cable trunking if exposed to weather.

---

## Cost Summary

| Item | Estimated cost |
|---|---|
| Raspberry Pi 3B+ | ~35 EUR |
| USB webcam (basic) | ~10 EUR |
| microSD 16 GB | ~7 EUR |
| Power supply | ~8 EUR |
| Birdhouse (DIY wood) | ~5–10 EUR |
| **Total (minimum)** | **~40–50 EUR** |
| Pi 4 (2 GB) upgrade | ~45 EUR |
| IR night-vision USB camera | ~20–35 EUR |
| Solar + battery kit | ~30–60 EUR |
