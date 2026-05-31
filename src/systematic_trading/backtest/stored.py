from __future__ import annotations

from bisect import bisect_left
from datetime import date
from decimal import Decimal
from typing import Mapping, Sequence

from pydantic import BaseModel

from systematic_trading.data.analytics import realized_volatility_from_bars
from systematic_trading.domain.enums import Currency
from systematic_trading.domain.market import Instrument, PriceBar
from systematic_trading.domain.portfolio import AllocationTarget, CashBalance
from systematic_trading.portfolio.beta import BetaInstrumentState, RiskParityBetaSleeve
from systematic_trading.backtest.engine import BacktestResult, DailyBacktestEngine
from systematic_trading.signals.base import SignalContext, TargetOverlay
from systematic_trading.storage.sqlite import SQLiteStore


class StoredRiskParityBacktestConfig(BaseModel):
    start_date: date
    end_date: date
    initial_cash_cnh: Decimal
    lookback_bars: int = 63
    rebalance_frequency: str = "monthly"
    max_weight: Decimal = Decimal("0.45")
    cash_reserve_weight: Decimal = Decimal("0.02")
    rebalance_min_weight_delta: Decimal = Decimal("0")
    rebalance_min_total_weight_delta: Decimal = Decimal("0")
    rebalance_force_on_asset_change: bool = False
    transaction_cost_bps: Decimal = Decimal("0")
    sleeve_name: str = "stored-monthly-risk-parity"


def run_stored_risk_parity_backtest(
    *,
    store: SQLiteStore,
    instruments: Mapping[str, Instrument],
    config: StoredRiskParityBacktestConfig,
    target_overlays: Sequence[TargetOverlay] | None = None,
) -> BacktestResult:
    bars_by_symbol = {
        symbol: store.list_price_bars(symbol, start_date=config.start_date, end_date=config.end_date)
        for symbol in instruments
    }
    common_dates = _common_price_dates(bars_by_symbol)
    if not common_dates:
        raise ValueError("No common price dates are available for the requested symbols.")

    fx_rates = store.list_fx_rates(Currency.USD, start_date=config.start_date, end_date=config.end_date)
    if not fx_rates:
        raise ValueError("USD/CNH FX rates are required for CNH reporting.")
    usd_cnh_by_date = {rate.rate_date: rate.rate for rate in fx_rates}

    daily_prices = {
        trade_date: {
            symbol: _bar_by_date(bars)[trade_date].close
            for symbol, bars in bars_by_symbol.items()
        }
        for trade_date in common_dates
    }
    daily_execution_prices = _open_prices_by_date(bars_by_symbol, common_dates)
    daily_rebalance_prices = _prior_close_prices_by_date(bars_by_symbol, common_dates)
    daily_fx = {
        trade_date: {Currency.USD: _latest_rate(usd_cnh_by_date, trade_date)}
        for trade_date in common_dates
    }
    target_schedule = _target_schedule(
        instruments=instruments,
        bars_by_symbol=bars_by_symbol,
        trade_dates=common_dates,
        rebalance_frequency=config.rebalance_frequency,
        lookback_bars=config.lookback_bars,
        max_weight=config.max_weight,
        cash_reserve_weight=config.cash_reserve_weight,
        sleeve_name=config.sleeve_name,
        target_overlays=target_overlays or (),
        min_weight_delta=config.rebalance_min_weight_delta,
        min_total_weight_delta=config.rebalance_min_total_weight_delta,
        force_on_asset_change=config.rebalance_force_on_asset_change,
    )

    engine = DailyBacktestEngine()
    return engine.run(
        trade_dates=common_dates,
        instruments=instruments,
        initial_cash=[CashBalance(currency=Currency.CNH, amount=config.initial_cash_cnh)],
        daily_prices=daily_prices,
        daily_fx_to_cnh=daily_fx,
        target_schedule=target_schedule,
        daily_rebalance_prices=daily_rebalance_prices,
        daily_execution_prices=daily_execution_prices,
        decision_dates_by_trade_date=_previous_trade_dates(common_dates),
        transaction_cost_bps=config.transaction_cost_bps,
        sleeve=config.sleeve_name,
    )


