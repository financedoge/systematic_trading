from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Mapping, Sequence

from pydantic import BaseModel

from systematic_trading.backtest.engine import BacktestResult, DailyBacktestEngine
from systematic_trading.backtest.stored import (
    _bar_by_date,
    _common_price_dates,
    _latest_rate,
    _open_prices_by_date,
    _previous_trade_dates,
    _prior_close_prices_by_date,
)
from systematic_trading.data.analytics import realized_volatility_from_bars
from systematic_trading.domain.enums import Currency
from systematic_trading.domain.market import FundamentalSnapshot, Instrument, PriceBar
from systematic_trading.domain.portfolio import AllocationTarget, CashBalance
from systematic_trading.portfolio.beta import BetaInstrumentState, RiskParityBetaSleeve
from systematic_trading.research import GLOBAL_ETF_UNIVERSE, SPY_REPLACEMENT_SYMBOL
from systematic_trading.signals.base import SignalContext, TargetOverlay
from systematic_trading.storage.sqlite import SQLiteStore
from systematic_trading.valuation.framework import StockValuationReport, framework_allocation_weights
from systematic_trading.valuation.quantitative import build_quantitative_framework_screen
from systematic_trading.valuation.screener import build_market_feature_snapshots


class StockReplacementBacktestConfig(BaseModel):
    start_date: date
    end_date: date
    initial_cash_cnh: Decimal
    lookback_bars: int = 63
    rebalance_frequency: str = "monthly"
    max_weight: Decimal = Decimal("0.45")
    cash_reserve_weight: Decimal = Decimal("0.02")
    sleeve_name: str = "stock-framework-spy-replacement"
    replacement_symbol: str = SPY_REPLACEMENT_SYMBOL
    stock_weighting: str = "framework"
    max_stock_weight_within_replacement: float | None = None
    stock_selection_mode: Literal["static", "quantitative_point_in_time"] = "static"
    dynamic_top_n: int | None = None


def run_spy_replacement_backtest(
    *,
    store: SQLiteStore,
    stock_instruments: Mapping[str, Instrument],
    selected_symbols: Sequence[str],
    config: StockReplacementBacktestConfig,
    stock_reports: Sequence[StockValuationReport] | None = None,
    base_instruments: Mapping[str, Instrument] = GLOBAL_ETF_UNIVERSE,
    base_target_overlays: Sequence[TargetOverlay] | None = None,
    fundamentals_by_symbol: Mapping[str, Sequence[FundamentalSnapshot]] | None = None,
) -> BacktestResult:
    selected = [symbol.upper() for symbol in selected_symbols]
    if not selected:
        raise ValueError("At least one stock symbol is required.")
    unknown = sorted(set(selected) - set(stock_instruments))
    if unknown:
        raise ValueError(f"Unknown stock symbols: {', '.join(unknown)}")
    if config.replacement_symbol not in base_instruments:
        raise ValueError(f"{config.replacement_symbol} is not in the base ETF universe.")

    replacement_symbol = config.replacement_symbol
    tradable_instruments: dict[str, Instrument] = {
        symbol: instrument
        for symbol, instrument in base_instruments.items()
        if symbol != replacement_symbol
    }
    tradable_instruments.update({symbol: stock_instruments[symbol] for symbol in selected})

    base_bars_by_symbol = {
        symbol: store.list_price_bars(symbol, start_date=config.start_date, end_date=config.end_date)
        for symbol in base_instruments
    }
    tradable_bars_by_symbol = {
        symbol: store.list_price_bars(symbol, start_date=config.start_date, end_date=config.end_date)
        for symbol in tradable_instruments
    }
    required_bars_by_symbol = dict(tradable_bars_by_symbol)
    required_bars_by_symbol[replacement_symbol] = base_bars_by_symbol[replacement_symbol]
    common_dates = _common_price_dates(required_bars_by_symbol)
    if not common_dates:
        raise ValueError("No common price dates are available for the replacement basket.")

    fx_rates = store.list_fx_rates(Currency.USD, start_date=config.start_date, end_date=config.end_date)
    if not fx_rates:
        raise ValueError("USD/CNH FX rates are required for CNH reporting.")
    usd_cnh_by_date = {rate.rate_date: rate.rate for rate in fx_rates}

    daily_prices = {
        trade_date: {
            symbol: _bar_by_date(bars)[trade_date].close
            for symbol, bars in tradable_bars_by_symbol.items()
        }
        for trade_date in common_dates
    }
    daily_execution_prices = _open_prices_by_date(tradable_bars_by_symbol, common_dates)
    daily_rebalance_prices = _prior_close_prices_by_date(tradable_bars_by_symbol, common_dates)
    daily_fx = {
        trade_date: {Currency.USD: _latest_rate(usd_cnh_by_date, trade_date)}
        for trade_date in common_dates
    }
    target_schedule = _replacement_target_schedule(
        selected_symbols=selected,
        base_instruments=base_instruments,
        base_bars_by_symbol=base_bars_by_symbol,
        stock_bars_by_symbol={symbol: tradable_bars_by_symbol[symbol] for symbol in selected},
        stock_instruments={symbol: stock_instruments[symbol] for symbol in selected},
        trade_dates=common_dates,
        config=config,
        stock_reports=stock_reports or (),
        base_target_overlays=base_target_overlays or (),
        fundamentals_by_symbol=fundamentals_by_symbol or {},
    )

    engine = DailyBacktestEngine()
    return engine.run(
        trade_dates=common_dates,
        instruments=tradable_instruments,
        initial_cash=[CashBalance(currency=Currency.CNH, amount=config.initial_cash_cnh)],
        daily_prices=daily_prices,
        daily_fx_to_cnh=daily_fx,
        target_schedule=target_schedule,
        daily_rebalance_prices=daily_rebalance_prices,
        daily_execution_prices=daily_execution_prices,
        decision_dates_by_trade_date=_previous_trade_dates(common_dates),
        sleeve=config.sleeve_name,
    )


