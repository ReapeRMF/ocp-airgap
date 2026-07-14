Multi-Phase Air-Gapped Bastion Lifecycle Guide

This runbook details the end-to-end process for bundling infrastructure assets, manually verifying target host filesystem execution constraints, and running the native offline deployment pipeline.

                                [ ONLINE WORKSTATION ]
                                          │
                        1. Seed: Run playbooks/seed_airgap_bundle.yml
                                          │
                                          ▼
                             [ airgap_bundle.tar.gz ]
                                          │
                         2. Transport via USB / Sneakernet
                                          │
                                          ▼
                               [ AIR-GAPPED HARDWARE ]
                                          │
                        3. Unpack to an Executable Partition
                                          │
                                          ▼
                        4. Verify & Deploy: Run ansible-playbook


Phase 1: Online Payload Seeding (Workstation)

Navigate to your project directory and explicitly isolate your Ansible environment:

cd ~/ansible
export ANSIBLE_CONFIG="$HOME/ansible/ansible.cfg"


Compile your dynamic shipment payload archive:

ansible-playbook playbooks/seed_airgap_bundle.yml


Confirm the payload airgap_bundle.tar.gz (~120MB) exists in the repository root before transferring it over the physical air-gap.

Phase 2: Manual Target Host Pre-Flight Audits

Before extraction, you must verify that your intended staging partition does not enforce noexec restrictions. If it does, Ansible will bail mid-run during virtualenv compilation.

Step 2.1: Audit the partition mount flags

mount | grep -E '/var|/tmp|/opt'


Look for noexec within the parenthesis block. If present, the OS will block the deployment.

Step 2.2: Run a definitive live execution test

TARGET_DIR="/var/tmp/airgap_payload"
mkdir -p "$TARGET_DIR"
echo -e '#!/bin/bash\necho "EXEC_OK"' > "$TARGET_DIR/.test.sh" && chmod +x "$TARGET_DIR/.test.sh"
"$TARGET_DIR/.test.sh"


If it prints EXEC_OK: The partition is safe. Proceed to Scenario A bundle extraction.

If it prints Permission denied: The partition is blocked. You MUST use Scenario B.

Phase 3: Extraction & Native Deployment

Step 3.1: Initialize the target environment

cd ~/ansible
export ANSIBLE_CONFIG="$HOME/ansible/ansible.cfg"


Step 3.2: Unpack the payload based on your Phase 2 results

Scenario A: Standard Executable mounts

mkdir -p ~/ansible/airgap_payload
tar -xzvf ./airgap_bundle.tar.gz -C ~/ansible/airgap_payload


Scenario B: Hardened mounts (Home Fallback)

mkdir -p ~/airgap_payload
tar -xzvf ./airgap_bundle.tar.gz -C ~/airgap_payload


Step 3.3: Launch the native deployment playbook

If you used Scenario A (repo-relative):

ansible-playbook playbooks/deploy_airgap_bastion.yml


If you used Scenario B (hardened override):

ansible-playbook playbooks/deploy_airgap_bastion.yml -e "airgap_staging_dir=$HOME/airgap_payload"


Phase 4: Post-Deployment Health Checks

Run these to verify that the air-gapped network offline engines are fully active:

# 1. Verify the telemetry hardware collector daemon
systemctl status hw_collector.service

# 2. Verify the local DHCP provisioning engine
systemctl status dhcpd.service

# 3. Confirm the HTTPD engine is serving iPXE binaries offline
curl -I http://localhost/ipxe/boot.ipxe


Phase 5: Manual In-Band IPMI Validation (Target Discovery Node)

If a discovery target host initializes but its out-of-band management endpoints fail to populate within the database report, verify the local host driver communication layer using these standard utilities:

# 1. Confirm that the operating system kernel successfully registers the local KCS interface
lsmod | grep ipmi

# 2. Query the active BMC hardware map to ensure channel configuration is readable
ipmitool lan print 1

# 3. Trace hardware system errors directly from the hardware event registers
ipmitool sel list

