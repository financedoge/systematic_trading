from datetime import date, timedelta
from decimal import Decimal

from systematic_trading.domain.enums import AssetClass, Currency, Exchange
from systematic_trading.domain.market import Instrument, PriceBar
from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.signals import (
    AdaptiveTrendOverlay,
    RegimeGatedRelativeMomentumOverlay,
    SignalContext,
    TimeSeriesMomentumOverlay,
)


def test_time_series_momentum_overlay_moves_negative_trend_to_cash() -> None:
    context = SignalContext(
        as_of=date(2024, 1, 10),
        instruments={"SPY": _instrument("SPY")},
        bars_by_symbol={"SPY": _bars([Decimal("100"), Decimal("98"), Decimal("95"), Decimal("90")])},
        trade_dates=[],
    )
    overlay = TimeSeriesMomentumOverlay(lookback_bars=2)

    targets = overlay.apply([_target("SPY", Decimal("0.75"))], context)

    assert targets[0].target_weight == Decimal("0")
    assert "set the allocation to cash" in targets[0].rationale


def test_time_series_momentum_overlay_can_reallocate_positive_survivors() -> None:
    context = SignalContext(
        as_of=date(2024, 1, 10),
        instruments={"SPY": _instrument("SPY"), "VGK": _instrument("VGK")},
        bars_by_symbol={
            "SPY": _bars([Decimal("100"), Decimal("102"), Decimal("104"), Decimal("105")]),
            "VGK": _bars([Decimal("100"), Decimal("99"), Decimal("98"), Decimal("90")]),
        },
        trade_dates=[],
    )
    overlay = TimeSeriesMomentumOverlay(lookback_bars=2, reallocate_survivors=True)

    targets = overlay.apply([_target("SPY", Decimal("0.40")), _target("VGK", Decimal("0.40"))], context)
    weights = {target.symbol: target.target_weight for target in targets}

    assert weights["SPY"] == Decimal("0.80")
    assert weights["VGK"] == Decimal("0")


def test_adaptive_trend_overlay_keeps_partial_exposure_during_rebound() -> None:
    context = SignalContext(
        as_of=date(2024, 1, 10),
        instruments={"SPY": _instrument("SPY")},
        bars_by_symbol={"SPY": _bars([Decimal("100"), Decimal("96"), Decimal("88"), Decimal("82"), Decimal("91")])},
        trade_dates=[],
    )
    overlay = AdaptiveTrendOverlay(
        short_lookback_bars=2,
        medium_lookback_bars=3,
        long_lookback_bars=4,
        rebound_lookback_bars=2,
        volume_lookback_bars=2,
        fast_volatility_bars=2,
        slow_volatility_bars=4,
        short_threshold=Decimal("0.20"),
        medium_threshold=Decimal("0.20"),
        long_threshold=Decimal("0.20"),
        rebound_threshold=Decimal("0.03"),
        rebound_scale=Decimal("0.75"),
        reallocate_residual=False,
    )

    targets = overlay.apply([_target("SPY", Decimal("0.80"))], context)

    assert targets[0].target_weight == Decimal("0.6000")
    assert "rebound exposure" in targets[0].rationale


def test_adaptive_trend_overlay_reallocates_residual_to_stronger_assets() -> None:
    context = SignalContext(
        as_of=date(2024, 1, 10),
        instruments={"SPY": _instrument("SPY"), "VGK": _instrument("VGK")},
        bars_by_symbol={
            "SPY": _bars([Decimal("100"), Decimal("102"), Decimal("104"), Decimal("106"), Decimal("108")]),
            "VGK": _bars([Decimal("100"), Decimal("98"), Decimal("96"), Decimal("94"), Decimal("92")]),
        },
        trade_dates=[],
    )
    overlay = AdaptiveTrendOverlay(
        short_lookback_bars=2,
        medium_lookback_bars=3,
        long_lookback_bars=4,
        rebound_lookback_bars=2,
        volume_lookback_bars=2,
        fast_volatility_bars=2,
        slow_volatility_bars=4,
        weak_scale=Decimal("0.50"),
        reallocate_residual=True,
    )

    targets = overlay.apply([_target("SPY", Decimal("0.40")), _target("VGK", Decimal("0.40"))], context)
    weights = {target.symbol: target.target_weight for target in targets}

    assert weights["SPY"] == Decimal("0.6000")
    assert weights["VGK"] == Decimal("0.2000")