def run_dynamic_risk_parity_backtest(
    *,
    store: SQLiteStore,
    instruments: Mapping[str, Instrument],
    config: StoredRiskParityBacktestConfig,
    target_overlays: Sequence[TargetOverlay] | None = None,
) -> BacktestResult:
    bars_by_symbol = {
        symbol: store.list_price_bars(symbol, start_date=config.start_date, end_date=config.end_date)
        for symbol in instruments
    }
    trade_dates = sorted({bar.trade_date for bars in bars_by_symbol.values() for bar in bars})
    trade_dates = [item for item in trade_dates if config.start_date <= item <= config.end_date]
    if not trade_dates:
        raise ValueError("No price dates are available for the requested symbols.")

    fx_rates = store.list_fx_rates(Currency.USD, start_date=config.start_date, end_date=config.end_date)
    if not fx_rates:
        raise ValueError("USD/CNH FX rates are required for CNH reporting.")
    usd_cnh_by_date = {rate.rate_date: rate.rate for rate in fx_rates}
    latest_bars_by_date = _latest_bars_by_date(bars_by_symbol, trade_dates)

    daily_prices = {
        trade_date: {symbol: bar.close for symbol, bar in latest_bars_by_date[trade_date].items()}
        for trade_date in trade_dates
    }
    daily_execution_prices = _open_prices_by_date(bars_by_symbol, trade_dates)
    daily_rebalance_prices = _prior_close_prices_by_date(bars_by_symbol, trade_dates)
    daily_fx = {
        trade_date: {Currency.USD: _latest_rate(usd_cnh_by_date, trade_date)}
        for trade_date in trade_dates
    }
    target_schedule = _dynamic_target_schedule(
        instruments=instruments,
        bars_by_symbol=bars_by_symbol,
        trade_dates=trade_dates,
        rebalance_frequency=config.rebalance_frequency,
        lookback_bars=config.lookback_bars,
        max_weight=config.max_weight,
        cash_reserve_weight=config.cash_reserve_weight,
        sleeve_name=config.sleeve_name,
        target_overlays=target_overlays or (),
        min_weight_delta=config.rebalance_min_weight_delta,
        min_total_weight_delta=config.rebalance_min_total_weight_delta,
        force_on_asset_change=config.rebalance_force_on_asset_change,
    )

    engine = DailyBacktestEngine()
    return engine.run(
        trade_dates=trade_dates,
        instruments=instruments,
        initial_cash=[CashBalance(currency=Currency.CNH, amount=config.initial_cash_cnh)],
        daily_prices=daily_prices,
        daily_fx_to_cnh=daily_fx,
        target_schedule=target_schedule,
        daily_rebalance_prices=daily_rebalance_prices,
        daily_execution_prices=daily_execution_prices,
        decision_dates_by_trade_date=_previous_trade_dates(trade_dates),
        transaction_cost_bps=config.transaction_cost_bps,
        sleeve=config.sleeve_name,
    )


def _common_price_dates(bars_by_symbol: Mapping[str, Sequence[PriceBar]]) -> list[date]:
    date_sets = [{bar.trade_date for bar in bars} for bars in bars_by_symbol.values()]
    return sorted(set.intersection(*date_sets))


def _bar_by_date(bars: Sequence[PriceBar]) -> dict[date, PriceBar]:
    return {bar.trade_date: bar for bar in bars}


def _latest_rate(rates_by_date: Mapping[date, Decimal], trade_date: date) -> Decimal:
    available_dates = [rate_date for rate_date in rates_by_date if rate_date <= trade_date]
    if not available_dates:
        raise ValueError(f"No USD/CNH FX rate is available on or before {trade_date}.")
    return rates_by_date[max(available_dates)]


