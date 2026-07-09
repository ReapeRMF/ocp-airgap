# hw_discovery role

This role configures a bastion machine so it can PXE boot new servers, show an iPXE menu, and run a hardware discovery process.

It sets up dnsmasq (for DHCP and TFTP), httpd (to serve the boot image and iPXE menu), copies the needed iPXE binaries, and deploys the main boot menu.

## What this role does

- Creates the TFTP and HTTP directory structure used for PXE booting.
- Copies iPXE binaries (undionly.kpxe, ipxe.efi, snponly.efi, etc.) from a prepared offline artifacts directory.
- Writes a dnsmasq configuration that provides DHCP addresses and serves files over TFTP.
- Deploys an iPXE menu that lets the operator choose safe discovery, destructive wipe, or chain mode.
- Starts and enables dnsmasq, httpd, and lldpd.
- Opens the necessary firewall ports when firewalld is running.

## Important notes on configuration

The iPXE menu template passes options such as `chain=yes` and `wipe=strong` directly on the `kernel` line. Testing showed that using `imgargs` after loading the kernel did not reliably make those options appear in `/proc/cmdline` inside the live image. Putting the options on the kernel line is the method that worked consistently.

**DHCP Backend Choice**

This role supports two options via the `dhcp_backend` variable:

- `dnsmasq` (default): One process for DHCP + TFTP. Simpler but had repeated reliability problems (port 53 conflicts, not listening on DHCP ports) during testing.
- `isc`: Uses traditional ISC DHCP (`dhcpd`) + `tftp-server`. This is what ultimately worked reliably in our environment after dnsmasq issues.

Set `dhcp_backend: isc` in your inventory or when running the playbook if you want the ISC path.

The dnsmasq configuration uses `bind-dynamic` and listens on a specific interface. On systems where `systemd-resolved` is also running and using port 53, dnsmasq will fail to start. In that case `systemd-resolved` should be stopped and disabled before using this role for DHCP.

## Variables

See `defaults/main.yml` for the full list. The most commonly changed values are:

- `bastion_ip` — IP address the new machines will use to reach this server
- `dhcp_interface` — the network interface that faces the new machines
- `dhcp_range_start` / `dhcp_range_end` — IP range handed out to new machines
- `offline_artifacts_dir` — where the prepared iPXE binaries and Fedora image live after extraction

## Typical usage

Include the role in a playbook that runs on the bastion:

```yaml
- hosts: bastion
  roles:
    - hw_discovery
```

After the role runs, the bastion should be ready to serve PXE boots for hardware discovery.

## Related roles

- `hw_collector` — receives the JSON reports sent by the discovery image
- Custom IPA element `rich-discovery` — adds the actual collection script and systemd service into the boot image
