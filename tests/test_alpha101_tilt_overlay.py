"""The deployed Alpha101 family tilt: rule parity with the measured study, contracts and registration."""
import json
from decimal import Decimal as D
from pathlib import Path

import pytest

from systematic_trading.research import alpha101_tilt_overlay as overlay
from systematic_trading.research import alpha101_tilt_study as study
from systematic_trading.research.strategy_catalog import (alpha101_tilt_definition, instantiate_overlays,
                                                          registered_strategy_definition)
from systematic_trading.research.strategy_diagram import decision_diagrams

KEY = 'research_fr25_alpha_tilt_5_v1'


def target(symbol, weight, sleeve='pooled'):
    from systematic_trading.domain.portfolio import AllocationTarget
    return AllocationTarget(symbol=symbol, target_weight=D(str(weight)), sleeve=sleeve, rationale='base')


class Context:
    """A minimal SignalContext stand-in: bars are already truncated to before the decision."""

    def __init__(self, bars):
        self.bars_by_symbol = bars


def test_the_registered_recipe_is_the_measured_one():
    assert overlay.PARAMETERS['version'] == 'alpha101-family-tilt-v1'
    assert overlay.PARAMETERS['budget'] == '0.05'
    assert len(overlay.PARAMETERS['alphas']) == 16
    assert overlay.PARAMETERS['maxWeight'] == '0.45'


def test_the_definition_appends_the_tilt_last_and_registers():
    definition = registered_strategy_definition(KEY)
    assert definition is not None and definition.key == alpha101_tilt_definition().key
    assert [o.kind for o in definition.overlays][-1] == 'alpha101_tilt'
    assert definition.universe_key == 'multi_asset_14' and definition.scheduler == 'static_monthly'
    instances = instantiate_overlays(definition)
    assert isinstance(instances[-1], overlay.Alpha101FamilyTiltOverlay)
    assert instances[-1].budget == D('0.05') and len(instances[-1].alphas) == 16
    # the spec sheet must carry the evidence status, not just the recipe
    assert 'not established' in definition.description
    assert '0 of 20' in definition.description
    assert 'no allocation, approval or execution authority' in definition.description


def test_a_different_recipe_is_refused():
    from dataclasses import replace
    definition = alpha101_tilt_definition()
    tampered = replace(definition, overlays=(
        *definition.overlays[:-1],
        replace(definition.overlays[-1], parameters=dict(overlay.PARAMETERS, budget='0.50'))))
    with pytest.raises(ValueError, match='Unsupported Alpha101 tilt recipe'):
        instantiate_overlays(tampered)


def test_the_spec_sheet_diagram_explains_the_tilt():
    diagrams = decision_diagrams(alpha101_tilt_definition())
    text = json.dumps(diagrams)
    assert 'sixteen registered Alpha101' in text
    assert 'Rank only the names the book already holds' in text
    assert 'Hold until the next monthly decision' in text


def test_rank_scores_and_the_composite_are_scale_free_and_mean_zero():
    scores = overlay.rank_scores(['a', 'b', 'c'], {'a': 1.0, 'b': 2.0, 'c': 3.0})
    assert scores == {'c': 1.0, 'b': 0.0, 'a': -1.0}
    assert sum(scores.values()) == 0
    assert overlay.rank_scores(['a'], {'a': 1.0}) is None
    assert overlay.rank_scores(['a', 'b'], {'a': 1.0, 'b': 1.0}) is None      # no spread
    # alphas whose values differ by eight orders of magnitude must still contribute equally
    composite = overlay.composite_scores(['a', 'b'], {'1': {'a': 1e6, 'b': -1e6}, '2': {'a': 0.02, 'b': 0.01}})
    assert composite['a'] > composite['b'] and sum(composite.values()) == pytest.approx(0.0)
    # and a composite whose alphas disagree exactly carries no view at all
    assert overlay.composite_scores(['a', 'b'], {'1': {'a': 1e6, 'b': -1e6},
                                                 '2': {'a': 0.01, 'b': 0.02}}) is None


def test_the_tilt_is_nav_neutral_and_bounded():
    weights = {'a': D('0.40'), 'b': D('0.30'), 'c': D('0.20'), 'd': D('0.08')}
    scores = {'a': 3.0, 'b': 1.0, 'c': -1.0, 'd': -3.0}
    tilts, diagnostics = overlay.tilt_vector(weights, scores, D('0.05'))
    assert diagnostics['applied'] and diagnostics['names'] == 4
    assert abs(sum(tilts.values())) < D('1e-20')
    assert tilts['a'] > 0 > tilts['d']
    capped, capped_diagnostics = overlay.tilt_vector({'a': D('0.45'), 'b': D('0.30'), 'c': D('0.23')},
                                                     {'a': 2.0, 'b': 0.0, 'c': -2.0}, D('0.20'))
    assert capped_diagnostics['applied'] is False and capped_diagnostics['scale'] == 0.0
    assert all(value == 0 for value in capped.values())


def test_apply_keeps_the_contracts_the_fallback_protects():
    bars = {symbol: [] for symbol in ('a', 'b', 'c')}
    instance = overlay.Alpha101FamilyTiltOverlay(alphas=('101',), lookback=2)
    targets = [target('a', '0.5'), target('b', '0.3'), target('c', '0.0')]
    # no usable history: the overlay must leave the book exactly as it found it
    assert instance.apply(targets, Context(bars)) == targets
    assert instance.diagnostics['applied'] is False


def test_the_deployed_rule_reproduces_the_measured_study_rule():
    """The production overlay must not drift from the thing that was measured."""
    weights = {symbol: D(str(weight)) for symbol, weight in
               (('a', 0.42), ('b', 0.31), ('c', 0.19), ('d', 0.06))}
    scores = {'a': 2.5, 'b': 0.5, 'c': -0.5, 'd': -2.5}
    deployed, deployed_diagnostics = overlay.tilt_vector(weights, scores, D('0.10'))
    measured, measured_diagnostics = study.tilt_vector(weights, scores, D('0.10'))
    assert deployed_diagnostics == measured_diagnostics
    assert {symbol: str(value) for symbol, value in deployed.items()} == \
           {symbol: str(value) for symbol, value in measured.items()}


def test_the_monitoring_config_includes_the_strategy():
    config = json.loads(Path('config/strategy-monitoring.json').read_text(encoding='utf-8'))
    assert KEY in config['monitored_strategy_ids']
    assert config['schema_version'] == 2