def _latest_bars_by_date(
    bars_by_symbol: Mapping[str, Sequence[PriceBar]],
    trade_dates: Sequence[date],
) -> dict[date, dict[str, PriceBar]]:
    latest: dict[str, PriceBar] = {}
    indices = {symbol: 0 for symbol in bars_by_symbol}
    result: dict[date, dict[str, PriceBar]] = {}
    for trade_date in trade_dates:
        for symbol, bars in bars_by_symbol.items():
            index = indices[symbol]
            while index < len(bars) and bars[index].trade_date <= trade_date:
                latest[symbol] = bars[index]
                index += 1
            indices[symbol] = index
        result[trade_date] = dict(latest)
    return result


def _open_prices_by_date(
    bars_by_symbol: Mapping[str, Sequence[PriceBar]],
    trade_dates: Sequence[date],
) -> dict[date, dict[str, Decimal]]:
    bars_by_date = {symbol: _bar_by_date(bars) for symbol, bars in bars_by_symbol.items()}
    result: dict[date, dict[str, Decimal]] = {}
    for trade_date in trade_dates:
        prices: dict[str, Decimal] = {}
        for symbol, bars in bars_by_symbol.items():
            bar = bars_by_date[symbol].get(trade_date)
            if bar is not None:
                prices[symbol] = bar.open
                continue
            prior = _latest_bar_before(bars, trade_date)
            if prior is not None:
                prices[symbol] = prior.close
        result[trade_date] = prices
    return result


def _prior_close_prices_by_date(
    bars_by_symbol: Mapping[str, Sequence[PriceBar]],
    trade_dates: Sequence[date],
) -> dict[date, dict[str, Decimal]]:
    result: dict[date, dict[str, Decimal]] = {}
    for trade_date in trade_dates:
        prices: dict[str, Decimal] = {}
        for symbol, bars in bars_by_symbol.items():
            prior = _latest_bar_before(bars, trade_date)
            if prior is not None:
                prices[symbol] = prior.close
        result[trade_date] = prices
    return result


def _latest_bar_before(bars: Sequence[PriceBar], trade_date: date) -> PriceBar | None:
    candidates = [bar for bar in bars if bar.trade_date < trade_date]
    return candidates[-1] if candidates else None


def _previous_trade_dates(trade_dates: Sequence[date]) -> dict[date, date]:
    ordered = sorted(trade_dates)
    return {trade_date: ordered[index - 1] for index, trade_date in enumerate(ordered) if index > 0}


def _target_schedule(
    *,
    instruments: Mapping[str, Instrument],
    bars_by_symbol: Mapping[str, Sequence[PriceBar]],
    trade_dates: Sequence[date],
    rebalance_frequency: str,
    lookback_bars: int,
    max_weight: Decimal,
    cash_reserve_weight: Decimal,
    sleeve_name: str,
    target_overlays: Sequence[TargetOverlay],
    min_weight_delta: Decimal = Decimal("0"),
    min_total_weight_delta: Decimal = Decimal("0"),
    force_on_asset_change: bool = False,
) -> dict[date, list[AllocationTarget]]:
    sleeve = RiskParityBetaSleeve(name=sleeve_name, max_weight=max_weight)
    schedule: dict[date, list[AllocationTarget]] = {}
    sorted_bars_by_symbol, dates_by_symbol = _bars_and_dates_by_symbol(bars_by_symbol)

    for trade_date in _rebalance_trade_dates(trade_dates, rebalance_frequency):

        states: list[BetaInstrumentState] = []
        for symbol, instrument in instruments.items():
            bars = sorted_bars_by_symbol[symbol]
            history_end = bisect_left(dates_by_symbol[symbol], trade_date)
            if history_end < lookback_bars + 1:
                break
            lookback = bars[history_end - lookback_bars - 1 : history_end]
            volatility = realized_volatility_from_bars(lookback)
            if volatility <= Decimal("0"):
                break
            states.append(BetaInstrumentState(instrument=instrument, realized_volatility=volatility))
        else:
            investable_weight = Decimal("1") - cash_reserve_weight
            targets = [
                target.model_copy(update={"target_weight": target.target_weight * investable_weight})
                for target in sleeve.generate_targets(states)
            ]
            context = SignalContext(
                as_of=trade_date,
                instruments=instruments,
                bars_by_symbol=bars_by_symbol,
                trade_dates=trade_dates,
            )
            for overlay in target_overlays:
                targets = overlay.apply(targets, context)
            schedule[trade_date] = targets

    if not schedule:
        raise ValueError("No rebalance dates had enough lookback history.")
    return _apply_rebalance_gate(
        schedule,
        min_weight_delta=min_weight_delta,
        min_total_weight_delta=min_total_weight_delta,
        force_on_asset_change=force_on_asset_change,
    )


