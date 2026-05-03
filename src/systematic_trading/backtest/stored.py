from __future__ import annotations

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
    daily_fx = {
        trade_date: {Currency.USD: _latest_rate(usd_cnh_by_date, trade_date)}
        for trade_date in common_dates
    }
    target_schedule = _monthly_target_schedule(
        instruments=instruments,
        bars_by_symbol=bars_by_symbol,
        trade_dates=common_dates,
        lookback_bars=config.lookback_bars,
        max_weight=config.max_weight,
        cash_reserve_weight=config.cash_reserve_weight,
        sleeve_name=config.sleeve_name,
        target_overlays=target_overlays or (),
    )

    engine = DailyBacktestEngine()
    return engine.run(
        trade_dates=common_dates,
        instruments=instruments,
        initial_cash=[CashBalance(currency=Currency.CNH, amount=config.initial_cash_cnh)],
        daily_prices=daily_prices,
        daily_fx_to_cnh=daily_fx,
        target_schedule=target_schedule,
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
) -> dict[date, list[AllocationTarget]]:
    sleeve = RiskParityBetaSleeve(name=sleeve_name, max_weight=max_weight)
    schedule: dict[date, list[AllocationTarget]] = {}
    seen_months: set[tuple[int, int]] = set()

    for trade_date in trade_dates:
        month_key = (trade_date.year, trade_date.month)
        if month_key in seen_months:
            continue
        seen_months.add(month_key)

        states: list[BetaInstrumentState] = []
        for symbol, instrument in instruments.items():
            history = [bar for bar in bars_by_symbol[symbol] if bar.trade_date < trade_date]
            if len(history) < lookback_bars + 1:
                break
            lookback = history[-(lookback_bars + 1) :]
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
    return schedule
