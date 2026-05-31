from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(SCRIPT_DIR))

from optimize_multi_asset_combined_stack import (  # noqa: E402
    _buy_and_hold_payload,
    _sort_value,
    _stable_backtest_payload,
    _windowed_compare,
)
from systematic_trading.backtest.engine import DailyBacktestEngine  # noqa: E402
from systematic_trading.backtest.reporting import write_backtest_report  # noqa: E402
from systematic_trading.backtest.stability import (  # noqa: E402
    TARGET_RETENTION_HIGH,
    TARGET_RETENTION_LOW,
    percentile_scores,
    retention_band_distance,
    retention_band_pass,
    retention_closeness_scores,
    sharpe_retention_ratio,
)
from systematic_trading.backtest.stored import (  # noqa: E402
    StoredRiskParityBacktestConfig,
    _open_prices_by_date,
    _previous_trade_dates,
    _prior_close_prices_by_date,
    run_stored_risk_parity_backtest,
)
from systematic_trading.config import AppSettings  # noqa: E402
from systematic_trading.data.analytics import realized_volatility_from_bars  # noqa: E402
from systematic_trading.domain.enums import Currency  # noqa: E402
from systematic_trading.domain.market import Instrument, PriceBar  # noqa: E402
from systematic_trading.domain.portfolio import AllocationTarget, CashBalance  # noqa: E402
from systematic_trading.portfolio.beta import BetaInstrumentState, RiskParityBetaSleeve  # noqa: E402
from systematic_trading.research import (  # noqa: E402
    ALL_WEATHER_ETF_UNIVERSE,
    ALL_WEATHER_SPEC_BY_SYMBOL,
    GLOBAL_ETF_UNIVERSE,
    MSCI_WORLD_PROXY_NAME,
    MSCI_WORLD_PROXY_SYMBOL,
    MULTI_ASSET_BENCHMARK_NAME,
    MULTI_ASSET_BENCHMARK_SYMBOL,
    current_sota_definition,
    grouped_counts,
    instantiate_overlays,
)
from systematic_trading.signals import CommodityRiskGuardOverlay, SleeveCappedMomentumOverlay  # noqa: E402
from systematic_trading.signals.base import SignalContext, TargetOverlay  # noqa: E402
from systematic_trading.storage.sqlite import SQLiteStore  # noqa: E402


_WORKER_DATABASE_PATH: str | None = None
_WORKER_START_DATE: date | None = None
_WORKER_END_DATE: date | None = None
_WORKER_VALIDATION_DATE: date | None = None
_WORKER_OOS_DATE: date | None = None
_WORKER_INITIAL_CASH_CNH: Decimal | None = None
_WORKER_BASELINE_PAYLOADS: Mapping[str, dict[str, Any]] | None = None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run dynamic eligible-universe sleeve-capped momentum research plus SOTA tilt."
    )
    parser.add_argument("--database", default=None)
    parser.add_argument("--start-date", default="2012-01-01")
    parser.add_argument("--end-date", default="2026-04-29")
    parser.add_argument("--validation-date", default="2020-01-01")
    parser.add_argument("--oos-date", default="2023-01-01")
    parser.add_argument("--initial-cash-cnh", default="1000000")
    parser.add_argument("--output-dir", default="var/backtests/dynamic_sleeve_capped_research")
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--workers", type=int, default=min(os.cpu_count() or 1, 8))
    parser.add_argument(
        "--grid-mode",
        choices=["full", "risk-controls"],
        default="full",
        help="Use the original broad grid or a focused grid for commodity guard/rates-minimum tests.",
    )
    args = parser.parse_args()

    settings = AppSettings()
    database_path = Path(args.database) if args.database else settings.database_path
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(database_path)
    store.initialize()

    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)
    validation_date = date.fromisoformat(args.validation_date)
    oos_date = date.fromisoformat(args.oos_date)
    initial_cash_cnh = Decimal(args.initial_cash_cnh)

    baseline_payloads = _baseline_payloads(
        store=store,
        start_date=start_date,
        end_date=end_date,
        initial_cash_cnh=initial_cash_cnh,
    )
    grid = list(_risk_control_parameter_grid() if args.grid_mode == "risk-controls" else _parameter_grid())
    if args.max_cases is not None:
        grid = grid[: args.max_cases]

    tasks = list(enumerate(grid, start=1))
    workers = max(1, min(args.workers, len(tasks)))
    rows = _run_grid(
        tasks=tasks,
        workers=workers,
        database_path=database_path,
        start_date=start_date,
        end_date=end_date,
        validation_date=validation_date,
        oos_date=oos_date,
        initial_cash_cnh=initial_cash_cnh,
        baseline_payloads=baseline_payloads,
    )
    _score_rows(rows)
    ranked = sorted(rows, key=lambda row: row["validationObjectiveScore"], reverse=True)
    winner = ranked[0]
    winner_case = _case_from_row(winner, optimized=True)
    winner_payload = _run_candidate_payload(
        store=store,
        case=winner_case,
        start_date=start_date,
        end_date=end_date,
        initial_cash_cnh=initial_cash_cnh,
    )

    winner_path = output_dir / "optimized_dynamic_sleeve_capped_stack.json"
    winner_path.write_text(json.dumps(winner_payload, indent=2), encoding="utf-8")
    (output_dir / "current_sota.json").write_text(json.dumps(baseline_payloads["current_sota"]["payload"], indent=2), encoding="utf-8")
    (output_dir / "dynamic_all_weather_risk_parity.json").write_text(json.dumps(baseline_payloads["dynamic_all_weather_risk_parity"]["payload"], indent=2), encoding="utf-8")

    report = write_backtest_report(
        result_path=winner_path,
        output_path=output_dir / "optimized_dynamic_sleeve_capped_stack.html",
        database_path=database_path,
        split_date=oos_date,
        benchmark_symbol=MULTI_ASSET_BENCHMARK_SYMBOL,
        benchmark_name=MULTI_ASSET_BENCHMARK_NAME,
        extra_benchmarks=[
            {
                "id": "current_sota",
                "name": current_sota_definition().name,
                "nav_series": baseline_payloads["current_sota"]["payload"]["nav_series"],
            },
            {
                "id": "dynamic_all_weather_risk_parity",
                "name": "Dynamic all-weather risk parity",
                "nav_series": baseline_payloads["dynamic_all_weather_risk_parity"]["payload"]["nav_series"],
            },
            {
                "id": "msci_world",
                "name": MSCI_WORLD_PROXY_NAME,
                "symbol": MSCI_WORLD_PROXY_SYMBOL,
            },
        ],
    )
    if report.warnings:
        (output_dir / "optimized_dynamic_sleeve_capped_stack_report_warnings.txt").write_text(
            "\n".join(report.warnings) + "\n",
            encoding="utf-8",
        )

    results = {
        "method": {
            "candidateCount": len(rows),
            "workers": workers,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "validationDate": validation_date.isoformat(),
            "oosDate": oos_date.isoformat(),
            "stack": "dynamic eligibility -> global momentum rank -> sleeve/asset/region caps -> SOTA relative momentum",
            "gridMode": args.grid_mode,
            "objective": (
                "Pre-OOS stability-adjusted score: validation IR vs current SOTA, validation Sharpe, "
                "validation Calmar, validation IR vs dynamic all-weather risk parity, and validation/train "
                f"Sharpe retention closeness to {TARGET_RETENTION_LOW:.2f}-{TARGET_RETENTION_HIGH:.2f}."
            ),
        },
        "universeCounts": grouped_counts(),
        "winner": winner,
        "rankedCandidates": ranked,
        "bestOosByCurrentSotaIR": sorted(
            rows,
            key=lambda row: _sort_value(row["oosInformationRatioVsCurrentSota"]),
            reverse=True,
        )[:15],
    }
    results_json = output_dir / "optimization_results.json"
    results_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    results_md = output_dir / "optimization_results.md"
    results_md.write_text(_results_markdown(results), encoding="utf-8")
    model_card_path = output_dir / "optimized_model_card.html"
    _write_model_card(path=model_card_path, winner=winner)
    readme_path = output_dir / "README.md"
    readme_path.write_text(_readme(results=results, output_dir=output_dir), encoding="utf-8")

    for path in [
        results_md,
        results_json,
        winner_path,
        report.output_path,
        model_card_path,
        readme_path,
    ]:
        print(path)