def _monthly_target_schedule(
    *,
    instruments: Mapping[str, Instrument],
    bars_by_symbol: Mapping[str, Sequence[PriceBar]],
    trade_dates: Sequence[date],
    lookback_bars: int,
    max_weight: Decimal,
    cash_reserve_weight: Decimal,
    sleeve_name: str,
    target_overlays: Sequence[TargetOverlay],
    min_weight_delta: Decimal = Decimal("0"),
    min_total_weight_delta: Decimal = Decimal("0"),
    force_on_asset_change: bool = False,
) -> dict[date, list[AllocationTarget]]:
    return _target_schedule(
        instruments=instruments,
        bars_by_symbol=bars_by_symbol,
        trade_dates=trade_dates,
        rebalance_frequency="monthly",
        lookback_bars=lookback_bars,
        max_weight=max_weight,
        cash_reserve_weight=cash_reserve_weight,
        sleeve_name=sleeve_name,
        target_overlays=target_overlays,
        min_weight_delta=min_weight_delta,
        min_total_weight_delta=min_total_weight_delta,
        force_on_asset_change=force_on_asset_change,
    )


def _daily_target_schedule(
    *,
    instruments: Mapping[str, Instrument],
    bars_by_symbol: Mapping[str, Sequence[PriceBar]],
    trade_dates: Sequence[date],
    lookback_bars: int,
    max_weight: Decimal,
    cash_reserve_weight: Decimal,
    sleeve_name: str,
    target_overlays: Sequence[TargetOverlay],
    min_weight_delta: Decimal = Decimal("0"),
    min_total_weight_delta: Decimal = Decimal("0"),
    force_on_asset_change: bool = False,
) -> dict[date, list[AllocationTarget]]:
    return _target_schedule(
        instruments=instruments,
        bars_by_symbol=bars_by_symbol,
        trade_dates=trade_dates,
        rebalance_frequency="daily",
        lookback_bars=lookback_bars,
        max_weight=max_weight,
        cash_reserve_weight=cash_reserve_weight,
        sleeve_name=sleeve_name,
        target_overlays=target_overlays,
        min_weight_delta=min_weight_delta,
        min_total_weight_delta=min_total_weight_delta,
        force_on_asset_change=force_on_asset_change,
    )


