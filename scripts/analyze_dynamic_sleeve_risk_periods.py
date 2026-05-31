from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(SCRIPT_DIR))

from optimize_multi_asset_combined_stack import _stable_backtest_payload, _windowed_compare  # noqa: E402
from run_dynamic_sleeve_capped_research import (  # noqa: E402
    _case_from_row,
    _dynamic_monthly_target_schedule,
    _latest_bars_by_date,
    _latest_rate,
)
from systematic_trading.backtest.engine import DailyBacktestEngine  # noqa: E402
from systematic_trading.backtest.reporting import build_backtest_report_data  # noqa: E402
from systematic_trading.backtest.risk import inverse_volatility_weights  # noqa: E402
from systematic_trading.backtest.stored import (  # noqa: E402
    StoredRiskParityBacktestConfig,
    _open_prices_by_date,
    _previous_trade_dates,
    _prior_close_prices_by_date,
)
from systematic_trading.config import AppSettings  # noqa: E402
from systematic_trading.data.analytics import realized_volatility_from_bars  # noqa: E402
from systematic_trading.domain.enums import Currency  # noqa: E402
from systematic_trading.domain.portfolio import AllocationTarget, CashBalance  # noqa: E402
from systematic_trading.research import ALL_WEATHER_ETF_UNIVERSE, current_sota_definition  # noqa: E402
from systematic_trading.storage.sqlite import SQLiteStore  # noqa: E402


TRADING_DAYS_PER_YEAR = 252


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect weak periods for the dynamic sleeve-capped strategy.")
    parser.add_argument("--database", default=None)
    parser.add_argument("--input-dir", default="var/backtests/dynamic_sleeve_capped_research")
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--output-md", default=None)
    parser.add_argument("--start-date", default="2012-01-01")
    parser.add_argument("--end-date", default="2026-04-29")
    parser.add_argument("--oos-date", default="2023-01-01")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_json = Path(args.output_json) if args.output_json else input_dir / "risk_period_analysis.json"
    output_md = Path(args.output_md) if args.output_md else input_dir / "risk_period_analysis.md"
    database_path = Path(args.database) if args.database else AppSettings().database_path
    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)
    oos_date = date.fromisoformat(args.oos_date)

    winner_payload = json.loads((input_dir / "optimized_dynamic_sleeve_capped_stack.json").read_text(encoding="utf-8"))
    current_sota_payload = json.loads((input_dir / "current_sota.json").read_text(encoding="utf-8"))
    optimization = json.loads((input_dir / "optimization_results.json").read_text(encoding="utf-8"))

    report, warnings = build_backtest_report_data(
        result=winner_payload,
        result_path=input_dir / "optimized_dynamic_sleeve_capped_stack.json",
        database_path=database_path,
        split_date=oos_date,
        benchmark_nav_series=current_sota_payload["nav_series"],
        benchmark_name=current_sota_definition().name,
    )
    periods = _period_diagnostics(report, current_sota_payload)

    store = SQLiteStore(database_path)
    store.initialize()
    daily_reweight_payload = _run_daily_reweight_variant(
        store=store,
        winner_row=optimization["winner"],
        start_date=start_date,
        end_date=end_date,
        initial_cash_cnh=Decimal("1000000"),
        trigger_threshold=Decimal("0.05"),
        vol_spike_multiplier=Decimal("1.50"),
    )

    variants = {
        "base": winner_payload,
        "portfolio_vol_control_63d_15pct": _scaled_nav_payload(
            winner_payload,
            name="Portfolio vol control 63d target 15%",
            exposures=_vol_control_exposures(winner_payload, lookback=63, target_vol=0.15, max_exposure=1.0),
        ),
        "portfolio_drawdown_throttle_8pct_half": _scaled_nav_payload(
            winner_payload,
            name="Portfolio drawdown throttle 8% half exposure",
            exposures=_drawdown_throttle_exposures(winner_payload, threshold=-0.08, scaled_exposure=0.50),
        ),
        "portfolio_stop_loss_10pct_21d": _scaled_nav_payload(
            winner_payload,
            name="Portfolio stop loss 10% 21d cooldown",
            exposures=_stop_loss_exposures(winner_payload, threshold=-0.10, cooldown_days=21),
        ),
        "daily_inverse_vol_reweight_trigger": daily_reweight_payload,
    }
    variant_rows = [
        _variant_row(key, payload, current_sota_payload, oos_date, periods)
        for key, payload in variants.items()
    ]

    analysis = {
        "warnings": warnings,
        "periods": periods,
        "riskControlTests": variant_rows,
        "notes": [
            "Portfolio overlays use only prior-close strategy returns for triggers.",
            "The daily reweight test keeps monthly ETF selection but rebalances selected assets if inverse-vol target weights move by at least 5 percentage points or selected-asset vol rises 1.5x versus the monthly selection date.",
        ],
    }
    output_json.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    output_md.write_text(_markdown(analysis), encoding="utf-8")
    print(output_json)
    print(output_md)


