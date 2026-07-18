# Bare-Metal Hardware Discovery & Telemetry Pipeline

## Bastion Infrastructure & Operations Guide

This guide details the end-to-end administration, execution, and troubleshooting of the air-gapped bare-metal hardware discovery pipeline.

---

## 1. Architecture & Data Flow

When a bare-metal server is powered on, it initiates a stateless discovery loop that interfaces with the bastion services in a precise sequence:

```
[Target Server]                                                       [Bastion Host]
      │                                                                     │
      │─── 1. DHCP / PXE Boot Request ─────────────────────────────────────>│ (DHCPd / TFTP)
      │<── 2. Serves iPXE Boot Menu (boot.ipxe) ────────────────────────────│ (Apache)
      │─── 3. Pulls RAMdisk (vmlinuz & initrd.img) ────────────────────────>│ (Apache)
      │                                                                     │
  (Boots RAMdisk)                                                           │
  (Gathers metrics)                                                         │
      │                                                                     │
      │─── 4. POSTs Hardware Telemetry (JSON) ─────────────────────────────>│ (Gunicorn / Flask)
      │                                                                     │
      │                                             (Writes <ID>.json to /var/lib/hardware-inventory/)
      │                                             (Writes <ID>.ipxe to /var/www/html/nextboot/)
      │                                                                     │
      │<── 5. Sends API Response ("openshift_installer") ───────────────────│
      │                                                                     │
  (Reboots node)                                                            │
      │                                                                     │
      │─── 6. DHCP / PXE (Stage 2) ────────────────────────────────────────>│
      │<── 7. Serves Dynamic Next-Boot Script (/nextboot/<ID>.ipxe) ────────│ (Boots Target Installer)

```

---

## 2. Directory Layout Baseline

All obsolete Fedora files, duplicated playbooks, and stray scripts have been purged. The production directory layout is structured as follows:

| Path | Purpose | Owner / Perms |
| --- | --- | --- |
| `playbooks/seed_airgap_bundle.yml` | Online utility to download dependencies and wheels. | `dstratfo` (User) |
| `playbooks/deploy_airgap_bastion.yml` | Offline baseline package setup (pip, dnf). | `dstratfo` (User) |
| `playbooks/setup_bastion.yml` | Configures Apache, DHCP, Gunicorn, and directories. | `dstratfo` (User) |
| `playbooks/build_and_deploy_discovery_image.yml` | Compiles the CentOS 9 IPA image & deploys iPXE menu. | `dstratfo` (User) |
| `playbooks/hw_process_discovered.yml` | Administrative console helper to print active reports. | `dstratfo` (User) |
| `/opt/hw-collector/` | Operational directory containing `collector.py` and venv. | `collector_user:collector_group` (0755) |
| `/var/lib/hardware-inventory/` | Flat JSON database containing collected telemetry reports. | `collector_user:collector_group` (0755) |
| `/var/www/html/nextboot/` | Dynamic iPXE scripts generated dynamically by the collector. | `collector_user:collector_group` (0755) |
| `/var/www/html/discovery/` | Holds production `vmlinuz` and `initrd.img` boot assets. | `root:root` (0755) |

---

## 3. Standard Operating Procedures (SOPs)

### SOP 101: Adding a New Target Server to Discovery

To discover a brand-new physical host in the air-gapped lab:

1. Ensure the target host's network management interface is wired to the provisioning network switch.
2. Power on the target machine and enter the system BIOS/UEFI configuration.
3. Configure the primary boot interface to **Network Boot / PXE First**.
4. Save and reboot. The machine will load the iPXE menu and automatically timeout to run the **Safe Discovery** RAMdisk.

### SOP 102: Fetching the Discovered Inventory

Once the node completes its collection loop, it will gracefully reboot. To view the parsed hardware report:

* **Direct Filesystem Access:**
```bash
cat /var/lib/hardware-inventory/<SYSTEM-SERIAL-NUMBER>.json

```


* **Unified Console Summary:**
```bash
export ANSIBLE_CONFIG="$HOME/ansible/ansible.cfg"
ansible-playbook -i environments/dev/hosts playbooks/hw_process_discovered.yml

```



### SOP 103: Garbage Collection (Clearing the Database)

Over time, retired hardware or stale test records will clutter the telemetry directories. To flush the active database and next-boot files to start a clean discovery cycle:

```bash
# Delete all archived hardware reports
sudo rm -rf /var/lib/hardware-inventory/*.json

# Delete all generated dynamic target-specific iPXE scripts
sudo rm -rf /var/www/html/nextboot/*.ipxe

```

---

## 4. Diagnostics & Troubleshooting

> **Operational Warning on SELinux:**
> If you are running SELinux in `Enforcing` mode, Apache (`httpd`) might be blocked from reading your dynamic next-boot directory or Gunicorn might be blocked from writing to `/var/www/html/nextboot/`.
> Check your security context logs using: `sealert -a /var/log/audit/audit.log`

### Issue 1: PXE Client Displays `Exec format error` during Boot

* **Root Cause:** The `boot.ipxe` file on the web server contains a shell format signature instead of the native iPXE magic header.
* **Verification:** Run `head -n 1 /var/www/html/ipxe/boot.ipxe`. If it reads `#!/ipxe` or `#!/bin/bash`, it is invalid.
* **Correction:** Ensure the template has exactly `#!ipxe` (no forward slash) as its first line, and redeploy using:
```bash
ansible -i environments/dev/hosts localhost -c local -m ansible.builtin.template -a "src=roles/hw_discovery/templates/ipxe/boot.ipxe.j2 dest=/var/www/html/ipxe/boot.ipxe mode=0644" --become --ask-become-pass

```



### Issue 2: Gunicorn Collector Logs Permission Failures (`Permission denied`)

* **Root Cause:** Gunicorn runs as the isolated service worker user `collector_user` and lacks permissions to write to either `/var/lib/hardware-inventory/` or `/var/www/html/nextboot/`.
* **Correction:** Run the directory synchronization block from the bastion setup playbook, or apply file permissions manually:
```bash
sudo chown -R collector_user:collector_group /var/lib/hardware-inventory /var/www/html/nextboot
sudo chmod -R 0755 /var/lib/hardware-inventory /var/www/html/nextboot

```



### Issue 3: Target Server Boot Loops Repeatedly Back into Discovery

* **Root Cause:** After discovery finishes, the node reboots and hits PXE again. If your default TFTP configuration is set to loop back to discovery, the target will loop endlessly.
* **Verification:** Verify if a specialized next-boot file has been successfully written to `/var/www/html/nextboot/<PRIMARY_ID>.ipxe`.
* **Correction:** Configure your primary DHCP/PXE router to inspect this next-boot chain path, allowing the host to boot its dynamic next-stage payload instead of falling back to discovery.

---

## 5. System Daemon Administration Reference

Keep these core management commands handy when maintaining the backend bastion services:

```bash
# View live application logs for the Flask telemetry receiver
sudo journalctl -u hw_collector -f --no-tail

# Restart the multi-worker Gunicorn web engine
sudo systemctl restart hw_collector

# Restart the DHCP and TFTP engines
sudo systemctl restart dhcpd tftp

# Check Apache web server health
sudo systemctl status httpd

```