def _parameter_grid() -> Sequence[dict[str, Any]]:
    lookback_sets = [(21, 63, 126), (21, 63, 252), (21, 126, 252), (63, 126, 252)]
    weight_sets = [(Decimal("1.00"), Decimal("0.00")), (Decimal("0.80"), Decimal("0.20")), (Decimal("0.75"), Decimal("0.25"))]
    cases: list[dict[str, Any]] = []
    for short, medium, long in lookback_sets:
        for trend_weight, volume_weight in weight_sets:
            for top_n in [3, 4, 5]:
                for max_per_sleeve in [1, 2]:
                    for cap_profile in _cap_profiles():
                        cases.append(
                            {
                                "short_momentum_bars": short,
                                "medium_momentum_bars": medium,
                                "long_momentum_bars": long,
                                "trend_weight": trend_weight,
                                "volume_weight": volume_weight,
                                "top_n": top_n,
                                "max_per_sleeve": max_per_sleeve,
                                "cap_profile": cap_profile["name"],
                                "max_per_asset_class": cap_profile["assetClass"],
                                "max_per_region": cap_profile["region"],
                            }
                        )
    return cases


def _risk_control_parameter_grid() -> Sequence[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    base = {
        "short_momentum_bars": 21,
        "medium_momentum_bars": 63,
        "long_momentum_bars": 252,
        "trend_weight": Decimal("0.80"),
        "volume_weight": Decimal("0.20"),
        "top_n": 3,
    }
    for cap_profile in _cap_profiles():
        if cap_profile["name"] not in {"balanced_caps", "defensive_caps"}:
            continue
        for max_per_sleeve in [1, 2]:
            for force_rates in [False, True]:
                for guard_profile in _commodity_guard_profiles():
                    for daily_control in _daily_control_profiles():
                        if guard_profile["name"] != "none" and daily_control["name"] != "none":
                            continue
                        cases.append(
                            {
                                **base,
                                "max_per_sleeve": max_per_sleeve,
                                "cap_profile": cap_profile["name"],
                                "max_per_asset_class": cap_profile["assetClass"],
                                "min_per_asset_class": {"rates": 1} if force_rates else {},
                                "max_per_region": cap_profile["region"],
                                "commodity_guard": guard_profile,
                                "daily_control": daily_control,
                            }
                        )
    return cases


def _cap_profiles() -> list[dict[str, Any]]:
    base_region = {
        "US": 2,
        "Europe": 1,
        "China": 1,
        "Asia ex-China": 1,
        "Global ex-US": 2,
        "Energy": 1,
        "Base metals": 1,
        "Precious metals": 1,
        "Agriculture": 1,
    }
    return [
        {
            "name": "balanced_caps",
            "assetClass": {"equity": 2, "rates": 2, "credit": 1, "commodity": 2},
            "region": base_region,
        },
        {
            "name": "momentum_caps",
            "assetClass": {"equity": 3, "rates": 2, "credit": 1, "commodity": 2},
            "region": base_region | {"US": 3},
        },
        {
            "name": "defensive_caps",
            "assetClass": {"equity": 2, "rates": 3, "credit": 1, "commodity": 2},
            "region": base_region,
        },
    ]


def _commodity_guard_profiles() -> list[dict[str, Any]]:
    return [
        {"name": "none"},
        {
            "name": "monthly_commodity_guard_55",
            "maxAssetClassWeight": Decimal("0.55"),
            "triggeredScale": Decimal("0.50"),
            "shortMomentumBars": 10,
            "slowMomentumBars": 21,
            "shortMomentumThreshold": Decimal("-0.05"),
            "fastVolatilityBars": 10,
            "slowVolatilityBars": 63,
            "volatilitySpikeMultiple": Decimal("1.50"),
        },
        {
            "name": "monthly_commodity_guard_45",
            "maxAssetClassWeight": Decimal("0.45"),
            "triggeredScale": Decimal("0.50"),
            "shortMomentumBars": 10,
            "slowMomentumBars": 21,
            "shortMomentumThreshold": Decimal("-0.05"),
            "fastVolatilityBars": 10,
            "slowVolatilityBars": 63,
            "volatilitySpikeMultiple": Decimal("1.50"),
        },
    ]


def _daily_control_profiles() -> list[dict[str, Any]]:
    return [
        {"name": "none"},
        {
            "name": "daily_commodity_guard_55",
            "triggerThreshold": Decimal("0.03"),
            "commodityGuard": _commodity_guard_profiles()[1],
        },
        {
            "name": "daily_commodity_guard_45",
            "triggerThreshold": Decimal("0.03"),
            "commodityGuard": _commodity_guard_profiles()[2],
        },
    ]


def _run_grid(
    *,
    tasks: Sequence[tuple[int, dict[str, Any]]],
    workers: int,
    database_path: Path,
    start_date: date,
    end_date: date,
    validation_date: date,
    oos_date: date,
    initial_cash_cnh: Decimal,
    baseline_payloads: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if workers == 1:
        _init_worker(str(database_path), start_date.isoformat(), end_date.isoformat(), validation_date.isoformat(), oos_date.isoformat(), str(initial_cash_cnh), baseline_payloads)
        return [_run_candidate_task(task) for task in tasks]

    rows: list[dict[str, Any]] = []
    completed = 0
    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_worker,
        initargs=(str(database_path), start_date.isoformat(), end_date.isoformat(), validation_date.isoformat(), oos_date.isoformat(), str(initial_cash_cnh), baseline_payloads),
    ) as executor:
        futures = [executor.submit(_run_candidate_task, task) for task in tasks]
        for future in as_completed(futures):
            rows.append(future.result())
            completed += 1
            if completed == 1 or completed % 20 == 0 or completed == len(tasks):
                print(f"completed {completed}/{len(tasks)} dynamic sleeve-capped cases with {workers} workers", flush=True)
    return rows


def _init_worker(
    database_path: str,
    start_date: str,
    end_date: str,
    validation_date: str,
    oos_date: str,
    initial_cash_cnh: str,
    baseline_payloads: Mapping[str, dict[str, Any]],
) -> None:
    global _WORKER_DATABASE_PATH
    global _WORKER_START_DATE
    global _WORKER_END_DATE
    global _WORKER_VALIDATION_DATE
    global _WORKER_OOS_DATE
    global _WORKER_INITIAL_CASH_CNH
    global _WORKER_BASELINE_PAYLOADS
    _WORKER_DATABASE_PATH = database_path
    _WORKER_START_DATE = date.fromisoformat(start_date)
    _WORKER_END_DATE = date.fromisoformat(end_date)
    _WORKER_VALIDATION_DATE = date.fromisoformat(validation_date)
    _WORKER_OOS_DATE = date.fromisoformat(oos_date)
    _WORKER_INITIAL_CASH_CNH = Decimal(initial_cash_cnh)
    _WORKER_BASELINE_PAYLOADS = baseline_payloads


def _run_candidate_task(task: tuple[int, dict[str, Any]]) -> dict[str, Any]:
    if (
        _WORKER_DATABASE_PATH is None
        or _WORKER_START_DATE is None
        or _WORKER_END_DATE is None
        or _WORKER_VALIDATION_DATE is None
        or _WORKER_OOS_DATE is None
        or _WORKER_INITIAL_CASH_CNH is None
        or _WORKER_BASELINE_PAYLOADS is None
    ):
        raise RuntimeError("Dynamic sleeve-capped worker was not initialized.")
    index, params = task
    store = SQLiteStore(Path(_WORKER_DATABASE_PATH))
    case = _case(index, params)
    payload = _run_candidate_payload(
        store=store,
        case=case,
        start_date=_WORKER_START_DATE,
        end_date=_WORKER_END_DATE,
        initial_cash_cnh=_WORKER_INITIAL_CASH_CNH,
    )
    comparisons = _comparisons(
        candidate_payload=payload,
        candidate_name=case["name"],
        baseline_payloads=_WORKER_BASELINE_PAYLOADS,
        validation_date=_WORKER_VALIDATION_DATE,
        oos_date=_WORKER_OOS_DATE,
    )
    return _row(case=case, params=params, comparisons=comparisons)


def _case(index: int, params: Mapping[str, Any], *, optimized: bool = False) -> dict[str, Any]:
    key = "optimized_dynamic_sleeve_capped_stack" if optimized else f"dynamic_sleeve_capped_{index:03d}"
    min_per_asset_class = {item_key: int(value) for item_key, value in params.get("min_per_asset_class", {}).items()}
    commodity_guard = params.get("commodity_guard", {"name": "none"})
    daily_control = params.get("daily_control", {"name": "none"})
    extras = []
    if min_per_asset_class.get("rates", 0) > 0:
        extras.append("min 1 rates")
    if commodity_guard.get("name") != "none":
        extras.append(str(commodity_guard["name"]))
    if daily_control.get("name") != "none":
        extras.append(str(daily_control["name"]))
    extra_text = f" ({', '.join(extras)})" if extras else ""
    name = "Optimized dynamic sleeve-capped stack" if optimized else (
        f"Dynamic sleeve-capped {index:03d}: {params['cap_profile']} "
        f"{params['short_momentum_bars']}/{params['medium_momentum_bars']}/{params['long_momentum_bars']}d "
        f"top {params['top_n']}{extra_text}"
    )
    overlay = SleeveCappedMomentumOverlay(
        sleeve_by_symbol={symbol: spec.sleeve for symbol, spec in ALL_WEATHER_SPEC_BY_SYMBOL.items()},
        asset_class_by_symbol={symbol: spec.asset_class_group for symbol, spec in ALL_WEATHER_SPEC_BY_SYMBOL.items()},
        region_by_symbol={symbol: spec.region_group for symbol, spec in ALL_WEATHER_SPEC_BY_SYMBOL.items()},
        top_n=int(params["top_n"]),
        max_per_sleeve=int(params["max_per_sleeve"]),
        max_per_asset_class={key: int(value) for key, value in params["max_per_asset_class"].items()},
        min_per_asset_class=min_per_asset_class,
        max_per_region={key: int(value) for key, value in params["max_per_region"].items()},
        short_momentum_bars=int(params["short_momentum_bars"]),
        medium_momentum_bars=int(params["medium_momentum_bars"]),
        long_momentum_bars=int(params["long_momentum_bars"]),
        trend_weight=Decimal(str(params["trend_weight"])),
        volume_weight=Decimal(str(params["volume_weight"])),
        name=key,
    )
    overlays: list[TargetOverlay] = [overlay]
    if commodity_guard.get("name") != "none":
        overlays.append(_commodity_guard_overlay(commodity_guard))
    overlays.extend(instantiate_overlays(current_sota_definition()))
    return {
        "key": key,
        "name": name,
        "sleeve_name": key.replace("_", "-"),
        "overlays": overlays,
        "daily_control": daily_control if daily_control.get("name") != "none" else None,
        "params": _json_params(params),
    }


def _case_from_row(row: Mapping[str, Any], *, optimized: bool) -> dict[str, Any]:
    params = row["rawParameters"]
    parsed = {
        "short_momentum_bars": int(params["shortMomentumBars"]),
        "medium_momentum_bars": int(params["mediumMomentumBars"]),
        "long_momentum_bars": int(params["longMomentumBars"]),
        "trend_weight": Decimal(str(params["trendWeight"])),
        "volume_weight": Decimal(str(params["volumeWeight"])),
        "top_n": int(params["topN"]),
        "max_per_sleeve": int(params["maxPerSleeve"]),
        "cap_profile": params["capProfile"],
        "max_per_asset_class": {key: int(value) for key, value in params["maxPerAssetClass"].items()},
        "min_per_asset_class": {key: int(value) for key, value in params.get("minPerAssetClass", {}).items()},
        "max_per_region": {key: int(value) for key, value in params["maxPerRegion"].items()},
        "commodity_guard": _parse_guard_params(params.get("commodityGuard", {"name": "none"})),
        "daily_control": _parse_daily_control_params(params.get("dailyControl", {"name": "none"})),
    }
    return _case(0, parsed, optimized=optimized)


def _commodity_guard_overlay(profile: Mapping[str, Any]) -> CommodityRiskGuardOverlay:
    return CommodityRiskGuardOverlay(
        asset_class_by_symbol={symbol: spec.asset_class_group for symbol, spec in ALL_WEATHER_SPEC_BY_SYMBOL.items()},
        max_asset_class_weight=Decimal(str(profile["maxAssetClassWeight"])),
        triggered_scale=Decimal(str(profile["triggeredScale"])),
        short_momentum_bars=int(profile["shortMomentumBars"]),
        slow_momentum_bars=int(profile["slowMomentumBars"]),
        short_momentum_threshold=Decimal(str(profile["shortMomentumThreshold"])),
        fast_volatility_bars=int(profile["fastVolatilityBars"]),
        slow_volatility_bars=int(profile["slowVolatilityBars"]),
        volatility_spike_multiple=Decimal(str(profile["volatilitySpikeMultiple"])),
        reallocate_residual=True,
        name=str(profile["name"]),
    )


def _parse_guard_params(profile: Mapping[str, Any]) -> dict[str, Any]:
    if profile.get("name") == "none":
        return {"name": "none"}
    return {
        "name": profile["name"],
        "maxAssetClassWeight": Decimal(str(profile["maxAssetClassWeight"])),
        "triggeredScale": Decimal(str(profile["triggeredScale"])),
        "shortMomentumBars": int(profile["shortMomentumBars"]),
        "slowMomentumBars": int(profile["slowMomentumBars"]),
        "shortMomentumThreshold": Decimal(str(profile["shortMomentumThreshold"])),
        "fastVolatilityBars": int(profile["fastVolatilityBars"]),
        "slowVolatilityBars": int(profile["slowVolatilityBars"]),
        "volatilitySpikeMultiple": Decimal(str(profile["volatilitySpikeMultiple"])),
    }


def _parse_daily_control_params(profile: Mapping[str, Any]) -> dict[str, Any]:
    if profile.get("name") == "none":
        return {"name": "none"}
    return {
        "name": profile["name"],
        "triggerThreshold": Decimal(str(profile["triggerThreshold"])),
        "commodityGuard": _parse_guard_params(profile["commodityGuard"]),
    }


def _run_candidate_payload(
    *,
    store: SQLiteStore,
    case: Mapping[str, Any],
    start_date: date,
    end_date: date,
    initial_cash_cnh: Decimal,
) -> dict[str, Any]:
    result = _run_dynamic_risk_parity_backtest(
        store=store,
        instruments=ALL_WEATHER_ETF_UNIVERSE,
        config=StoredRiskParityBacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_cash_cnh=initial_cash_cnh,
            sleeve_name=str(case["sleeve_name"]),
        ),
        target_overlays=case["overlays"],
        daily_control=case.get("daily_control"),
    )
    payload = _stable_backtest_payload(result.model_dump(mode="json"))
    payload["researchCase"] = {
        "name": case["name"],
        "params": case["params"],
        "stack": "dynamic eligibility -> sleeve-capped momentum -> SOTA relative momentum",
    }
    return payload


