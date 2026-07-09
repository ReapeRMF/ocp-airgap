# hw_discovery Role

**PXE Infrastructure and Hardware Discovery for Bare-Metal Servers**

This role deploys a complete PXE boot environment designed to discover and inventory new bare-metal hardware. It uses **iPXE** as the primary bootloader (with proper chainloading for legacy BIOS) and boots machines into a customized Fedora Live environment for data collection.

## Overview

The role sets up:
- DHCP + TFTP services via dnsmasq
- iPXE boot menu with system information display
- HTTP server serving the custom Fedora Live image
- Safe fallback to classic pxelinux
- Integration with the `hw_collector` role for report submission

This is ideal for data center provisioning, bare-metal Kubernetes/OpenShift deployment preparation, or hardware inventory automation.

## Features

- Full support for both Legacy BIOS and UEFI systems
- Rich iPXE menu showing Service Tag / Serial Number for verification
- Safe-by-default behavior (no disk changes unless explicitly confirmed)
- Interactive confirmation for destructive operations
- LLDP-based switch neighbor discovery
- Optional 100MB disk header wipe (non-destructive to existing data partitions)
- Easy fallback to classic pxelinux
- Designed for air-gapped environments after initial preparation

## Safety Mechanisms

This role includes multiple layers of protection against accidental data loss:

1. **iPXE Menu Level**
   - Clear visual warning for wipe option
   - Interactive confirmation prompt (`y/n`)
   - Safe option is the default on timeout

2. **Discovery Script Level**
   - Hostname-based protection (blocks common bastion/management names)
   - Protected MAC address list (customizable)
   - Wipe only executes if `discovery.wipe=1` kernel parameter is present

3. **Operational**
   - Wipe option is clearly labeled as **DESTRUCTIVE**
   - System information (serial number) is displayed before any action

**Strong Recommendation**: Always add your bastion host's MAC address(es) to the `PROTECTED_MACS` array in `discovery-collect.sh`.

## Requirements

- Ansible control node (bastion) running Red Hat / Fedora
- Dedicated provisioning network interface (usually `eth0`)
- Firewall ports open: DHCP (67/68), TFTP (69), HTTP (80), Collector port (default 5000)
- Offline artifacts prepared using `prepare_offline_artifacts_x86_64.yml`

## Role Variables

See `defaults/main.yml` and `group_vars/all/pxe.yml`.

**Key Variables:**

| Variable                | Example Value                    | Description |
|-------------------------|----------------------------------|-----------|
| `pxe_subnet`            | `192.168.50.0/24`                | Provisioning subnet |
| `pxe_dhcp_range`        | `192.168.50.100,192.168.50.200`  | DHCP range for clients |
| `local_artifacts_dir`   | `/opt/offline-artifacts-x86_64`  | Path to extracted artifacts |
| `bastion_ip`            | (auto-detected)                  | IP clients should use |
| `collector_port`        | `5000`                           | Collector service port |

## Directory Structure Impact

This role manages:
- `/etc/dnsmasq.conf`
- `/var/lib/tftpboot/ipxe/`
- `/var/www/html/ipxe/boot.ipxe`
- `/var/www/html/fedora-live/`

## Usage

```bash
# Full deployment (PXE + Collector)
ansible-playbook playbooks/discover_hw.yml -i environments/production/hosts

## Boot Process

1. New server performs network boot (PXE)
2. dnsmasq serves the appropriate iPXE binary (`undionly.kpxe` for Legacy BIOS or `ipxe.efi` for UEFI)
3. iPXE loads and displays the boot menu with system information (Service Tag / Serial Number, Product Name, etc.)
4. User selects the desired option from the menu
5. The custom Fedora Live image boots into RAM and automatically executes `discovery-collect.sh`
6. Hardware inventory data (including LLDP switch info) is collected and the report is sent via HTTP POST to the collector on the bastion

## Troubleshooting

- Check dnsmasq logs: `journalctl -u dnsmasq -f`
- Verify iPXE files are present in the TFTP root: `ls -l /var/lib/tftpboot/ipxe/`
- Confirm firewall rules allow DHCP (UDP 67/68), TFTP (UDP 69), HTTP (TCP 80), and the collector port (default TCP 5000)
- Use the **iPXE Shell** option from the menu for manual debugging and testing network connectivity
- Check HTTP access to the squashfs image: `curl -I http://<bastion-ip>/fedora-live/squashfs.img`

## Security Considerations

- Run the PXE/DHCP services on an **isolated provisioning VLAN** whenever possible
- Restrict access to the collector port (default 5000) to only the provisioning subnet
- Regularly review and update the protected MAC address list in `discovery-collect.sh`
- Monitor collector logs for unexpected reports
- Consider implementing network ACLs or firewall rules to limit which machines can boot via PXE

