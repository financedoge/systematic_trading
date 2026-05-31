from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

IN_SAMPLE_SHARPE_FLOOR = 0.75

from systematic_trading.backtest.comparison import (  # noqa: E402
    build_signal_diagnostics,
    compare_backtests,
)
from systematic_trading.backtest.reporting import write_backtest_report  # noqa: E402
from systematic_trading.backtest.stability import (  # noqa: E402
    TARGET_RETENTION_HIGH,
    TARGET_RETENTION_LOW,
    finite_number,
    percentile_scores,
    retention_band_distance,
    retention_band_pass,
    retention_closeness_scores,
    sharpe_retention_ratio,
)
from systematic_trading.backtest.stored import StoredRiskParityBacktestConfig, run_stored_risk_parity_backtest  # noqa: E402
from systematic_trading.config import AppSettings  # noqa: E402
from systematic_trading.domain.enums import Currency  # noqa: E402
from systematic_trading.domain.market import Instrument  # noqa: E402
from systematic_trading.research import (  # noqa: E402
    ALL_WEATHER_ETF_UNIVERSE,
    ALL_WEATHER_SPEC_BY_SYMBOL,
    GLOBAL_ETF_UNIVERSE,
    MSCI_WORLD_PROXY_NAME,
    MSCI_WORLD_PROXY_SYMBOL,
    MULTI_ASSET_BENCHMARK_NAME,
    MULTI_ASSET_BENCHMARK_SYMBOL,
    MULTI_ASSET_ETF_UNIVERSE,
    StrategyDefinition,
    current_sota_definition,
    instruments_for_definition,
    instantiate_overlays,
    risk_parity_definition,
    strategy_definition_from_overlay,
    strategy_model_card,
)
from systematic_trading.signals import (  # noqa: E402
    AdaptiveTrendOverlay,
    AssetPoolFilterOverlay,
    BasketRiskControlOverlay,
    CommodityRiskGuardOverlay,
    DecisionTreeSignalOverlay,
    RegimeGatedRelativeMomentumOverlay,
    SleeveCappedMomentumOverlay,
    TimeSeriesMomentumOverlay,
    TrendQualityFilterOverlay,
    train_technical_tree_allocator_overlay,
)
from systematic_trading.storage.sqlite import SQLiteStore  # noqa: E402


@dataclass(frozen=True)
class ResearchCase:
    definition: StrategyDefinition
    instruments: Mapping[str, Instrument]
    universe_label: str


@dataclass(frozen=True)
class BacktestCaseJob:
    case: ResearchCase
    database_path: Path
    start_date: date
    end_date: date
    initial_cash_cnh: Decimal
    rebalance_frequency: str
    transaction_cost_bps: Decimal
    rebalance_min_weight_delta: Decimal
    rebalance_min_total_weight_delta: Decimal
    rebalance_trigger_asset_change: bool
    output_dir: Path
    metrics_only: bool
    compact_json: bool


@dataclass(frozen=True)
class BacktestCaseOutput:
    key: str
    path: Path


@dataclass(frozen=True)
class TechnicalTreeTrainingJob:
    spec: Mapping[str, Any]
    database_path: Path
    start_date: date
    end_date: date
    split_date: date
    rebalance_frequency: str


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run multi-asset ETF basket research against SOTA and multi-asset benchmarks."
    )
    parser.add_argument("--database", default=None)
    parser.add_argument("--start-date", default="2012-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--split-date", default="2023-01-01")
    parser.add_argument("--initial-cash-cnh", default="1000000")
    parser.add_argument("--output-dir", default="var/backtests/multi_asset_etf_research_2012")
    parser.add_argument("--rebalance-frequency", choices=["monthly", "daily"], default="monthly")
    parser.add_argument("--transaction-cost-bps", default="0")
    parser.add_argument("--rebalance-min-weight-delta", default="0")
    parser.add_argument("--rebalance-min-total-weight-delta", default="0")
    parser.add_argument(
        "--rebalance-trigger-asset-change",
        action="store_true",
        help="For thresholded daily scans, rebalance when the active target asset set changes.",
    )
    parser.add_argument(
        "--daily-core-only",
        action="store_true",
        help="When running daily rebalances, limit the sweep to the strongest baseline and technical-tree families.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Parallel strategy backtest workers. Default uses all logical CPUs up to the number of cases.",
    )
    parser.add_argument("--skip-reports", action="store_true", help="Write JSON/rankings/model cards without per-strategy HTML reports.")
    parser.add_argument(
        "--metrics-only",
        action="store_true",
        help="Store only NAV/final snapshot for strategy result JSON. Requires --skip-reports and is best for large daily sweeps.",
    )
    parser.add_argument(
        "--pretty-json",
        action="store_true",
        help="Pretty-print result JSON. Daily sweeps default to compact JSON to reduce disk I/O.",
    )
    args = parser.parse_args()
    if args.metrics_only and not args.skip_reports:
        raise ValueError("--metrics-only requires --skip-reports because report generation needs full proposal records.")

    settings = AppSettings()
    database_path = Path(args.database) if args.database else settings.database_path
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(database_path)
    store.initialize()

    all_symbols = sorted(
        set(GLOBAL_ETF_UNIVERSE)
        | set(ALL_WEATHER_ETF_UNIVERSE)
        | set(MULTI_ASSET_ETF_UNIVERSE)
        | {MULTI_ASSET_BENCHMARK_SYMBOL, MSCI_WORLD_PROXY_SYMBOL}
    )
    start_date, end_date = _date_range_from_store(
        store=store,
        symbols=all_symbols,
        start_date_arg=args.start_date,
        end_date_arg=args.end_date,
    )
    split_date = date.fromisoformat(args.split_date)
    initial_cash_cnh = Decimal(args.initial_cash_cnh)
    transaction_cost_bps = Decimal(args.transaction_cost_bps)
    rebalance_min_weight_delta = Decimal(args.rebalance_min_weight_delta)
    rebalance_min_total_weight_delta = Decimal(args.rebalance_min_total_weight_delta)
    requested_workers = _requested_worker_count(args.workers)
    print(
        f"Research range {start_date.isoformat()} to {end_date.isoformat()}, "
        f"split {split_date.isoformat()}, frequency={args.rebalance_frequency}, "
        f"transaction_cost_bps={transaction_cost_bps}, "
        f"rebalance_gate=max_delta>={rebalance_min_weight_delta}/total_delta>={rebalance_min_total_weight_delta}/"
        f"asset_change={args.rebalance_trigger_asset_change}, "
        f"requested_workers={requested_workers}.",
        flush=True,
    )

    cases = _research_cases() + _trained_technical_tree_cases(
        database_path=database_path,
        start_date=start_date,
        end_date=end_date,
        split_date=split_date,
        rebalance_frequency=args.rebalance_frequency,
        workers=requested_workers,
        core_only=args.daily_core_only,
    )
    if args.daily_core_only:
        cases = _daily_core_cases(cases)
    workers = _worker_count(requested_workers, len(cases))
    print(f"Running {len(cases)} strategy cases with {workers} worker process(es).", flush=True)
    payloads, paths = _run_case_backtests(
        cases=cases,
        database_path=database_path,
        start_date=start_date,
        end_date=end_date,
        initial_cash_cnh=initial_cash_cnh,
        rebalance_frequency=args.rebalance_frequency,
        transaction_cost_bps=transaction_cost_bps,
        rebalance_min_weight_delta=rebalance_min_weight_delta,
        rebalance_min_total_weight_delta=rebalance_min_total_weight_delta,
        rebalance_trigger_asset_change=args.rebalance_trigger_asset_change,
        output_dir=output_dir,
        workers=workers,
        metrics_only=args.metrics_only,
        compact_json=not args.pretty_json,
    )

    benchmark_payloads = {
        "aor": _buy_and_hold_payload(
            store=store,
            symbol=MULTI_ASSET_BENCHMARK_SYMBOL,
            start_date=start_date,
            end_date=end_date,
            initial_cash_cnh=initial_cash_cnh,
        ),
        "msci_world": _buy_and_hold_payload(
            store=store,
            symbol=MSCI_WORLD_PROXY_SYMBOL,
            start_date=start_date,
            end_date=end_date,
            initial_cash_cnh=initial_cash_cnh,
        ),
    }
    for key, payload in benchmark_payloads.items():
        path = output_dir / f"benchmark_{key}.json"
        path.write_text(_json_dump(payload, compact=not args.pretty_json), encoding="utf-8")

    print("Building benchmark comparisons and rankings.", flush=True)
    comparisons = _build_comparisons(
        cases=cases,
        payloads=payloads,
        benchmark_payloads=benchmark_payloads,
        split_date=split_date,
    )
    ranking = _ranking_rows(cases=cases, comparisons=comparisons)
    ranking_json = output_dir / "multi_asset_rankings.json"
    ranking_json.write_text(
        _json_dump({"rankings": ranking, "comparisons": comparisons}, compact=not args.pretty_json),
        encoding="utf-8",
    )
    ranking_md = output_dir / "multi_asset_rankings.md"
    ranking_md.write_text(
        _ranking_markdown(
            ranking,
            rebalance_frequency=args.rebalance_frequency,
            transaction_cost_bps=transaction_cost_bps,
            rebalance_min_weight_delta=rebalance_min_weight_delta,
            rebalance_min_total_weight_delta=rebalance_min_total_weight_delta,
            rebalance_trigger_asset_change=args.rebalance_trigger_asset_change,
        ),
        encoding="utf-8",
    )

    if not args.skip_reports:
        prices_by_symbol = _prices_by_symbol(store, all_symbols)
        multi_asset_rp_key = "multi_asset_risk_parity"
        for case in cases:
            signal_diagnostics = None
            if case.definition.overlays and case.universe_label == "multi_asset":
                signal_diagnostics = build_signal_diagnostics(
                    baseline=payloads[multi_asset_rp_key],
                    candidate=payloads[case.definition.key],
                    prices_by_symbol=prices_by_symbol,
                    split_date=split_date,
                    signal_name=case.definition.key,
                )
            extra_benchmarks = [
                {
                    "id": "current_sota",
                    "name": current_sota_definition().name,
                    "nav_series": payloads[current_sota_definition().key]["nav_series"],
                },
                {
                    "id": "multi_asset_risk_parity",
                    "name": "Multi-asset risk parity",
                    "nav_series": payloads[multi_asset_rp_key]["nav_series"],
                },
                {
                    "id": "msci_world",
                    "name": MSCI_WORLD_PROXY_NAME,
                    "symbol": MSCI_WORLD_PROXY_SYMBOL,
                },
            ]
            report = write_backtest_report(
                result_path=paths[case.definition.key],
                output_path=output_dir / f"{case.definition.key}.html",
                database_path=database_path,
                split_date=split_date,
                benchmark_symbol=MULTI_ASSET_BENCHMARK_SYMBOL,
                benchmark_name=MULTI_ASSET_BENCHMARK_NAME,
                extra_benchmarks=extra_benchmarks,
                signal_diagnostics=signal_diagnostics,
            )
            if report.warnings:
                warning_path = output_dir / f"{case.definition.key}_report_warnings.txt"
                warning_path.write_text("\n".join(report.warnings) + "\n", encoding="utf-8")

    model_cards_path = output_dir / "multi_asset_model_cards.html"
    _write_model_cards_html(path=model_cards_path, cases=cases, ranking=ranking)
    readme_path = output_dir / "README.md"
    readme_path.write_text(
        _readme(
            start_date=start_date,
            end_date=end_date,
            split_date=split_date,
            rebalance_frequency=args.rebalance_frequency,
            transaction_cost_bps=transaction_cost_bps,
            rebalance_min_weight_delta=rebalance_min_weight_delta,
            rebalance_min_total_weight_delta=rebalance_min_total_weight_delta,
            rebalance_trigger_asset_change=args.rebalance_trigger_asset_change,
            ranking=ranking,
            output_dir=output_dir,
        ),
        encoding="utf-8",
    )

    for path in [
        ranking_md,
        ranking_json,
        model_cards_path,
        readme_path,
        *[paths[case.definition.key] for case in cases],
    ]:
        print(path)


