"""Recorder tools must use the same machine-local storage policy as the API."""

import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize("script,arguments", [
    ("record_ib_market_data", []),
    ("catalog_market_data_raw", []),
    ("replay_market_data_raw", ["--date", "2026-09-25", "--symbol", "SPY"]),
])
@pytest.mark.parametrize("explicit_override", [False, True])
def test_recorder_tools_respect_storage_configuration(script, arguments, explicit_override, tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(script, Path("scripts") / f"{script}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    configured = tmp_path / "machine-storage.json"
    override = tmp_path / "override-storage.json"
    monkeypatch.setenv("ST_MARKET_DATA_STORAGE_POLICY_PATH", str(configured))
    selected = []

    class PolicySelected(Exception):
        pass

    def capture_policy(path):
        selected.append(path)
        raise PolicySelected

    # Stop at policy loading, before any database, file recording or broker access.
    monkeypatch.setattr(module, "load_storage_policy", capture_policy)
    args = arguments + (["--storage-policy", str(override)] if explicit_override else [])
    with pytest.raises(PolicySelected):
        module.main(args)
    assert selected == [override if explicit_override else configured]
