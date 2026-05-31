from datetime import date, timedelta
from decimal import Decimal

from systematic_trading.backtest.engine import DailyBacktestEngine
from systematic_trading.backtest.stored import _apply_rebalance_gate, _daily_target_schedule, _monthly_target_schedule
from systematic_trading.domain.enums import AssetClass, Currency, Exchange
from systematic_trading.domain.market import Instrument, PriceBar
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


def test_daily_backtest_engine_sizes_from_prior_close_and_executes_at_open_window_proxy() -> None:
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
    decision_date = date(2026, 4, 13)
    execution_date = date(2026, 4, 14)
    trade_dates = [decision_date, execution_date]
    daily_prices = {
        decision_date: {"SPY": Decimal("100")},
        execution_date: {"SPY": Decimal("110")},
    }
    daily_rebalance_prices = {
        execution_date: {"SPY": Decimal("100")},
    }
    daily_execution_prices = {
        execution_date: {"SPY": Decimal("105")},
    }
    daily_fx = {trade_date: {Currency.USD: Decimal("7.20")} for trade_date in trade_dates}
    target_schedule = {
        execution_date: [
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
        initial_cash=[CashBalance(currency=Currency.CNH, amount=Decimal("10000"))],
        daily_prices=daily_prices,
        daily_fx_to_cnh=daily_fx,
        target_schedule=target_schedule,
        daily_rebalance_prices=daily_rebalance_prices,
        daily_execution_prices=daily_execution_prices,
        decision_dates_by_trade_date={execution_date: decision_date},
    )

    proposal = result.proposals[0]
    assert proposal.as_of == decision_date
    assert proposal.intended_trade_date == execution_date
    assert proposal.orders[0].quantity == 13
    assert proposal.orders[0].reference_price == Decimal("100")
    assert result.final_snapshot.positions[0].average_cost == Decimal("105")
    assert result.final_snapshot.nav_cnh == Decimal("10468.00")


def test_daily_backtest_engine_scales_open_gap_buys_to_available_cash() -> None:
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
    decision_date = date(2026, 4, 13)
    execution_date = date(2026, 4, 14)
    daily_prices = {
        decision_date: {"SPY": Decimal("10")},
        execution_date: {"SPY": Decimal("12")},
    }
    target_schedule = {
        execution_date: [
            AllocationTarget(
                symbol="SPY",
                target_weight=Decimal("1.0"),
                sleeve="beta-risk-parity",
                rationale="Full allocation test target.",
            )
        ]
    }

    result = engine.run(
        trade_dates=[decision_date, execution_date],
        instruments=instruments,
        initial_cash=[CashBalance(currency=Currency.CNH, amount=Decimal("100"))],
        daily_prices=daily_prices,
        daily_fx_to_cnh={trade_date: {Currency.USD: Decimal("1")} for trade_date in [decision_date, execution_date]},
        target_schedule=target_schedule,
        daily_rebalance_prices={execution_date: {"SPY": Decimal("10")}},
        daily_execution_prices={execution_date: {"SPY": Decimal("12")}},
        decision_dates_by_trade_date={execution_date: decision_date},
    )

    assert result.proposals[0].orders[0].quantity == 10
    assert result.final_snapshot.positions[0].quantity == 8
    assert result.final_snapshot.cash[0].amount == Decimal("4.00")


def test_daily_backtest_engine_charges_transaction_cost_bps() -> None:
    engine = DailyBacktestEngine()
    instruments = {"SPY": _instrument("SPY")}
    trade_date = date(2026, 4, 13)
    target_schedule = {
        trade_date: [
            AllocationTarget(
                symbol="SPY",
                target_weight=Decimal("1.0"),
                sleeve="test",
                rationale="Full allocation test target.",
            )
        ]
    }

    result = engine.run(
        trade_dates=[trade_date],
        instruments=instruments,
        initial_cash=[CashBalance(currency=Currency.CNH, amount=Decimal("1001"))],
        daily_prices={trade_date: {"SPY": Decimal("100")}},
        daily_fx_to_cnh={trade_date: {Currency.USD: Decimal("1")}},
        target_schedule=target_schedule,
        transaction_cost_bps=Decimal("10"),
    )

    assert result.proposals[0].orders[0].quantity == 10
    assert result.final_snapshot.nav_cnh == Decimal("1000.00")


def test_stored_backtest_daily_schedule_uses_each_eligible_trade_date() -> None:
    instruments = {
        "SPY": _instrument("SPY"),
        "VGK": _instrument("VGK"),
    }
    trade_dates = [date(2026, 1, 1) + timedelta(days=index) for index in range(37)]
    bars_by_symbol = {
        "SPY": _price_bars(trade_dates, Decimal("100")),
        "VGK": _price_bars(trade_dates, Decimal("80")),
    }

    daily_schedule = _daily_target_schedule(
        instruments=instruments,
        bars_by_symbol=bars_by_symbol,
        trade_dates=trade_dates,
        lookback_bars=2,
        max_weight=Decimal("0.80"),
        cash_reserve_weight=Decimal("0.02"),
        sleeve_name="test",
        target_overlays=(),
    )
    monthly_schedule = _monthly_target_schedule(
        instruments=instruments,
        bars_by_symbol=bars_by_symbol,
        trade_dates=trade_dates,
        lookback_bars=2,
        max_weight=Decimal("0.80"),
        cash_reserve_weight=Decimal("0.02"),
        sleeve_name="test",
        target_overlays=(),
    )

    assert min(daily_schedule) == date(2026, 1, 4)
    assert len(daily_schedule) == len(trade_dates) - 3
    assert list(monthly_schedule) == [date(2026, 2, 1)]


def test_rebalance_gate_skips_small_daily_target_changes() -> None:
    schedule = {
        date(2026, 1, 2): [_target("SPY", "0.50"), _target("VGK", "0.50")],
        date(2026, 1, 3): [_target("SPY", "0.52"), _target("VGK", "0.48")],
        date(2026, 1, 4): [_target("SPY", "0.54"), _target("VGK", "0.46")],
        date(2026, 1, 5): [_target("SPY", "0.54"), _target("GLD", "0.46")],
    }

    gated = _apply_rebalance_gate(
        schedule,
        min_weight_delta=Decimal("0.03"),
        min_total_weight_delta=Decimal("0.08"),
        force_on_asset_change=True,
    )

    assert list(gated) == [date(2026, 1, 2), date(2026, 1, 4), date(2026, 1, 5)]


def _instrument(symbol: str) -> Instrument:
    return Instrument(
        symbol=symbol,
        name=symbol,
        asset_class=AssetClass.ETF,
        exchange=Exchange.NYSE,
        quote_currency=Currency.USD,
        country="US",
    )


def _price_bars(trade_dates: list[date], start_close: Decimal) -> list[PriceBar]:
    return [
        PriceBar(
            trade_date=trade_date,
            open=start_close + Decimal(index),
            high=start_close + Decimal(index) + Decimal("1"),
            low=start_close + Decimal(index) - Decimal("1"),
            close=start_close + Decimal(index) + Decimal("0.50"),
            volume=1_000_000 + index,
        )
        for index, trade_date in enumerate(trade_dates)
    ]


def _target(symbol: str, weight: str) -> AllocationTarget:
    return AllocationTarget(symbol=symbol, target_weight=Decimal(weight), sleeve="test", rationale="test")
