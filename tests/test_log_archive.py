import gzip
import hashlib
import json
import os
import time

import pytest

from systematic_trading.maintenance import log_archive


def old_log(tmp_path, name="worker-20260101.log"):
    path = tmp_path / name
    path.write_bytes(b"old record\n" * 100)
    os.utime(path, (time.time() - 8 * 86400,) * 2)
    return path


def test_closed_log_compresses_losslessly_with_durable_receipt(tmp_path):
    path = old_log(tmp_path)
    original = path.read_bytes()
    result = log_archive.archive_log(tmp_path, path.name)
    assert not path.exists()
    assert result["source_removed"]
    assert gzip.decompress(open(result["archive"], "rb").read()) == original
    assert result["source_sha256"] == hashlib.sha256(original).hexdigest()
    assert json.loads(open(result["archive"] + ".json").read()) == result


@pytest.mark.parametrize("name", ["../worker-20260101.log", "platform_operations.jsonl", "operator_dashboard.err.log"])
def test_unsafe_or_active_names_are_rejected(tmp_path, name):
    old_log(tmp_path)
    if "/" not in name:
        old_log(tmp_path, name)
    with pytest.raises(ValueError):
        log_archive.archive_log(tmp_path, name)


def test_recent_closed_log_is_retained(tmp_path):
    path = tmp_path / "worker-20260101.log"
    path.write_text("recent")
    with pytest.raises(ValueError, match="seven days"):
        log_archive.archive_log(tmp_path, path.name)
    assert path.read_text() == "recent"


def test_changed_source_is_never_removed(tmp_path, monkeypatch):
    path = old_log(tmp_path)
    original_hash = log_archive.file_hash
    def changed(source):
        if source == path:
            with source.open("ab") as stream:
                stream.write(b"late append")
        return original_hash(source)
    monkeypatch.setattr(log_archive, "file_hash", changed)
    with pytest.raises(ValueError, match="mismatch|changed"):
        log_archive.archive_log(tmp_path, path.name)
    assert path.read_bytes().endswith(b"late append")


@pytest.mark.skipif(os.name != "nt", reason="Windows file-sharing contract")
def test_rotation_refuses_open_writer_and_preserves_new_append(tmp_path):
    path = tmp_path / "platform_operations.jsonl"
    path.write_bytes(b"old\n")
    with path.open("a"):
        with pytest.raises(PermissionError):
            log_archive.archive_log(tmp_path, path.name, rotate=True)
    result = log_archive.archive_log(tmp_path, path.name, rotate=True)
    with path.open("ab") as stream:
        stream.write(b"new\n")
    assert path.read_bytes() == b"new\n"
    assert gzip.decompress(open(result["archive"], "rb").read()) == b"old\n"