def _research_cases() -> list[ResearchCase]:
    current_sota = current_sota_definition()
    sleeve_variants = _all_weather_sleeve_variant_cases()
    multi_risk_parity = replace(
        risk_parity_definition(),
        key="multi_asset_risk_parity",
        name="Multi-asset risk parity",
        sleeve_name="multi-asset-risk-parity",
        state="research",
        description=(
            "Inverse-volatility allocation across equity, China, bond, credit, gold, "
            "and broad commodity ETFs. This isolates the effect of adding the asset classes."
        ),
    )
    multi_relative = replace(
        current_sota,
        key="multi_asset_relative_momentum_20_60d_tilt20_regime",
        name="Multi-asset: risk parity + relative momentum 20/60d 20% tilt",
        sleeve_name="multi-asset-relative-momentum-20-60d-tilt20-regime",
        state="research",
        description=(
            "Applies the current SOTA relative-momentum overlay to the expanded multi-asset ETF basket."
        ),
    )
    ts_momentum = replace(
        strategy_definition_from_overlay(
            TimeSeriesMomentumOverlay(lookback_bars=252, reallocate_survivors=True)
        ),
        key="multi_asset_time_series_momentum_252d_reallocate",
        name="Multi-asset: risk parity + 252d time-series momentum filter",
        sleeve_name="multi-asset-ts-momentum-252d-reallocate",
        description="Filters assets with negative 252-day absolute momentum and reallocates survivors.",
    )
    adaptive = replace(
        strategy_definition_from_overlay(AdaptiveTrendOverlay()),
        key="multi_asset_adaptive_trend",
        name="Multi-asset: risk parity + adaptive trend filter",
        sleeve_name="multi-asset-adaptive-trend",
        description="Scales asset exposure using point-in-time trend, rebound, volume, and volatility signals.",
    )
    momentum_pool = replace(
        strategy_definition_from_overlay(
            AssetPoolFilterOverlay(
                top_n=6,
                min_selected=3,
                trend_weight=Decimal("1"),
                volume_weight=Decimal("0"),
                require_positive_long_momentum=True,
                reallocate_selected=True,
            )
        ),
        key="multi_asset_momentum_pool_filter_top6",
        name="Multi-asset: momentum pool filter top 6",
        sleeve_name="multi-asset-momentum-pool-filter-top6",
        description=(
            "Selects the top six ETFs from the expanded pool using point-in-time momentum ranks only."
        ),
    )
    price_volume_pool = replace(
        strategy_definition_from_overlay(
            AssetPoolFilterOverlay(
                top_n=6,
                min_selected=3,
                trend_weight=Decimal("0.75"),
                volume_weight=Decimal("0.25"),
                require_positive_long_momentum=True,
                reallocate_selected=True,
            )
        ),
        key="multi_asset_price_volume_pool_filter_top6",
        name="Multi-asset: price/volume pool filter top 6",
        sleeve_name="multi-asset-price-volume-pool-filter-top6",
        description=(
            "Selects the top six ETFs from the expanded pool using momentum ranks plus volume confirmation."
        ),
    )
    basket_guard = strategy_definition_from_overlay(
        BasketRiskControlOverlay(
            neutral_scale=Decimal("0.90"),
            defensive_scale=Decimal("0.65"),
            severe_scale=Decimal("0.45"),
        )
    )
    price_volume_basket_guard = replace(
        price_volume_pool,
        key="multi_asset_price_volume_pool_filter_top6_basket_guard65",
        name="Multi-asset: price/volume pool filter top 6 + basket risk control",
        sleeve_name="multi-asset-price-volume-pool-filter-top6-basket-guard65",
        description=(
            "Selects the top six ETFs using momentum and volume confirmation, then scales total basket "
            "exposure when breadth, drawdown, or volatility deteriorates."
        ),
        overlays=price_volume_pool.overlays + basket_guard.overlays,
    )
    trend_quality_pool = replace(
        strategy_definition_from_overlay(
            TrendQualityFilterOverlay(
                top_n=6,
                min_selected=3,
                reallocate_selected=True,
            )
        ),
        key="multi_asset_trend_quality_pool_filter_top6",
        name="Multi-asset: trend-quality pool filter top 6",
        sleeve_name="multi-asset-trend-quality-pool-filter-top6",
        description=(
            "Selects the top six ETFs using raw momentum, risk-adjusted momentum, consistency, "
            "and drawdown-quality ranks."
        ),
    )
    trend_quality_low_vol_pool = replace(
        strategy_definition_from_overlay(
            TrendQualityFilterOverlay(
                top_n=6,
                min_selected=3,
                momentum_weight=Decimal("0.45"),
                risk_adjusted_weight=Decimal("0.25"),
                consistency_weight=Decimal("0.10"),
                drawdown_weight=Decimal("0.10"),
                low_volatility_weight=Decimal("0.10"),
                reallocate_selected=True,
            )
        ),
        key="multi_asset_trend_quality_lowvol_pool_filter_top6",
        name="Multi-asset: trend-quality/low-vol pool filter top 6",
        sleeve_name="multi-asset-trend-quality-lowvol-pool-filter-top6",
        description=(
            "Selects the top six ETFs using trend-quality ranks with a small low-volatility preference."
        ),
    )
    relative12_definition = strategy_definition_from_overlay(
        RegimeGatedRelativeMomentumOverlay(
            medium_lookback_bars=20,
            long_lookback_bars=60,
            calm_tilt=Decimal("0.12"),
            risk_tilt=Decimal("0.12"),
            max_active_weight=Decimal("0.05"),
        )
    )
    trend_quality_relative = replace(
        trend_quality_pool,
        key="multi_asset_trend_quality_pool_filter_relative12_top6",
        name="Multi-asset: trend-quality pool filter top 6 + 20/60 relative tilt",
        sleeve_name="multi-asset-trend-quality-pool-filter-relative12-top6",
        description=(
            "Selects ETFs with trend-quality ranks, then adds the restrained 20/60d relative-momentum tilt."
        ),
        overlays=trend_quality_pool.overlays + relative12_definition.overlays,
    )
    concentrated_pool = replace(
        strategy_definition_from_overlay(
            AssetPoolFilterOverlay(
                top_n=4,
                min_selected=2,
                trend_weight=Decimal("0.80"),
                volume_weight=Decimal("0.20"),
                require_positive_long_momentum=True,
                reallocate_selected=True,
            )
        ),
        key="multi_asset_price_volume_pool_filter_top4",
        name="Multi-asset: price/volume pool filter top 4",
        sleeve_name="multi-asset-price-volume-pool-filter-top4",
        description="A more concentrated top-four pool filter using momentum and volume confirmation.",
    )
    return [
        ResearchCase(current_sota, instruments_for_definition(current_sota), current_sota.universe_key),
        *sleeve_variants,
        ResearchCase(multi_risk_parity, MULTI_ASSET_ETF_UNIVERSE, "multi_asset"),
        ResearchCase(multi_relative, MULTI_ASSET_ETF_UNIVERSE, "multi_asset"),
        ResearchCase(ts_momentum, MULTI_ASSET_ETF_UNIVERSE, "multi_asset"),
        ResearchCase(adaptive, MULTI_ASSET_ETF_UNIVERSE, "multi_asset"),
        ResearchCase(momentum_pool, MULTI_ASSET_ETF_UNIVERSE, "multi_asset"),
        ResearchCase(price_volume_pool, MULTI_ASSET_ETF_UNIVERSE, "multi_asset"),
        ResearchCase(price_volume_basket_guard, MULTI_ASSET_ETF_UNIVERSE, "multi_asset"),
        ResearchCase(trend_quality_pool, MULTI_ASSET_ETF_UNIVERSE, "multi_asset"),
        ResearchCase(trend_quality_low_vol_pool, MULTI_ASSET_ETF_UNIVERSE, "multi_asset"),
        ResearchCase(trend_quality_relative, MULTI_ASSET_ETF_UNIVERSE, "multi_asset"),
        ResearchCase(concentrated_pool, MULTI_ASSET_ETF_UNIVERSE, "multi_asset"),
    ]


