"""Focused tests: the hierarchical class score's population (peer review, 2026-10-11).

The v1 rule scored a class from its globally top-ranked eligible members, while the
members it actually held came from the parent overlay's within-sleeve reranking. The
review's synthetic case scored ``TLT``/``HYG`` but held ``IEF``/``TLT``. The registered
v2 design is a two-population design with one invariant: **the class score is the mean of
the global member scores of exactly the members the within-sleeve reranking holds.** The
synthetic cross-section below is the review's case in miniature — the globally top-ranked
fixed-income members are ``HYG``/``TLT``, the members the rule holds are ``LQD``/``TLT`` —
and it is strong enough that the class choice itself changes with the population.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from systematic_trading.domain.enums import AssetClass, Currency, Exchange
from systematic_trading.domain.market import Instrument, PriceBar
from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.research import hierarchical_construction_study as study
from systematic_trading.research import hierarchical_selection
from systematic_trading.research.hierarchical_selection import HierarchicalSelection
from systematic_trading.signals.base import SignalContext

SLOTS = 2
# Piecewise-constant daily growth for the four 150-bar segments 0-21/21-63/63-126/126-150.
FACTORS = {
    'IEF': ('0.995', '1.005', '0.996', '0.999'),
    'TLT': ('1.003', '0.997', '1.005', '1.000'),
    'LQD': ('0.998', '1.002', '1.003', '0.999'),
    'HYG': ('1.005', '0.997', '1.004', '1.000'),
    'DBC': ('0.999', '0.999', '1.002', '1.001'),
    'GLD': ('0.999', '0.999', '0.999', '1.002'),
}
UP_VOLUME = {'IEF': 300, 'TLT': 500, 'LQD': 400, 'HYG': 200, 'DBC': 200, 'GLD': 600}
SLEEVE_OF = {'IEF': 'fixed_income', 'TLT': 'fixed_income', 'LQD': 'fixed_income', 'HYG': 'fixed_income',
             'DBC': 'commodity', 'GLD': 'gold'}
SEGMENTS = ((0, 21, 0), (21, 63, 1), (63, 126, 2), (126, 150, 3))


def _closes(factors: tuple[str, ...]) -> list[Decimal]:
    value, closes = Decimal('100'), []
    for start, end, index in SEGMENTS:
        factor = Decimal(factors[index])
        for _ in range(end - start):
            value = value * factor
            closes.append(value)
    return closes


def _bars(closes: list[Decimal], up_volume: int) -> list[PriceBar]:
    start = date(2019, 1, 1)
    return [PriceBar(trade_date=start + timedelta(days=index), open=close, high=close, low=close, close=close,
                     volume=up_volume if index % 2 == 0 else 1000 - up_volume)
            for index, close in enumerate(closes)]


def _fixture() -> tuple[SignalContext, list[AllocationTarget]]:
    context = SignalContext(
        as_of=date(2021, 1, 1),
        instruments={symbol: Instrument(symbol=symbol, name=symbol, asset_class=AssetClass.ETF,
                                        exchange=Exchange.NYSE, quote_currency=Currency.USD, country='US')
                     for symbol in FACTORS},
        bars_by_symbol={symbol: _bars(_closes(factors), UP_VOLUME[symbol])
                        for symbol, factors in FACTORS.items()},
        trade_dates=[])
    targets = [AllocationTarget(symbol=symbol, target_weight=Decimal('0.1'), sleeve='plan', rationale='Base.')
               for symbol in FACTORS]
    return context, targets


def _overlay(top_classes: int) -> HierarchicalSelection:
    return HierarchicalSelection(top_classes=top_classes, sleeve_by_symbol=SLEEVE_OF,
                                 sleeve_budgets={sleeve: 0 for sleeve in dict.fromkeys(SLEEVE_OF.values())},
                                 top_n_per_sleeve=SLOTS, min_selected_per_sleeve=1, short_momentum_bars=21,
                                 medium_momentum_bars=63, long_momentum_bars=126, volume_bars=21,
                                 slow_volume_bars=126, trend_weight=Decimal('0.75'), volume_weight=Decimal('0.25'),
                                 require_positive_long_momentum=True, min_long_momentum=Decimal('0'),
                                 fallback_to_top_ranked=False, name='class-score-population-fixture')


def _v1_population(scores, sleeve: str) -> tuple[list[str], Decimal]:
    """The superseded v1 population: the globally top-ranked eligible members of the class."""
    eligible = {symbol: score for symbol, score in scores.items()
                if score.long_momentum is not None and score.long_momentum > Decimal('0')}
    members = sorted((symbol for symbol in eligible if SLEEVE_OF[symbol] == sleeve),
                     key=lambda symbol: (-eligible[symbol].total, symbol))
    top = members[:SLOTS]
    return top, sum((eligible[symbol].total for symbol in top), Decimal('0')) / Decimal(len(top))


def test_the_class_score_is_the_mean_of_the_members_the_rule_holds():
    context, targets = _fixture()
    overlay = _overlay(top_classes=2)

    result = overlay.apply(targets, context)
    held = {target.symbol for target in result if target.target_weight > 0}
    scores = overlay._scores(targets, context)

    assert overlay.observed['chosen'] == ['commodity', 'fixed_income']
    assert held == {'DBC', 'LQD', 'TLT'}
    assert held <= set(SLEEVE_OF)
    # the scored population is exactly the held population
    assert overlay.observed['class_members']['fixed_income'] == ['LQD', 'TLT']
    assert held & {'IEF', 'TLT', 'LQD', 'HYG'} == set(overlay.observed['class_members']['fixed_income'])
    # and the number is the mean of those held members' global scores
    expected = (scores['LQD'].total + scores['TLT'].total) / Decimal(2)
    assert Decimal(overlay.observed['class_scores']['fixed_income']) == expected
    assert overlay.observed['class_members']['commodity'] == ['DBC']
    assert Decimal(overlay.observed['class_scores']['commodity']) == scores['DBC'].total


def test_the_v1_global_top_ranked_population_would_have_scored_a_member_the_rule_does_not_hold():
    context, targets = _fixture()
    overlay = _overlay(top_classes=2)
    overlay.apply(targets, context)
    scores = overlay._scores(targets, context)

    old_members, old_score = _v1_population(scores, 'fixed_income')

    # the review's disagreement, reproduced: v1 scores TLT/HYG, the rule holds LQD/TLT
    assert old_members == ['TLT', 'HYG']
    assert overlay.observed['class_members']['fixed_income'] == ['LQD', 'TLT']
    assert set(old_members) != set(overlay.observed['class_members']['fixed_income'])
    # and the disagreement is not cosmetic: the two populations give different numbers
    assert old_score == Decimal('0.32375')
    assert Decimal(overlay.observed['class_scores']['fixed_income']) == Decimal('0.2475')
    assert old_score != Decimal(overlay.observed['class_scores']['fixed_income'])


def test_the_chosen_class_follows_the_population_the_rule_holds():
    context, targets = _fixture()
    overlay = _overlay(top_classes=1)

    result = overlay.apply(targets, context)
    scores = overlay._scores(targets, context)
    old_score = _v1_population(scores, 'fixed_income')[1]
    commodity_score = scores['DBC'].total

    # with the held population the commodity class ranks first; with v1's population it does not
    assert old_score > commodity_score > Decimal(overlay.observed['class_scores']['fixed_income'])
    assert overlay.observed['chosen'] == ['commodity']
    assert {target.symbol for target in result if target.target_weight > 0} == {'DBC'}


def test_a_class_whose_only_member_fails_the_gate_is_neither_scored_nor_chosen():
    context, targets = _fixture()
    overlay = _overlay(top_classes=3)
    scores = overlay._scores(targets, context)

    assert scores['GLD'].long_momentum < 0  # the fixture's gold member is in a downtrend
    result = overlay.apply(targets, context)
    weights = {target.symbol: target.target_weight for target in result}

    assert 'gold' not in overlay.observed['qualifying']
    assert 'gold' not in overlay.observed['class_scores']
    assert weights['GLD'] == 0
    rationale = next(target.rationale for target in result if target.symbol == 'GLD')
    assert 'gate rejected' in rationale


def test_the_class_score_helper_averages_exactly_the_members_it_is_given():
    assert study.class_score([Decimal('0.9'), Decimal('0.5'), Decimal('0.1')]) == Decimal('0.5')
    assert study.class_score([Decimal('0.4')]) == Decimal('0.4')
    assert study.class_score([Decimal('0.25'), Decimal('0.25')]) == Decimal('0.25')
    with pytest.raises(ValueError):
        study.class_score([])


def test_the_registered_rule_states_both_populations():
    overlay_doc = hierarchical_selection.__doc__ or ''

    assert 'actually hold' in (study.__doc__ or '')
    assert 'global cross-section rank table' in (study.__doc__ or '')
    assert 'within-sleeve' in overlay_doc and 'global' in overlay_doc
    assert 'will hold' in overlay_doc
