# Security hardening

## Collector

`roles/hw_collector/files/collector_app.py` accepts only a JSON object whose
`primary_id` matches `[A-Za-z0-9._-]{1,64}` and is not `.`, `..`, or a path.
The output path has to stay inside the inventory and nextboot directories
after `realpath`. Requests larger than `collector_max_body_bytes` (default 1
MiB) are rejected. An existing next-boot script is left in place unless
`collector_overwrite_nextboot` is true.

Gunicorn binds to `bastion_ip` rather than every interface. When firewalld is
active, the role adds a rich rule allowing `collector_port`/tcp only from
`pxe_subnet`. If firewalld is not active, `setup_bastion.yml` fails. Lab hosts
that do not run firewalld can pass `-e collector_skip_firewalld=true`.

The bearer token is generated on the bastion into
`/etc/hw-collector/auth_token` (mode 0640) unless `collector_auth_token` is
passed as a variable. It is not stored in git. The iPXE menu puts it on the
kernel command line as `collector_token=`, and the discovery ramdisk sends
`Authorization: Bearer`. Anyone who can read the provisioning web root can
read that token. That is the trust boundary of the provisioning network.
Rotate the token by replacing the file and re-rendering `boot.ipxe`; the
ramdisk reads the command line, so the image does not need a rebuild.

## RPM signatures and the bundle manifest

`airgap_disable_gpg_check` now defaults to `false` in
`environments/dev/group_vars/all.yml`. The seed playbook copies
`/etc/pki/rpm-gpg/RPM-GPG-KEY-*` into the bundle, writes `SHA256SUMS` for the
staged files, and writes `airgap_bundle.tar.gz.sha256` beside the tarball.
Before installing RPMs, the bastion runs `sha256sum -c SHA256SUMS` and imports
the bundled keys.

Check the tarball after it crosses the air gap:

```bash
sha256sum -c airgap_bundle.tar.gz.sha256
```

Pass `-e airgap_disable_gpg_check=true` only when the bastion cannot import
those keys.

## iPXE checksums

`vars/ipxe_checksums.yml` pins the SHA256 of the `boot.ipxe.org` builds
fetched on 2026-11-19. Those URLs are rolling, so a later upstream build fails
the seed until the checksums are updated. Pass `-e allow_unverified_ipxe=true`
to download without a checksum.

`deploy_airgap_bastion.yml` fails if `ipxe.pxe` or `ipxe.efi` is missing from
the extracted bundle.