def _dynamic_target_schedule(
    *,
    instruments: Mapping[str, Instrument],
    bars_by_symbol: Mapping[str, Sequence[PriceBar]],
    trade_dates: Sequence[date],
    rebalance_frequency: str,
    lookback_bars: int,
    max_weight: Decimal,
    cash_reserve_weight: Decimal,
    sleeve_name: str,
    target_overlays: Sequence[TargetOverlay],
    min_weight_delta: Decimal = Decimal("0"),
    min_total_weight_delta: Decimal = Decimal("0"),
    force_on_asset_change: bool = False,
) -> dict[date, list[AllocationTarget]]:
    sleeve = RiskParityBetaSleeve(name=sleeve_name, max_weight=max_weight)
    schedule: dict[date, list[AllocationTarget]] = {}
    max_required_history = max(
        [lookback_bars, *[getattr(overlay, "lookback_bars", lookback_bars) for overlay in target_overlays]]
    )
    sorted_bars_by_symbol, dates_by_symbol = _bars_and_dates_by_symbol(bars_by_symbol)
    bar_date_sets_by_symbol = {symbol: set(dates) for symbol, dates in dates_by_symbol.items()}

    for trade_date in _rebalance_trade_dates(trade_dates, rebalance_frequency):

        states: list[BetaInstrumentState] = []
        for symbol, instrument in instruments.items():
            if trade_date not in bar_date_sets_by_symbol.get(symbol, set()):
                continue
            bars = sorted_bars_by_symbol[symbol]
            history_end = bisect_left(dates_by_symbol[symbol], trade_date)
            if history_end < max_required_history + 1:
                continue
            lookback = bars[history_end - lookback_bars - 1 : history_end]
            volatility = realized_volatility_from_bars(lookback)
            if volatility <= Decimal("0"):
                continue
            states.append(BetaInstrumentState(instrument=instrument, realized_volatility=volatility))
        if len(states) < 2:
            continue

        investable_weight = Decimal("1") - cash_reserve_weight
        targets = [
            target.model_copy(update={"target_weight": target.target_weight * investable_weight})
            for target in sleeve.generate_targets(states)
        ]
        context = SignalContext(
            as_of=trade_date,
            instruments={state.instrument.symbol: state.instrument for state in states},
            bars_by_symbol=bars_by_symbol,
            trade_dates=trade_dates,
        )
        for overlay in target_overlays:
            targets = overlay.apply(targets, context)
        schedule[trade_date] = targets

    if not schedule:
        raise ValueError("No rebalance dates had enough dynamic eligible history.")
    return _apply_rebalance_gate(
        schedule,
        min_weight_delta=min_weight_delta,
        min_total_weight_delta=min_total_weight_delta,
        force_on_asset_change=force_on_asset_change,
    )


def _dynamic_monthly_target_schedule(
    *,
    instruments: Mapping[str, Instrument],
    bars_by_symbol: Mapping[str, Sequence[PriceBar]],
    trade_dates: Sequence[date],
    lookback_bars: int,
    max_weight: Decimal,
    cash_reserve_weight: Decimal,
    sleeve_name: str,
    target_overlays: Sequence[TargetOverlay],
    min_weight_delta: Decimal = Decimal("0"),
    min_total_weight_delta: Decimal = Decimal("0"),
    force_on_asset_change: bool = False,
) -> dict[date, list[AllocationTarget]]:
    return _dynamic_target_schedule(
        instruments=instruments,
        bars_by_symbol=bars_by_symbol,
        trade_dates=trade_dates,
        rebalance_frequency="monthly",
        lookback_bars=lookback_bars,
        max_weight=max_weight,
        cash_reserve_weight=cash_reserve_weight,
        sleeve_name=sleeve_name,
        target_overlays=target_overlays,
        min_weight_delta=min_weight_delta,
        min_total_weight_delta=min_total_weight_delta,
        force_on_asset_change=force_on_asset_change,
    )


def _dynamic_daily_target_schedule(
    *,
    instruments: Mapping[str, Instrument],
    bars_by_symbol: Mapping[str, Sequence[PriceBar]],
    trade_dates: Sequence[date],
    lookback_bars: int,
    max_weight: Decimal,
    cash_reserve_weight: Decimal,
    sleeve_name: str,
    target_overlays: Sequence[TargetOverlay],
    min_weight_delta: Decimal = Decimal("0"),
    min_total_weight_delta: Decimal = Decimal("0"),
    force_on_asset_change: bool = False,
) -> dict[date, list[AllocationTarget]]:
    return _dynamic_target_schedule(
        instruments=instruments,
        bars_by_symbol=bars_by_symbol,
        trade_dates=trade_dates,
        rebalance_frequency="daily",
        lookback_bars=lookback_bars,
        max_weight=max_weight,
        cash_reserve_weight=cash_reserve_weight,
        sleeve_name=sleeve_name,
        target_overlays=target_overlays,
        min_weight_delta=min_weight_delta,
        min_total_weight_delta=min_total_weight_delta,
        force_on_asset_change=force_on_asset_change,
    )


