"""Dated fund mapping cannot fall back to a current or ambiguous portfolio."""
import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
SPEC=importlib.util.spec_from_file_location('holdings_coverage',SCRIPTS/'capture_wrds_holdings_coverage.py')
source=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)
sys.path.pop(0)


@pytest.mark.parametrize('value',[None,0,-1,1.5,'NaN','Infinity'])
def test_invalid_permanent_identifiers_fail(value):
    with pytest.raises((ValueError, ArithmeticError)):
        source.identifiers([dict(id=value)],'id',10)


def test_mapping_uses_both_dated_intervals_and_unique_etf_class():
    names=[dict(ticker='MDY',et_flag='F',crsp_fundno=1,chgdt='2020-01-01',chgenddt='2025-01-01')]
    maps=[dict(crsp_fundno=1,crsp_portno=2,begdt='2024-01-01',enddt='2024-12-31')]
    assert source.detail_portfolio(names,maps,'MDY','2024-12-31')==2
    for changed_names,changed_maps in [(names,maps*2),(names,[]),
        ([dict(names[0],et_flag='N')],maps),([dict(names[0],chgdt='2025-01-01')],maps),
        (names,[dict(maps[0],enddt='2024-12-30')])]:
        with pytest.raises(ValueError,match='Ambiguous'):
            source.detail_portfolio(changed_names,changed_maps,'MDY','2024-12-31')
