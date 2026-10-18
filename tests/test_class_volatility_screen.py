"""Causal inputs, selection boundaries and frozen screen accounting."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest


SPEC = importlib.util.spec_from_file_location('class_screen', Path(__file__).parents[1]/'scripts/run_class_volatility_screen.py')
study = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(study)


def protocol():
    return dict(arms=['pooled_raw', 'pooled_risk', 'class_raw', 'class_risk'], overlap_parents={})


def targets(momentum, vol, *, groups=None, arm='pooled_raw', p=None):
    symbols = sorted(momentum)
    return study.build_targets(symbols, [momentum[s] for s in symbols], [vol[s] for s in symbols],
        symbols, groups or {s: s for s in symbols}, {s: s for s in symbols}, p or protocol(), arm)


def test_features_use_exact_prior_windows_and_ignore_future():
    rng = np.random.default_rng(7)
    prices = 100*np.cumprod(1+rng.normal(.001, .01, (300, 2)), axis=0)
    m, v = study.features(prices, 270)
    np.testing.assert_allclose(m, prices[269]/prices[143]-1)
    np.testing.assert_allclose(v, (prices[207:270]/prices[206:269]-1).std(axis=0, ddof=1)*np.sqrt(252))
    prices[270:] = 99999
    m2, v2 = study.features(prices, 270)
    np.testing.assert_array_equal(m, m2)
    np.testing.assert_array_equal(v, v2)


@pytest.mark.parametrize('bad', [0., np.nan, -1.])
def test_bad_prices_fail_closed(bad):
    values = np.ones((270, 2))*100
    values[250, 0] = bad
    with pytest.raises(ValueError, match='Unsupported'):
        study.features(values, 260)


@pytest.mark.parametrize('arm', protocol()['arms'])
def test_absolute_gate_singletons_zero_vol_and_no_forced_fills(arm):
    w, detail = targets(dict(A=-.1, B=0., C=.1), dict(A=.1, B=.1, C=0.), arm=arm)
    assert not detail['selected']
    assert sum(w.values()) == 0


def test_raw_and_risk_rankings_differ_without_changing_sizing():
    m = {str(i): .2 for i in range(7)}
    v = {str(i): .1 for i in range(7)}
    m['6'], v['6'] = .4, .8
    _, raw = targets(m, v)
    _, risk = targets(m, v, arm='pooled_risk')
    assert '6' in raw['selected'] and '6' not in risk['selected']


def test_cash_slots_cap_and_inverse_volatility_arithmetic():
    w, _ = targets(dict(A=.1, B=.2), dict(A=.1, B=.2))
    assert float(sum(w.values())) == pytest.approx(.98*2/6)
    assert w['A']/w['B'] == 2
    m = {str(i): .2 for i in range(6)}
    v = {str(i): .1 if i else .0001 for i in range(6)}
    w, _ = targets(m, v)
    assert float(w['0']) == .45 and sum(w.values()) < study.D('.98')


def test_class_scores_use_actually_selected_members_and_unused_slots_are_cash():
    w, d = targets(dict(A=.5, B=.3, C=.1), dict(A=.1, B=.2, C=.1),
                   groups=dict(A='g', B='g', C='h'), arm='class_raw')
    assert d['classes'][0] == dict(group='g', members=['A', 'B'], score=.4)
    assert float(sum(w.values())) == pytest.approx(.49)
    assert w['A']/w['B'] == 2


@pytest.mark.parametrize('arm', ['pooled_raw', 'class_raw'])
def test_broad_parent_excludes_children_in_either_selection_order(arm):
    p = dict(protocol(), overlap_parents={'A': ['B']})
    for momentum in [dict(A=.5, B=.4, C=.3), dict(A=.4, B=.5, C=.3)]:
        _, d = targets(momentum, dict(A=.1, B=.1, C=.1), arm=arm, p=p)
        assert not {'A', 'B'} <= set(d['selected'])
        assert len(d['selected']) == 2
        for group in d['classes']:
            assert group['score'] == pytest.approx(np.mean([momentum[s] for s in group['members']]))


def test_taxonomy_covers_every_candidate_once():
    p = study.read(Path(__file__).parents[1]/study.PROTOCOL)
    symbols = [s for group in p['classes'].values() for s in group]
    assert len(study.class_map(p, symbols)) == 52
    p['classes']['duplicate'] = ['SPY']
    with pytest.raises(ValueError, match='exactly one'):
        study.class_map(p, symbols)


def test_turnover_counts_security_legs_not_cash_and_keeps_previous_anchor():
    def row(weight):
        return dict(targets=[dict(symbol='A', target_weight=str(weight))])
    decisions = {'2020-12-01': row(.5), '2021-01-04': row(.7), '2021-06-01': row(.4)}
    t = study.turnover(decisions, '2021-01-01', '2021-12-31')
    assert t['total_target_change'] == pytest.approx(.5)
    assert t['years'] == pytest.approx(364/365.25)


def test_missing_candidate_ic_never_falls_back_to_reference():
    result = study.evaluate_gate(dict(annual_turnover=0), [dict(ic=None, forward_returns=[])])
    assert result['status'] == 'insufficient' and result['candidate_ic'] is None


def test_ic_labels_stop_at_window_boundary_and_zero_weights_are_included():
    days = [f'2021-01-{i:02}' for i in range(1, 32)]
    symbols = ['A', 'B', 'C', 'D']
    opens = np.ones((31, 4))*100
    opens[21] = [104, 103, 102, 101]
    tape = {days[0]: dict(targets=[dict(symbol=s, target_weight=w)
                                 for s, w in zip(symbols, [.4, .3, 0, 0], strict=True)])}
    obs = study.ic_rows(tape, {days[0]: symbols}, [days[0]], days, opens, symbols, days[0], days[21])
    assert obs[0]['count'] == 4 and obs[0]['ic'] > .9
    assert not study.ic_rows(tape, {days[0]: symbols}, [days[0]], days, opens, symbols, days[0], days[20])


def test_frozen_manifest_rejects_tampering_and_path_escape(tmp_path):
    path = tmp_path/'data.json'
    study.write(path, {'a': 1})
    study.manifest(tmp_path, 'manifest.json', [path])
    study.verify(tmp_path, 'manifest.json')
    study.write(path, {'a': 2})
    with pytest.raises(ValueError, match='hash mismatch'):
        study.verify(tmp_path, 'manifest.json')
    study.write(tmp_path/'manifest.json', {'../outside': '0'*64})
    with pytest.raises(ValueError, match='hash mismatch'):
        study.verify(tmp_path, 'manifest.json')


def test_joint_bootstrap_identical_arms_remain_identical():
    p = dict(uncertainty=dict(mean_block_months=[3], seed=17, replications=2000))
    rows = [dict(day=str(i), ic=(i-6)/20) for i in range(12)]
    result = study.bootstrap({'a': rows, 'b': rows}, p)
    assert result['a'] == result['b']
    interval = result['a']['3']
    assert interval['family_95_bonferroni'][0] <= interval['individual_95'][0]
    assert interval['family_95_bonferroni'][1] >= interval['individual_95'][1]