def _run_dynamic_risk_parity_backtest(
    *,
    store: SQLiteStore,
    instruments: Mapping[str, Instrument],
    config: StoredRiskParityBacktestConfig,
    target_overlays: Sequence[TargetOverlay] = (),
    daily_control: Mapping[str, Any] | None = None,
) -> Any:
    bars_by_symbol = {
        symbol: store.list_price_bars(symbol, start_date=config.start_date, end_date=config.end_date)
        for symbol in instruments
    }
    master_dates = sorted({bar.trade_date for bars in bars_by_symbol.values() for bar in bars})
    master_dates = [item for item in master_dates if config.start_date <= item <= config.end_date]
    if not master_dates:
        raise ValueError("No price dates are available.")
    fx_rates = store.list_fx_rates(Currency.USD, start_date=config.start_date, end_date=config.end_date)
    if not fx_rates:
        raise ValueError("USD/CNH FX rates are required.")
    usd_cnh_by_date = {rate.rate_date: rate.rate for rate in fx_rates}
    bar_by_symbol_date = {symbol: {bar.trade_date: bar for bar in bars} for symbol, bars in bars_by_symbol.items()}
    latest_bars_by_date = _latest_bars_by_date(bars_by_symbol, master_dates)
    daily_prices = {
        trade_date: {
            symbol: bar.close
            for symbol, bar in latest_bars_by_date[trade_date].items()
        }
        for trade_date in master_dates
    }
    daily_execution_prices = _open_prices_by_date(bars_by_symbol, master_dates)
    daily_rebalance_prices = _prior_close_prices_by_date(bars_by_symbol, master_dates)
    daily_fx = {
        trade_date: {Currency.USD: _latest_rate(usd_cnh_by_date, trade_date)}
        for trade_date in master_dates
    }
    target_schedule = _dynamic_monthly_target_schedule(
        instruments=instruments,
        bars_by_symbol=bars_by_symbol,
        trade_dates=master_dates,
        lookback_bars=config.lookback_bars,
        max_weight=config.max_weight,
        cash_reserve_weight=config.cash_reserve_weight,
        sleeve_name=config.sleeve_name,
        target_overlays=target_overlays,
    )
    if daily_control is not None:
        target_schedule = _daily_control_target_schedule(
            instruments=instruments,
            bars_by_symbol=bars_by_symbol,
            trade_dates=master_dates,
            monthly_schedule=target_schedule,
            daily_control=daily_control,
        )
    return DailyBacktestEngine().run(
        trade_dates=master_dates,
        instruments=instruments,
        initial_cash=[CashBalance(currency=Currency.CNH, amount=config.initial_cash_cnh)],
        daily_prices=daily_prices,
        daily_fx_to_cnh=daily_fx,
        target_schedule=target_schedule,
        daily_rebalance_prices=daily_rebalance_prices,
        daily_execution_prices=daily_execution_prices,
        decision_dates_by_trade_date=_previous_trade_dates(master_dates),
        sleeve=config.sleeve_name,
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
) -> dict[date, list[AllocationTarget]]:
    sleeve = RiskParityBetaSleeve(name=sleeve_name, max_weight=max_weight)
    schedule: dict[date, list[AllocationTarget]] = {}
    seen_months: set[tuple[int, int]] = set()
    max_required_history = max([lookback_bars, *[getattr(overlay, "lookback_bars", lookback_bars) for overlay in target_overlays]])
    bar_dates_by_symbol = {symbol: {bar.trade_date for bar in bars} for symbol, bars in bars_by_symbol.items()}

    for trade_date in trade_dates:
        month_key = (trade_date.year, trade_date.month)
        if month_key in seen_months:
            continue
        seen_months.add(month_key)
        states: list[BetaInstrumentState] = []
        for symbol, instrument in instruments.items():
            if trade_date not in bar_dates_by_symbol.get(symbol, set()):
                continue
            history = [bar for bar in bars_by_symbol[symbol] if bar.trade_date < trade_date]
            if len(history) < max_required_history + 1:
                continue
            lookback = history[-(lookback_bars + 1) :]
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
    return schedule