def test_regime_gated_relative_momentum_tilts_within_total_weight() -> None:
    context = SignalContext(
        as_of=date(2024, 1, 10),
        instruments={"SPY": _instrument("SPY"), "EWJ": _instrument("EWJ"), "VGK": _instrument("VGK")},
        bars_by_symbol={
            "SPY": _bars([Decimal("100"), Decimal("102"), Decimal("104"), Decimal("106"), Decimal("108")]),
            "EWJ": _bars([Decimal("100"), Decimal("100"), Decimal("100"), Decimal("100"), Decimal("100")]),
            "VGK": _bars([Decimal("100"), Decimal("98"), Decimal("96"), Decimal("94"), Decimal("92")]),
        },
        trade_dates=[],
    )
    overlay = RegimeGatedRelativeMomentumOverlay(
        medium_lookback_bars=2,
        long_lookback_bars=4,
        fast_volatility_bars=2,
        slow_volatility_bars=4,
        drawdown_lookback_bars=4,
        calm_tilt=Decimal("0.10"),
        risk_tilt=Decimal("0.30"),
        drawdown_trigger=Decimal("-1"),
    )

    targets = overlay.apply(
        [_target("SPY", Decimal("0.30")), _target("EWJ", Decimal("0.30")), _target("VGK", Decimal("0.30"))],
        context,
    )
    weights = {target.symbol: target.target_weight for target in targets}

    assert weights["SPY"] > Decimal("0.30")
    assert weights["EWJ"] == Decimal("0.30")
    assert weights["VGK"] < Decimal("0.30")
    assert sum(weights.values(), Decimal("0")) == Decimal("0.9000")


def test_regime_gated_relative_momentum_uses_stronger_risk_tilt() -> None:
    context = SignalContext(
        as_of=date(2024, 1, 10),
        instruments={"SPY": _instrument("SPY"), "EWJ": _instrument("EWJ"), "VGK": _instrument("VGK")},
        bars_by_symbol={
            "SPY": _bars([Decimal("100"), Decimal("102"), Decimal("104"), Decimal("106"), Decimal("108")]),
            "EWJ": _bars([Decimal("100"), Decimal("100"), Decimal("100"), Decimal("100"), Decimal("100")]),
            "VGK": _bars([Decimal("100"), Decimal("98"), Decimal("96"), Decimal("94"), Decimal("92")]),
        },
        trade_dates=[],
    )
    base_targets = [_target("SPY", Decimal("0.30")), _target("EWJ", Decimal("0.30")), _target("VGK", Decimal("0.30"))]
    calm = RegimeGatedRelativeMomentumOverlay(
        medium_lookback_bars=2,
        long_lookback_bars=4,
        fast_volatility_bars=2,
        slow_volatility_bars=4,
        drawdown_lookback_bars=4,
        calm_tilt=Decimal("0.10"),
        risk_tilt=Decimal("0.30"),
        drawdown_trigger=Decimal("-1"),
    )
    risk = RegimeGatedRelativeMomentumOverlay(
        medium_lookback_bars=2,
        long_lookback_bars=4,
        fast_volatility_bars=2,
        slow_volatility_bars=4,
        drawdown_lookback_bars=4,
        calm_tilt=Decimal("0.10"),
        risk_tilt=Decimal("0.30"),
        drawdown_trigger=Decimal("0"),
    )

    calm_weights = {target.symbol: target.target_weight for target in calm.apply(base_targets, context)}
    risk_weights = {target.symbol: target.target_weight for target in risk.apply(base_targets, context)}

    assert risk_weights["SPY"] - Decimal("0.30") > calm_weights["SPY"] - Decimal("0.30")
    assert Decimal("0.30") - risk_weights["VGK"] > Decimal("0.30") - calm_weights["VGK"]


def _instrument(symbol: str) -> Instrument:
    return Instrument(
        symbol=symbol,
        name=symbol,
        asset_class=AssetClass.ETF,
        exchange=Exchange.NYSE,
        quote_currency=Currency.USD,
        country="US",
    )


def _target(symbol: str, weight: Decimal) -> AllocationTarget:
    return AllocationTarget(
        symbol=symbol,
        target_weight=weight,
        sleeve="test",
        rationale="Base risk target.",
    )


def _bars(closes: list[Decimal]) -> list[PriceBar]:
    start = date(2024, 1, 1)
    return [
        PriceBar(
            trade_date=start + timedelta(days=index),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=100,
        )
        for index, close in enumerate(closes)
    ]
