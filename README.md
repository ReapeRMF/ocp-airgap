# Bare-Metal Hardware Discovery & Telemetry Pipeline (Air-Gapped)

This repository automates the deployment of a stateless, lightweight hardware discovery infrastructure on an air-gapped bastion host. It compiles a custom **CentOS Stream 9 Ironic Python Agent (IPA)** RAMdisk, serves it over PXE/iPXE, collects hardware telemetry, and automatically configures target nodes for next-stage operating system installations.

## Core Architecture

1. **PXE/iPXE Boot:** Bare-metal target machines boot via DHCP/TFTP and retrieve an iPXE boot menu.
2. **Stateless RAMdisk:** The target boots the custom-compiled CentOS Stream 9 IPA image (`/discovery/vmlinuz` and `initrd.img`).
3. **Telemetry Gathering:** At boot, `hw-discovery.sh` executes local probes (CPU microcode, UEFI boot sequence, detailed disk/NIC telemetry).
4. **Data Ingestion:** The telemetry is POSTed to the multi-worker Gunicorn/Flask receiver on the Bastion.
5. **Next-Boot Stage:** The receiver dumps the hardware profile to `/var/lib/hardware-inventory/` and automatically writes the next boot payload (e.g., OpenShift) in `/var/lib/pxe-nextboot/`.

---

## Lifecycle Playbooks

### Step 1: Seeding (Online Workstation)
Run the seeding playbook on an internet-connected workstation to pre-cache all required system packages, Python wheels, and Ansible collections:
```bash
ansible-playbook playbooks/seed_airgap_bundle.yml
```
*This generates the `airgap_bundle.tar.gz` archive.*

### Step 2: Deployment (Offline Bastion)
Copy the tarball to your air-gapped bastion, extract it, and run the offline setup playbooks:
```bash
# 1. Install baseline offline system structures
ansible-playbook playbooks/deploy_airgap_bastion.yml

# 2. Configure baseline network infrastructure (DHCP, TFTP, Apache, Gunicorn App)
ansible-playbook -i environments/dev/hosts playbooks/setup_bastion.yml --ask-become-pass
```

### Step 3: Image Compilation (CentOS Stream 9 IPA)
Build the lightweight discovery ramdisk image and deploy it directly to the web server directory:
```bash
ansible-playbook -i environments/dev/hosts playbooks/build_and_deploy_discovery_image.yml --ask-become-pass
```

---

## Administrative Utilities

### View Discovered Hardware Profiles
Captured nodes register under `/var/lib/hardware-inventory/<PRIMARY_ID>.json` with deep metrics, including UEFI NVRAM variables and CPU microcode. You can view a fast terminal summary of discovered systems by running:
```bash
ansible-playbook -i environments/dev/hosts playbooks/hw_process_discovered.yml
```
