"""Security checks for the hardware collector."""
import importlib.util
import json
import os
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "files" / "collector_app.py"
SPEC = importlib.util.spec_from_file_location("collector_app", MODULE_PATH)
collector_app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector_app)


def _app(tmp_path, token="test-token", overwrite=False, max_body=1048576, enroll_token="enroll-token"):
    inventory = tmp_path / "inventory"
    nextboot = tmp_path / "nextboot"
    inventory.mkdir(exist_ok=True)
    nextboot.mkdir(exist_ok=True)
    return collector_app.create_app(
        str(inventory),
        str(nextboot),
        token,
        "192.0.2.10",
        max_body_bytes=max_body,
        overwrite_nextboot=overwrite,
        enroll_token=enroll_token,
    ).test_client()


def _post(client, primary_id, token="test-token", payload=None):
    body = {"primary_id": primary_id, "serial_number": "abc"}
    if payload is not None:
        body = payload
    return client.post(
        "/api/inventory",
        data=json.dumps(body),
        content_type="application/json",
        headers={"Authorization": f"Bearer {token}"},
    )


def test_rejects_missing_and_wrong_token(tmp_path):
    client = _app(tmp_path)
    missing = client.post(
        "/api/inventory",
        data=json.dumps({"primary_id": "node1"}),
        content_type="application/json",
    )
    assert missing.status_code == 401
    wrong = _post(client, "node1", token="other")
    assert wrong.status_code == 401
    assert not (tmp_path / "inventory" / "node1.json").exists()


def test_rejects_non_object_json(tmp_path):
    client = _app(tmp_path)
    response = client.post(
        "/api/inventory",
        data=json.dumps(["not", "an", "object"]),
        content_type="application/json",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 400


def test_rejects_path_traversal_and_absolute_ids(tmp_path):
    client = _app(tmp_path)
    for primary_id in ("../../../tmp/pwn", "..", ".", ".hidden", "-node", "/etc/evil", "foo/bar", "a\\b"):
        response = _post(client, primary_id)
        assert response.status_code == 400, primary_id
    assert list((tmp_path / "inventory").iterdir()) == []
    assert not Path("/tmp/pwn.json").exists()


def test_valid_id_stays_inside_the_inventory_directory(tmp_path):
    client = _app(tmp_path)
    response = _post(client, "NODE_1.abc")
    assert response.status_code == 200
    inventory_file = tmp_path / "inventory" / "NODE_1.abc.json"
    nextboot_file = tmp_path / "nextboot" / "NODE_1.abc.ipxe"
    assert inventory_file.is_file()
    assert nextboot_file.is_file()
    saved = json.loads(inventory_file.read_text())
    assert saved["primary_id"] == "NODE_1.abc"
    assert "192.0.2.10" in nextboot_file.read_text()
    assert os.path.realpath(inventory_file).startswith(os.path.realpath(tmp_path / "inventory") + os.sep)
    assert (inventory_file.stat().st_mode & 0o777) == 0o640


def test_existing_nextboot_is_kept_unless_overwrite_is_set(tmp_path):
    client = _app(tmp_path)
    assert _post(client, "node1").status_code == 200
    nextboot = tmp_path / "nextboot" / "node1.ipxe"
    nextboot.write_text("#!ipxe\necho kept\n")
    again = _post(client, "node1")
    assert again.status_code == 200
    assert again.get_json()["nextboot"] == "unchanged"
    assert nextboot.read_text() == "#!ipxe\necho kept\n"
    replacing = _app(tmp_path, overwrite=True)
    replaced = _post(replacing, "node1")
    assert replaced.get_json()["nextboot"] == "written"
    assert "kept" not in nextboot.read_text()


def test_request_body_cap(tmp_path):
    client = _app(tmp_path, max_body=64)
    response = client.post(
        "/api/inventory",
        data=b"{" + b"x" * 200,
        content_type="application/json",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 413


def test_enroll_token_can_create_but_not_overwrite(tmp_path):
    client = _app(tmp_path)
    created = _post(client, "node1", token="enroll-token")
    assert created.status_code == 200
    inventory = tmp_path / "inventory" / "node1.json"
    nextboot = tmp_path / "nextboot" / "node1.ipxe"
    original_inventory = inventory.read_text()
    original_nextboot = nextboot.read_text()
    again = _post(
        client,
        "node1",
        token="enroll-token",
        payload={"primary_id": "node1", "serial_number": "changed"},
    )
    assert again.status_code == 409
    assert again.get_json() == {"status": "error", "message": "record exists"}
    assert inventory.read_text() == original_inventory
    assert nextboot.read_text() == original_nextboot
    assert "changed" not in again.get_data(as_text=True)


def test_non_ascii_authorization_is_unauthorized(tmp_path):
    client = _app(tmp_path)
    response = client.post(
        "/api/inventory",
        data=json.dumps({"primary_id": "node1"}),
        content_type="application/json",
        headers={"Authorization": "Bearer töken"},
    )
    assert response.status_code == 401
    assert not (tmp_path / "inventory" / "node1.json").exists()


def test_validate_primary_id_helper():
    assert collector_app.validate_primary_id("abc-DEF.1")
    assert not collector_app.validate_primary_id("../../../tmp/pwn")
    assert not collector_app.validate_primary_id("..")
    assert not collector_app.validate_primary_id(".hidden")
    assert not collector_app.validate_primary_id("-node")
    assert not collector_app.validate_primary_id(None)


def test_contained_output_path_rejects_escape(tmp_path):
    with pytest.raises(ValueError):
        collector_app.contained_output_path(tmp_path, "../../../tmp/pwn", ".json")
