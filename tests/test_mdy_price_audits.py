from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from diagnose_mdy_price_audits import CHECK_FIELDS, comparison


def bar(day, adjusted, raw=10):
    return {**dict.fromkeys(CHECK_FIELDS, raw), 'trade_date':day, 'adjusted_close':adjusted}


def test_constant_adjustment_scale_does_not_change_adjacent_returns():
    old = [bar('2024-12-30',10), bar('2024-12-31',12)]
    new = [bar('2024-12-30',5), bar('2024-12-31',6)]
    result = comparison(new,old)
    assert result['adjusted_close_median_ratio'] == .5
    assert result['raw_close'] == {'comparable':2, 'identical':2}
    assert result['max_adjacent_adjusted_log_return_difference_bp'] == pytest.approx(0)


def test_absent_raw_or_disjoint_dates_cannot_be_counted_as_matches():
    old = [bar('2020-04-01',10,raw=None)]
    new = [bar('2020-04-01',10), bar('2024-12-31',60)]
    result = comparison(new,old)
    assert result['sessions'] == 1
    assert result['raw_volume'] == {'comparable':0,'identical':0}
    assert result['max_adjacent_adjusted_log_return_difference_bp'] is None
    assert comparison(new[1:],old) == {'sessions':0}
