# Security hardening

## Collector tokens

Two tokens are generated on the bastion and are not committed.

- Admin token: `/etc/hw-collector/auth_token` (mode 0640). It can create and
  update inventory. It is not written under the web root. In-band probing
  uses this token. If `collector_auth_token` is passed into the play, the
  play does not read the file. Otherwise it reads the file as root.
- Enroll token: `/etc/hw-collector/enroll_token` (mode 0640). `boot.ipxe`
  puts only this token on the kernel command line. The enroll token can
  create a discovery record that does not exist yet. If the inventory file
  or the next-boot script already exists, the collector returns 409 and
  does not write or return the stored record. The admin token is what can
  update an existing record.

`primary_id` must match `[A-Za-z0-9._-]{1,64}`, must not start with `.` or
`-`, and must not be a path. Inventory files are mode 0640. A non-ASCII
`Authorization` header is 401. Bodies over 1 MiB and non-object JSON are
rejected.

Gunicorn binds to `bastion_ip`. When firewalld is active, `collector_port`/tcp
is allowed only from `pxe_subnet`. If firewalld is not active, setup fails
unless `-e collector_skip_firewalld=true`.

httpd is installed when the boot menu is deployed. `/etc/httpd/conf.d/ipxe-discovery.conf`
contains `Require ip {{ pxe_subnet }}` for `/ipxe`.

### Residual risk

Anyone who can reach httpd from `pxe_subnet` can fetch `/ipxe/boot.ipxe` and
read the enroll token. With that token they can create new discovery records
for ids that do not exist yet. They cannot overwrite an existing inventory
file or next-boot script, and the API does not return stored records.
`/discovery` and `/nextboot` are not covered by that Apache location. The
admin token stays off the web server, but it is still on the bastion disk
and in the memory of an in-band play that passes it. A wrong or very wide
`pxe_subnet` widens who can read the enroll token. If httpd is started
without `ipxe-discovery.conf`, the enroll token is reachable by anyone who
can reach port 80.

## RPM signatures and the bundle manifest

`airgap_disable_gpg_check` defaults to `false`. Only RPM keys whose primary
fingerprint is listed in `vars/rpm_gpg_keys.yml` are copied and imported.
The list currently contains the CentOS official signing key
`99DB70FAE1D7CE227FB6488205B555B38483C65D`. Add the online host's repository
key fingerprints to that file before seeding if they differ. Keys that are
not listed are not copied. A bundled key that is not listed fails the deploy.

The trust anchor for the extracted bundle is the SHA256 of the `SHA256SUMS`
file, carried outside the archive. The seed playbook writes
`airgap_sha256sums.sha256` next to the tarball and does not put that digest
inside the tarball. On the bastion, before any collection or RPM install:

```bash
ansible-playbook playbooks/deploy_airgap_bastion.yml \
  -e airgap_sha256sums_digest=<hex-from-airgap_sha256sums.sha256>
```

The play checks that digest against `SHA256SUMS`, then runs
`sha256sum -c SHA256SUMS`. This is an out-of-band digest, not a GPG signature
on the manifest. The RPM keys travel inside the bundle, so they cannot
authenticate `SHA256SUMS`. The outer `airgap_bundle.tar.gz.sha256` still
checks the tarball before you extract it. The digest above is what makes
the extracted manifest trustworthy.

Pass `-e airgap_disable_gpg_check=true` only when the bastion cannot import
the pinned keys.

## iPXE checksums

`vars/ipxe_checksums.yml` pins the SHA256 of the `boot.ipxe.org` builds
fetched on 2026-11-19. Pass `-e allow_unverified_ipxe=true` to skip that
check. Deploy fails if `ipxe.pxe` or `ipxe.efi` is missing.

Python packages in the collector virtualenv and the seed wheel download are
pinned to gunicorn 23.0.0, Flask 3.1.2, and Werkzeug 3.1.9.