def _replacement_target_schedule(
    *,
    selected_symbols: Sequence[str],
    base_instruments: Mapping[str, Instrument],
    base_bars_by_symbol: Mapping[str, Sequence[PriceBar]],
    stock_bars_by_symbol: Mapping[str, Sequence[PriceBar]],
    stock_instruments: Mapping[str, Instrument],
    trade_dates: Sequence[date],
    config: StockReplacementBacktestConfig,
    stock_reports: Sequence[StockValuationReport],
    base_target_overlays: Sequence[TargetOverlay],
    fundamentals_by_symbol: Mapping[str, Sequence[FundamentalSnapshot]],
) -> dict[date, list[AllocationTarget]]:
    sleeve = RiskParityBetaSleeve(name=config.sleeve_name, max_weight=config.max_weight)
    schedule: dict[date, list[AllocationTarget]] = {}
    seen_months: set[tuple[int, int]] = set()
    reports_by_symbol = {report.ticker: report for report in stock_reports}

    for trade_date in trade_dates:
        month_key = (trade_date.year, trade_date.month)
        if month_key in seen_months:
            continue
        seen_months.add(month_key)

        states: list[BetaInstrumentState] = []
        for symbol, instrument in base_instruments.items():
            history = [bar for bar in base_bars_by_symbol[symbol] if bar.trade_date < trade_date]
            if len(history) < config.lookback_bars + 1:
                break
            lookback = history[-(config.lookback_bars + 1) :]
            volatility = realized_volatility_from_bars(lookback)
            if volatility <= Decimal("0"):
                break
            states.append(BetaInstrumentState(instrument=instrument, realized_volatility=volatility))
        else:
            investable_weight = Decimal("1") - config.cash_reserve_weight
            base_targets = [
                target.model_copy(update={"target_weight": target.target_weight * investable_weight})
                for target in sleeve.generate_targets(states)
            ]
            context = SignalContext(
                as_of=trade_date,
                instruments=base_instruments,
                bars_by_symbol=base_bars_by_symbol,
                trade_dates=trade_dates,
            )
            for overlay in base_target_overlays:
                base_targets = overlay.apply(base_targets, context)

            effective_symbols, effective_reports_by_symbol = _effective_stock_selection(
                selected_symbols=selected_symbols,
                stock_instruments=stock_instruments,
                stock_bars_by_symbol=stock_bars_by_symbol,
                trade_date=trade_date,
                trade_dates=trade_dates,
                config=config,
                static_reports_by_symbol=reports_by_symbol,
                fundamentals_by_symbol=fundamentals_by_symbol,
            )
            if not effective_symbols:
                continue
            stock_weights = _stock_weight_map(
                symbols=effective_symbols,
                stock_bars_by_symbol=stock_bars_by_symbol,
                trade_date=trade_date,
                reports_by_symbol=effective_reports_by_symbol,
                config=config,
            )
            schedule[trade_date] = _expand_replacement_target(
                base_targets=base_targets,
                stock_weights=stock_weights,
                reports_by_symbol=effective_reports_by_symbol,
                config=config,
            )

    if not schedule:
        raise ValueError("No rebalance dates had enough lookback history.")
    return schedule


