import hashlib
from pathlib import Path

import pytest

from systematic_trading.lean.contracts import sha256


@pytest.mark.parametrize("size", [0, 1, 262143, 262144, 262145, 1048583])
def test_streamed_verification_preserves_exact_hash_without_full_read(tmp_path, monkeypatch, size):
    path = tmp_path / "input.bin"
    data = (bytes(range(256)) * (size // 256 + 1))[:size]
    path.write_bytes(data)
    monkeypatch.setattr(Path, "read_bytes", lambda self: pytest.fail("Verification must stream files"))
    assert sha256(path) == hashlib.sha256(data).hexdigest()
