"""Direct-minute diagnostics reject incomplete, changed and out-of-scope evidence."""
import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("fix_minute_diagnostic", SCRIPTS / "inspect_fix_minute_gaps.py")
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)
sys.path.pop(0)


@pytest.fixture
def case(monkeypatch):
    p = source.protocol()
    monkeypatch.setattr(source.transport, "protocol", lambda: p)
    return p["cases"][0]


def payload(case, **updates):
    row = dict(t=case["start"], i=1, x="N", z="A", c=[" "], p=100, s=3)
    row.update(updates)
    return dict(symbol="FIX", trades=[row], next_page_token=None)


def test_minute_bounds_include_last_nanosecond_but_not_next_minute(case):
    data = payload(case, t=case["end"])
    assert source.validate_minute(data, case) == data["trades"]
    with pytest.raises(ValueError, match="outside the declared minute"):
        source.validate_minute(payload(case, t="2025-02-07T15:54:00Z"), case)
    with pytest.raises(ValueError):
        source.validate_minute(payload(case, t="2025-02-07T15:52:59.999999999Z"), case)


@pytest.mark.parametrize("token", ["next", "", 0])
def test_short_minute_response_requires_explicit_terminal_token(case, token):
    data = payload(case)
    data["next_page_token"] = token
    with pytest.raises(ValueError, match="not terminal"):
        source.validate_minute(data, case)
    del data["next_page_token"]
    with pytest.raises(ValueError, match="not terminal"):
        source.validate_minute(data, case)


def test_minute_keeps_original_identity_and_duplicate_guards(case):
    with pytest.raises(ValueError, match="tape"):
        source.validate_minute(payload(case, z="C"), case)
    data = payload(case)
    data["trades"] *= 2
    with pytest.raises(ValueError, match="repeated trade"):
        source.validate_minute(data, case)


def test_original_manifest_changes_and_missing_source_are_rejected(tmp_path):
    sources = []
    for provider in ("alpaca", "ibkr"):
        root = tmp_path / provider / "capture"
        root.mkdir(parents=True)
        raw = b'{"retained":true}'
        (root / "manifest.json").write_bytes(raw)
        sources.append(dict(archive=str(root), manifest_sha256=source.sha(raw)))
    prior = dict(sources=sources)
    assert set(source.source_roots(prior)) == {"alpaca", "ibkr"}
    with pytest.raises(ValueError, match="Both"):
        source.source_roots(dict(sources=sources[:1]))
    with pytest.raises(ValueError, match="repeated"):
        source.source_roots(dict(sources=[sources[0], sources[0]]))
    (Path(sources[1]["archive"]) / "manifest.json").write_bytes(b'{}')
    with pytest.raises(ValueError, match="Changed"):
        source.source_roots(prior)
