#!/bin/bash

echo "=== Collecting hardware information ==="

MAC=$(ip -o link show | awk '/link\/ether/ {print $2; exit}' | tr ':' '-')
IP=$(ip -4 -o addr show scope global | awk '{print $4; exit}' | cut -d/ -f1)
TIMESTAMP=$(date -Iseconds)

# Force sudo for dmidecode (memory & BIOS often need it)
MEMORY_JSON=$(sudo dmidecode --type memory --json 2>/dev/null || echo '{}')
BIOS_JSON=$(sudo dmidecode --type bios --json 2>/dev/null || echo '{}')

cat > /var/tmp/hardware.json << JSON
{
  "mac": "${MAC}",
  "current_ip": "${IP}",
  "timestamp": "${TIMESTAMP}",
  "cpu": $(lscpu --json 2>/dev/null || echo '{}'),
  "memory": ${MEMORY_JSON},
  "disks": $(lsblk -J -o NAME,SIZE,TYPE,MODEL,SERIAL 2>/dev/null || echo '{}'),
  "nics": $(ip -j addr show 2>/dev/null || echo '[]'),
  "bios": ${BIOS_JSON}
}
JSON

curl -sS -X POST \
  -H "Content-Type: application/json" \
  --data @/var/tmp/hardware.json \
  "http://192.168.1.185:5000/api/inventory" || echo "Failed to send report"

echo ""
echo "Report sent for ${MAC}"
