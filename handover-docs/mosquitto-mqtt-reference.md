# Mosquitto / MQTT reference

## History
Originally the sensor script and Node-RED both connected to a **HiveMQ Cloud** broker (`0d1903740afc4f049ca384c3861a9ea3.s1.eu.hivemq.cloud:8883`, TLS, username/password auth). This kept failing to reconnect after the pole install (`[mqtt-broker] Connection failed` in the logs). Root cause turned out to be compounded by a separate bug — see `streetlight_sensors.py`'s history: the script was missing `client.loop_start()`, so it never processed keepalives/reconnects regardless of which broker it used.

Fix: installed **Mosquitto locally on the Pi** so both the sensor script and Node-RED talk to `localhost:1883` — no internet dependency, no TLS/auth to misconfigure.

## Install (Raspberry Pi OS / Debian)
```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable --now mosquitto
sudo systemctl status mosquitto
```
Default config (`/etc/mosquitto/mosquitto.conf`) was left at its defaults — listens on `localhost:1883`, anonymous access allowed. Fine for local-only traffic; would need a listener change + auth if ever exposed beyond the Pi itself.

## Verify it works
```bash
mosquitto_sub -h localhost -t test/topic -v &
mosquitto_pub -h localhost -t test/topic -m 'hello'
# should print: test/topic hello
```

## Topics in use
Published by `streetlight_sensors.py`, subscribed by Node-RED (`mqtt in` node, topic `streetlight/1/#`):

| Topic | Payload | Published |
|---|---|---|
| `streetlight/1/lux` | lux reading (string, 2dp) | every 2s |
| `streetlight/1/temp` | °C (string, 2dp) | every 2s |
| `streetlight/1/voltage` | V (string, 2dp) | every 2s |
| `streetlight/1/power` | W (string, 2dp) | every 2s |
| `streetlight/1/energy` | Wh (string, 3dp) | every 2s |
| `streetlight/1/motion` | `"1"` or `"0"` | immediately on PIR state change, plus every 2s regardless (so Node-RED's cached state never goes stale) |

## Broker config as used in Node-RED
Two `mqtt-broker` config nodes exist in `flows.json`:
- **In use:** `localhost`, port `1883`, no TLS, no auth
- **Leftover/unused:** the old HiveMQ Cloud config (`...s1.eu.hivemq.cloud`, port `8883`, TLS) — not wired to any node, safe to delete if tidying up the flow later

## Watch it live
```bash
mosquitto_sub -h localhost -t 'streetlight/#' -v
```
Useful for confirming the sensor script is actually publishing without needing to check Node-RED or GIMS at all.