def _all_weather_sleeve_variant_cases() -> list[ResearchCase]:
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
    cap_profiles = [
        ("balanced", {"equity": 2, "rates": 2, "credit": 1, "commodity": 2}, base_region),
        ("momentum", {"equity": 3, "rates": 2, "credit": 1, "commodity": 2}, base_region | {"US": 3}),
        ("defensive", {"equity": 2, "rates": 3, "credit": 1, "commodity": 2}, base_region),
    ]
    guard_profiles = [
        ("none", None),
        (
            "guard55",
            CommodityRiskGuardOverlay(
                asset_class_by_symbol={
                    symbol: spec.asset_class_group for symbol, spec in ALL_WEATHER_SPEC_BY_SYMBOL.items()
                },
                max_asset_class_weight=Decimal("0.55"),
                triggered_scale=Decimal("0.50"),
                short_momentum_bars=10,
                slow_momentum_bars=21,
                short_momentum_threshold=Decimal("-0.05"),
                fast_volatility_bars=10,
                slow_volatility_bars=63,
                volatility_spike_multiple=Decimal("1.50"),
                reallocate_residual=True,
                name="monthly-commodity-guard-55",
            ),
        ),
        (
            "guard45",
            CommodityRiskGuardOverlay(
                asset_class_by_symbol={
                    symbol: spec.asset_class_group for symbol, spec in ALL_WEATHER_SPEC_BY_SYMBOL.items()
                },
                max_asset_class_weight=Decimal("0.45"),
                triggered_scale=Decimal("0.50"),
                short_momentum_bars=10,
                slow_momentum_bars=21,
                short_momentum_threshold=Decimal("-0.05"),
                fast_volatility_bars=10,
                slow_volatility_bars=63,
                volatility_spike_multiple=Decimal("1.50"),
                reallocate_residual=True,
                name="monthly-commodity-guard-45",
            ),
        ),
    ]
    relative_definition = strategy_definition_from_overlay(
        RegimeGatedRelativeMomentumOverlay(
            medium_lookback_bars=20,
            long_lookback_bars=60,
            calm_tilt=Decimal("0.20"),
            risk_tilt=Decimal("0.20"),
            max_active_weight=Decimal("0.07"),
        )
    )
    cases: list[ResearchCase] = []
    for cap_name, max_per_asset_class, max_per_region in cap_profiles:
        for guard_name, guard_overlay in guard_profiles:
            sleeve_overlay = SleeveCappedMomentumOverlay(
                sleeve_by_symbol={symbol: spec.sleeve for symbol, spec in ALL_WEATHER_SPEC_BY_SYMBOL.items()},
                asset_class_by_symbol={
                    symbol: spec.asset_class_group for symbol, spec in ALL_WEATHER_SPEC_BY_SYMBOL.items()
                },
                region_by_symbol={symbol: spec.region_group for symbol, spec in ALL_WEATHER_SPEC_BY_SYMBOL.items()},
                short_momentum_bars=21,
                medium_momentum_bars=63,
                long_momentum_bars=126,
                volume_bars=21,
                slow_volume_bars=126,
                trend_weight=Decimal("0.80"),
                volume_weight=Decimal("0.20"),
                top_n=3,
                max_per_sleeve=1,
                max_per_asset_class=max_per_asset_class,
                max_per_region=max_per_region,
                require_positive_long_momentum=True,
                min_long_momentum=Decimal("0"),
                reallocate_selected=True,
            )
            sleeve_definition = strategy_definition_from_overlay(sleeve_overlay)
            guard_definition = (
                strategy_definition_from_overlay(guard_overlay) if guard_overlay is not None else None
            )
            overlays = sleeve_definition.overlays
            if guard_definition is not None:
                overlays += guard_definition.overlays
            overlays += relative_definition.overlays
            guard_suffix = "" if guard_name == "none" else f"_{guard_name}"
            cases.append(
                ResearchCase(
                    replace(
                        sleeve_definition,
                        key=f"all_weather_sleeve_{cap_name}_21_63_126_top3{guard_suffix}",
                        name=(
                            f"All-weather sleeve-capped {cap_name} 21/63/126d top 3"
                            + ("" if guard_name == "none" else f" + commodity {guard_name}")
                        ),
                        sleeve_name=f"all-weather-sleeve-{cap_name}-21-63-126-top3{guard_suffix.replace('_', '-')}",
                        state="research",
                        universe_key="all_weather",
                        scheduler="dynamic_monthly",
                        description=(
                            "All-weather dynamic sleeve-capped momentum variant using a shorter 126d long trend "
                            "lookback and the SOTA 20/60d relative-momentum tilt."
                        ),
                        overlays=overlays,
                    ),
                    ALL_WEATHER_ETF_UNIVERSE,
                    "all_weather",
                )
            )
    return cases


