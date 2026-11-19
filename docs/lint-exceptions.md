# Lint exceptions and owner decisions

CI (`.github/workflows/ci.yml`) runs yamllint, `ansible-lint --profile production`,
`ansible-playbook --syntax-check` on every file under `playbooks/` and
`roles/*/tests/`, shellcheck on `*.sh`, and gitleaks. No job is skipped.

Production ansible-lint stays enabled. One rule is skipped because fixing it
would change deployed behavior. Everything else that failed the first production
run was fixed or given an inline `noqa` with a reason.

## Skipped ansible-lint rule

| Rule | Why it stays off |
| --- | --- |
| `var-naming[no-role-prefix]` | Role defaults are the public contract. `environments/dev/group_vars/all.yml`, playbook vars, and templates set `bastion_ip`, `collector_port`, `collector_dir`, `dhcp_*`, and `pxe_*` with no role prefix. Renaming them to `hw_discovery_` / `hw_collector_` / `online_prep_` would silently stop those overrides from applying. `var-naming[read-only]` is still enforced. |

`playbooks/hw_process_discovered.yml` used to set `inventory_dir`, which is a read-only Ansible variable. The play var is now `hardware_inventory_dir`. The path is still `/var/lib/hardware-inventory`.

## Inline noqa

`playbooks/seed_airgap_bundle.yml` packs the bundle with `tar -czf ... -C staging .` so the archive root is the staging contents (`rpm_packages/`, `ipxe_binaries/`, ...). `community.general.archive` does not preserve that layout, and `unarchive` only extracts. The task is marked `# noqa: command-instead-of-module`.

## Checks that are not clean, on purpose

These were not "fixed" by flipping a default. Each one needs an owner decision.

### PXE variables disagree, and only one file is loaded

`environments/dev/all.yml` and `environments/dev/group_vars/all.yml` set the same keys to different networks:

| Key | `environments/dev/all.yml` (not auto-loaded) | `environments/dev/group_vars/all.yml` (loaded) |
| --- | --- | --- |
| `pxe_subnet` | `192.168.50.0/24` | `192.168.1.0/24` |
| `pxe_dhcp_range` | `192.168.50.100,192.168.50.200` | `192.168.1.100,192.168.1.200` |
| `bastion_ip` | `ansible_default_ipv4` or `192.168.50.10` | `192.168.1.185` |
| `collector_dir` | `/var/lib/hardware-inventory` | `/opt/hw-collector` |

Inventory is `environments/dev/hosts`, so Ansible loads `environments/dev/group_vars/all.yml` only. `environments/dev/all.yml` is an ordinary file in that directory. Nothing in this change copies values from one file to the other.

Two related mismatches, also left as-is:

- DHCP templates use `dhcp_subnet`, `dhcp_range_start`, and `dhcp_range_end` from `roles/hw_discovery/defaults/main.yml` (`192.168.50.0/24`, `.100`–`.200`). They do not read `pxe_subnet` or `pxe_dhcp_range`, so the group_vars subnet does not drive DHCP.
- Group vars set `local_artifacts_dir`. The discovery role reads `offline_artifacts_dir`.
- `playbooks/build_and_deploy_discovery_image.yml` sets `bastion_ip` to the host's default IPv4 or `192.168.50.10`, which overrides group_vars for that play only.
- `roles/hw_discovery/files/hardware-discovery.sh` posts to `http://192.168.1.185:5000`. No playbook copies that file. The IPA element embedded in `roles/hw_discovery/tasks/build-ipa.yml` uses `{{ bastion_ip }}` and `{{ collector_port }}`.

### GPG verification is still disabled for air-gap RPMs

`playbooks/deploy_airgap_bastion.yml` installs local RPMs with `disable_gpg_check: "{{ airgap_disable_gpg_check | bool }}"`. The default is still `true`. Turn it off only after the bastion has the keys that signed the packages downloaded on the online host:

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

`online_prep` honors `ipxe_pxe_checksum` the same way. It still downloads only `ipxe.pxe`, not the EFI binary the seed playbook downloads. No playbook includes the `online_prep` role; `playbooks/seed_airgap_bundle.yml` is the wired seeding entrypoint. The role's collection download uses `playbook_dir/../requirements.yml`, which is the repo root when the playbook lives in `playbooks/`.

### Hardcoded path, not a credential

`seed_airgap_bundle.yml` still defaults `staging_dir` to `/home/dstratfo/airgap_shipment`. Override with `-e seed_staging_dir=...`. No passwords, tokens, or API keys are committed. gitleaks covers that in CI.

`ansible.cfg` sets `host_key_checking = False`. Left unchanged. The discovery plays are localhost, but `hw_process_discovered.yml` does not force `connection: local`.

### Collector API has no authentication

`roles/hw_collector/templates/hw_collector_app.py.j2` accepts unauthenticated POSTs on `0.0.0.0:{{ collector_port }}` and uses `primary_id` in a file path. Adding auth or path sanitizing would change the discovery protocol. Not done here.

### IPA image rebuilds whenever the discovery role runs

`roles/hw_discovery/tasks/main.yml` includes `build-ipa.yml` when `build_ipa_image` is true, and that default is `true`. `playbooks/setup_bastion.yml` therefore deletes previous IPA artifacts and rebuilds the image. `changed_when: true` on the builder records that the task is not a no-op. Set `-e build_ipa_image=false` to configure services without rebuilding. The default was not changed.

`build-ipa.yml` also deletes `~/.cache/ipa-build/ipa-hw-discovery*` before every build, so that task cannot be idempotent.

### Missing iPXE binaries do not fail the deploy

`deploy_airgap_bastion.yml` copies `ipxe.pxe` and `ipxe.efi` with `failed_when: false`. A missing file still ends the play as success. Change that only if every air-gap bundle is known to contain both binaries.

### BMC values in `hardware-discovery.sh` do not reach the generated script

The script collects `BMC_*` metrics, then writes `/usr/local/bin/hardware-discovery` from a quoted heredoc (`<<'SCRIPT'`). The quoted heredoc does not expand those variables, so the generated script's BMC fields stay empty. The values are exported so shellcheck can see they are intentional. They are not substituted into the heredoc. No playbook invokes this file; the image build uses the script embedded in `build-ipa.yml`.

### In-band probe fallback now actually returns `unknown`

The live-probe shell tasks already ended with `|| echo "unknown"`. Without `pipefail`, `cut`/`awk` exit 0 on empty input, so the fallback never ran and the report got an empty string. They now use `set -o pipefail` under `/bin/bash`. A failed `efibootmgr` or microcode grep records `unknown`. This applies only when `build_ipa_image` is false.

## Collection pin

`requirements.yml` pins `community.general` `11.4.10` (`requires_ansible: >=2.16.0`). The seed playbook and `online_prep` download that file instead of an unpinned `community.general`, which currently resolves to a release that needs ansible-core >= 2.19.
