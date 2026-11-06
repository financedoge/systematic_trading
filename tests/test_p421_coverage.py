from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from assess_constituent_coverage import decisions, parse_value, upper_bound


def test_uncertified_and_unmatched_positions_stay_in_denominator():
    catalog={'A':{'status':'audited_with_limitations'},'B':{'status':'review'}}
    result=upper_bound([('A',8),('B',90),(None,2)],catalog)
    assert result['name_fraction']==pytest.approx(1/3)
    assert result['value_fraction']==.08
    assert upper_bound([('A',8),(None,None)],catalog)['value_fraction'] is None


def test_missing_or_nonfinite_value_is_unknown():
    assert parse_value('10,500.75')==10500.75
    for val in ('-',None,'NaN','Infinity'):
        assert parse_value(val) is None


def test_monthly_coverage_uses_prior_actual_session_close():
    dates=dict(decisions())
    assert len(dates)==71
    assert dates['2021-01-04'].isoformat()=='2020-12-31T16:00:00-05:00'
    assert dates['2026-11-02'].isoformat()=='2026-10-30T16:00:00-04:00'