def _run_case_backtests(
    *,
    cases: Sequence[ResearchCase],
    database_path: Path,
    start_date: date,
    end_date: date,
    initial_cash_cnh: Decimal,
    rebalance_frequency: str,
    transaction_cost_bps: Decimal,
    rebalance_min_weight_delta: Decimal,
    rebalance_min_total_weight_delta: Decimal,
    rebalance_trigger_asset_change: bool,
    output_dir: Path,
    workers: int,
    metrics_only: bool,
    compact_json: bool,
) -> tuple[dict[str, dict[str, Any]], dict[str, Path]]:
    jobs = [
        BacktestCaseJob(
            case=case,
            database_path=database_path,
            start_date=start_date,
            end_date=end_date,
            initial_cash_cnh=initial_cash_cnh,
            rebalance_frequency=rebalance_frequency,
            transaction_cost_bps=transaction_cost_bps,
            rebalance_min_weight_delta=rebalance_min_weight_delta,
            rebalance_min_total_weight_delta=rebalance_min_total_weight_delta,
            rebalance_trigger_asset_change=rebalance_trigger_asset_change,
            output_dir=output_dir,
            metrics_only=metrics_only,
            compact_json=compact_json,
        )
        for case in cases
    ]
    outputs: list[BacktestCaseOutput] = []
    if workers == 1:
        for job in jobs:
            output = _run_case_backtest_job(job)
            print(f"Finished {output.key}: {output.path}", flush=True)
            outputs.append(output)
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            future_by_key = {executor.submit(_run_case_backtest_job, job): job.case.definition.key for job in jobs}
            for future in as_completed(future_by_key):
                key = future_by_key[future]
                try:
                    output = future.result()
                except Exception as exc:
                    raise RuntimeError(f"Backtest case failed: {key}") from exc
                print(f"Finished {output.key}: {output.path}", flush=True)
                outputs.append(output)

    paths = {output.key: output.path for output in outputs}
    payloads = {key: json.loads(path.read_text(encoding="utf-8")) for key, path in paths.items()}
    return payloads, paths


def _run_case_backtest_job(job: BacktestCaseJob) -> BacktestCaseOutput:
    store = SQLiteStore(job.database_path)
    config = StoredRiskParityBacktestConfig(
        start_date=job.start_date,
        end_date=job.end_date,
        initial_cash_cnh=job.initial_cash_cnh,
        rebalance_frequency=job.rebalance_frequency,
        transaction_cost_bps=job.transaction_cost_bps,
        rebalance_min_weight_delta=job.rebalance_min_weight_delta,
        rebalance_min_total_weight_delta=job.rebalance_min_total_weight_delta,
        rebalance_force_on_asset_change=job.rebalance_trigger_asset_change,
        sleeve_name=job.case.definition.sleeve_name,
    )
    result = run_stored_risk_parity_backtest(
        store=store,
        instruments=job.case.instruments,
        config=config,
        target_overlays=instantiate_overlays(job.case.definition),
    )
    if job.metrics_only:
        payload = result.model_dump(mode="json", include={"nav_series", "final_snapshot"})
        payload["proposals"] = []
    else:
        payload = _stable_backtest_payload(result.model_dump(mode="json"))
    path = job.output_dir / f"{job.case.definition.key}.json"
    path.write_text(_json_dump(payload, compact=job.compact_json), encoding="utf-8")
    return BacktestCaseOutput(key=job.case.definition.key, path=path)


def _requested_worker_count(requested_workers: int | None) -> int:
    if requested_workers is None:
        requested_workers = os.cpu_count() or 1
    if requested_workers < 1:
        raise ValueError("--workers must be at least 1.")
    return requested_workers


def _worker_count(requested_workers: int, case_count: int) -> int:
    if case_count <= 0:
        raise ValueError("No research cases were selected.")
    return min(requested_workers, case_count)


def _trained_technical_tree_cases(
    *,
    database_path: Path,
    start_date: date,
    end_date: date,
    split_date: date,
    rebalance_frequency: str = "monthly",
    workers: int = 1,
    core_only: bool = False,
) -> list[ResearchCase]:
    specs = _technical_tree_specs()
    if core_only:
        specs = specs[:1]
    train_workers = _worker_count(workers, len(specs))
    print(f"Training {len(specs)} technical tree model(s) with {train_workers} worker process(es).", flush=True)
    jobs = [
        TechnicalTreeTrainingJob(
            spec=spec,
            database_path=database_path,
            start_date=start_date,
            end_date=end_date,
            split_date=split_date,
            rebalance_frequency=rebalance_frequency,
        )
        for spec in specs
    ]
    batches: list[list[ResearchCase]] = []
    if train_workers == 1:
        for job in jobs:
            batch = _train_technical_tree_case_job(job)
            print(f"Finished technical tree training: {job.spec['key']}", flush=True)
            batches.append(batch)
    else:
        with ProcessPoolExecutor(max_workers=train_workers) as executor:
            future_by_key = {executor.submit(_train_technical_tree_case_job, job): str(job.spec["key"]) for job in jobs}
            for future in as_completed(future_by_key):
                key = future_by_key[future]
                try:
                    batch = future.result()
                except Exception as exc:
                    raise RuntimeError(f"Technical tree training failed: {key}") from exc
                print(f"Finished technical tree training: {key}", flush=True)
                batches.append(batch)
    case_by_key = {case.definition.key: case for batch in batches for case in batch}
    ordered_cases: list[ResearchCase] = []
    for spec in specs:
        for key in _technical_tree_case_keys(spec):
            if key in case_by_key:
                ordered_cases.append(case_by_key[key])
    return ordered_cases


def _train_technical_tree_case_job(job: TechnicalTreeTrainingJob) -> list[ResearchCase]:
    store = SQLiteStore(job.database_path)
    bars_by_symbol = {
        symbol: store.list_price_bars(symbol, start_date=job.start_date, end_date=job.end_date)
        for symbol in MULTI_ASSET_ETF_UNIVERSE
    }
    trade_dates = _common_dates(bars_by_symbol)
    rebalance_dates = _training_rebalance_dates(trade_dates, job.rebalance_frequency)
    spec = job.spec
    overlay = train_technical_tree_allocator_overlay(
        symbols=sorted(MULTI_ASSET_ETF_UNIVERSE),
        bars_by_symbol=bars_by_symbol,
        trade_dates=trade_dates,
        rebalance_dates=rebalance_dates,
        split_date=job.split_date,
        max_depth=spec["max_depth"],
        min_samples_leaf=_technical_tree_min_samples_leaf(spec, job.rebalance_frequency),
        top_n=spec["top_n"],
        min_selected=spec["min_selected"],
        tree_weight=spec["tree_weight"],
        momentum_weight=spec["momentum_weight"],
        technical_weight=spec["technical_weight"],
        allocation_tilt=spec["allocation_tilt"],
        min_long_momentum=Decimal("0"),
        require_positive_timeseries=True,
        reallocate_selected=True,
    )
    return _technical_tree_cases_from_overlay(spec=spec, overlay=overlay)


