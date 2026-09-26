import copy
from datetime import date
from decimal import Decimal
import importlib.util
from pathlib import Path
import sys

import pytest

from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.lean.strategy import targets_for_day
from systematic_trading.research.constituent_signals import ConstituentOverlaySpec
from systematic_trading.research.constituent_integration import (
    choose_residual_model, constrain_to_base, ConstituentSelection,
)
from systematic_trading.signals.trend import AssetPoolFilterOverlay, AssetPoolSelectionScore
from test_flow_concentration import histories


def preparation_module():
    scripts = Path(__file__).resolve().parents[1]/'scripts'
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location('prepare_constituent_integration', scripts/'prepare_constituent_integration.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def records():
    return [dict(known_through=f'{2022+i//12}-{i%12+1:02d}-01', label_end=f'{2022+i//12}-{i%12+1:02d}-28',
        residual=(-.01 if i < 12 else .02), inputs=dict(mom_63=i/100, mom_126=i/50,
        base_forecast=.01, breadth=i/24, signed_activity=(i-12)/100)) for i in range(24)]


def test_future_and_uncompleted_labels_cannot_change_a_fitted_tree():
    fit = preparation_module().fit_models
    rows = records()
    expected = fit(rows, [2024])
    changed = copy.deepcopy(rows)
    changed.append(dict(known_through='2023-12-29', label_end='2024-01-02', residual=999,
                        inputs=rows[0]['inputs']))
    changed.append(dict(known_through='2024-02-01', label_end='2024-02-28', residual=-999,
                        inputs=rows[0]['inputs']))
    assert fit(changed, [2024]) == expected
    assert expected['joint']['2024-01-01']['training_samples'] == 24
    assert 'breadth' not in expected['price']['2024-01-01']['model']['featureNames']
    assert 'breadth' in expected['joint']['2024-01-01']['model']['featureNames']


def test_tree_activation_future_record_and_label_guards():
    models = preparation_module().fit_models(records(), [2024])
    data = {'integration_models': models}
    assert choose_residual_model(data, '2023-12-29', 'joint') is None
    before = choose_residual_model(data, '2024-03-28', 'joint')
    data['integration_models']['joint']['2025-01-01'] = {'invalid_future_payload': True}
    assert choose_residual_model(data, '2024-03-28', 'joint') == before
    models['joint']['2024-01-01']['max_label_end'] = '2024-01-01'
    with pytest.raises(ValueError, match='unavailable training'):
        choose_residual_model(data, '2024-03-28', 'joint')


def test_selection_changes_rank_but_preserves_eligibility(monkeypatch):
    scores = {'SPY': AssetPoolSelectionScore(Decimal('.1'), {}, {'longMomentum': Decimal('-.1')}),
              'GLD': AssetPoolSelectionScore(Decimal('.15'), {}, {'longMomentum': Decimal('.2')})}
    monkeypatch.setattr(AssetPoolFilterOverlay, '_selection_scores', lambda *args: dict(scores))
    adapter = ConstituentSelection(AssetPoolFilterOverlay(), 1, .15)
    revised = adapter._selection_scores([], None)
    assert revised['SPY'].total > revised['GLD'].total
    assert revised['SPY'].raw_metrics['longMomentum'] == Decimal('-.1')
    assert scores['SPY'].total == Decimal('.1')


def target(s, w):
    return AllocationTarget(symbol=s, target_weight=Decimal(w), rationale='', sleeve='test')


def test_selection_can_enter_spy_with_matched_exposure_and_active_bounds():
    base = [target('SPY', '0'), target('GLD', '.40'), target('TLT', '.40'), target('EWJ', '.18')]
    proposal = [target('SPY', '.30'), target('GLD', '.20'), target('TLT', '.40'), target('EWJ', '0')]
    result = constrain_to_base(base, proposal, .03)
    assert result[0].target_weight == pytest.approx(Decimal('.03'))
    assert sum(t.target_weight for t in result) == pytest.approx(Decimal('.98'))
    assert all(abs(a.target_weight-b.target_weight) <= Decimal('.030000000000001') for a,b in zip(result,base))
    assert all(0 <= t.target_weight <= Decimal('.45') for t in result)


@pytest.mark.parametrize('stage', ['early', 'selection', 'tree'])
def test_integration_has_no_effect_without_qualified_features(stage):
    rows = histories()
    day = date(2024, 5, 1)
    baseline = targets_for_day(rows, day)
    assert targets_for_day(rows, day, constituent_overlay=ConstituentOverlaySpec(stage=stage), constituent_features={}) == baseline


@pytest.mark.parametrize('stage', ['early', 'selection', 'tree'])
def test_future_bar_and_constituent_changes_do_not_affect_targets(stage):
    rows = histories()
    day = date(2024, 5, 1)
    known = max(r['trade_date'] for r in rows['SPY'] if r['trade_date'] < str(day))
    features = {'45': {known: dict(known_through=known, snapshot='2024-02-29', assumed_available='2024-04-14',
        value_coverage=.99, name_coverage=.99, values=dict(breadth=.7, signed_activity=.1), scores={'signed_activity':1})},
        'integration_models': preparation_module().fit_models(records(), [2024])}
    spec = ConstituentOverlaySpec(stage=stage, signal='signed_activity')
    expected = targets_for_day(rows, day, constituent_overlay=spec, constituent_features=features)
    changed = copy.deepcopy(rows)
    for series in changed.values():
        for r in series:
            if r['trade_date'] >= str(day):
                r.update(close='99999', high='99999', open='99999', low='99999', volume=999999)
    features['45']['2024-05-02'] = {'malformed_future_data':True}
    features['integration_models']['joint']['2025-01-01'] = {'malformed_future_model':True}
    assert targets_for_day(changed, day, constituent_overlay=spec, constituent_features=features) == expected