def _daily_control_target_schedule(
    *,
    instruments: Mapping[str, Instrument],
    bars_by_symbol: Mapping[str, Sequence[PriceBar]],
    trade_dates: Sequence[date],
    monthly_schedule: Mapping[date, Sequence[AllocationTarget]],
    daily_control: Mapping[str, Any],
) -> dict[date, list[AllocationTarget]]:
    schedule = {trade_date: list(targets) for trade_date, targets in monthly_schedule.items()}
    trigger_threshold = Decimal(str(daily_control.get("triggerThreshold", "0.03")))
    guard_profile = daily_control.get("commodityGuard", {"name": "none"})
    guard = _commodity_guard_overlay(guard_profile) if guard_profile.get("name") != "none" else None
    if guard is None:
        return schedule

    base_targets: list[AllocationTarget] | None = None
    current_targets: list[AllocationTarget] | None = None
    for trade_date in trade_dates:
        if trade_date in monthly_schedule:
            base_targets = list(monthly_schedule[trade_date])
            current_targets = base_targets
            continue
        if base_targets is None or current_targets is None:
            continue

        active_symbols = {target.symbol for target in base_targets if target.target_weight > Decimal("0")}
        context = SignalContext(
            as_of=trade_date,
            instruments={symbol: instrument for symbol, instrument in instruments.items() if symbol in active_symbols},
            bars_by_symbol=bars_by_symbol,
            trade_dates=trade_dates,
        )
        candidate_targets = guard.apply(base_targets, context)
        if _max_weight_difference(current_targets, candidate_targets) < trigger_threshold:
            continue
        schedule[trade_date] = candidate_targets
        current_targets = candidate_targets
    return schedule


