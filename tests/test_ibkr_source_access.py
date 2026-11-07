import importlib.util
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "ibkr_source_access", Path(__file__).resolve().parents[1] / "scripts/probe_ibkr_source_access.py"
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def test_recent_subscription_warning_does_not_negate_complete_old_history():
    result = probe.inspect_history(True, [{"date": "20250224"}], [{"code": 2188}])
    assert result["history_returned"]
    assert result["recent_api_subscription_warning"]


def test_actual_denial_empty_history_or_missing_end_are_not_success():
    assert not probe.inspect_history(True, [{}], [{"code": 162}])["history_returned"]
    assert not probe.inspect_history(True, [], [])["history_returned"]
    assert not probe.inspect_history(False, [{}], [])["history_returned"]
