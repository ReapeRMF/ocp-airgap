# hw_collector role

This role installs and configures the service that receives hardware inventory reports from machines that have booted the discovery image.

Reports are saved as JSON files named after the machine's MAC address in `/var/lib/hardware-inventory/` (or the directory configured in defaults).

## Current implementation

- Creates a system user and group for the collector.
- Sets up a Python virtual environment.
- Installs gunicorn and a small Flask application that listens for POST requests on `/api/inventory`.
- Deploys a systemd service that runs the collector under gunicorn.
- The collector writes each incoming report to disk. No database is used at this stage.

## Why gunicorn

Gunicorn is used to run the collector application. It provides proper process management and multiple worker processes. The role installs gunicorn and configures the systemd service to start the collector under it.

## Variables

See `defaults/main.yml`. The main values you may want to change are:

- `collector_port` — TCP port the collector listens on (default 5000)
- `collector_dir` — base directory for the collector code and reports

## How reports are used

After a machine finishes discovery it sends a JSON blob. The collector saves it. Operators (or later automation) can then read these files with `show-hw-summary --latest` or by looking directly in the reports directory.

This role only receives and stores reports. It does not yet contain logic to decide what the machine should do next (that logic belongs in a separate watcher or in future updates to this role).
