"""Focused tests: the balanced-group overlay's absolute-momentum gate (peer-review defect 7).

The review's reproduction: a synthetic ``DBC`` series with 150 valid falling observations,
whose 126-session momentum is -0.711864, was still allocated 0.98, because a one-name
sleeve has no rank table and the overlay returned its target list unchanged instead of
testing the gate. The fallback branch had the same hole for a many-name sleeve in which
every member failed the gate. These tests pin the corrected contract: absolute-momentum
eligibility is decided for every member from that member's own price history, before any
ranking or rank fallback and independently of sleeve size.
"""
from datetime import date, timedelta
from decimal import Decimal

from systematic_trading.domain.enums import AssetClass, Currency, Exchange
from systematic_trading.domain.market import Instrument, PriceBar
from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.signals.balanced import BalancedAssetGroupOverlay
from systematic_trading.signals.base import SignalContext


def _closes_from_momentum(momentum: Decimal, observations: int = 150, sessions: int = 126) -> list[Decimal]:
    """A geometric path whose final ``sessions``-bar return is ``momentum``."""
    factor = Decimal(str(float(Decimal('1') + momentum) ** (1 / sessions)))
    value, closes = Decimal('100'), []
    for _ in range(observations):
        value = value * factor
        closes.append(value)
    return closes


def _v_shaped_closes(observations: int = 150) -> list[Decimal]:
    """Falls for the first 87 bars, then recovers: negative 126-bar, positive 63-bar momentum."""
    closes, value = [], Decimal('100')
    for index in range(observations):
        value = value * (Decimal('0.985') if index < 87 else Decimal('1.0015'))
        closes.append(value)
    return closes


def _bars(closes: list[Decimal], volume: int = 1000) -> list[PriceBar]:
    start = date(2019, 1, 1)
    return [PriceBar(trade_date=start + timedelta(days=index), open=close, high=close, low=close, close=close,
                     volume=volume if index % 2 == 0 else 800)
            for index, close in enumerate(closes)]


def _context(series: dict[str, list[Decimal]]) -> SignalContext:
    return SignalContext(
        as_of=date(2021, 1, 1),
        instruments={symbol: Instrument(symbol=symbol, name=symbol, asset_class=AssetClass.ETF,
                                        exchange=Exchange.NYSE, quote_currency=Currency.USD, country='US')
                     for symbol in series},
        bars_by_symbol={symbol: _bars(closes) for symbol, closes in series.items()},
        trade_dates=[])


def _target(symbol: str, weight: Decimal = Decimal('0.98'), sleeve: str = 'commodity') -> AllocationTarget:
    return AllocationTarget(symbol=symbol, target_weight=weight, sleeve=sleeve, rationale='Base risk target.')


def _overlay(sleeve_by_symbol: dict[str, str], sleeve_budgets: dict[str, Decimal], **overrides
             ) -> BalancedAssetGroupOverlay:
    """The overlay with the studies' declared parameters (21/63/126, 0.75/0.25, 126-bar gate)."""
    parameters = dict(top_n_per_sleeve=2, min_selected_per_sleeve=1, short_momentum_bars=21,
                      medium_momentum_bars=63, long_momentum_bars=126, volume_bars=21, slow_volume_bars=126,
                      trend_weight=Decimal('0.75'), volume_weight=Decimal('0.25'),
                      require_positive_long_momentum=True, min_long_momentum=Decimal('0'),
                      fallback_to_top_ranked=False, name='focused-momentum-gate-test')
    parameters.update(overrides)
    return BalancedAssetGroupOverlay(sleeve_by_symbol=sleeve_by_symbol, sleeve_budgets=sleeve_budgets, **parameters)


# --- the review's fixture ------------------------------------------------------

