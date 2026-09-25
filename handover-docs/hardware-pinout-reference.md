# Hardware / pinout reference

Extracted from `streetlight_sensors.py`. All sensors are read directly on the Raspberry Pi 5.

| Sensor / module | Interface | Pin / bus / address | Reads |
|---|---|---|---|
| PIR motion sensor | GPIO (digital in), BCM numbering | GPIO27 | Motion: 1 = detected, 0 = clear. Time-Delay potentiometer on the PIR module itself set to 10s ± 3s (see conclusion.html open items). |
| BH1750 (ambient light) | I2C, bus 1 | Address `0x23` | Lux |
| BME280 (temp/pressure/humidity) | I2C, bus 1 (shares the bus with BH1750) | Address `0x76` | Temperature (°C) — humidity/pressure available from the sensor but not currently read |
| PZEM power meter ⚠️ **abandoned 2026-09-22** | UART/Modbus (RTU), via `minimalmodbus` | `/dev/ttyAMA0`, slave address 1, 9600 baud | Was: voltage (V), active power (W), energy (Wh). Extensively troubleshot (UART config, TX/RX wiring, a resistor divider, a 60-attempt wiggle-test) with no success — deliberately not pursued further. Does not affect auto-dim. Recommended: physically disconnect this wiring from the Pi rather than leave a non-functional, unprotected 5V line in place. |

## Power supply
Raspberry Pi 5 — needs a stable 5V/5A (25W official) supply. Project history: suspected (long USB-C cable → undervoltage) then confirmed (per user, 2026-09-09) actual root cause of the recurring offline incidents was a **hardware fault — intermittent SD card read failures**, not the power cable. See `conclusion.html` → Open Items for current status.

## Moot — PZEM abandoned: TX voltage protection notes kept for historical reference

The PZEM-004T v3's TTL TX line idles at 5V, but it's wired straight into the Pi's UART RX (pin 10 / GPIO15), which is rated 3.3V — no protection currently installed. This is out-of-spec and the risk isn't reliably small: it could keep working, fail immediately, or degrade the input over time. It predates this documentation (present on both the old Pi 5 and current Pi 4B), but should be fixed before handover rather than carried forward.

**Fix — a resistor divider, no level-shifter board needed:**
```
PZEM TX ──[1kΩ]──●── Pi pin 10 / GPIO15 (RXD)
                  │
                [2kΩ]
                  │
                 GND
```
This divides 5V down to ~3.3V at the Pi's input (5V × 2k/(1k+2k) = 3.33V). Cheap, simple, two resistors.

**The other direction is fine as-is:** Pi pin 8 / GPIO14 (TXD) → PZEM RX needs no protection — leave that wire direct.

Skipping this is only defensible if a qualified measurement confirms the PZEM TX signal never actually exceeds 3.3V in practice — but safely taking that measurement means working with powered equipment near mains, which is more effort and more risk than just installing the two resistors. Treat this as required work, not optional.

## GPIO/I2C library notes
- `RPi.GPIO` on this Pi 5 runs on the `lgpio` backend (not the classic sysfs GPIO driver) — a pin can only be claimed by one process at a time. Attempting to read GPIO27 from a second process while `streetlight-sensors.service` is running fails with `lgpio.error: 'GPIO busy'`. To do standalone GPIO diagnostics, either stop the service first or read the existing service's own logs/journal instead (it already prints `Motion: <value>` on every transition).
- I2C bus 1 is shared between the BH1750 and BME280 — both initialize independently at startup and each has its own online/offline retry logic if a read fails (see `streetlight_sensors.py`).
