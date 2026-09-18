#!/bin/bash
LOGFILE="/home/pi/logs/health.log"
TS=$(date '+%Y-%m-%d %H:%M:%S')

check_service() {
    SERVICE=$1
    if systemctl is-active --quiet "$SERVICE"; then
        echo "$TS [OK] $SERVICE is running" >> "$LOGFILE"
    else
        echo "$TS [FAIL] $SERVICE is NOT running" >> "$LOGFILE"
    fi
}

check_service mosquitto
check_service nodered.service
check_service streetlight-sensors.service

GATEWAY=$(ip route | awk '/default/ {print $3}')
if ping -c 1 -W 3 "$GATEWAY" > /dev/null 2>&1; then
    echo "$TS [OK] network reachable (gateway $GATEWAY)" >> "$LOGFILE"
else
    echo "$TS [FAIL] network unreachable (gateway $GATEWAY)" >> "$LOGFILE"
fi

DISK_USE=$(df -h / | awk 'NR==2 {print $5}' | tr -d '%')
if [ "$DISK_USE" -ge 90 ]; then
    echo "$TS [WARN] disk usage at ${DISK_USE}%" >> "$LOGFILE"
fi

POWER_LOG="/home/pi/logs/power.log"
THROTTLED=$(vcgencmd get_throttled)
VOLT_5V=$(vcgencmd pmic_read_adc | grep EXT5V_V | awk -F= '{print $2}')
echo "$TS $THROTTLED EXT5V=$VOLT_5V" >> "$POWER_LOG"

if [ "$THROTTLED" != "throttled=0x0" ]; then
    echo "$TS [WARN] undervoltage/throttle flag set: $THROTTLED" >> "$LOGFILE"
fi