def _period_diagnostics(report: Mapping[str, Any], current_sota_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    period_specs = [
        ("2022-06", "monthly"),
        ("2022-Q4", "quarterly"),
        ("2023-Q1", "quarterly"),
    ]
    current_sota_nav = _nav_by_date(current_sota_payload)
    diagnostics: list[dict[str, Any]] = []
    for period, frequency in period_specs:
        metrics = _find_period_metric(report["metricsByBenchmark"]["primary"][frequency], period)
        contributions = _find_contribution_period(report["holdingContributions"][frequency], period)
        if metrics is None or contributions is None:
            continue
        start = date.fromisoformat(contributions["start"])
        end = date.fromisoformat(contributions["end"])
        sota_return = _window_return(current_sota_nav, start, end)
        top_negative = sorted(
            [item for item in contributions["holdings"] if item["contribution"] < 0],
            key=lambda item: item["contribution"],
        )[:6]
        top_positive = sorted(
            [item for item in contributions["holdings"] if item["contribution"] > 0],
            key=lambda item: item["contribution"],
            reverse=True,
        )[:6]
        diagnostics.append(
            {
                "period": period,
                "frequency": frequency,
                "start": contributions["start"],
                "end": contributions["end"],
                "strategyReturn": metrics["return"],
                "currentSotaReturn": sota_return,
                "activeReturnVsCurrentSota": (
                    metrics["return"] - sota_return if sota_return is not None and metrics["return"] is not None else None
                ),
                "maxDrawdown": metrics["maxDrawdown"],
                "topNegativeContributors": top_negative,
                "topPositiveContributors": top_positive,
            }
        )
    return diagnostics


def _run_daily_reweight_variant(
    *,
    store: SQLiteStore,
    winner_row: Mapping[str, Any],
    start_date: date,
    end_date: date,
    initial_cash_cnh: Decimal,
    trigger_threshold: Decimal,
    vol_spike_multiplier: Decimal,
) -> dict[str, Any]:
    case = _case_from_row(winner_row, optimized=True)
    config = StoredRiskParityBacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_cash_cnh=initial_cash_cnh,
        sleeve_name="dynamic-sleeve-daily-reweight-trigger",
    )
    bars_by_symbol = {
        symbol: store.list_price_bars(symbol, start_date=config.start_date, end_date=config.end_date)
        for symbol in ALL_WEATHER_ETF_UNIVERSE
    }
    trade_dates = sorted({bar.trade_date for bars in bars_by_symbol.values() for bar in bars})
    trade_dates = [item for item in trade_dates if config.start_date <= item <= config.end_date]
    fx_rates = store.list_fx_rates(Currency.USD, start_date=config.start_date, end_date=config.end_date)
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
    monthly_schedule = _dynamic_monthly_target_schedule(
        instruments=ALL_WEATHER_ETF_UNIVERSE,
        bars_by_symbol=bars_by_symbol,
        trade_dates=trade_dates,
        lookback_bars=config.lookback_bars,
        max_weight=config.max_weight,
        cash_reserve_weight=config.cash_reserve_weight,
        sleeve_name=config.sleeve_name,
        target_overlays=case["overlays"],
    )
    target_schedule = _daily_reweight_schedule(
        bars_by_symbol=bars_by_symbol,
        trade_dates=trade_dates,
        monthly_schedule=monthly_schedule,
        lookback_bars=config.lookback_bars,
        max_weight=config.max_weight,
        sleeve_name=config.sleeve_name,
        trigger_threshold=trigger_threshold,
        vol_spike_multiplier=vol_spike_multiplier,
    )
    result = DailyBacktestEngine().run(
        trade_dates=trade_dates,
        instruments=ALL_WEATHER_ETF_UNIVERSE,
        initial_cash=[CashBalance(currency=Currency.CNH, amount=config.initial_cash_cnh)],
        daily_prices=daily_prices,
        daily_fx_to_cnh=daily_fx,
        target_schedule=target_schedule,
        daily_rebalance_prices=daily_rebalance_prices,
        daily_execution_prices=daily_execution_prices,
        decision_dates_by_trade_date=_previous_trade_dates(trade_dates),
        sleeve=config.sleeve_name,
    )
    payload = _stable_backtest_payload(result.model_dump(mode="json"))
    payload["researchCase"] = {
        "name": "Daily inverse-vol reweight trigger",
        "params": {
            "triggerThreshold": str(trigger_threshold),
            "volSpikeMultiplier": str(vol_spike_multiplier),
        },
        "stack": "monthly dynamic selection -> daily inverse-vol reweight trigger",
    }
    return payload


