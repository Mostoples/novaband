#!/usr/bin/env bash
# Upload firmware ke ESP32-C3 lewat WiFi (casing tertutup). Syarat:
#   - jam LilyGo menyala (kalau mati, C3 tidur dan OTA tidak tersedia)
#   - komputer di WiFi yang sama dengan C3 (novaband-id)
#   - firewall komputer mengizinkan C3 menyambung balik: skrip ini memakai TCP 8899 (ubah PORT bila perlu)
# Pakai:  firmware/ota-c3.sh [IP-C3]     (tanpa argumen: IP diambil dari RTDB /devices/esp32c3/info/ip)
set -euo pipefail
cd "$(dirname "$0")"
DB=https://novaband-id-default-rtdb.asia-southeast1.firebasedatabase.app
IP=${1:-$(curl -s "$DB/devices/esp32c3/info/ip.json" | tr -d '"')}
PORT=8899
OUT=${TMPDIR:-/tmp}/novaband_c3_build
ESPOTA=$(ls ~/.arduino15/packages/esp32/hardware/esp32/*/tools/espota.py | tail -1)
PASS=$(grep OTA_PASS novaband_c3_sensors/secrets.h | cut -d'"' -f2)
echo "C3 di $IP"
arduino-cli compile -b "esp32:esp32:esp32c3:CDCOnBoot=cdc,PartitionScheme=min_spiffs" --output-dir "$OUT" novaband_c3_sensors
python3 "$ESPOTA" -i "$IP" -p 3232 -P "$PORT" -a "$PASS" -f "$OUT/novaband_c3_sensors.ino.bin"
