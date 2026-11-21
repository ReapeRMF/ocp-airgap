# Lint exceptions and owner decisions

CI (`.github/workflows/ci.yml`) runs yamllint, `ansible-lint --profile production`,
`ansible-playbook --syntax-check` on ansible-core 2.16.20 and 2.21.6 for every
file under `playbooks/` and `roles/*/tests/`, shellcheck, and gitleaks. No job
is skipped. Actions are pinned to commit SHAs. The gitleaks tarball is checked
against the release `checksums.txt` and a digest pinned in the workflow.
`requirements-ci.txt` pins the Python tools. Dependabot watches GitHub Actions
and that pip file.

Production ansible-lint stays enabled. `var-naming[no-role-prefix]` is not
disabled for the repository. Role-internal registers were renamed. The public
defaults that inventory overrides stay unprefixed and are listed in
`.ansible-lint-ignore`.

## Ignored ansible-lint paths

Each entry in `.ansible-lint-ignore` uses the `skip` qualifier so these known defaults are not warnings. A new unprefixed variable in any other file still fails.

| Path | Rule | Why |
| --- | --- | --- |
| `roles/hw_discovery/defaults/main.yml` | `var-naming[no-role-prefix]` | Inventory, playbooks, and templates set `bastion_ip`, `collector_port`, `build_ipa_image`, and `pxe_*` with no role prefix. |
| `roles/hw_collector/defaults/main.yml` | `var-naming[no-role-prefix]` | Same contract for `collector_user`, `collector_dir`, `collector_port`, and `offline_wheel_dir`. |

The `online_prep` role was removed. Seeding is `playbooks/seed_airgap_bundle.yml`.

Internal names now use a role prefix: `hw_collector_wheel_dir_stat`,
`hw_discovery_ipmi_lan_raw`, `hw_discovery_local_bmc_ip`,
`hw_discovery_local_bmc_mac`, `hw_discovery_live_boot_sequence`,
`hw_discovery_live_active_boot_target`, and `hw_discovery_live_cpu_microcode`.
`var-naming[read-only]` is still enforced everywhere.

`playbooks/hw_process_discovered.yml` used to set `inventory_dir`, which is a read-only Ansible variable. The play var is now `hardware_inventory_dir`. The path is still `/var/lib/hardware-inventory`.

## Inline noqa

`playbooks/seed_airgap_bundle.yml` packs the bundle with `tar -czf ... -C staging .` so the archive root is the staging contents (`rpm_packages/`, `ipxe_binaries/`, ...). `community.general.archive` does not preserve that layout, and `unarchive` only extracts. The task is marked `# noqa: command-instead-of-module`.

## Checks that are not clean, on purpose

These were not "fixed" by flipping a default. Each one needs an owner decision.

### PXE variables

`environments/dev/all.yml` was not loaded by Ansible and has been deleted. The loaded file is `environments/dev/group_vars/all.yml` (`192.168.1.0/24`, bastion `192.168.1.185`).

No task ever rendered `dhcpd.conf.j2` or `dnsmasq.conf.j2`, so this repository does not serve DHCP. Those templates, the unused pxelinux template, and the dnsmasq/dhcpd handlers were removed rather than inventing a DHCP service. `pxe_subnet` and `pxe_dhcp_range` remain in group_vars as the lab network record. `local_artifacts_dir` was renamed to `offline_artifacts_dir`, which is the name the role reads. The path is still `/opt/offline-artifacts-x86_64`.

`playbooks/build_and_deploy_discovery_image.yml` still sets `bastion_ip` to the host address or `192.168.50.10` for that play only.

### GPG verification is still disabled for air-gap RPMs

`playbooks/deploy_airgap_bastion.yml` installs local RPMs with `disable_gpg_check: "{{ airgap_disable_gpg_check | default(true) | bool }}"`. The value lives in `environments/dev/group_vars/all.yml` (still `true`), so inventory can override it. A play var cannot, because play vars outrank group_vars. Turn it off only after the bastion has the keys that signed the packages downloaded on the online host:

```bash
ansible-playbook playbooks/deploy_airgap_bastion.yml -e airgap_disable_gpg_check=false
```

### iPXE downloads have no checksum until one is supplied

`https://boot.ipxe.org/ipxe.pxe` and `https://boot.ipxe.org/x86_64-efi/snponly.efi` are rolling URLs. No checksum is committed, because a stale hash would fail the next seed. `get_url` accepts one when the owner pins a build:

```bash
ansible-playbook playbooks/seed_airgap_bundle.yml \
  -e ipxe_pxe_checksum='sha256:<hex>' \
  -e ipxe_efi_checksum='sha256:<hex>'
```

The seed playbook is the only seeding entrypoint.

### Hardcoded path, not a credential

`seed_airgap_bundle.yml` still defaults `staging_dir` to `/home/dstratfo/airgap_shipment`. Override with `-e seed_staging_dir=...`. No passwords, tokens, or API keys are committed. gitleaks covers that in CI.

`ansible.cfg` sets `host_key_checking = False`. `environments/dev/hosts` sets `ansible_connection=local` for localhost, and the bogus `ENV=environments/dev` host line is gone.

### Collector API has no authentication

`roles/hw_collector/templates/hw_collector_app.py.j2` accepts unauthenticated POSTs on `0.0.0.0:{{ collector_port }}` and uses `primary_id` in a file path. Adding auth or path sanitizing would change the discovery protocol. Not done here.

### IPA image build

`build_ipa_image` defaults to false, so `setup_bastion.yml` does not rebuild the image. It also does not fall through into in-band probing; that runs only when `inband_discovery` is true. The image playbook calls `build-ipa.yml` directly. That task still deletes `~/.cache/ipa-build/ipa-hw-discovery*` before every build.

### Missing iPXE binaries do not fail the deploy

`deploy_airgap_bastion.yml` copies `ipxe.pxe` and `ipxe.efi` with `failed_when: false`. A missing file still ends the play as success. Change that only if every air-gap bundle is known to contain both binaries.

### Discovery script

`roles/hw_discovery/files/hardware-discovery.sh` was not copied by any task and hardcoded `192.168.1.185`. It was deleted. The image build uses the script embedded in `build-ipa.yml`. The unused `online_prep` role was deleted as well.

### In-band probe fallback now actually returns `unknown`

The live-probe shell tasks already ended with `|| echo "unknown"`. Without `pipefail`, `cut`/`awk` exit 0 on empty input, so the fallback never ran and the report got an empty string. They now use `set -o pipefail` under `/bin/bash`. A failed `efibootmgr` or microcode grep records `unknown`. This applies only when `inband_discovery` is true.

## Collection pin

`requirements.yml` pins `community.general` `11.4.10` (`requires_ansible: >=2.16.0`). The seed playbook downloads that file instead of an unpinned `community.general`, which currently resolves to a release that needs ansible-core >= 2.19.
