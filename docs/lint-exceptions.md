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

No task ever rendered `dhcpd.conf.j2` or `dnsmasq.conf.j2`, so this repository does not serve DHCP. Those templates, the pxelinux template, and the dnsmasq/dhcpd handlers were removed. `pxe_subnet` is used: the collector firewalld rule allows `collector_port`/tcp only from that subnet, and the httpd `/ipxe` location uses the same limit. `pxe_dhcp_range` remains the lab network record and is not applied to a DHCP daemon. `local_artifacts_dir` was renamed to `offline_artifacts_dir`. The path is still `/opt/offline-artifacts-x86_64`.

`playbooks/build_and_deploy_discovery_image.yml` does not set `bastion_ip`. The image and the collector use the inventory value.

### GPG verification and iPXE checksums

`airgap_disable_gpg_check` defaults to `false`. The seed playbook ships only RPM signing keys whose fingerprints are listed in `vars/rpm_gpg_keys.yml`. iPXE downloads require the checksums in `vars/ipxe_checksums.yml` unless `-e allow_unverified_ipxe=true`. The bastion deploy fails if `ipxe.pxe` or `ipxe.efi` is missing. Details are in `docs/security.md`.

### Hardcoded path, not a credential

`seed_airgap_bundle.yml` still defaults `staging_dir` to `/home/dstratfo/airgap_shipment`. Override with `-e seed_staging_dir=...`. No passwords, tokens, or API keys are committed. gitleaks covers that in CI.

`ansible.cfg` sets `host_key_checking = False`. `environments/dev/hosts` sets `ansible_connection=local` for localhost, and the bogus `ENV=environments/dev` host line is gone.

### Collector authentication

The collector requires a bearer token, rejects path traversal in `primary_id`, binds to `bastion_ip`, and limits the port with firewalld. See `docs/security.md`.

### IPA image build

`build_ipa_image` defaults to false, so `setup_bastion.yml` does not rebuild the image. It also does not fall through into in-band probing; that runs only when `inband_discovery` is true. The image playbook calls `build-ipa.yml` directly. That task still deletes `~/.cache/ipa-build/ipa-hw-discovery*` before every build.

### Missing iPXE binaries fail the deploy

`deploy_airgap_bastion.yml` stats `ipxe.pxe` and `ipxe.efi` and asserts that both exist before copying them.

### Discovery script

`roles/hw_discovery/files/hardware-discovery.sh` was not copied by any task and hardcoded `192.168.1.185`. It was deleted. The image build uses the script embedded in `build-ipa.yml`. The unused `online_prep` role was deleted as well.

### In-band probe fallback now actually returns `unknown`

The live-probe shell tasks already ended with `|| echo "unknown"`. Without `pipefail`, `cut`/`awk` exit 0 on empty input, so the fallback never ran and the report got an empty string. They now use `set -o pipefail` under `/bin/bash`. A failed `efibootmgr` or microcode grep records `unknown`. This applies only when `inband_discovery` is true.

## Collection pin

`requirements.yml` pins `community.general` `11.4.10` (`requires_ansible: >=2.16.0`). The seed playbook downloads that file instead of an unpinned `community.general`, which currently resolves to a release that needs ansible-core >= 2.19.