def test_the_review_fixture_falling_singleton_is_allocated_zero():
    closes = _closes_from_momentum(Decimal('-0.711864'))
    assert len(closes) == 150
    momentum = (closes[-1] / closes[-127]) - Decimal('1')
    assert abs(momentum - Decimal('-0.711864')) < Decimal('1e-9')
    context = _context({'DBC': closes})
    target = _target('DBC', Decimal('0.98'))
    overlay = _overlay({'DBC': 'commodity'}, {'commodity': Decimal('1')})

    # the mechanism the review identified: a one-name sleeve has no rank table at all,
    # which is exactly why the old code returned the target unchanged
    assert overlay._scores([target], context) is None

    result = overlay.apply([target], context)

    assert result[0].target_weight == Decimal('0')
    assert 'long=-71.19%' in result[0].rationale
    assert 'gate rejected' in result[0].rationale


def test_a_flat_singleton_is_allocated_zero_because_the_gate_is_strictly_positive():
    closes = _closes_from_momentum(Decimal('0'))
    context = _context({'GLD': closes})
    overlay = _overlay({'GLD': 'gold'}, {'gold': Decimal('1')})

    result = overlay.apply([_target('GLD', Decimal('0.98'), sleeve='gold')], context)

    assert result[0].target_weight == Decimal('0')
    assert 'long=0.00%' in result[0].rationale
    assert 'gate rejected' in result[0].rationale


def test_a_positive_singleton_is_allocated_its_weight():
    closes = _closes_from_momentum(Decimal('0.25'))
    context = _context({'GLD': closes})
    overlay = _overlay({'GLD': 'gold'}, {'gold': Decimal('1')})

    result = overlay.apply([_target('GLD', Decimal('0.98'), sleeve='gold')], context)

    assert result[0].target_weight == Decimal('0.98')
    assert 'long=25.00%' in result[0].rationale
    assert 'selected momentum-eligible sleeve assets' in result[0].rationale


def test_a_singleton_without_126_sessions_of_history_is_not_allocated():
    closes = _closes_from_momentum(Decimal('0.25'), observations=100)
    context = _context({'DBC': closes})
    overlay = _overlay({'DBC': 'commodity'}, {'commodity': Decimal('1')})

    result = overlay.apply([_target('DBC', Decimal('0.98'))], context)

    assert result[0].target_weight == Decimal('0')
    assert 'long=n/a' in result[0].rationale
    assert 'gate rejected' in result[0].rationale


def test_the_gate_uses_the_declared_long_lookback_not_a_wired_in_constant():
    closes = _v_shaped_closes()
    context = _context({'DBC': closes})
    target = _target('DBC', Decimal('0.98'))

    gated_at_126 = _overlay({'DBC': 'commodity'}, {'commodity': Decimal('1')}, long_momentum_bars=126)
    gated_at_63 = _overlay({'DBC': 'commodity'}, {'commodity': Decimal('1')}, long_momentum_bars=63)

    assert gated_at_126.apply([target], context)[0].target_weight == Decimal('0')
    assert gated_at_63.apply([target], context)[0].target_weight == Decimal('0.98')


# --- the gate is a property of the member, not of the sleeve -------------------

def test_the_gate_does_not_depend_on_sleeve_size():
    series = {
        'SPY': _closes_from_momentum(Decimal('-0.10')),
        'VGK': _closes_from_momentum(Decimal('-0.20')),
        'EWJ': _closes_from_momentum(Decimal('-0.30')),
        'XLE': _closes_from_momentum(Decimal('0.15')),
    }
    weights = {symbol: Decimal('0.20') for symbol in series}
    context = _context(series)
    target_list = [_target(symbol, weight) for symbol, weight in weights.items()]

    many = _overlay({symbol: 'equity' for symbol in series}, {'equity': Decimal('1')}, top_n_per_sleeve=4)
    many_result = many.apply(target_list, context)
    many_weights = {target.symbol: target.target_weight for target in many_result}

    # inside the four-name sleeve the gate keeps exactly the one rising member
    assert many_weights['XLE'] == Decimal('0.80')
    assert {symbol: weight for symbol, weight in many_weights.items() if symbol != 'XLE'} == \
        {'SPY': Decimal('0'), 'VGK': Decimal('0'), 'EWJ': Decimal('0')}

    # the same members as one-name sleeves get exactly the same eligibility decision
    singles = {symbol: _overlay({symbol: symbol}, {symbol: Decimal('1')}) for symbol in series}
    for symbol in series:
        single_result = singles[symbol].apply([_target(symbol, weights[symbol], sleeve=symbol)], context)
        assert (single_result[0].target_weight > 0) is (symbol == 'XLE'), symbol