def _rebalance_trade_dates(trade_dates: Sequence[date], rebalance_frequency: str) -> list[date]:
    frequency = rebalance_frequency.lower()
    if frequency == "daily":
        return list(trade_dates)
    if frequency == "monthly":
        result: list[date] = []
        seen_months: set[tuple[int, int]] = set()
        for trade_date in trade_dates:
            month_key = (trade_date.year, trade_date.month)
            if month_key in seen_months:
                continue
            seen_months.add(month_key)
            result.append(trade_date)
        return result
    raise ValueError(f"Unsupported rebalance_frequency '{rebalance_frequency}'. Use 'monthly' or 'daily'.")


def _apply_rebalance_gate(
    schedule: Mapping[date, Sequence[AllocationTarget]],
    *,
    min_weight_delta: Decimal,
    min_total_weight_delta: Decimal,
    force_on_asset_change: bool,
) -> dict[date, list[AllocationTarget]]:
    min_weight_delta = Decimal(min_weight_delta)
    min_total_weight_delta = Decimal(min_total_weight_delta)
    if min_weight_delta <= Decimal("0") and min_total_weight_delta <= Decimal("0") and not force_on_asset_change:
        return {trade_date: list(targets) for trade_date, targets in schedule.items()}

    gated: dict[date, list[AllocationTarget]] = {}
    last_weights: dict[str, Decimal] | None = None
    for trade_date, targets in sorted(schedule.items()):
        weights = _target_weights(targets)
        if last_weights is None or _rebalance_gate_triggered(
            previous=last_weights,
            candidate=weights,
            min_weight_delta=min_weight_delta,
            min_total_weight_delta=min_total_weight_delta,
            force_on_asset_change=force_on_asset_change,
        ):
            gated[trade_date] = list(targets)
            last_weights = weights
    if not gated:
        raise ValueError("No rebalance dates passed the rebalance gate.")
    return gated


def _rebalance_gate_triggered(
    *,
    previous: Mapping[str, Decimal],
    candidate: Mapping[str, Decimal],
    min_weight_delta: Decimal,
    min_total_weight_delta: Decimal,
    force_on_asset_change: bool,
) -> bool:
    symbols = set(previous) | set(candidate)
    deltas = [abs(candidate.get(symbol, Decimal("0")) - previous.get(symbol, Decimal("0"))) for symbol in symbols]
    if force_on_asset_change and _active_symbols(previous) != _active_symbols(candidate):
        return True
    if min_weight_delta > Decimal("0") and max(deltas, default=Decimal("0")) >= min_weight_delta:
        return True
    if min_total_weight_delta > Decimal("0") and sum(deltas, Decimal("0")) >= min_total_weight_delta:
        return True
    return False


def _target_weights(targets: Sequence[AllocationTarget]) -> dict[str, Decimal]:
    return {target.symbol: Decimal(target.target_weight) for target in targets}


def _active_symbols(weights: Mapping[str, Decimal]) -> set[str]:
    return {symbol for symbol, weight in weights.items() if weight > Decimal("0.0001")}


def _bars_and_dates_by_symbol(
    bars_by_symbol: Mapping[str, Sequence[PriceBar]],
) -> tuple[dict[str, list[PriceBar]], dict[str, list[date]]]:
    sorted_bars_by_symbol = {
        symbol: sorted(bars, key=lambda bar: bar.trade_date)
        for symbol, bars in bars_by_symbol.items()
    }
    dates_by_symbol = {
        symbol: [bar.trade_date for bar in bars]
        for symbol, bars in sorted_bars_by_symbol.items()
    }
    return sorted_bars_by_symbol, dates_by_symbol
