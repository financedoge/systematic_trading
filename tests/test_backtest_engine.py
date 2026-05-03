from datetime import date
from decimal import Decimal

from systematic_trading.backtest.engine import DailyBacktestEngine
from systematic_trading.domain.enums import AssetClass, Currency, Exchange
from systematic_trading.domain.market import Instrument
from systematic_trading.domain.portfolio import AllocationTarget, CashBalance


def test_daily_backtest_engine_revalues_cnh_nav() -> None:
    engine = DailyBacktestEngine()
    instruments = {
        "SPY": Instrument(
            symbol="SPY",
            name="SPDR S&P 500 ETF Trust",
            asset_class=AssetClass.ETF,
            exchange=Exchange.NYSE,
            quote_currency=Currency.USD,
            country="US",
        )
    }
    trade_dates = [date(2026, 4, 13), date(2026, 4, 14), date(2026, 4, 15)]
    daily_prices = {
        date(2026, 4, 13): {"SPY": Decimal("100")},
        date(2026, 4, 14): {"SPY": Decimal("110")},
        date(2026, 4, 15): {"SPY": Decimal("120")},
    }
    daily_fx = {trade_date: {Currency.USD: Decimal("7.20")} for trade_date in trade_dates}
    target_schedule = {
        date(2026, 4, 13): [
            AllocationTarget(
                symbol="SPY",
                target_weight=Decimal("1.0"),
                sleeve="beta-risk-parity",
                rationale="Full allocation test target.",
                hold_horizon_months=12,
            )
        ]
    }

    result = engine.run(
        trade_dates=trade_dates,
        instruments=instruments,
        initial_cash=[CashBalance(currency=Currency.CNH, amount=Decimal("7200"))],
        daily_prices=daily_prices,
        daily_fx_to_cnh=daily_fx,
        target_schedule=target_schedule,
    )

    assert len(result.proposals) == 1
    assert result.proposals[0].orders[0].quantity == 10
    assert result.final_snapshot.nav_cnh == Decimal("8640.00")


def test_daily_backtest_engine_applies_sells_before_buys_on_rebalance() -> None:
    engine = DailyBacktestEngine()
    instruments = {
        "SPY": Instrument(
            symbol="SPY",
            name="SPDR S&P 500 ETF Trust",
            asset_class=AssetClass.ETF,
            exchange=Exchange.NYSE,
            quote_currency=Currency.USD,
            country="US",
        ),
        "VGK": Instrument(
            symbol="VGK",
            name="Vanguard FTSE Europe ETF",
            asset_class=AssetClass.ETF,
            exchange=Exchange.NYSE,
            quote_currency=Currency.USD,
            country="Europe",
        ),
    }
    trade_dates = [date(2026, 4, 13), date(2026, 5, 1)]
    daily_prices = {
        date(2026, 4, 13): {"SPY": Decimal("100"), "VGK": Decimal("100")},
        date(2026, 5, 1): {"SPY": Decimal("100"), "VGK": Decimal("100")},
    }
    daily_fx = {trade_date: {Currency.USD: Decimal("7.20")} for trade_date in trade_dates}
    target_schedule = {
        date(2026, 4, 13): [
            AllocationTarget(
                symbol="SPY",
                target_weight=Decimal("1.0"),
                sleeve="test",
                rationale="Initial full SPY allocation.",
            )
        ],
        date(2026, 5, 1): [
            AllocationTarget(
                symbol="VGK",
                target_weight=Decimal("1.0"),
                sleeve="test",
                rationale="Rotate fully to VGK.",
            )
        ],
    }

    result = engine.run(
        trade_dates=trade_dates,
        instruments=instruments,
        initial_cash=[CashBalance(currency=Currency.CNH, amount=Decimal("7200"))],
        daily_prices=daily_prices,
        daily_fx_to_cnh=daily_fx,
        target_schedule=target_schedule,
    )

    assert result.final_snapshot.positions[0].symbol == "VGK"
    assert result.final_snapshot.positions[0].quantity == 10
