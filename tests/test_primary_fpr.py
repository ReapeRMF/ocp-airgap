"""The RPM fingerprint awk must ignore subkeys."""
import os
import subprocess
from pathlib import Path

AWK = Path(__file__).resolve().parents[1] / "scripts" / "primary-fpr.awk"


def _gpg(gnupg, *args, stdout=subprocess.PIPE):
    env = os.environ.copy()
    env["GNUPGHOME"] = str(gnupg)
    return subprocess.run(
        ["gpg", "--batch", "--pinentry-mode", "loopback", "--passphrase", "", *args],
        check=True,
        env=env,
        stdout=stdout,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_primary_fpr_ignores_encryption_subkey(tmp_path):
    gnupg = tmp_path / "gnupg"
    gnupg.mkdir(mode=0o700)
    _gpg(
        gnupg,
        "--quick-generate-key",
        "Bundle Test <bundle@example.com>",
        "ed25519",
        "cert",
    )
    primary = _gpg(gnupg, "--list-keys", "--with-colons", "bundle@example.com")
    primary_fpr = next(
        line.split(":")[9]
        for line in primary.stdout.splitlines()
        if line.startswith("fpr:")
    )
    _gpg(gnupg, "--quick-add-key", primary_fpr, "cv25519", "encr")
    exported = tmp_path / "key.asc"
    with exported.open("w", encoding="utf-8") as handle:
        _gpg(gnupg, "--armor", "--export", "bundle@example.com", stdout=handle)
    shown = _gpg(
        gnupg,
        "--with-colons",
        "--import-options",
        "show-only",
        "--import",
        str(exported),
    )
    all_fprs = [
        line.split(":")[9].upper()
        for line in shown.stdout.splitlines()
        if line.startswith("fpr:")
    ]
    primary = subprocess.run(
        ["awk", "-f", str(AWK)],
        input=shown.stdout,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.split()
    assert len(all_fprs) >= 2
    assert primary == [all_fprs[0]]
    assert primary[0] not in all_fprs[1:]