def test_a_falling_singleton_stays_in_cash_without_reallocating_its_share():
    series = {'DBC': _closes_from_momentum(Decimal('-0.71')), 'SPY': _closes_from_momentum(Decimal('0.20')),
              'VGK': _closes_from_momentum(Decimal('0.10'))}
    context = _context(series)
    overlay = _overlay({'DBC': 'commodity', 'SPY': 'equity', 'VGK': 'equity'},
                       {'commodity': Decimal('0.5'), 'equity': Decimal('0.5')})
    targets = [_target('DBC', Decimal('0.10')), _target('SPY', Decimal('0.10'), 'equity'),
               _target('VGK', Decimal('0.10'), 'equity')]

    result = {target.symbol: target.target_weight for target in overlay.apply(targets, context)}

    assert result['DBC'] == Decimal('0')
    assert result['SPY'] == Decimal('0.075') and result['VGK'] == Decimal('0.075')
    assert sum(result.values()) == Decimal('0.15')


def test_the_gate_can_be_switched_off_and_then_the_neutral_parent_behaviour_returns():
    closes = _closes_from_momentum(Decimal('-0.711864'))
    context = _context({'DBC': closes})
    overlay = _overlay({'DBC': 'commodity'}, {'commodity': Decimal('1')},
                       require_positive_long_momentum=False)

    result = overlay.apply([_target('DBC', Decimal('0.98'))], context)

    assert result[0].target_weight == Decimal('0.98')
    assert 'selected all sleeve assets because ranking history was incomplete' in result[0].rationale


# --- the rank fallback may widen slots, never the gate -------------------------

def test_the_top_ranked_fallback_never_selects_a_member_that_failed_the_gate():
    series = {'IEF': _closes_from_momentum(Decimal('-0.05')), 'TLT': _closes_from_momentum(Decimal('-0.15')),
              'LQD': _closes_from_momentum(Decimal('-0.25')), 'HYG': _closes_from_momentum(Decimal('-0.35'))}
    context = _context(series)
    target_list = [_target(symbol, Decimal('0.24'), 'fixed_income') for symbol in series]
    overlay = _overlay({symbol: 'fixed_income' for symbol in series}, {'fixed_income': Decimal('1')},
                       min_selected_per_sleeve=2, fallback_to_top_ranked=True)

    result = {target.symbol: target.target_weight for target in overlay.apply(target_list, context)}

    assert set(result.values()) == {Decimal('0')}
    assert all('gate rejected' in target.rationale
               for target in overlay.apply(target_list, context))


def test_the_fallback_fills_only_from_members_that_passed_the_gate():
    series = {'IEF': _closes_from_momentum(Decimal('0.18')), 'TLT': _closes_from_momentum(Decimal('-0.15')),
              'LQD': _closes_from_momentum(Decimal('-0.25'))}
    context = _context(series)
    target_list = [_target(symbol, Decimal('0.10'), 'fixed_income') for symbol in series]
    overlay = _overlay({symbol: 'fixed_income' for symbol in series}, {'fixed_income': Decimal('1')},
                       top_n_per_sleeve=3, min_selected_per_sleeve=2, fallback_to_top_ranked=True)

    result = {target.symbol: target.target_weight for target in overlay.apply(target_list, context)}

    # only one member passes the gate, so the widened slot count still buys one name
    assert result['IEF'] == Decimal('0.30')
    assert result['TLT'] == Decimal('0') and result['LQD'] == Decimal('0')


def test_a_one_name_sleeve_is_gated_the_same_way_whether_or_not_a_fallback_is_configured():
    closes = _closes_from_momentum(Decimal('-0.711864'))
    context = _context({'DBC': closes})
    target = _target('DBC', Decimal('0.98'))

    for fallback in (False, True):
        overlay = _overlay({'DBC': 'commodity'}, {'commodity': Decimal('1')},
                           min_selected_per_sleeve=2, fallback_to_top_ranked=fallback)
        assert overlay.apply([target], context)[0].target_weight == Decimal('0'), fallback
