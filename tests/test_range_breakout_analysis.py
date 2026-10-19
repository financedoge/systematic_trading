"""Chronological research selection must not inspect its evaluation outcomes."""
import copy
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
spec = importlib.util.spec_from_file_location('range_analysis', ROOT/'scripts/analyze_range_breakout.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def evidence():
    result = {}
    for name in ('M1__monthly', 'Ladaptive-V1-H0__trading__monthly', 'Ladaptive-V1-H1__trading__monthly'):
        for scenario in ('c5d0', 'c10d0', 'c5d1'):
            result[name+'__'+scenario] = dict(control='M1__monthly', windows={
                'train2024': dict(sharpe=1.0 if name.startswith('M1') else 1.2,
                                  cagr=.08, max_drawdown=-.1, annual_turnover=2.),
                'evaluation': dict(sharpe=-100, cagr=-.9, max_drawdown=-.9)})
    return result


def test_selector_cannot_use_later_performance():
    original = evidence()
    changed = copy.deepcopy(original)
    for i, row in enumerate(changed.values()):
        row['windows']['evaluation'] = dict(sharpe=1e9*i, cagr=1e9*i, max_drawdown=0)
    assert analysis.select_year(original, 'trading', 2024) == analysis.select_year(changed, 'trading', 2024)


def test_isolated_success_cannot_satisfy_neighbor_guard():
    result = evidence()
    result['Ladaptive-V1-H1__trading__monthly__c5d1']['windows']['train2024']['sharpe'] = 0
    selected = analysis.select_year(result, 'trading', 2024)
    assert len(selected['passing']) == 1
    assert selected['selected'] == 'M1__monthly'


def test_extra_return_cannot_hide_excessive_drawdown():
    result = evidence()
    for key, row in result.items():
        if key.startswith('L'):
            row['windows']['train2024'].update(cagr=.99, max_drawdown=-.5)
    assert analysis.select_year(result, 'trading', 2024)['selected'] == 'M1__monthly'