def _technical_tree_specs() -> list[dict[str, Any]]:
    return [
        {
            "key": "multi_asset_technical_tree_allocator_top6",
            "name": "Multi-asset: technical tree allocator top 6",
            "sleeve": "multi-asset-technical-tree-allocator-top6",
            "top_n": 6,
            "min_selected": 4,
            "max_depth": 3,
            "min_samples_leaf": 25,
            "tree_weight": Decimal("0.45"),
            "momentum_weight": Decimal("0.35"),
            "technical_weight": Decimal("0.20"),
            "allocation_tilt": Decimal("0.35"),
            "add_pool_tree_tilt": True,
        },
        {
            "key": "multi_asset_technical_tree_allocator_top8",
            "name": "Multi-asset: technical tree allocator top 8",
            "sleeve": "multi-asset-technical-tree-allocator-top8",
            "top_n": 8,
            "min_selected": 5,
            "max_depth": 3,
            "min_samples_leaf": 25,
            "tree_weight": Decimal("0.45"),
            "momentum_weight": Decimal("0.35"),
            "technical_weight": Decimal("0.20"),
            "allocation_tilt": Decimal("0.35"),
            "add_pool_tree_tilt": True,
        },
        {
            "key": "multi_asset_technical_tree_allocator_top10",
            "name": "Multi-asset: technical tree allocator top 10",
            "sleeve": "multi-asset-technical-tree-allocator-top10",
            "top_n": 10,
            "min_selected": 6,
            "max_depth": 4,
            "min_samples_leaf": 30,
            "tree_weight": Decimal("0.50"),
            "momentum_weight": Decimal("0.30"),
            "technical_weight": Decimal("0.20"),
            "allocation_tilt": Decimal("0.30"),
            "add_pool_tree_tilt": False,
        },
    ]


def _technical_tree_cases_from_overlay(
    *,
    spec: Mapping[str, Any],
    overlay: Any,
) -> list[ResearchCase]:
    cases: list[ResearchCase] = []
    definition = replace(
        strategy_definition_from_overlay(overlay),
        key=spec["key"],
        name=spec["name"],
        sleeve_name=spec["sleeve"],
        state="research",
        description=(
            "Pre-2023 trained technical decision-tree allocator that blends frozen tree forecasts, "
            "cross-sectional momentum ranks, and MACD/Bollinger/RSI technical-health ranks; keeps more "
            "assets than the old concentrated top-4 filter."
        ),
    )
    cases.append(ResearchCase(definition, MULTI_ASSET_ETF_UNIVERSE, "multi_asset"))
    if spec["add_pool_tree_tilt"]:
        pool_overlay = AssetPoolFilterOverlay(
            top_n=spec["top_n"],
            min_selected=spec["min_selected"],
            trend_weight=Decimal("0.75"),
            volume_weight=Decimal("0.25"),
            require_positive_long_momentum=True,
            reallocate_selected=True,
        )
        pool_definition = strategy_definition_from_overlay(pool_overlay)
        tree_definition = strategy_definition_from_overlay(
            DecisionTreeSignalOverlay(
                model=overlay.model,
                tilt=Decimal("0.16"),
                max_active_weight=Decimal("0.06"),
            )
        )
        combined = replace(
            pool_definition,
            key=f"multi_asset_price_volume_technical_tree_tilt_top{spec['top_n']}",
            name=f"Multi-asset: price/volume top {spec['top_n']} + technical tree tilt",
            sleeve_name=f"multi-asset-price-volume-technical-tree-tilt-top{spec['top_n']}",
            state="research",
            description=(
                "Two-stage candidate: select a diversified top-ranked ETF set with price/volume ranks, "
                "then tilt allocation weights using a pre-2023 trained technical decision tree with "
                "MACD, Bollinger, RSI, momentum, volume, and volatility features."
            ),
            overlays=pool_definition.overlays + tree_definition.overlays,
        )
        cases.append(ResearchCase(combined, MULTI_ASSET_ETF_UNIVERSE, "multi_asset"))
        if spec["top_n"] == 6:
            cases.extend(
                _technical_tree_combo_cases(
                    pool_definition=pool_definition,
                    tree_definition=tree_definition,
                    top_n=spec["top_n"],
                )
            )
    return cases


def _technical_tree_case_keys(spec: Mapping[str, Any]) -> list[str]:
    keys = [str(spec["key"])]
    if spec["add_pool_tree_tilt"]:
        top_n = spec["top_n"]
        keys.append(f"multi_asset_price_volume_technical_tree_tilt_top{top_n}")
        if top_n == 6:
            keys.extend(
                [
                    f"multi_asset_price_volume_technical_tree_relative12_top{top_n}",
                    f"multi_asset_price_volume_technical_tree_adaptive_top{top_n}",
                    f"multi_asset_price_volume_technical_tree_ts252_top{top_n}",
                    f"multi_asset_price_volume_technical_tree_relative12_adaptive_top{top_n}",
                    f"multi_asset_price_volume_technical_tree_basket_guard65_top{top_n}",
                    f"multi_asset_price_volume_technical_tree_relative12_basket_guard65_top{top_n}",
                    f"multi_asset_price_volume_technical_tree_relative12_basket_guard55_top{top_n}",
                    f"multi_asset_price_volume_technical_tree_relative12_adaptive_basket_guard65_top{top_n}",
                    f"multi_asset_trend_quality_technical_tree_relative12_top{top_n}",
                    f"multi_asset_trend_quality_technical_tree_relative12_adaptive_top{top_n}",
                ]
            )
    return keys


def _daily_core_cases(cases: Sequence[ResearchCase]) -> list[ResearchCase]:
    allowed_keys = [
        current_sota_definition().key,
        "multi_asset_risk_parity",
        "multi_asset_relative_momentum_20_60d_tilt20_regime",
        "multi_asset_price_volume_pool_filter_top6",
        "multi_asset_technical_tree_allocator_top6",
        "multi_asset_price_volume_technical_tree_tilt_top6",
        "multi_asset_price_volume_technical_tree_relative12_top6",
        "multi_asset_price_volume_technical_tree_relative12_adaptive_top6",
    ]
    case_by_key = {case.definition.key: case for case in cases}
    missing = [key for key in allowed_keys if key not in case_by_key]
    if missing:
        raise ValueError(f"Daily core research case set is missing: {', '.join(missing)}")
    return [case_by_key[key] for key in allowed_keys]


