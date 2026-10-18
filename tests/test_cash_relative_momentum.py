"""Cash-relative hypothesis and unchanged-control isolation."""
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest

SCRIPTS = Path(__file__).parents[1]/'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('cash_relative', SCRIPTS/'run_cash_relative_momentum.py')
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)
base_spec = importlib.util.spec_from_file_location('screen_base', SCRIPTS/'run_class_volatility_screen.py')
base = importlib.util.module_from_spec(base_spec)
base_spec.loader.exec_module(base)


def build(momentum, volatility, arm='pooled_cash_relative_risk'):
    symbols = sorted(momentum)
    p = dict(arms=[arm], overlap_parents={})
    return study.candidate_targets(base.build_targets, symbols,
        [momentum[s] for s in symbols], [volatility[s] for s in symbols],
        symbols, {s: s for s in symbols}, {s: s for s in symbols}, p, arm)


@pytest.mark.parametrize('arm', ['pooled_remove_bill_risk', 'class_remove_bill_risk',
                                 'pooled_cash_relative_risk', 'class_cash_relative_risk'])
def test_bills_never_compete_or_receive_an_allocation(arm):
    w, d = build(dict(BIL=.1, A=.2, B=.3), dict(BIL=.00001, A=.1, B=.2), arm)
    assert w['BIL'] == 0
    assert 'BIL' not in d['eligible'] and 'BIL' not in d['scores']


def test_positive_raw_and_excess_gates_are_both_required():
    w, _ = build(dict(BIL=.05, A=.04, B=.06, C=-.1), dict(BIL=.001, A=.1, B=.1, C=.1))
    assert w['A'] == w['C'] == 0 and w['B'] > 0
    w, _ = build(dict(BIL=-.1, A=-.05, B=.01), dict(BIL=.001, A=.1, B=.1))
    assert w['A'] == 0 and w['B'] > 0  # Negative absolute momentum cannot pass.


def test_subtraction_precedes_risk_division():
    _, d = build(dict(BIL=.03, A=.12, B=.07), dict(BIL=.001, A=.2, B=.1))
    assert d['scores']['A'] == pytest.approx(.45)
    assert d['scores']['B'] == pytest.approx(.4)
    _, control = build(dict(BIL=.03, A=.12, B=.07), dict(BIL=.001, A=.2, B=.1), 'pooled_remove_bill_risk')
    assert control['scores']['A'] < control['scores']['B']
    assert d['scores']['A'] > d['scores']['B']


def test_zero_cash_return_makes_primary_equal_to_removal_only_control():
    m, v = dict(BIL=0., A=.12, B=.07), dict(BIL=.001, A=.2, B=.1)
    primary, _ = build(m, v)
    control, _ = build(m, v, 'pooled_remove_bill_risk')
    assert primary == control


@pytest.mark.parametrize('bill', [np.nan, np.inf, -np.inf])
def test_bad_cash_reference_cannot_be_replaced(bill):
    with pytest.raises(ValueError, match='Unsupported BIL'):
        build(dict(BIL=bill, A=.1), dict(BIL=.001, A=.2))


def test_absent_cash_reference_fails_closed():
    with pytest.raises(ValueError, match='BIL reference required'):
        build(dict(A=.1), dict(A=.2))


def test_common_cash_subtraction_cannot_manufacture_rank_information():
    weights = [0, .1, .1, .3, .4]
    returns = np.array([.01, .04, -.02, .03, .07])
    assert study.rank_ic(weights, returns) == study.rank_ic(weights, returns-.015)
    assert study.rank_ic([0]*5, returns) is None
    assert study.rank_ic([1, 2], [1, 2], minimum=3) is None


def test_removal_control_is_original_builder_with_only_bill_masked():
    symbols = ['A', 'B', 'BIL', 'C']
    m, v = [.2, .1, .03, -.1], [.2, .1, .001, .1]
    p = dict(arms=['pooled_remove_bill_risk'], overlap_parents={})
    maps = {s: s for s in symbols}
    expected, _ = base.build_targets(symbols, m, v, ['A', 'B', 'C'], maps, maps, p, p['arms'][0])
    actual, _ = study.candidate_targets(base.build_targets, symbols, m, v, symbols, maps, maps, p, p['arms'][0])
    assert expected == actual


def test_reserved_prospective_dates_match_application_calendar():
    calendar = study.prospective_calendar()
    assert len(calendar['sessions']) == 147
    assert calendar['first'] == '2026-10-19'
    assert calendar['last_signal'] == '2027-04-20'
    assert calendar['last_label'] == '2027-05-19'


def test_diagnostics_omit_labels_outside_window_and_match_static_payoff():
    # Synthetic synchronous observations are intentionally not an exchange calendar.
    days = [f'2024-01-{i:02}' for i in range(1, 32)]
    symbols = ['A', 'B', 'C', 'BIL']
    pool = dict(calendar=days, bars={s: [dict(open=100*(1+.01*i*(j+1))) for i in range(31)]
                                    for j, s in enumerate(symbols)})
    tapes = {}
    for shape in ('pooled', 'class'):
        for kind, weight in [('remove_bill', .1), ('cash_relative', .2)]:
            tapes[shape+'_'+kind+'_risk'] = {days[0]: dict(targets=[dict(symbol=s, target_weight=weight if s=='A' else 0)
                for s in symbols], detail=dict(scores={'A': 1., 'B': 2., 'C': 3.}))}
    p = dict(start=days[0], calibration_end=days[20], later_start='2025-01-01', through='2026-10-12',
             registration=dict(diagnostics=dict(horizons_sessions=[1, 21])), classes=dict(peer=['A','B','C'], bills=['BIL']))
    out = study.forward_diagnostics(tapes, pool, {days[0]: dict(admitted=symbols)}, [days[0]], p)
    assert not out['diagnostics']['calibration']['21']['pooled_cash_relative_risk']
    pair = out['paired_static_excess_contribution']['calibration']['pooled-1'][0]
    assert pair['value'] == pytest.approx(.1*(.01-.04))
    peer = out['diagnostics']['calibration']['1']['pooled_cash_relative_risk'][0]['class_conditioning']
    assert peer['bills']['ic'] is None and peer['peer']['count'] == 3
