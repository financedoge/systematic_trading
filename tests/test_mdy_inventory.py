import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from inventory_mdy_price_gaps import priority_group, summarize, valid


def test_complete_closes_cannot_stand_in_for_complete_raw_ohlcv():
    assert priority_group(False, True, True, True) == 'adjusted_window_raw_or_volume_missing'
    assert priority_group(False, False, True, True) == 'complete_comparison_candidate'
    assert priority_group(False, False, False, True) == 'partial_window_records'
    assert priority_group(False, False, False, False) == 'no_window_records'


@pytest.mark.parametrize('bad', [None, 0., -1., float('nan'), float('inf')])
def test_unknown_and_invalid_activity_cannot_pass(bad):
    assert not valid({'close':10.,'volume':bad}, ['close','volume'])


def test_scope_weights_keep_the_full_portfolio_denominator():
    group = [{'value_usd':'5.25'},{'value_usd':'4.75'}]
    assert summarize(group,Decimal('100')) == dict(count=2,value_usd='10.00',equity_pct=10.)
    assert summarize([],Decimal('100'))['equity_pct']==0.
