
import time
import smbus2
import bme280
import minimalmodbus
import RPi.GPIO as GPIO
import paho.mqtt.client as mqtt
import ssl

import json
import requests
from datetime import datetime, timezone
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleAuthRequest

import logging
from logging.handlers import RotatingFileHandler

logger = logging.getLogger("streetlight")
logger.setLevel(logging.INFO)
_handler = RotatingFileHandler("/home/pi/logs/mqtt.log", maxBytes=1_000_000, backupCount=3)
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_handler)

gims_logger = logging.getLogger("gims")
gims_logger.setLevel(logging.INFO)
_gims_handler = RotatingFileHandler("/home/pi/logs/gims.log", maxBytes=1_000_000, backupCount=3)
_gims_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
gims_logger.addHandler(_gims_handler)

MQTT_SERVER = "localhost"
MQTT_PORT   = 1883
PIR_PIN     = 27

GIMS_KEY_FILE         = "/home/pi/sa-key.json"
GIMS_API_URL          = "https://gims-api-744852476592.asia-southeast1.run.app"
GIMS_TENANT_ID        = "761988e2-8b8b-4f66-882d-a4d844561266"
GIMS_EDGE_DEVICE_ID   = "35c0bd55-401d-5a5f-9afc-fee9806d0efe"
GIMS_PUBLISH_INTERVAL = 30

GPIO.setmode(GPIO.BCM)
GPIO.setup(PIR_PIN, GPIO.IN)

bus = smbus2.SMBus(1)
BH1750_ADDR = 0x23
BME280_ADDR = 0x76

def init_bh1750():
    bus.write_byte(BH1750_ADDR, 0x10)
    time.sleep(0.2)

try:
    init_bh1750()
    bh1750_ok = True
except OSError as ex:
    print("BH1750 init failed, lux readings disabled:", ex)
    bh1750_ok = False

try:
    bme_calib = bme280.load_calibration_params(bus, BME280_ADDR)
    bme280_ok = True
except OSError as ex:
    print("BME280 init failed, temp readings disabled:", ex)
    bme280_ok = False

def read_lux():
    data = bus.read_i2c_block_data(BH1750_ADDR, 0x10, 2)
    return (data[0] << 8 | data[1]) / 1.2

def read_temp():
    data = bme280.sample(bus, BME280_ADDR, bme_calib)
    return data.temperature

pzem = minimalmodbus.Instrument('/dev/ttyAMA0', 1)
pzem.serial.baudrate = 9600
pzem.serial.timeout = 1

def read_pzem():
    regs = pzem.read_registers(0, 9, functioncode=4)
    voltage = regs[0] / 10.0
    power   = ((regs[4] << 16) | regs[3]) / 10.0
    energy  = (regs[6] << 16) | regs[5]
    return voltage, power, energy

def on_connect(client, userdata, flags, rc):
    logger.info(f"Connected to broker, rc={rc}")

def on_disconnect(client, userdata, rc):
    logger.warning(f"Disconnected from broker, rc={rc}")

client = mqtt.Client()
client.on_connect = on_connect
client.on_disconnect = on_disconnect
logger.info(f"Attempting connection to broker at {MQTT_SERVER}:{MQTT_PORT}")
client.connect(MQTT_SERVER, MQTT_PORT)
client.loop_start()

try:
    _gims_id_token_credentials = service_account.IDTokenCredentials.from_service_account_file(
        GIMS_KEY_FILE, target_audience=GIMS_API_URL)
    gims_logger.info("GIMS ID token credentials initialized")
except Exception as ex:
    _gims_id_token_credentials = None
    gims_logger.error(f"Failed to initialize GIMS credentials: {ex}")

def _get_gims_token():
    _gims_id_token_credentials.refresh(GoogleAuthRequest())
    return _gims_id_token_credentials.token

latest_readings = {}

def publish_gims_telemetry():
    if _gims_id_token_credentials is None or not latest_readings:
        return
    payload = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "readings": dict(latest_readings),
    }
    url = f"{GIMS_API_URL}/api/v1/edge_devices/{GIMS_EDGE_DEVICE_ID}/telemetry"
    try:
        token = _get_gims_token()
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-Id": GIMS_TENANT_ID,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10,
        )
        if resp.ok:
            gims_logger.info(f"Published (HTTP {resp.status_code}): {payload['readings']}")
        else:
            gims_logger.warning(f"Publish failed (HTTP {resp.status_code}): {resp.text[:300]}")
    except Exception as ex:
        gims_logger.warning(f"Publish failed: {ex}")


last_motion = GPIO.input(PIR_PIN)
last_publish = 0
last_gims_publish = 0

try:
    while True:
        motion = GPIO.input(PIR_PIN)
        if motion != last_motion:
            client.publish("streetlight/1/motion", "1" if motion else "0")
            print("Motion:", motion)
            last_motion = motion

        now = time.time()
        if now - last_publish >= 2:
            client.publish("streetlight/1/motion", "1" if motion else "0")
            last_publish = now

            if bh1750_ok:
                try:
                    lux = read_lux()
                    client.publish("streetlight/1/lux", f"{lux:.2f}")
                    print(f"Lux: {lux:.2f}")
                    latest_readings["monitor-1.lux"] = round(lux, 2)
                except OSError as ex:
                    print("Lux read failed:", ex)
                    bh1750_ok = False

            if bme280_ok:
                try:
                    temp = read_temp()
                    client.publish("streetlight/1/temp", f"{temp:.2f}")
                    print(f"Temp: {temp:.2f}")
                    latest_readings["monitor-1.temperature"] = round(temp, 2)
                except OSError as ex:
                    print("Temp read failed:", ex)
                    bme280_ok = False

            if not bh1750_ok:
                try:
                    init_bh1750()
                    bh1750_ok = True
                    print("BH1750 back online")
                except OSError:
                    pass

            if not bme280_ok:
                try:
                    bme_calib = bme280.load_calibration_params(bus, BME280_ADDR)
                    bme280_ok = True
                    print("BME280 back online")
                except OSError:
                    pass

            try:
                v, p, e = read_pzem()
                client.publish("streetlight/1/voltage", f"{v:.2f}")
                client.publish("streetlight/1/power", f"{p:.2f}")
                client.publish("streetlight/1/energy", f"{e:.3f}")
                print(f"Voltage: {v:.2f}  Power: {p:.2f}  Energy: {e}")
                latest_readings["monitor-1.voltage"] = round(v, 2)
                latest_readings["monitor-1.activePower"] = round(p, 2)
            except Exception as ex:
                print("PZEM read failed:", ex)

            if now - last_gims_publish >= GIMS_PUBLISH_INTERVAL:
                last_gims_publish = now
                publish_gims_telemetry()

        time.sleep(0.1)
except KeyboardInterrupt:
    GPIO.cleanup()
