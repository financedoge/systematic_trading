from datetime import date
from decimal import Decimal

from systematic_trading.data.analytics import close_to_close_returns, realized_volatility_from_bars
from systematic_trading.domain.market import PriceBar


def test_realized_volatility_from_bars_uses_close_to_close_returns() -> None:
    bars = [
        PriceBar(
            trade_date=date(2026, 4, 13),
            open=Decimal("100"),
            high=Decimal("102"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=1000,
        ),
        PriceBar(
            trade_date=date(2026, 4, 14),
            open=Decimal("100"),
            high=Decimal("112"),
            low=Decimal("100"),
            close=Decimal("110"),
            volume=1000,
        ),
        PriceBar(
            trade_date=date(2026, 4, 15),
            open=Decimal("110"),
            high=Decimal("111"),
            low=Decimal("104"),
            close=Decimal("105"),
            volume=1000,
        ),
        PriceBar(
            trade_date=date(2026, 4, 16),
            open=Decimal("105"),
            high=Decimal("109"),
            low=Decimal("104"),
            close=Decimal("108"),
            volume=1000,
        ),
    ]

    returns = close_to_close_returns(bars)

    assert returns == [
        Decimal("0.1"),
        Decimal("-0.0454545454545454545454545455"),
        Decimal("0.028571428571428571428571429"),
    ]
    assert realized_volatility_from_bars(bars) == Decimal("1.1546")