def _daily_reweight_schedule(
    *,
    bars_by_symbol: Mapping[str, Sequence[Any]],
    trade_dates: Sequence[date],
    monthly_schedule: Mapping[date, Sequence[AllocationTarget]],
    lookback_bars: int,
    max_weight: Decimal,
    sleeve_name: str,
    trigger_threshold: Decimal,
    vol_spike_multiplier: Decimal,
) -> dict[date, list[AllocationTarget]]:
    schedule: dict[date, list[AllocationTarget]] = {}
    selected: list[str] = []
    gross_weight = Decimal("0")
    monthly_vols: dict[str, Decimal] = {}
    last_targets: dict[str, Decimal] = {}
    rationale_by_symbol: dict[str, str] = {}

    for trade_date in trade_dates:
        if trade_date in monthly_schedule:
            monthly_targets = list(monthly_schedule[trade_date])
            selected = [target.symbol for target in monthly_targets if target.target_weight > Decimal("0.0001")]
            gross_weight = sum((target.target_weight for target in monthly_targets if target.symbol in selected), Decimal("0"))
            monthly_vols = _volatility_map(bars_by_symbol, selected, trade_date, lookback_bars)
            rationale_by_symbol = {target.symbol: target.rationale for target in monthly_targets}
            last_targets = {target.symbol: target.target_weight for target in monthly_targets if target.symbol in selected}
            schedule[trade_date] = monthly_targets
            continue

        if not selected or gross_weight <= Decimal("0"):
            continue
        vols = _volatility_map(bars_by_symbol, selected, trade_date, lookback_bars)
        if set(vols) != set(selected):
            continue
        candidate = _inverse_vol_targets(
            selected=selected,
            volatility_by_symbol=vols,
            gross_weight=gross_weight,
            max_weight=max_weight,
            sleeve_name=sleeve_name,
            rationale_by_symbol=rationale_by_symbol,
            trade_date=trade_date,
        )
        candidate_weights = {target.symbol: target.target_weight for target in candidate}
        max_drift = max(
            (abs(candidate_weights.get(symbol, Decimal("0")) - last_targets.get(symbol, Decimal("0"))) for symbol in selected),
            default=Decimal("0"),
        )
        vol_spiked = any(
            monthly_vols.get(symbol, Decimal("0")) > Decimal("0")
            and vols[symbol] >= monthly_vols[symbol] * vol_spike_multiplier
            for symbol in selected
        )
        if max_drift >= trigger_threshold or vol_spiked:
            schedule[trade_date] = candidate
            last_targets = candidate_weights
    return schedule


def _inverse_vol_targets(
    *,
    selected: Sequence[str],
    volatility_by_symbol: Mapping[str, Decimal],
    gross_weight: Decimal,
    max_weight: Decimal,
    sleeve_name: str,
    rationale_by_symbol: Mapping[str, str],
    trade_date: date,
) -> list[AllocationTarget]:
    if len(selected) == 1:
        weights = {selected[0]: Decimal("1")}
    else:
        adjusted_max = max(max_weight, (Decimal("1") / Decimal(len(selected))).quantize(Decimal("0.0001")))
        weights = inverse_volatility_weights(volatility_by_symbol, max_weight=adjusted_max)
    targets = []
    for symbol in selected:
        target_weight = weights[symbol] * gross_weight
        targets.append(
            AllocationTarget(
                symbol=symbol,
                target_weight=target_weight,
                sleeve=sleeve_name,
                rationale=(
                    f"{rationale_by_symbol.get(symbol, 'Monthly selected asset.')} "
                    f"Daily reweight trigger reset {symbol} to inverse-vol weight on {trade_date}."
                ),
            )
        )
    return targets