def _max_weight_difference(
    current_targets: Sequence[AllocationTarget],
    candidate_targets: Sequence[AllocationTarget],
) -> Decimal:
    current = {target.symbol: target.target_weight for target in current_targets}
    candidate = {target.symbol: target.target_weight for target in candidate_targets}
    symbols = set(current) | set(candidate)
    return max(
        (abs(candidate.get(symbol, Decimal("0")) - current.get(symbol, Decimal("0"))) for symbol in symbols),
        default=Decimal("0"),
    )


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


def _baseline_payloads(
    *,
    store: SQLiteStore,
    start_date: date,
    end_date: date,
    initial_cash_cnh: Decimal,
) -> dict[str, dict[str, Any]]:
    current_sota = current_sota_definition()
    current_sota_result = run_stored_risk_parity_backtest(
        store=store,
        instruments=GLOBAL_ETF_UNIVERSE,
        config=StoredRiskParityBacktestConfig(start_date=start_date, end_date=end_date, initial_cash_cnh=initial_cash_cnh, sleeve_name=current_sota.sleeve_name),
        target_overlays=instantiate_overlays(current_sota),
    )
    dynamic_rp = _run_dynamic_risk_parity_backtest(
        store=store,
        instruments=ALL_WEATHER_ETF_UNIVERSE,
        config=StoredRiskParityBacktestConfig(start_date=start_date, end_date=end_date, initial_cash_cnh=initial_cash_cnh, sleeve_name="dynamic-all-weather-risk-parity"),
    )
    return {
        "current_sota": {"name": current_sota.name, "payload": _stable_backtest_payload(current_sota_result.model_dump(mode="json"))},
        "dynamic_all_weather_risk_parity": {"name": "Dynamic all-weather risk parity", "payload": _stable_backtest_payload(dynamic_rp.model_dump(mode="json"))},
        "aor": {
            "name": MULTI_ASSET_BENCHMARK_NAME,
            "payload": _buy_and_hold_payload(store=store, symbol=MULTI_ASSET_BENCHMARK_SYMBOL, start_date=start_date, end_date=end_date, initial_cash_cnh=initial_cash_cnh),
        },
    }


