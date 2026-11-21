#!/usr/bin/env python3
"""Receive hardware-discovery reports and write the next iPXE boot script.

The token, directories, and bind address come from the environment so this
file can be copied as-is and tested without Ansible templating.
"""
import errno
import hmac
import json
import os
import re
import tempfile

from flask import Flask, jsonify, request

PRIMARY_ID_RE = re.compile(r"[A-Za-z0-9._-]{1,64}\Z")


class RecordExists(Exception):
    """An exclusive create lost the race or the record was already there."""


def normalize_primary_id(value):
    """Return a lowercase id, or None when the id is not safe to store."""
    if not isinstance(value, str) or not value:
        return None
    if value[0] in ".-" or value.endswith("."):
        return None
    lowered = value.lower()
    if lowered.endswith(".json") or lowered.endswith(".ipxe"):
        return None
    if ".." in value or "/" in value or "\\" in value:
        return None
    if not PRIMARY_ID_RE.fullmatch(lowered):
        return None
    return lowered


def validate_primary_id(value):
    """Accept a single path segment. Reject traversal and absolute paths."""
    return normalize_primary_id(value) is not None


def bearer_matches(presented, token):
    """Constant-time compare. Non-ASCII headers are unauthorized, not errors."""
    if not isinstance(presented, str) or not isinstance(token, str):
        return False
    try:
        presented_b = presented.encode("ascii")
        expected_b = ("Bearer " + token).encode("ascii")
    except UnicodeEncodeError:
        return False
    return hmac.compare_digest(presented_b, expected_b)


def contained_output_path(root, primary_id, suffix):
    """Return a real path that stays inside root, or raise ValueError."""
    primary_id = normalize_primary_id(primary_id)
    if primary_id is None:
        raise ValueError("invalid primary_id")
    root_real = os.path.realpath(root)
    path = os.path.realpath(os.path.join(root_real, primary_id + suffix))
    if not path.startswith(root_real + os.sep):
        raise ValueError("path escapes collector directory")
    return path


def atomic_write(path, text, mode=0o644):
    """Replace path with text. A crash leaves the previous file in place."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
        os.chmod(path, mode)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def exclusive_create(path, text, mode):
    """Create path only if it does not exist. EEXIST becomes RecordExists."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        try:
            os.link(tmp, path)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                raise RecordExists() from exc
            raise
        os.chmod(path, mode)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def nextboot_script(primary_id, bastion_ip):
    """iPXE script written after a successful inventory post."""
    return (
        "#!ipxe\n"
        "echo ================================================\n"
        f"echo Hardware discovery complete for {primary_id}\n"
        "echo Booting OpenShift Installer (Air-Gapped)...\n"
        "echo ================================================\n"
        f"kernel http://{bastion_ip}/openshift/vmlinuz\n"
        f"initrd http://{bastion_ip}/openshift/initrd.img\n"
        "imgargs vmlinuz initrd=initrd.img "
        f"coreos.live.rootfs_url=http://{bastion_ip}/openshift/rootfs.img "
        "ip=dhcp rd.neednet=1 quiet\n"
        "boot\n"
    )


def create_app(
    inventory_dir,
    nextboot_dir,
    token,
    bastion_ip,
    max_body_bytes=1048576,
    overwrite_nextboot=False,
    enroll_token="",
):
    """Build the Flask app.

    token is the admin bearer. It can create and update.
    enroll_token can create a missing record and cannot overwrite or read one.
    """
    if not isinstance(token, str) or not token.strip():
        raise ValueError("collector token is empty")
    token = token.strip()
    enroll_token = (enroll_token or "").strip()
    if enroll_token and enroll_token == token:
        raise ValueError("enroll token must differ from the admin token")
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = int(max_body_bytes)

    @app.route("/api/inventory", methods=["POST"])
    def receive():
        presented = request.headers.get("Authorization", "")
        if bearer_matches(presented, token):
            role = "admin"
        elif enroll_token and bearer_matches(presented, enroll_token):
            role = "enroll"
        else:
            return jsonify({"status": "error", "message": "unauthorized"}), 401
        data = request.get_json(force=False, silent=True)
        if not isinstance(data, dict):
            return jsonify({"status": "error", "message": "JSON object required"}), 400
        primary_id = normalize_primary_id(data.get("primary_id"))
        if primary_id is None:
            return jsonify({"status": "error", "message": "invalid primary_id"}), 400
        data = dict(data)
        data["primary_id"] = primary_id
        try:
            inventory_path = contained_output_path(inventory_dir, primary_id, ".json")
            nextboot_path = contained_output_path(nextboot_dir, primary_id, ".ipxe")
        except ValueError:
            return jsonify({"status": "error", "message": "invalid primary_id"}), 400
        payload = json.dumps(data, indent=2) + "\n"
        script = nextboot_script(primary_id, bastion_ip)
        if role == "enroll":
            # Claim both names, or neither. A nextboot that already exists
            # must not leave a newly written inventory file behind.
            created_inventory = False
            try:
                exclusive_create(inventory_path, payload, 0o640)
                created_inventory = True
                exclusive_create(nextboot_path, script, 0o644)
            except RecordExists:
                if created_inventory:
                    try:
                        os.unlink(inventory_path)
                    except OSError:
                        pass
                return jsonify({"status": "error", "message": "record exists"}), 409
            nextboot_state = "written"
        else:
            atomic_write(inventory_path, payload, mode=0o640)
            if os.path.exists(nextboot_path) and not overwrite_nextboot:
                nextboot_state = "unchanged"
            else:
                atomic_write(nextboot_path, script)
                nextboot_state = "written"
        return (
            jsonify(
                {
                    "status": "ok",
                    "primary_id": primary_id,
                    "next": "openshift_installer",
                    "nextboot": nextboot_state,
                }
            ),
            200,
        )

    return app


def app_from_env():
    """Load runtime settings. Gunicorn imports collector_app:app."""
    with open(os.environ["COLLECTOR_TOKEN_FILE"], encoding="utf-8") as handle:
        token = handle.read()
    with open(os.environ["COLLECTOR_ENROLL_TOKEN_FILE"], encoding="utf-8") as handle:
        enroll_token = handle.read()
    overwrite = os.environ.get("COLLECTOR_OVERWRITE_NEXTBOOT", "false").lower() == "true"
    return create_app(
        inventory_dir=os.environ["COLLECTOR_INVENTORY_DIR"],
        nextboot_dir=os.environ["COLLECTOR_NEXTBOOT_DIR"],
        token=token,
        bastion_ip=os.environ["COLLECTOR_BASTION_IP"],
        max_body_bytes=os.environ.get("COLLECTOR_MAX_BODY_BYTES", "1048576"),
        overwrite_nextboot=overwrite,
        enroll_token=enroll_token,
    )


if os.environ.get("COLLECTOR_INVENTORY_DIR"):
    app = app_from_env()