def _volatility_map(
    bars_by_symbol: Mapping[str, Sequence[Any]],
    symbols: Sequence[str],
    trade_date: date,
    lookback_bars: int,
) -> dict[str, Decimal]:
    vols: dict[str, Decimal] = {}
    for symbol in symbols:
        history = [bar for bar in bars_by_symbol[symbol] if bar.trade_date < trade_date]
        if len(history) < lookback_bars + 1:
            continue
        volatility = realized_volatility_from_bars(history[-(lookback_bars + 1) :])
        if volatility > Decimal("0"):
            vols[symbol] = volatility
    return vols


def _vol_control_exposures(
    payload: Mapping[str, Any],
    *,
    lookback: int,
    target_vol: float,
    max_exposure: float,
) -> list[float]:
    returns = _daily_returns(payload)
    exposures = [1.0]
    for index in range(1, len(_nav_series(payload))):
        history = returns[max(0, index - lookback) : index]
        if len(history) < max(10, lookback // 2):
            exposures.append(1.0)
            continue
        vol = _stddev(history) * math.sqrt(TRADING_DAYS_PER_YEAR)
        exposures.append(min(max_exposure, target_vol / vol) if vol > 0 else 1.0)
    return exposures


def _drawdown_throttle_exposures(
    payload: Mapping[str, Any],
    *,
    threshold: float,
    scaled_exposure: float,
) -> list[float]:
    navs = [item[1] for item in _nav_series(payload)]
    exposures = [1.0]
    peak = navs[0]
    for index in range(1, len(navs)):
        previous_nav = navs[index - 1]
        peak = max(peak, previous_nav)
        drawdown = (previous_nav / peak) - 1
        exposures.append(scaled_exposure if drawdown <= threshold else 1.0)
    return exposures


def _stop_loss_exposures(
    payload: Mapping[str, Any],
    *,
    threshold: float,
    cooldown_days: int,
) -> list[float]:
    navs = [item[1] for item in _nav_series(payload)]
    exposures = [1.0]
    peak = navs[0]
    cooldown = 0
    for index in range(1, len(navs)):
        previous_nav = navs[index - 1]
        peak = max(peak, previous_nav)
        drawdown = (previous_nav / peak) - 1
        if cooldown > 0:
            exposures.append(0.0)
            cooldown -= 1
            continue
        if drawdown <= threshold:
            exposures.append(0.0)
            cooldown = cooldown_days - 1
            continue
        exposures.append(1.0)
    return exposures


def _scaled_nav_payload(payload: Mapping[str, Any], *, name: str, exposures: Sequence[float]) -> dict[str, Any]:
    nav_series = _nav_series(payload)
    scaled_nav = nav_series[0][1]
    rows = [
        {
            "trade_date": nav_series[0][0].isoformat(),
            "nav_cnh": f"{scaled_nav:.2f}",
            "gross_exposure_cnh": "0.00",
            "cash_cnh": f"{scaled_nav:.2f}",
        }
    ]
    for index in range(1, len(nav_series)):
        previous_nav = nav_series[index - 1][1]
        current_nav = nav_series[index][1]
        daily_return = (current_nav / previous_nav) - 1 if previous_nav else 0.0
        scaled_nav *= 1 + daily_return * exposures[index - 1]
        rows.append(
            {
                "trade_date": nav_series[index][0].isoformat(),
                "nav_cnh": f"{scaled_nav:.2f}",
                "gross_exposure_cnh": f"{scaled_nav * exposures[index]:.2f}",
                "cash_cnh": f"{scaled_nav * (1 - exposures[index]):.2f}",
            }
        )
    return {"nav_series": rows, "proposals": [], "final_snapshot": {"positions": []}, "researchCase": {"name": name}}


def _variant_row(
    key: str,
    payload: Mapping[str, Any],
    current_sota_payload: Mapping[str, Any],
    oos_date: date,
    periods: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    comparison = _windowed_compare(
        baseline=current_sota_payload,
        candidate=payload,
        baseline_name=current_sota_definition().name,
        candidate_name=key,
        validation_date=date(2020, 1, 1),
        oos_date=oos_date,
    )
    metrics = comparison["metrics"]["out_of_sample"]["candidate"]
    active = comparison["metrics"]["out_of_sample"]["active"]
    nav = _nav_by_date(payload)
    period_returns = {
        period["period"]: _window_return(
            nav,
            date.fromisoformat(str(period["start"])),
            date.fromisoformat(str(period["end"])),
        )
        for period in periods
    }
    return {
        "key": key,
        "name": payload.get("researchCase", {}).get("name", key),
        "oosAnnualizedReturn": metrics["annualizedReturn"],
        "oosSharpe": metrics["sharpe"],
        "oosCalmar": metrics["calmar"],
        "oosMaxDrawdown": metrics["maxDrawdown"],
        "oosInformationRatioVsCurrentSota": active["informationRatio"],
        "periodReturns": period_returns,
    }


def _find_period_metric(rows: Sequence[Mapping[str, Any]], period: str) -> Mapping[str, Any] | None:
    return next((row for row in rows if row.get("period") == period), None)


def _find_contribution_period(rows: Sequence[Mapping[str, Any]], period: str) -> Mapping[str, Any] | None:
    return next((row for row in rows if row.get("period") == period), None)


def _nav_series(payload: Mapping[str, Any]) -> list[tuple[date, float]]:
    return [
        (date.fromisoformat(str(item["trade_date"])), float(item["nav_cnh"]))
        for item in payload.get("nav_series", [])
    ]


def _nav_by_date(payload: Mapping[str, Any]) -> dict[date, float]:
    return dict(_nav_series(payload))


def _daily_returns(payload: Mapping[str, Any]) -> list[float]:
    nav = _nav_series(payload)
    return [
        (nav[index][1] / nav[index - 1][1]) - 1
        for index in range(1, len(nav))
        if nav[index - 1][1] != 0
    ]


def _window_return(nav_by_date: Mapping[date, float], start: date, end: date) -> float | None:
    available = sorted(day for day in nav_by_date if start <= day <= end)
    if len(available) < 2:
        return None
    start_nav = nav_by_date[available[0]]
    end_nav = nav_by_date[available[-1]]
    return (end_nav / start_nav) - 1 if start_nav else None


def _stddev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def _markdown(analysis: Mapping[str, Any]) -> str:
    lines = [
        "# Dynamic Sleeve-Capped Risk Period Analysis",
        "",
        "## Period Inspection",
        "",
    ]
    for period in analysis["periods"]:
        lines.extend(
            [
                f"### {period['period']}",
                "",
                f"- Window: {period['start']} to {period['end']}",
                f"- Strategy return: {_fmt_pct(period['strategyReturn'])}",
                f"- Current SOTA return: {_fmt_pct(period['currentSotaReturn'])}",
                f"- Active return vs SOTA: {_fmt_pct(period['activeReturnVsCurrentSota'])}",
                f"- Period max drawdown: {_fmt_pct(period['maxDrawdown'])}",
                "",
                "| Negative contributor | Avg wt | Asset return | Contribution |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for item in period["topNegativeContributors"]:
            lines.append(
                f"| {item['symbol']} | {_fmt_pct(item['averageWeight'])} | "
                f"{_fmt_pct(item['assetReturn'])} | {_fmt_pct(item['contribution'])} |"
            )
        lines.extend(["", "| Positive contributor | Avg wt | Asset return | Contribution |", "| --- | ---: | ---: | ---: |"])
        for item in period["topPositiveContributors"]:
            lines.append(
                f"| {item['symbol']} | {_fmt_pct(item['averageWeight'])} | "
                f"{_fmt_pct(item['assetReturn'])} | {_fmt_pct(item['contribution'])} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Risk-Control Tests",
            "",
            "| Variant | OOS ann. return | OOS Sharpe | OOS Calmar | OOS max DD | OOS IR vs SOTA | 2022-06 | 2022-Q4 | 2023-Q1 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in analysis["riskControlTests"]:
        period_returns = row["periodReturns"]
        lines.append(
            f"| {row['name']} | {_fmt_pct(row['oosAnnualizedReturn'])} | {_fmt_num(row['oosSharpe'])} | "
            f"{_fmt_num(row['oosCalmar'])} | {_fmt_pct(row['oosMaxDrawdown'])} | "
            f"{_fmt_num(row['oosInformationRatioVsCurrentSota'])} | {_fmt_pct(period_returns.get('2022-06'))} | "
            f"{_fmt_pct(period_returns.get('2022-Q4'))} | {_fmt_pct(period_returns.get('2023-Q1'))} |"
        )
    if analysis.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in analysis["warnings"])
    lines.append("")
    return "\n".join(lines)


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def _fmt_num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


if __name__ == "__main__":
    main()