def _technical_tree_combo_cases(
    *,
    pool_definition: StrategyDefinition,
    tree_definition: StrategyDefinition,
    top_n: int,
) -> list[ResearchCase]:
    relative_definition = strategy_definition_from_overlay(
        RegimeGatedRelativeMomentumOverlay(
            medium_lookback_bars=20,
            long_lookback_bars=60,
            calm_tilt=Decimal("0.12"),
            risk_tilt=Decimal("0.12"),
            max_active_weight=Decimal("0.05"),
        )
    )
    adaptive_definition = strategy_definition_from_overlay(
        AdaptiveTrendOverlay(
            weak_scale=Decimal("0.50"),
            neutral_scale=Decimal("0.80"),
            defensive_scale=Decimal("0.35"),
            rebound_scale=Decimal("1.00"),
        )
    )
    ts_definition = strategy_definition_from_overlay(
        TimeSeriesMomentumOverlay(
            lookback_bars=252,
            threshold=Decimal("0"),
            reallocate_survivors=True,
        )
    )
    basket_guard65_definition = strategy_definition_from_overlay(
        BasketRiskControlOverlay(
            neutral_scale=Decimal("0.90"),
            defensive_scale=Decimal("0.65"),
            severe_scale=Decimal("0.45"),
        )
    )
    basket_guard55_definition = strategy_definition_from_overlay(
        BasketRiskControlOverlay(
            weak_breadth_threshold=Decimal("0.50"),
            healthy_breadth_threshold=Decimal("0.65"),
            drawdown_trigger=Decimal("-0.06"),
            severe_drawdown_trigger=Decimal("-0.12"),
            volatility_ratio_trigger=Decimal("1.25"),
            severe_volatility_ratio_trigger=Decimal("1.55"),
            neutral_scale=Decimal("0.85"),
            defensive_scale=Decimal("0.55"),
            severe_scale=Decimal("0.35"),
        )
    )
    quality_definition = strategy_definition_from_overlay(
        TrendQualityFilterOverlay(
            top_n=top_n,
            min_selected=max(3, min(4, top_n)),
            reallocate_selected=True,
        )
    )
    specs = [
        (
            "relative12",
            f"Multi-asset: price/volume top {top_n} + technical tree + 20/60 relative tilt",
            pool_definition.overlays + tree_definition.overlays + relative_definition.overlays,
            "Adds a restrained 20/60d relative-momentum tilt after the pre-2023 trained technical tree tilt.",
        ),
        (
            "adaptive",
            f"Multi-asset: price/volume top {top_n} + technical tree + adaptive trend",
            pool_definition.overlays + tree_definition.overlays + adaptive_definition.overlays,
            "Adds per-asset adaptive trend exposure scaling after the pre-2023 trained technical tree tilt.",
        ),
        (
            "ts252",
            f"Multi-asset: price/volume top {top_n} + technical tree + 252d TS momentum",
            pool_definition.overlays + tree_definition.overlays + ts_definition.overlays,
            "Adds a 252d time-series momentum gate after the pre-2023 trained technical tree tilt.",
        ),
        (
            "relative12_adaptive",
            f"Multi-asset: price/volume top {top_n} + technical tree + relative/adaptive",
            pool_definition.overlays + tree_definition.overlays + relative_definition.overlays + adaptive_definition.overlays,
            "Combines a restrained 20/60d relative-momentum tilt with adaptive trend exposure scaling.",
        ),
        (
            "basket_guard65",
            f"Multi-asset: price/volume top {top_n} + technical tree + basket risk control",
            pool_definition.overlays + tree_definition.overlays + basket_guard65_definition.overlays,
            "Adds portfolio-level breadth, drawdown, and volatility exposure scaling after the technical tree tilt.",
        ),
        (
            "relative12_basket_guard65",
            f"Multi-asset: price/volume top {top_n} + technical tree + relative tilt + basket risk control",
            pool_definition.overlays
            + tree_definition.overlays
            + relative_definition.overlays
            + basket_guard65_definition.overlays,
            "Combines the restrained 20/60d relative-momentum tilt with moderate basket-level risk scaling.",
        ),
        (
            "relative12_basket_guard55",
            f"Multi-asset: price/volume top {top_n} + technical tree + relative tilt + strict basket risk control",
            pool_definition.overlays
            + tree_definition.overlays
            + relative_definition.overlays
            + basket_guard55_definition.overlays,
            "Combines the restrained 20/60d relative-momentum tilt with stricter basket-level risk scaling.",
        ),
        (
            "relative12_adaptive_basket_guard65",
            f"Multi-asset: price/volume top {top_n} + technical tree + relative/adaptive + basket risk control",
            pool_definition.overlays
            + tree_definition.overlays
            + relative_definition.overlays
            + adaptive_definition.overlays
            + basket_guard65_definition.overlays,
            "Combines relative momentum, per-asset adaptive trend scaling, and portfolio-level basket risk control.",
        ),
        (
            "quality_relative12",
            f"Multi-asset: trend-quality top {top_n} + technical tree + 20/60 relative tilt",
            quality_definition.overlays + tree_definition.overlays + relative_definition.overlays,
            "Uses risk-adjusted trend-quality selection before the technical tree tilt and restrained relative momentum.",
        ),
        (
            "quality_relative12_adaptive",
            f"Multi-asset: trend-quality top {top_n} + technical tree + relative/adaptive",
            quality_definition.overlays
            + tree_definition.overlays
            + relative_definition.overlays
            + adaptive_definition.overlays,
            "Combines risk-adjusted trend-quality selection, technical tree tilt, relative momentum, and adaptive trend scaling.",
        ),
    ]
    return [
        ResearchCase(
            replace(
                quality_definition if suffix.startswith("quality_") else pool_definition,
                key=(
                    f"multi_asset_trend_quality_technical_tree_{suffix.removeprefix('quality_')}_top{top_n}"
                    if suffix.startswith("quality_")
                    else f"multi_asset_price_volume_technical_tree_{suffix}_top{top_n}"
                ),
                name=name,
                sleeve_name=(
                    f"multi-asset-trend-quality-technical-tree-{suffix.removeprefix('quality_')}-top{top_n}"
                    if suffix.startswith("quality_")
                    else f"multi-asset-price-volume-technical-tree-{suffix}-top{top_n}"
                ),
                state="research",
                description=description,
                overlays=overlays,
            ),
            MULTI_ASSET_ETF_UNIVERSE,
            "multi_asset",
        )
        for suffix, name, overlays, description in specs
    ]


def _common_dates(bars_by_symbol: Mapping[str, Sequence[Any]]) -> list[date]:
    date_sets = [{bar.trade_date for bar in bars} for bars in bars_by_symbol.values() if bars]
    return sorted(set.intersection(*date_sets)) if date_sets else []


def _month_start_dates(trade_dates: Sequence[date]) -> list[date]:
    result: list[date] = []
    seen: set[tuple[int, int]] = set()
    for trade_date in sorted(trade_dates):
        key = (trade_date.year, trade_date.month)
        if key in seen:
            continue
        seen.add(key)
        result.append(trade_date)
    return result


def _training_rebalance_dates(trade_dates: Sequence[date], rebalance_frequency: str) -> list[date]:
    frequency = rebalance_frequency.lower()
    if frequency == "daily":
        return list(trade_dates)
    if frequency == "monthly":
        return _month_start_dates(trade_dates)
    raise ValueError(f"Unsupported rebalance_frequency '{rebalance_frequency}'. Use 'monthly' or 'daily'.")


def _technical_tree_min_samples_leaf(spec: Mapping[str, Any], rebalance_frequency: str) -> int:
    min_samples_leaf = int(spec["min_samples_leaf"])
    if rebalance_frequency.lower() == "daily":
        return max(min_samples_leaf, 250)
    return min_samples_leaf


def _date_range_from_store(
    *,
    store: SQLiteStore,
    symbols: Sequence[str],
    start_date_arg: str | None,
    end_date_arg: str | None,
) -> tuple[date, date]:
    first_dates: list[date] = []
    last_dates: list[date] = []
    missing: list[str] = []
    for symbol in symbols:
        bars = store.list_price_bars(symbol)
        if not bars:
            missing.append(symbol)
            continue
        first_dates.append(bars[0].trade_date)
        last_dates.append(bars[-1].trade_date)
    if missing:
        raise ValueError(
            "Missing stored bars for "
            + ", ".join(missing)
            + ". Run scripts/backfill_tushare_us.py first; fall back to Yahoo if Tushare is unavailable."
        )

    start_date = date.fromisoformat(start_date_arg) if start_date_arg else max(first_dates)
    end_date = date.fromisoformat(end_date_arg) if end_date_arg else min(last_dates)
    if end_date <= start_date:
        raise ValueError(f"Invalid backtest range: {start_date} to {end_date}.")
    return start_date, end_date


def _build_comparisons(
    *,
    cases: Sequence[ResearchCase],
    payloads: Mapping[str, dict[str, Any]],
    benchmark_payloads: Mapping[str, dict[str, Any]],
    split_date: date,
) -> dict[str, dict[str, Any]]:
    current_sota = current_sota_definition()
    benchmarks = {
        "current_sota": (current_sota.name, payloads[current_sota.key]),
        "multi_asset_risk_parity": ("Multi-asset risk parity", payloads["multi_asset_risk_parity"]),
        "aor": (MULTI_ASSET_BENCHMARK_NAME, benchmark_payloads["aor"]),
        "msci_world": (MSCI_WORLD_PROXY_NAME, benchmark_payloads["msci_world"]),
    }
    comparisons: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_comparisons: dict[str, Any] = {}
        for benchmark_key, (benchmark_name, benchmark_payload) in benchmarks.items():
            case_comparisons[benchmark_key] = compare_backtests(
                baseline=benchmark_payload,
                candidate=payloads[case.definition.key],
                split_date=split_date,
                baseline_name=benchmark_name,
                candidate_name=case.definition.name,
            )
        comparisons[case.definition.key] = case_comparisons
    return comparisons


