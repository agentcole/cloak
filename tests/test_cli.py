"""CLI smoke tests for scan / mask / unmask."""

from __future__ import annotations

import importlib.util
import json

import pytest

from cloak.cli import main

_HAS_CRYPTO = importlib.util.find_spec("cryptography") is not None


def test_missing_input_file_is_clean_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["scan", str(tmp_path / "does-not-exist.txt"), "--detectors", "regex"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "cloak: error:" in err
    assert "Traceback" not in err


def test_missing_vault_is_clean_error(tmp_path, capsys):
    src = tmp_path / "m.txt"
    src.write_text("[EMAIL_1]")
    with pytest.raises(SystemExit) as exc:
        main(["unmask", str(src), "--vault", str(tmp_path / "nope.json")])
    assert exc.value.code == 2
    assert "cannot read vault" in capsys.readouterr().err


def test_scan_json(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text("mail a@b.com and ip 10.0.0.1")
    assert main(["scan", str(src), "--detectors", "regex", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    types = {e["type"] for e in data}
    assert {"EMAIL", "IP_ADDRESS"} <= types


def test_mask_unmask_roundtrip(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text("mail a@b.com")
    vault = tmp_path / "v.json"

    assert main(["mask", str(src), "--detectors", "regex", "--vault", str(vault)]) == 0
    masked = capsys.readouterr().out
    assert masked == "mail [EMAIL_1]"
    assert vault.exists()

    masked_file = tmp_path / "m.txt"
    masked_file.write_text(masked)
    assert main(["unmask", str(masked_file), "--vault", str(vault)]) == 0
    assert capsys.readouterr().out == "mail a@b.com"


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_encrypted_vault_roundtrip(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text("mail a@b.com")
    vault = tmp_path / "v.enc"
    pw = "hunter2"

    assert main(
        ["mask", str(src), "--detectors", "regex", "--vault", str(vault), "--password", pw]
    ) == 0
    masked = capsys.readouterr().out

    mfile = tmp_path / "m.txt"
    mfile.write_text(masked)
    assert main(["unmask", str(mfile), "--vault", str(vault), "--password", pw]) == 0
    assert capsys.readouterr().out == "mail a@b.com"
