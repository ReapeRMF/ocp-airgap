#!/bin/bash
set -e

echo "=== hw-discovery: installing runtime discovery service ==="

cat > /usr/local/bin/hardware-discovery <<'SCRIPT'
#!/bin/bash
set -e

echo "=== Hardware discovery starting ==="

WIPE_MODE="none"
CHAIN_MODE="no"

grep -q 'wipe=strong' /proc/cmdline && WIPE_MODE="strong"
grep -q 'chain=yes' /proc/cmdline && CHAIN_MODE="yes"

PRIMARY_ID=$(dmidecode -s system-serial-number 2>/dev/null | tr -d ' \t\r\n')
[ -z "$PRIMARY_ID" ] && PRIMARY_ID=$(dmidecode -s system-uuid 2>/dev/null | tr -d ' \t\r\n')
[ -z "$PRIMARY_ID" ] && PRIMARY_ID=$(ip -o link show | awk '/link\/ether/ {print $2; exit}' | tr ':' '-')

MAC=$(cat /sys/class/net/*/address 2>/dev/null | grep -v '00:00:00:00:00:00' | head -1 | tr ':' '-')
IP=$(ip -4 -o addr show scope global 2>/dev/null | awk '{print $4; exit}' | cut -d/ -f1)

python3 - <<'PY' > /var/tmp/hardware.json
import glob
import json
import os
import subprocess
from pathlib import Path


def run(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return ""


def load_json(raw):
    try:
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def read_text(path):
    try:
        return Path(path).read_text().strip()
    except Exception:
        return ""


payload = {
    "primary_id": os.environ.get("PRIMARY_ID", "") or "unknown",
    "mac": os.environ.get("MAC", "") or "unknown",
    "current_ip": os.environ.get("IP", "") or "unknown",
    "wipe_mode": os.environ.get("WIPE_MODE", "none"),
    "chain_mode": os.environ.get("CHAIN_MODE", "no"),
    "timestamp": subprocess.check_output(["date", "-Iseconds"], text=True).strip(),
    "source": "hw-discovery",
}

# System info
system = {}
for key, cmd in [
    ("manufacturer", ["dmidecode", "-s", "system-manufacturer"]),
    ("product", ["dmidecode", "-s", "system-product-name"]),
    ("serial", ["dmidecode", "-s", "system-serial-number"]),
    ("uuid", ["dmidecode", "-s", "system-uuid"]),
    ("bios_vendor", ["dmidecode", "-s", "bios-vendor"]),
    ("bios_version", ["dmidecode", "-s", "bios-version"]),
]:
    value = run(cmd).strip()
    if value:
        system[key] = value
payload["system"] = system

# CPU and memory
cpu_raw = run(["lscpu", "--json"])
payload["cpu"] = load_json(cpu_raw) or {"raw": run(["lscpu"]).splitlines()}
mem_raw = run(["dmidecode", "--type", "memory", "--json"])
payload["memory"] = load_json(mem_raw) or {}
bios_raw = run(["dmidecode", "--type", "bios", "--json"])
payload["bios"] = load_json(bios_raw) or {}

# Disks and storage
lsblk_raw = run([
    "lsblk",
    "-J",
    "-b",
    "-o",
    "NAME,PATH,TYPE,SIZE,MODEL,SERIAL,WWN,HCTL,ROTA,VENDOR,UUID,FSTYPE,PKNAME,PARTLABEL,PARTUUID,MAJOR,MINOR",
])
lsblk_data = load_json(lsblk_raw) or {}
payload["disks"] = lsblk_data.get("blockdevices", [])

# NIC interfaces
ip_raw = run(["ip", "-j", "addr", "show"])
payload["nics"] = load_json(ip_raw) or []

# RAID / storage controller information
raid_sections = []
for name in ["/proc/mdstat", "/etc/mdadm/mdadm.conf"]:
    content = read_text(name)
    if content:
        raid_sections.append({"source": name, "content": content})
mdadm_raw = run(["mdadm", "--detail", "--scan"])
if mdadm_raw.strip():
    raid_sections.append({"source": "mdadm", "content": mdadm_raw})
payload["raid"] = raid_sections

# LLDP / switch discovery if available
lldp_raw = run(["lldpctl", "-f", "json"])
if lldp_raw:
    payload["lldp"] = load_json(lldp_raw) or []
else:
    lldp_plain = run(["lldpctl"]).strip()
    if lldp_plain:
        payload["lldp"] = [{"raw": lldp_plain}]
    else:
        payload["lldp"] = []

# Root device hints candidates for OCP
root_candidates = []
for disk in payload.get("disks", []):
    if disk.get("type") not in {"disk", "raid0", "raid1", "raid10", "raid5", "raid6", "lvm"}:
        continue
    candidate = {
        "deviceName": f"/dev/{disk.get('name', '')}" if disk.get('name') else None,
        "wwn": disk.get("wwn") or disk.get("serial"),
        "serialNumber": disk.get("serial"),
        "vendor": disk.get("vendor"),
        "model": disk.get("model"),
        "sizeBytes": disk.get("size"),
        "path": disk.get("path"),
        "rota": disk.get("rota"),
        "type": disk.get("type"),
    }
    if any(candidate.get(k) for k in ["deviceName", "wwn", "serialNumber", "vendor", "model"]):
        root_candidates.append(candidate)
payload["root_device_hints"] = {
    "disks": root_candidates,
    "preferred_disk": root_candidates[0] if root_candidates else None,
}

# Disk-by-id links for stable device names
by_id = {}
for path in sorted(glob.glob("/dev/disk/by-id/*")):
    try:
        target = os.readlink(path)
    except OSError:
        continue
    by_id[os.path.basename(path)] = target
payload["disk_by_id"] = by_id

json.dump(payload, open("/var/tmp/hardware.json", "w"), indent=2, sort_keys=True)
PY

echo ">>> Report written to /var/tmp/hardware.json"

if command -v curl >/dev/null 2>&1; then
  curl -sS -X POST -H "Content-Type: application/json" \
    --data @/var/tmp/hardware.json \
    http://192.168.1.185:5000/api/inventory >/dev/null 2>&1 || true
fi

if [ "$CHAIN_MODE" = "yes" ]; then
  echo ">>> Chain mode enabled; staying up for follow-on actions."
  while true; do
    sleep 300
  done
else
  echo ">>> Discovery complete; rebooting."
  sleep 10
  reboot
fi
SCRIPT

chmod +x /usr/local/bin/hardware-discovery

cat > /etc/systemd/system/hardware-discovery.service <<'SERVICE'
[Unit]
Description=Hardware Discovery Collection
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/hardware-discovery
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
SERVICE

if command -v systemctl >/dev/null 2>&1; then
  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl enable hardware-discovery.service >/dev/null 2>&1 || true
fi

mkdir -p /etc/systemd/system/multi-user.target.wants
ln -sfn /etc/systemd/system/hardware-discovery.service /etc/systemd/system/multi-user.target.wants/hardware-discovery.service

echo "=== hw-discovery: runtime discovery service installed ==="