def _ranking_rows(
    *,
    cases: Sequence[ResearchCase],
    comparisons: Mapping[str, Mapping[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        primary = comparisons[case.definition.key]["aor"]
        full = primary["metrics"]["full"]
        in_sample = primary["metrics"]["in_sample"]
        oos = primary["metrics"]["out_of_sample"]
        vs_sota_oos = comparisons[case.definition.key]["current_sota"]["metrics"]["out_of_sample"]
        vs_multi_rp_oos = comparisons[case.definition.key]["multi_asset_risk_parity"]["metrics"]["out_of_sample"]
        vs_aor_oos = primary["metrics"]["out_of_sample"]
        retention_ratio = sharpe_retention_ratio(in_sample["candidate"]["sharpe"], oos["candidate"]["sharpe"])
        rows.append(
            {
                "key": case.definition.key,
                "name": case.definition.name,
                "universe": case.universe_label,
                "fullReturn": full["candidate"]["return"],
                "fullAnnualizedReturn": full["candidate"]["annualizedReturn"],
                "fullSharpe": full["candidate"]["sharpe"],
                "fullCalmar": full["candidate"]["calmar"],
                "fullMaxDrawdown": full["candidate"]["maxDrawdown"],
                "inSampleSharpe": in_sample["candidate"]["sharpe"],
                "oosReturn": oos["candidate"]["return"],
                "oosAnnualizedReturn": oos["candidate"]["annualizedReturn"],
                "oosSharpe": oos["candidate"]["sharpe"],
                "oosCalmar": oos["candidate"]["calmar"],
                "oosMaxDrawdown": oos["candidate"]["maxDrawdown"],
                "outToInSharpeRatio": retention_ratio,
                "sharpeRetentionBandDistance": retention_band_distance(retention_ratio),
                "sharpeRetentionBandPass": retention_band_pass(retention_ratio),
                "oosAlphaVsCurrentSota": vs_sota_oos["delta"]["return"],
                "oosInformationRatioVsCurrentSota": vs_sota_oos["active"]["informationRatio"],
                "oosAlphaVsMultiAssetRiskParity": vs_multi_rp_oos["delta"]["return"],
                "oosInformationRatioVsMultiAssetRiskParity": vs_multi_rp_oos["active"]["informationRatio"],
                "oosAlphaVsAor": vs_aor_oos["delta"]["return"],
                "oosInformationRatioVsAor": vs_aor_oos["active"]["informationRatio"],
            }
        )
    _score_ranking_rows(rows)
    return sorted(
        rows,
        key=lambda row: (
            _sort_value(row.get("stabilityAdjustedScore")),
            _sort_value(row.get("oosSharpe")),
            _sort_value(row.get("oosCalmar")),
        ),
        reverse=True,
    )


def _score_ranking_rows(rows: list[dict[str, Any]]) -> None:
    scores = {
        "oosSharpe": percentile_scores(rows, "oosSharpe"),
        "retention": retention_closeness_scores(rows),
        "oosCalmar": percentile_scores(rows, "oosCalmar"),
        "oosInformationRatioVsCurrentSota": percentile_scores(rows, "oosInformationRatioVsCurrentSota"),
    }
    for row in rows:
        key = row["key"]
        raw_score = (
            0.45 * scores["oosSharpe"].get(key, 0.0)
            + 0.30 * scores["retention"].get(key, 0.0)
            + 0.15 * scores["oosCalmar"].get(key, 0.0)
            + 0.10 * scores["oosInformationRatioVsCurrentSota"].get(key, 0.0)
        )
        floor_multiplier = _in_sample_sharpe_floor_multiplier(row.get("inSampleSharpe"))
        row["inSampleSharpeFloorMultiplier"] = floor_multiplier
        row["stabilityAdjustedScore"] = raw_score * floor_multiplier


def _in_sample_sharpe_floor_multiplier(value: Any) -> float:
    if not finite_number(value):
        return 0.0
    sharpe = float(value)
    if sharpe <= 0:
        return 0.0
    return min(1.0, sharpe / IN_SAMPLE_SHARPE_FLOOR)


def _ranking_markdown(
    rows: Sequence[dict[str, Any]],
    *,
    rebalance_frequency: str = "monthly",
    transaction_cost_bps: Decimal = Decimal("0"),
    rebalance_min_weight_delta: Decimal = Decimal("0"),
    rebalance_min_total_weight_delta: Decimal = Decimal("0"),
    rebalance_trigger_asset_change: bool = False,
) -> str:
    lines = [
        "# Multi-Asset ETF Research",
        "",
        f"Rebalance frequency: `{rebalance_frequency}`.",
        f"Transaction cost: `{transaction_cost_bps}` bps one-way.",
        (
            "Rebalance gate: "
            f"max target-weight delta `{rebalance_min_weight_delta}`, "
            f"total target-weight delta `{rebalance_min_total_weight_delta}`, "
            f"asset-set change `{rebalance_trigger_asset_change}`."
        ),
        "",
        "Primary external benchmark: AOR, a multi-asset allocation ETF. URTH/MSCI World is retained as an equity-only opportunity-cost reference, not as the primary benchmark for a strategy that can allocate to bonds and commodities.",
        "",
        f"Ranking score: 45% OOS Sharpe percentile, 30% OOS/IS Sharpe retention closeness to {TARGET_RETENTION_LOW:.2f}-{TARGET_RETENTION_HIGH:.2f}, 15% OOS Calmar percentile, 10% OOS IR vs SOTA percentile; multiplied by an IS Sharpe floor against {IN_SAMPLE_SHARPE_FLOOR:.2f}.",
        "",
        "| Rank | Strategy | Universe | Stability Score | IS Sharpe | OOS Sharpe | OOS/IS | Band Pass | OOS Ann. Return | OOS Calmar | OOS Max DD | OOS IR vs SOTA |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for index, row in enumerate(rows, start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(index),
                    row["name"],
                    row["universe"],
                    _fmt_num(row["stabilityAdjustedScore"]),
                    _fmt_num(row["inSampleSharpe"]),
                    _fmt_num(row["oosSharpe"]),
                    _fmt_num(row["outToInSharpeRatio"]),
                    "yes" if row["sharpeRetentionBandPass"] else "no",
                    _fmt_pct(row["oosAnnualizedReturn"]),
                    _fmt_num(row["oosCalmar"]),
                    _fmt_pct(row["oosMaxDrawdown"]),
                    _fmt_num(row["oosInformationRatioVsCurrentSota"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Benchmark Interpretation",
            "",
            "- `current_sota` remains the research hurdle because it is the live SOTA process being challenged.",
            "- `multi_asset_risk_parity` isolates whether adding China, bond, credit, gold, and commodity ETFs helps before adding filters.",
            "- `AOR` is a better external benchmark for multi-asset ETF strategies than MSCI World because it already mixes global equities and fixed income.",
            "- `URTH`/MSCI World is still useful as an equity opportunity-cost reference, but it is no longer sufficient as the primary benchmark once bonds and commodities are investable.",
            "",
        ]
    )
    return "\n".join(lines)


def _buy_and_hold_payload(
    *,
    store: SQLiteStore,
    symbol: str,
    start_date: date,
    end_date: date,
    initial_cash_cnh: Decimal,
) -> dict[str, Any]:
    bars = store.list_price_bars(symbol, start_date=start_date, end_date=end_date)
    rates = store.list_fx_rates(Currency.USD, start_date=start_date, end_date=end_date)
    if not bars:
        raise ValueError(f"No bars found for benchmark {symbol}.")
    if not rates:
        raise ValueError("USD/CNH FX rates are required for benchmark NAV.")
    rates_by_date = {rate.rate_date: rate.rate for rate in rates}
    first_rate = _latest_rate(rates_by_date, bars[0].trade_date)
    first_value_cnh = bars[0].close * first_rate
    shares = initial_cash_cnh / first_value_cnh
    nav_series = []
    for bar in bars:
        rate = _latest_rate(rates_by_date, bar.trade_date)
        nav = shares * bar.close * rate
        nav_series.append(
            {
                "trade_date": bar.trade_date.isoformat(),
                "nav_cnh": str(nav),
                "gross_exposure_cnh": str(nav),
                "cash_cnh": "0",
            }
        )
    return {
        "nav_series": nav_series,
        "proposals": [],
        "final_snapshot": {},
        "benchmark": {"symbol": symbol, "kind": "buy_and_hold"},
    }


def _prices_by_symbol(store: SQLiteStore, symbols: Sequence[str]) -> dict[str, dict[date, float]]:
    return {
        symbol: {bar.trade_date: float(bar.close) for bar in store.list_price_bars(symbol)}
        for symbol in symbols
    }


def _latest_rate(rates_by_date: Mapping[date, Decimal], trade_date: date) -> Decimal:
    available_dates = [rate_date for rate_date in rates_by_date if rate_date <= trade_date]
    if not available_dates:
        raise ValueError(f"No USD/CNH FX rate is available on or before {trade_date}.")
    return rates_by_date[max(available_dates)]


def _stable_backtest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    for proposal in payload.get("proposals", []):
        as_of = str(proposal["as_of"])
        sleeve = str(proposal["sleeve"])
        proposal["proposal_id"] = hashlib.sha1(f"{sleeve}:{as_of}".encode("utf-8")).hexdigest()[:12]
        proposal["created_at"] = f"{as_of}T00:00:00Z"
    return payload


def _json_dump(payload: Any, *, compact: bool) -> str:
    if compact:
        return json.dumps(payload, separators=(",", ":"))
    return json.dumps(payload, indent=2)


def _write_model_cards_html(
    *,
    path: Path,
    cases: Sequence[ResearchCase],
    ranking: Sequence[dict[str, Any]],
) -> None:
    cards = [strategy_model_card(case.definition) for case in cases]
    table_rows = "\n".join(
        (
            f"<tr><td>{index}</td><td>{_esc(row['name'])}</td><td>{_esc(row['universe'])}</td>"
            f"<td>{_fmt_num(row['stabilityAdjustedScore'])}</td><td>{_fmt_num(row['inSampleSharpe'])}</td>"
            f"<td>{_fmt_num(row['oosSharpe'])}</td><td>{_fmt_num(row['outToInSharpeRatio'])}</td>"
            f"<td>{_fmt_num(row['oosInformationRatioVsCurrentSota'])}</td></tr>"
        )
        for index, row in enumerate(ranking, start=1)
    )
    sections = "\n".join(_card_section(card) for card in cards)
    content = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Multi-Asset ETF Model Cards</title>
  <script type="module">import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs'; mermaid.initialize({{startOnLoad: true}});</script>
  <style>
    body {{ margin: 0; font-family: Segoe UI, Arial, sans-serif; color: #172033; background: #f7f9fc; }}
    main {{ max-width: 1200px; margin: 0 auto; padding: 28px; }}
    h1, h2, h3 {{ margin: 0; }}
    h1 {{ font-size: 30px; }}
    h2 {{ margin-top: 28px; font-size: 21px; }}
    h3 {{ margin-top: 18px; font-size: 16px; }}
    p {{ line-height: 1.5; }}
    .subtle {{ color: #607089; }}
    .panel {{ background: #fff; border: 1px solid #dce4ef; border-radius: 8px; padding: 18px; margin-top: 16px; overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ border-bottom: 1px solid #e6edf5; padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ color: #607089; font-size: 12px; text-transform: uppercase; }}
    code, pre {{ font-family: Consolas, Monaco, monospace; }}
    pre {{ background: #101828; color: #e5edf8; padding: 14px; border-radius: 6px; overflow-x: auto; }}
    .mermaid {{ background: #fff; border: 1px solid #e6edf5; border-radius: 6px; padding: 12px; margin-top: 10px; }}
  </style>
</head>
<body>
<main>
  <h1>Multi-Asset ETF Research Models</h1>
  <p class="subtle">AOR is treated as the primary external multi-asset benchmark. MSCI World remains an equity-only reference.</p>
  <section class="panel">
    <h2>Ranking Snapshot</h2>
    <table>
      <thead><tr><th>Rank</th><th>Strategy</th><th>Universe</th><th>Stability Score</th><th>IS Sharpe</th><th>OOS Sharpe</th><th>OOS/IS</th><th>OOS IR vs SOTA</th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </section>
  {sections}
</main>
</body>
</html>
"""
    path.write_text(content, encoding="utf-8")


def _card_section(card: dict[str, Any]) -> str:
    definition = card["definition"]
    return f"""
  <section class="panel">
    <h2>{_esc(definition['name'])}</h2>
    <p class="subtle">{_esc(definition['description'])}</p>
    <h3>Layer Diagram</h3>
    <div class="mermaid">{_esc(card['layerDiagram'])}</div>
    <h3>Decision Tree</h3>
    <div class="mermaid">{_esc(card['decisionTree'])}</div>
    <h3>Raw Decision Tree</h3>
    <pre>{_esc(card['decisionTree'])}</pre>
  </section>
"""


def _readme(
    *,
    start_date: date,
    end_date: date,
    split_date: date,
    rebalance_frequency: str,
    transaction_cost_bps: Decimal,
    rebalance_min_weight_delta: Decimal,
    rebalance_min_total_weight_delta: Decimal,
    rebalance_trigger_asset_change: bool,
    ranking: Sequence[dict[str, Any]],
    output_dir: Path,
) -> str:
    best = ranking[0]
    return "\n".join(
        [
            "# Multi-Asset ETF Research",
            "",
            f"- Range: {start_date.isoformat()} to {end_date.isoformat()}",
            f"- OOS split: {split_date.isoformat()}",
            f"- Rebalance frequency: {rebalance_frequency}",
            f"- Transaction cost: {transaction_cost_bps} bps one-way",
            (
                "- Rebalance gate: "
                f"max target-weight delta {rebalance_min_weight_delta}, "
                f"total target-weight delta {rebalance_min_total_weight_delta}, "
                f"asset-set change {rebalance_trigger_asset_change}"
            ),
            f"- Primary external benchmark: {MULTI_ASSET_BENCHMARK_NAME}",
            f"- Equity-only reference: {MSCI_WORLD_PROXY_NAME}",
            f"- Top stability-adjusted candidate: {best['name']}",
            f"- Top candidate stability score: {_fmt_num(best['stabilityAdjustedScore'])}",
            f"- Top candidate IS Sharpe: {_fmt_num(best['inSampleSharpe'])}",
            f"- Top candidate OOS Sharpe: {_fmt_num(best['oosSharpe'])}",
            f"- Top candidate OOS/IS Sharpe ratio: {_fmt_num(best['outToInSharpeRatio'])}",
            f"- Top candidate OOS IR vs current SOTA: {_fmt_num(best['oosInformationRatioVsCurrentSota'])}",
            "",
            "## Files",
            "",
            f"- Rankings: `{output_dir / 'multi_asset_rankings.md'}`",
            f"- Ranking data: `{output_dir / 'multi_asset_rankings.json'}`",
            f"- Model cards: `{output_dir / 'multi_asset_model_cards.html'}`",
            "- Each strategy also has a `.json` result and `.html` report in this folder.",
            "",
        ]
    )


def _sort_value(value: Any) -> float:
    return float(value) if isinstance(value, int | float) else float("-inf")


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def _fmt_num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


if __name__ == "__main__":
    main()
