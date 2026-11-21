# hw_discovery role

This role builds the discovery IPA image and can render the iPXE menu. It does not configure DHCP or TFTP. Those templates were removed because no task rendered them; the bastion's DHCP service, if any, is outside this repository.

`build_ipa_image` defaults to false, so `setup_bastion.yml` does not rebuild the image. `playbooks/build_and_deploy_discovery_image.yml` calls `build-ipa.yml` directly. In-band probing runs only when `inband_discovery` is true.

## What this role does

- Builds the CentOS Stream 9 IPA image when `build-ipa.yml` is included.
- Deploys the iPXE menu from `templates/ipxe/boot.ipxe.j2` at the end of that build.
- Optionally probes the local host and posts inventory when `inband_discovery` is true.

## Important notes on configuration

The iPXE menu template passes options such as `chain=yes` and `wipe=strong` directly on the `kernel` line. Testing showed that using `imgargs` after loading the kernel did not reliably make those options appear in `/proc/cmdline` inside the live image. Putting the options on the kernel line is the method that worked consistently.

DHCP and TFTP are not configured by this role. Earlier drafts described dnsmasq and ISC dhcpd; no task rendered those templates, so the templates and handlers were removed.

## Variables

See `defaults/main.yml`. Values inventory commonly overrides:

- `bastion_ip` — address clients use to reach this server
- `build_ipa_image` — defaults to false; the image playbook builds directly
- `inband_discovery` — defaults to false
- `offline_artifacts_dir` — extracted offline artifacts

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
