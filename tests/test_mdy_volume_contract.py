import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from qualify_mdy_volume_contract import available_activity, ratio_diagnostics


def test_fixed_scale_and_time_varying_coverage_are_distinct():
    assert ratio_diagnostics([.01,.01,.01])['p99_residual_after_median_scaling']==0
    assert ratio_diagnostics([.01,.01,.01])['median_relative_error_by_multiplier']['100']==0
    assert ratio_diagnostics([.1,.3,.6])['p99_residual_after_median_scaling']>.9


@pytest.mark.parametrize('values',[[],[1],[1,0],[1,float('nan')]])
def test_unsupported_ratios_fail(values):
    with pytest.raises(ValueError):
        ratio_diagnostics(values)


def test_close_cutoff_excludes_same_day_full_session_and_late_captures():
    cutoff='2025-02-28T16:00:00-05:00'
    valid=dict(session_end='2025-02-27T20:00:00-05:00',published_at='2025-02-28T08:00:00-05:00',
               captured_at='2025-02-28T08:01:00-05:00')
    assert available_activity(valid,cutoff)
    assert not available_activity(dict(valid,session_end='2025-02-28T20:00:00-05:00'),cutoff)
    assert not available_activity(dict(valid,captured_at='2026-11-07T08:01:00-05:00'),cutoff)
    assert not available_activity(dict(valid,published_at=None),cutoff)
    assert not available_activity(valid,'2025-02-28T16:00:00')
