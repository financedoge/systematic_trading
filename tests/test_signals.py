from datetime import date, timedelta
from decimal import Decimal

from systematic_trading.domain.enums import AssetClass, Currency, Exchange
from systematic_trading.domain.market import Instrument, PriceBar
from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.signals import SignalContext, TimeSeriesMomentumOverlay


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
