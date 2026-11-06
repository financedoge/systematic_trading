import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from acquire_mdy_ibkr_history import completed_status
from reconcile_mdy_ibkr_history import compare, indexed_bars


def bar(day, close=10, volume=50):
    return dict(date=day, open=close, high=close, low=close, close=close, volume=volume)


def test_warning_cannot_replace_completion_or_hide_real_error():
    assert completed_status(True, [{'code':2188}]) == 'complete'
    assert completed_status(False, [{'code':2188}]) == 'review'
    assert completed_status(True, [{'code':2188}, {'code':162}]) == 'review'


@pytest.mark.parametrize('rows', [[], [bar('20240227'),bar('20240227')],
                                 [bar('20240227',volume=0)], [bar('20240227',close=float('nan'))],
                                 [dict(bar('20240227'),high=9)]])
def test_missing_duplicate_and_invalid_observations_fail(rows):
    with pytest.raises(ValueError):
        indexed_bars(rows, ['2024-02-27'])


def test_vintage_scale_cancels_in_returns_but_volume_is_not_rescaled():
    days=['2024-02-27','2024-02-28']
    raw=[bar('20240227',10),bar('20240228',11)]
    adjusted=[bar('20240227',5),bar('20240228',5.5)]
    pub=[dict(trade_date=d,raw_open=c,raw_high=c,raw_low=c,raw_close=c,
              adjusted_close=c*.9,raw_volume=100) for d,c in zip(days,[10,11])]
    result=compare(raw,adjusted,pub,days)
    assert result['close_within_half_cent']==2
    assert result['max_adjusted_return_difference_bp'] < 1e-10
    assert result['volume_ratio_median']==.5
    assert result['volume_exact_matches']==0
    assert result['details'][0]['broker_volume_as_returned']==50