def _effective_stock_selection(
    *,
    selected_symbols: Sequence[str],
    stock_instruments: Mapping[str, Instrument],
    stock_bars_by_symbol: Mapping[str, Sequence[PriceBar]],
    trade_date: date,
    trade_dates: Sequence[date],
    config: StockReplacementBacktestConfig,
    static_reports_by_symbol: Mapping[str, StockValuationReport],
    fundamentals_by_symbol: Mapping[str, Sequence[FundamentalSnapshot]],
) -> tuple[list[str], dict[str, StockValuationReport]]:
    if config.stock_selection_mode == "static":
        return list(selected_symbols), dict(static_reports_by_symbol)

    if config.stock_selection_mode != "quantitative_point_in_time":
        raise ValueError(f"Unsupported stock selection mode: {config.stock_selection_mode}")

    feature_date = _latest_trade_date_before(trade_dates, trade_date)
    if feature_date is None:
        return [], {}
    features = build_market_feature_snapshots(stock_bars_by_symbol, as_of=feature_date)
    screen = build_quantitative_framework_screen(
        instruments={symbol: stock_instruments[symbol] for symbol in selected_symbols},
        features=features,
        fundamentals_by_symbol=fundamentals_by_symbol,
        as_of=trade_date,
        top_n=config.dynamic_top_n or len(selected_symbols),
        universe_name="point-in-time stock replacement universe",
    )
    symbols = [report.ticker for report in screen.reports]
    if not symbols:
        return [], {}
    return symbols, {report.ticker: report for report in screen.reports}


def _latest_trade_date_before(trade_dates: Sequence[date], trade_date: date) -> date | None:
    previous = [item for item in trade_dates if item < trade_date]
    return previous[-1] if previous else None


def _stock_weight_map(
    *,
    symbols: Sequence[str],
    stock_bars_by_symbol: Mapping[str, Sequence[PriceBar]],
    trade_date: date,
    reports_by_symbol: Mapping[str, StockValuationReport],
    config: StockReplacementBacktestConfig,
) -> dict[str, float]:
    if config.stock_weighting == "equal" or len(symbols) == 1:
        return {symbol: 1 / len(symbols) for symbol in symbols}

    volatility_by_symbol = {
        symbol: _stock_volatility(stock_bars_by_symbol[symbol], trade_date, config.lookback_bars)
        for symbol in symbols
    }
    if config.stock_weighting == "inverse-vol":
        inverse = {
            symbol: 1 / max(volatility or 0.25, 0.05)
            for symbol, volatility in volatility_by_symbol.items()
        }
        total = sum(inverse.values())
        return {symbol: value / total for symbol, value in inverse.items()}

    if config.stock_weighting != "framework":
        raise ValueError(f"Unsupported stock weighting mode: {config.stock_weighting}")

    reports = [reports_by_symbol[symbol] for symbol in symbols if symbol in reports_by_symbol]
    if len(reports) != len(symbols):
        return {symbol: 1 / len(symbols) for symbol in symbols}
    return framework_allocation_weights(
        reports,
        volatility_by_symbol=volatility_by_symbol,
        max_single_name_weight=config.max_stock_weight_within_replacement,
    )


def _stock_volatility(bars: Sequence[PriceBar], trade_date: date, lookback_bars: int) -> float | None:
    history = [bar for bar in bars if bar.trade_date < trade_date]
    if len(history) < lookback_bars + 1:
        return None
    value = realized_volatility_from_bars(history[-(lookback_bars + 1) :])
    return float(value)


def _expand_replacement_target(
    *,
    base_targets: Sequence[AllocationTarget],
    stock_weights: Mapping[str, float],
    reports_by_symbol: Mapping[str, StockValuationReport],
    config: StockReplacementBacktestConfig,
) -> list[AllocationTarget]:
    expanded: list[AllocationTarget] = []
    for target in base_targets:
        if target.symbol != config.replacement_symbol:
            expanded.append(target)
            continue
        for symbol, stock_weight in sorted(stock_weights.items()):
            report = reports_by_symbol.get(symbol)
            thesis = report.key_thesis if report is not None else "selected stock replacement basket member"
            expanded.append(
                AllocationTarget(
                    symbol=symbol,
                    target_weight=target.target_weight * Decimal(str(stock_weight)),
                    sleeve=config.sleeve_name,
                    rationale=(
                        f"Replaces {config.replacement_symbol} sleeve exposure. "
                        f"{symbol} receives {stock_weight:.2%} of the replacement basket using "
                        f"{config.stock_weighting} weighting. {thesis}"
                    ),
                    hold_horizon_months=target.hold_horizon_months,
                )
            )
    return expanded