def _comparisons(
    *,
    candidate_payload: dict[str, Any],
    candidate_name: str,
    baseline_payloads: Mapping[str, dict[str, Any]],
    validation_date: date,
    oos_date: date,
) -> dict[str, Any]:
    return {
        key: _windowed_compare(
            baseline=item["payload"],
            candidate=candidate_payload,
            baseline_name=item["name"],
            candidate_name=candidate_name,
            validation_date=validation_date,
            oos_date=oos_date,
        )
        for key, item in baseline_payloads.items()
    }


def _row(
    *,
    case: Mapping[str, Any],
    params: Mapping[str, Any],
    comparisons: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    vs_aor = comparisons["aor"]
    vs_rp = comparisons["dynamic_all_weather_risk_parity"]
    vs_sota = comparisons["current_sota"]
    train = vs_aor["metrics"]["train"]["candidate"]
    validation = vs_aor["metrics"]["validation"]["candidate"]
    oos = vs_aor["metrics"]["out_of_sample"]["candidate"]
    validation_to_train = sharpe_retention_ratio(train["sharpe"], validation["sharpe"])
    out_to_validation = sharpe_retention_ratio(validation["sharpe"], oos["sharpe"])
    return {
        "key": case["key"],
        "name": case["name"],
        "rawParameters": _json_params(params),
        "trainSharpe": train["sharpe"],
        "validationAnnualizedReturn": validation["annualizedReturn"],
        "validationSharpe": validation["sharpe"],
        "validationCalmar": validation["calmar"],
        "validationToTrainSharpeRatio": validation_to_train,
        "validationToTrainSharpeBandDistance": retention_band_distance(validation_to_train),
        "validationToTrainSharpeBandPass": retention_band_pass(validation_to_train),
        "validationInformationRatioVsRiskParity": vs_rp["metrics"]["validation"]["active"]["informationRatio"],
        "validationInformationRatioVsCurrentSota": vs_sota["metrics"]["validation"]["active"]["informationRatio"],
        "oosAnnualizedReturn": oos["annualizedReturn"],
        "oosReturn": oos["return"],
        "oosSharpe": oos["sharpe"],
        "oosCalmar": oos["calmar"],
        "oosMaxDrawdown": oos["maxDrawdown"],
        "outToValidationSharpeRatio": out_to_validation,
        "outToValidationSharpeBandDistance": retention_band_distance(out_to_validation),
        "outToValidationSharpeBandPass": retention_band_pass(out_to_validation),
        "oosInformationRatioVsRiskParity": vs_rp["metrics"]["out_of_sample"]["active"]["informationRatio"],
        "oosInformationRatioVsCurrentSota": vs_sota["metrics"]["out_of_sample"]["active"]["informationRatio"],
        "oosInformationRatioVsAor": vs_aor["metrics"]["out_of_sample"]["active"]["informationRatio"],
    }


def _score_rows(rows: list[dict[str, Any]]) -> None:
    score_specs = [
        ("validationInformationRatioVsCurrentSota", Decimal("0.30")),
        ("validationSharpe", Decimal("0.20")),
        ("validationCalmar", Decimal("0.10")),
        ("validationInformationRatioVsRiskParity", Decimal("0.15")),
    ]
    percentiles = {key: percentile_scores(rows, key) for key, _weight in score_specs}
    retention_scores = retention_closeness_scores(rows, distance_key="validationToTrainSharpeBandDistance")
    for row in rows:
        score = Decimal("0")
        for key, weight in score_specs:
            score += weight * Decimal(str(percentiles[key].get(row["key"], 0.0)))
        score += Decimal("0.25") * Decimal(str(retention_scores.get(row["key"], 0.0)))
        row["validationObjectiveScore"] = float(score)


def _percentile_scores(rows: Sequence[dict[str, Any]], key: str) -> dict[str, float]:
    present = [row for row in rows if isinstance(row.get(key), int | float)]
    ranked = sorted(present, key=lambda row: (float(row[key]), row["key"]))
    if len(ranked) < 2:
        return {row["key"]: 1.0 for row in ranked}
    denominator = len(ranked) - 1
    return {row["key"]: index / denominator for index, row in enumerate(ranked)}


def _json_params(params: Mapping[str, Any]) -> dict[str, Any]:
    commodity_guard = params.get("commodity_guard", {"name": "none"})
    daily_control = params.get("daily_control", {"name": "none"})
    return {
        "shortMomentumBars": params["short_momentum_bars"],
        "mediumMomentumBars": params["medium_momentum_bars"],
        "longMomentumBars": params["long_momentum_bars"],
        "trendWeight": str(params["trend_weight"]),
        "volumeWeight": str(params["volume_weight"]),
        "topN": params["top_n"],
        "maxPerSleeve": params["max_per_sleeve"],
        "capProfile": params["cap_profile"],
        "maxPerAssetClass": dict(params["max_per_asset_class"]),
        "minPerAssetClass": dict(params.get("min_per_asset_class", {})),
        "maxPerRegion": dict(params["max_per_region"]),
        "commodityGuard": _json_guard_params(commodity_guard),
        "dailyControl": _json_daily_control_params(daily_control),
    }


def _json_guard_params(profile: Mapping[str, Any]) -> dict[str, Any]:
    if profile.get("name") == "none":
        return {"name": "none"}
    return {
        "name": profile["name"],
        "maxAssetClassWeight": str(profile["maxAssetClassWeight"]),
        "triggeredScale": str(profile["triggeredScale"]),
        "shortMomentumBars": profile["shortMomentumBars"],
        "slowMomentumBars": profile["slowMomentumBars"],
        "shortMomentumThreshold": str(profile["shortMomentumThreshold"]),
        "fastVolatilityBars": profile["fastVolatilityBars"],
        "slowVolatilityBars": profile["slowVolatilityBars"],
        "volatilitySpikeMultiple": str(profile["volatilitySpikeMultiple"]),
    }


def _json_daily_control_params(profile: Mapping[str, Any]) -> dict[str, Any]:
    if profile.get("name") == "none":
        return {"name": "none"}
    return {
        "name": profile["name"],
        "triggerThreshold": str(profile["triggerThreshold"]),
        "commodityGuard": _json_guard_params(profile["commodityGuard"]),
    }


def _latest_rate(rates_by_date: Mapping[date, Decimal], trade_date: date) -> Decimal:
    available_dates = [rate_date for rate_date in rates_by_date if rate_date <= trade_date]
    if not available_dates:
        raise ValueError(f"No USD/CNH FX rate is available on or before {trade_date}.")
    return rates_by_date[max(available_dates)]


def _results_markdown(results: Mapping[str, Any]) -> str:
    winner = results["winner"]
    lines = [
        "# Dynamic Sleeve-Capped Momentum Research",
        "",
        f"- Candidate count: {results['method']['candidateCount']}",
        f"- Worker processes: {results['method']['workers']}",
        f"- Data range: {results['method']['startDate']} to {results['method']['endDate']}",
        f"- Validation date: {results['method']['validationDate']}",
        f"- OOS date: {results['method']['oosDate']}",
        f"- Stack: {results['method']['stack']}",
        "",
        "## Validation-Selected Winner",
        "",
        f"- Strategy: {winner['name']}",
        f"- Validation objective score: {_fmt_num(winner['validationObjectiveScore'])}",
        f"- Train Sharpe: {_fmt_num(winner['trainSharpe'])}",
        f"- Validation Sharpe: {_fmt_num(winner['validationSharpe'])}",
        f"- Validation/train Sharpe ratio: {_fmt_num(winner['validationToTrainSharpeRatio'])}",
        f"- Validation IR vs current SOTA: {_fmt_num(winner['validationInformationRatioVsCurrentSota'])}",
        f"- OOS annualized return: {_fmt_pct(winner['oosAnnualizedReturn'])}",
        f"- OOS Sharpe: {_fmt_num(winner['oosSharpe'])}",
        f"- OOS/validation Sharpe ratio: {_fmt_num(winner['outToValidationSharpeRatio'])}",
        f"- OOS Calmar: {_fmt_num(winner['oosCalmar'])}",
        f"- OOS max drawdown: {_fmt_pct(winner['oosMaxDrawdown'])}",
        f"- OOS IR vs current SOTA: {_fmt_num(winner['oosInformationRatioVsCurrentSota'])}",
        f"- OOS IR vs dynamic all-weather risk parity: {_fmt_num(winner['oosInformationRatioVsRiskParity'])}",
        "",
        "## Top 15 By Validation Objective",
        "",
        "| Rank | Strategy | Val Score | Train Sharpe | Val Sharpe | Val/Train | OOS Sharpe | OOS/Val | OOS IR vs SOTA | OOS IR vs RP |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for index, row in enumerate(results["rankedCandidates"][:15], start=1):
        lines.append(_summary_row(index, row))
    lines.extend(
        [
            "",
            "## Top 15 By OOS IR vs Current SOTA",
            "",
            "| Rank | Strategy | Val Score | Train Sharpe | Val Sharpe | Val/Train | OOS Sharpe | OOS/Val | OOS IR vs SOTA | OOS IR vs RP |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for index, row in enumerate(results["bestOosByCurrentSotaIR"], start=1):
        lines.append(_summary_row(index, row))
    lines.append("")
    return "\n".join(lines)


def _summary_row(index: int, row: Mapping[str, Any]) -> str:
    return (
        "| "
        + " | ".join(
            [
                str(index),
                str(row["name"]),
                _fmt_num(row.get("validationObjectiveScore")),
                _fmt_num(row["trainSharpe"]),
                _fmt_num(row["validationSharpe"]),
                _fmt_num(row["validationToTrainSharpeRatio"]),
                _fmt_num(row["oosSharpe"]),
                _fmt_num(row["outToValidationSharpeRatio"]),
                _fmt_num(row["oosInformationRatioVsCurrentSota"]),
                _fmt_num(row["oosInformationRatioVsRiskParity"]),
            ]
        )
        + " |"
    )


def _write_model_card(*, path: Path, winner: Mapping[str, Any]) -> None:
    content = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Optimized Dynamic Sleeve-Capped Stack</title>
  <style>
    body {{ margin: 0; font-family: Segoe UI, Arial, sans-serif; color: #172033; background: #f7f9fc; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 28px; }}
    h1, h2 {{ margin: 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin: 18px 0; }}
    .stat, .panel {{ background: #fff; border: 1px solid #dce4ef; border-radius: 8px; padding: 16px; }}
    .stat span {{ display: block; color: #607089; font-size: 12px; margin-bottom: 6px; }}
    .stat strong {{ font-size: 22px; }}
  </style>
</head>
<body>
<main>
  <h1>Optimized Dynamic Sleeve-Capped Stack</h1>
  <section class="grid">
    <div class="stat"><span>Validation Score</span><strong>{_fmt_num(winner['validationObjectiveScore'])}</strong></div>
    <div class="stat"><span>Val/Train Sharpe</span><strong>{_fmt_num(winner['validationToTrainSharpeRatio'])}</strong></div>
    <div class="stat"><span>OOS Return</span><strong>{_fmt_pct(winner['oosAnnualizedReturn'])}</strong></div>
    <div class="stat"><span>OOS/Val Sharpe</span><strong>{_fmt_num(winner['outToValidationSharpeRatio'])}</strong></div>
  </section>
  <section class="panel">
    <h2>Decision Stack</h2>
    <ol>
      <li>At each rebalance, include only ETFs with enough point-in-time price history.</li>
      <li>Compute inverse-volatility base weights across eligible ETFs.</li>
      <li>Rank eligible ETFs globally by momentum and optional volume confirmation.</li>
      <li>Select top ranked ETFs subject to sleeve, asset-class, and region caps.</li>
      <li>Apply the current SOTA 20/60d regime-gated relative-momentum tilt.</li>
    </ol>
  </section>
</main>
</body>
</html>
"""
    path.write_text(content, encoding="utf-8")


def _readme(*, results: Mapping[str, Any], output_dir: Path) -> str:
    winner = results["winner"]
    return "\n".join(
        [
            "# Dynamic Sleeve-Capped Momentum Research",
            "",
            f"- Candidate count: {results['method']['candidateCount']}",
            f"- Winner: {winner['name']}",
            f"- Winner OOS annualized return: {_fmt_pct(winner['oosAnnualizedReturn'])}",
            f"- Winner OOS Sharpe: {_fmt_num(winner['oosSharpe'])}",
            f"- Winner validation/train Sharpe ratio: {_fmt_num(winner['validationToTrainSharpeRatio'])}",
            f"- Winner OOS/validation Sharpe ratio: {_fmt_num(winner['outToValidationSharpeRatio'])}",
            f"- Winner OOS Calmar: {_fmt_num(winner['oosCalmar'])}",
            f"- Winner OOS IR vs current SOTA: {_fmt_num(winner['oosInformationRatioVsCurrentSota'])}",
            "",
            "## Files",
            "",
            f"- Results: `{output_dir / 'optimization_results.md'}`",
            f"- Winner report: `{output_dir / 'optimized_dynamic_sleeve_capped_stack.html'}`",
            f"- Winner model card: `{output_dir / 'optimized_model_card.html'}`",
            "",
        ]
    )


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def _fmt_num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


if __name__ == "__main__":
    main()
