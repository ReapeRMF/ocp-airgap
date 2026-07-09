# hw_collector Role

Lightweight Flask-based collector for hardware inventory reports from PXE-booted machines.

## Overview

Receives JSON POSTs from the `discovery-collect.sh` script running inside the Fedora Live environment and stores them as individual JSON files for later processing.

## Features

- Simple REST endpoint (`/api/inventory`)
- Automatic directory creation
- MAC-based filename deduplication
- Robust error handling
- Systemd service with auto-restart

## Requirements

- Python 3 + Flask (installed by the role)
- Network access from provisioning subnet to the collector port

## Role Variables

| Variable             | Default                  | Description |
|----------------------|--------------------------|-----------|
| `collector_port`     | `5000`                   | Listening port |
| `collector_dir`      | `/var/lib/hardware-inventory` | Storage location for reports |

## Files Deployed

- `/opt/hardware-collector/collector.py`
- `/etc/systemd/system/hw_collector.service`

## Example Playbook

```yaml
- hosts: bastion
  become: true
  roles:
    - hw_collector



=========================================


## Service Management

# After deployment
systemctl status hw_collector
systemctl restart hw_collector
journalctl -u hw_collector -f

## Report Format
Reports are stored as <MAC>.json and contain:

System identifiers (MAC, IP)
* CPU, memory, disk, NIC details
* Switch LLDP neighbor data
* Optional disk wipe results

## Post-Processing
See playbooks/process_discovered_hardware.yml for example report parsing and dynamic inventory generation.
Security Notes

Runs on a dedicated provisioning network
Consider adding firewall rules to restrict access to the collector port
No authentication (intended for isolated provisioning VLAN)
