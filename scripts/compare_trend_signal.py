from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.backtest.comparison import (
    build_decision_diagnostics,
    build_market_data_audit,
    build_signal_diagnostics,
    build_signal_forecast_diagnostics,
    compare_backtests,
    write_comparison_artifacts,
    write_robustness_artifacts,
)
from systematic_trading.backtest.reporting import write_backtest_report
from systematic_trading.backtest.stored import StoredRiskParityBacktestConfig, run_stored_risk_parity_backtest
from systematic_trading.config import AppSettings
from systematic_trading.data.yahoo import YahooChartProvider
from systematic_trading.research import (
    BENCHMARK_INSTRUMENTS,
    GLOBAL_ETF_UNIVERSE,
    MSCI_WORLD_PROXY_NAME,
    MSCI_WORLD_PROXY_SYMBOL,
    build_model_structure_comparison,
    current_sota_definition,
    instantiate_overlays,
    risk_parity_definition,
    strategy_definition_from_overlay,
)
from systematic_trading.signals import (
    AdaptiveTrendOverlay,
    CountryCompositeFactorOverlay,
    DecisionTreeSignalOverlay,
    RegimeGatedRelativeMomentumOverlay,
    TimeSeriesMomentumOverlay,
    train_decision_tree_overlay,
)
from systematic_trading.signals.library import signal_library_rows, write_signal_library_markdown
from systematic_trading.storage.sqlite import SQLiteStore


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare a research overlay against the registered SOTA or legacy risk-parity baseline."
    )
    parser.add_argument("--database", default=None)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--split-date", default="2023-01-01")
    parser.add_argument("--initial-cash-cnh", default="1000000")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument(
        "--baseline-model",
        choices=["sota", "risk-parity"],
        default="sota",
        help="Research hurdle used as the comparison baseline.",
    )
    parser.add_argument(
        "--overlay",
        choices=["trend", "adaptive", "relative", "country-factor", "decision-tree"],
        default="trend",
    )
    parser.add_argument("--trend-lookback-bars", type=int, default=252)
    parser.add_argument("--trend-threshold", default="0")
    parser.add_argument("--adaptive-short-lookback-bars", type=int, default=63)
    parser.add_argument("--adaptive-medium-lookback-bars", type=int, default=126)
    parser.add_argument("--adaptive-long-lookback-bars", type=int, default=252)
    parser.add_argument("--adaptive-weak-scale", default="0.35")
    parser.add_argument("--adaptive-neutral-scale", default="0.75")
    parser.add_argument("--adaptive-defensive-scale", default="0.35")
    parser.add_argument("--adaptive-rebound-scale", default="1.00")
    parser.add_argument(
        "--no-adaptive-reallocate-residual",
        action="store_true",
        help="Leave residual from scaled-down adaptive positions in cash.",
    )
    parser.add_argument("--relative-medium-lookback-bars", type=int, default=126)
    parser.add_argument("--relative-long-lookback-bars", type=int, default=252)
    parser.add_argument("--relative-calm-tilt", default="0.12")
    parser.add_argument("--relative-risk-tilt", default="0.12")
    parser.add_argument("--relative-max-active-weight", default="0.07")
    parser.add_argument("--factor-short-momentum-bars", type=int, default=63)
    parser.add_argument("--factor-medium-momentum-bars", type=int, default=126)
    parser.add_argument("--factor-long-momentum-bars", type=int, default=252)
    parser.add_argument("--factor-reversal-bars", type=int, default=21)
    parser.add_argument("--factor-mean-reversion-bars", type=int, default=63)
    parser.add_argument("--factor-volume-bars", type=int, default=21)
    parser.add_argument("--factor-slow-volume-bars", type=int, default=126)
    parser.add_argument("--factor-trend-weight", default="0.40")
    parser.add_argument("--factor-volume-weight", default="0.15")
    parser.add_argument("--factor-mean-reversion-weight", default="0.20")
    parser.add_argument("--factor-valuation-weight", default="0.15")
    parser.add_argument("--factor-macro-weight", default="0.10")
    parser.add_argument("--factor-tilt", default="0.12")
    parser.add_argument("--factor-max-active-weight", default="0.06")
    parser.add_argument("--tree-max-depth", type=int, default=3)
    parser.add_argument("--tree-min-samples-leaf", type=int, default=25)
    parser.add_argument("--tree-tilt", default="0.12")
    parser.add_argument("--tree-max-active-weight", default="0.06")
    parser.add_argument(
        "--factor-valuation-scores",
        default="",
        help="Comma-separated SYMBOL=SCORE map where positive means cheaper/more attractive.",
    )
    parser.add_argument(
        "--factor-macro-scores",
        default="",
        help="Comma-separated SYMBOL=SCORE map where positive means stronger macro growth.",
    )
    parser.add_argument(
        "--skip-robustness",
        action="store_true",
        help="Skip the parameter robustness grid.",
    )
    parser.add_argument(
        "--robustness-lookbacks",
        default="63,126,252,378",
        help="Comma-separated trend lookback bars for robustness diagnostics.",
    )
    parser.add_argument(
        "--robustness-thresholds",
        default="-0.05,0,0.05",
        help="Comma-separated trend thresholds for robustness diagnostics.",
    )
    parser.add_argument(
        "--adaptive-robustness-weak-scales",
        default="0.35,0.50,0.65",
        help="Comma-separated weak-exposure scales for adaptive robustness diagnostics.",
    )
    parser.add_argument(
        "--adaptive-robustness-rebound-scales",
        default="0.75,1.00",
        help="Comma-separated rebound scales for adaptive robustness diagnostics.",
    )
    parser.add_argument(
        "--relative-robustness-calm-tilts",
        default="0.04,0.08,0.12",
        help="Comma-separated calm-regime relative tilt strengths.",
    )
    parser.add_argument(
        "--relative-robustness-risk-tilts",
        default="0.12,0.18,0.24",
        help="Comma-separated risk-regime relative tilt strengths.",
    )
    parser.add_argument(
        "--factor-robustness-tilts",
        default="0.06,0.10,0.12,0.16",
        help="Comma-separated composite country-factor tilt strengths.",
    )
    parser.add_argument(
        "--factor-robustness-mean-reversion-weights",
        default="0.10,0.20,0.30",
        help="Comma-separated composite country-factor mean-reversion weights.",
    )
    parser.add_argument(
        "--tree-robustness-tilts",
        default="0.08,0.12,0.16,0.20",
        help="Comma-separated decision-tree tilt strengths.",
    )
    parser.add_argument(
        "--no-fetch-benchmarks",
        action="store_true",
        help="Do not fetch missing benchmark bars from Yahoo before rendering benchmark choices.",
    )
    parser.add_argument(
        "--adjusted-prices",
        action="store_true",
        help="Mark the market-data audit as adjusted-price based.",
    )
    parser.add_argument(
        "--reallocate-survivors",
        action="store_true",
        help="If set, inactive assets are reallocated across positive-trend assets instead of left in cash.",
    )
    args = parser.parse_args()

    settings = AppSettings()
    database_path = Path(args.database) if args.database else settings.database_path
    store = SQLiteStore(database_path)
    store.initialize()

    start_date, end_date = _date_range_from_store(store, args.start_date, args.end_date)
    if not args.no_fetch_benchmarks:
        _ensure_benchmark_data(store, start_date, end_date)
    output_dir = Path(args.output_dir or _default_output_dir(args.overlay))
    output_dir.mkdir(parents=True, exist_ok=True)

    split_date = date.fromisoformat(args.split_date)
    if args.overlay == "decision-tree":
        overlay = _build_decision_tree_overlay(
            store=store,
            args=args,
            start_date=start_date,
            end_date=end_date,
            split_date=split_date,
        )
    else:
        overlay = _build_overlay(args)
    baseline_definition = current_sota_definition() if args.baseline_model == "sota" else risk_parity_definition()
    candidate_definition = strategy_definition_from_overlay(overlay)
    baseline_overlays = instantiate_overlays(baseline_definition)

    baseline_config = StoredRiskParityBacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_cash_cnh=Decimal(args.initial_cash_cnh),
        sleeve_name=baseline_definition.sleeve_name,
    )
    candidate_config = baseline_config.model_copy(
        update={"sleeve_name": candidate_definition.sleeve_name}
    )

    baseline = run_stored_risk_parity_backtest(
        store=store,
        instruments=GLOBAL_ETF_UNIVERSE,
        config=baseline_config,
        target_overlays=baseline_overlays,
    )
    candidate = run_stored_risk_parity_backtest(
        store=store,
        instruments=GLOBAL_ETF_UNIVERSE,
        config=candidate_config,
        target_overlays=[overlay],
    )

    risk_parity_reference_payload = None
    risk_parity_reference_path = None
    if baseline_definition.key != "risk_parity":
        risk_parity_reference = run_stored_risk_parity_backtest(
            store=store,
            instruments=GLOBAL_ETF_UNIVERSE,
            config=baseline_config.model_copy(update={"sleeve_name": risk_parity_definition().sleeve_name}),
        )
        risk_parity_reference_payload = _stable_backtest_payload(risk_parity_reference.model_dump(mode="json"))
        risk_parity_reference_path = output_dir / "risk_parity_reference.json"
        risk_parity_reference_path.write_text(json.dumps(risk_parity_reference_payload, indent=2), encoding="utf-8")

    baseline_path = output_dir / f"{baseline_definition.key}.json"
    candidate_path = output_dir / f"{overlay.name}.json"
    baseline_payload = _stable_backtest_payload(baseline.model_dump(mode="json"))
    candidate_payload = _stable_backtest_payload(candidate.model_dump(mode="json"))
    baseline_path.write_text(json.dumps(baseline_payload, indent=2), encoding="utf-8")
    candidate_path.write_text(json.dumps(candidate_payload, indent=2), encoding="utf-8")

    comparison = compare_backtests(
        baseline=baseline_payload,
        candidate=candidate_payload,
        split_date=split_date,
        baseline_name=baseline_definition.name,
        candidate_name=candidate_definition.name,
    )
    prices_by_symbol = _prices_by_symbol(store)
    signal_diagnostics = build_signal_diagnostics(
        baseline=baseline_payload,
        candidate=candidate_payload,
        prices_by_symbol=prices_by_symbol,
        split_date=split_date,
        signal_name=overlay.name,
    )
    decision_diagnostics = build_decision_diagnostics(signal_diagnostics)
    market_data_audit = build_market_data_audit(
        prices_by_symbol=prices_by_symbol,
        required_dates=[date.fromisoformat(point["trade_date"]) for point in baseline_payload["nav_series"]],
        source_name=f"SQLite {database_path}",
        adjusted_prices=args.adjusted_prices,
    )
    forecast_diagnostics = build_signal_forecast_diagnostics(
        prices_by_symbol=prices_by_symbol,
        rebalance_dates=_rebalance_dates(baseline_payload),
        split_date=split_date,
        lookback_bars=overlay.lookback_bars,
        threshold=float(overlay.threshold),
    )
    artifacts = write_comparison_artifacts(
        comparison=comparison,
        output_dir=output_dir,
        stem="comparison",
        signal_diagnostics=signal_diagnostics,
        market_data_audit=market_data_audit,
        decision_diagnostics=decision_diagnostics,
        forecast_diagnostics=forecast_diagnostics,
        model_structure=build_model_structure_comparison(
            baseline=baseline_definition,
            candidate=candidate_definition,
        ),
    )
    robustness_artifacts = None
    if not args.skip_robustness:
        if args.overlay == "trend":
            robustness_cases = _run_robustness_grid(
                store=store,
                baseline_config=baseline_config,
                baseline_payload=baseline_payload,
                current_overlay=overlay,
                current_candidate_payload=candidate_payload,
                split_date=split_date,
                baseline_name=baseline_definition.name,
                lookbacks=_parse_int_list(args.robustness_lookbacks, include=overlay.lookback_bars),
                thresholds=_parse_decimal_list(args.robustness_thresholds, include=overlay.threshold),
            )
        elif args.overlay == "adaptive":
            robustness_cases = _run_adaptive_robustness_grid(
                store=store,
                baseline_config=baseline_config,
                baseline_payload=baseline_payload,
                current_overlay=overlay,
                current_candidate_payload=candidate_payload,
                split_date=split_date,
                baseline_name=baseline_definition.name,
                weak_scales=_parse_decimal_list(args.adaptive_robustness_weak_scales, include=overlay.weak_scale),
                rebound_scales=_parse_decimal_list(args.adaptive_robustness_rebound_scales, include=overlay.rebound_scale),
            )
        elif args.overlay == "relative":
            robustness_cases = _run_relative_robustness_grid(
                store=store,
                baseline_config=baseline_config,
                baseline_payload=baseline_payload,
                current_overlay=overlay,
                current_candidate_payload=candidate_payload,
                split_date=split_date,
                baseline_name=baseline_definition.name,
                calm_tilts=_parse_decimal_list(args.relative_robustness_calm_tilts, include=overlay.calm_tilt),
                risk_tilts=_parse_decimal_list(args.relative_robustness_risk_tilts, include=overlay.risk_tilt),
            )
        elif args.overlay == "country-factor":
            robustness_cases = _run_country_factor_robustness_grid(
                store=store,
                baseline_config=baseline_config,
                baseline_payload=baseline_payload,
                current_overlay=overlay,
                current_candidate_payload=candidate_payload,
                split_date=split_date,
                baseline_name=baseline_definition.name,
                tilts=_parse_decimal_list(args.factor_robustness_tilts, include=overlay.tilt),
                mean_reversion_weights=_parse_decimal_list(
                    args.factor_robustness_mean_reversion_weights,
                    include=overlay.mean_reversion_weight,
                ),
            )
        else:
            robustness_cases = _run_decision_tree_robustness_grid(
                store=store,
                baseline_config=baseline_config,
                baseline_payload=baseline_payload,
                current_overlay=overlay,
                current_candidate_payload=candidate_payload,
                split_date=split_date,
                baseline_name=baseline_definition.name,
                tilts=_parse_decimal_list(args.tree_robustness_tilts, include=overlay.tilt),
            )
        robustness_artifacts = write_robustness_artifacts(
            cases=robustness_cases,
            output_dir=output_dir,
            stem="robustness",
        )

    if isinstance(overlay, DecisionTreeSignalOverlay):
        training_path = output_dir / "decision_tree_training.json"
        training_path.write_text(
            json.dumps(
                {
                    "model": overlay.model.to_dict(),
                    "signalLibrary": signal_library_rows(),
                    "valuationScores": {symbol: str(value) for symbol, value in sorted(overlay.valuation_scores.items())},
                    "macroScores": {symbol: str(value) for symbol, value in sorted(overlay.macro_scores.items())},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        write_signal_library_markdown(output_dir / "signal_library.md")
    extra_benchmarks = []
    if risk_parity_reference_payload is not None:
        extra_benchmarks.append(
            {
                "id": "risk_parity",
                "name": risk_parity_definition().name,
                "nav_series": risk_parity_reference_payload["nav_series"],
            }
        )
    extra_benchmarks.append({"id": "msci_world", "name": MSCI_WORLD_PROXY_NAME, "symbol": MSCI_WORLD_PROXY_SYMBOL})

    report = write_backtest_report(
        result_path=candidate_path,
        output_path=output_dir / f"{overlay.name}.html",
        database_path=database_path,
        split_date=split_date,
        benchmark_nav_series=baseline_payload["nav_series"],
        benchmark_name=baseline_definition.name,
        extra_benchmarks=extra_benchmarks,
        signal_diagnostics=signal_diagnostics,
    )

    print(baseline_path)
    if risk_parity_reference_path is not None:
        print(risk_parity_reference_path)
    print(candidate_path)
    print(artifacts.markdown_path)
    print(artifacts.json_path)
    if robustness_artifacts is not None:
        print(robustness_artifacts.markdown_path)
        print(robustness_artifacts.json_path)
    print(report.output_path)


def _build_overlay(
    args: argparse.Namespace,
) -> TimeSeriesMomentumOverlay | AdaptiveTrendOverlay | RegimeGatedRelativeMomentumOverlay | CountryCompositeFactorOverlay:
    if args.overlay == "country-factor":
        return CountryCompositeFactorOverlay(
            short_momentum_bars=args.factor_short_momentum_bars,
            medium_momentum_bars=args.factor_medium_momentum_bars,
            long_momentum_bars=args.factor_long_momentum_bars,
            reversal_bars=args.factor_reversal_bars,
            mean_reversion_bars=args.factor_mean_reversion_bars,
            volume_bars=args.factor_volume_bars,
            slow_volume_bars=args.factor_slow_volume_bars,
            trend_weight=Decimal(args.factor_trend_weight),
            volume_weight=Decimal(args.factor_volume_weight),
            mean_reversion_weight=Decimal(args.factor_mean_reversion_weight),
            valuation_weight=Decimal(args.factor_valuation_weight),
            macro_weight=Decimal(args.factor_macro_weight),
            tilt=Decimal(args.factor_tilt),
            max_active_weight=Decimal(args.factor_max_active_weight),
            valuation_scores=_parse_score_map(args.factor_valuation_scores),
            macro_scores=_parse_score_map(args.factor_macro_scores),
        )
    if args.overlay == "adaptive":
        return AdaptiveTrendOverlay(
            short_lookback_bars=args.adaptive_short_lookback_bars,
            medium_lookback_bars=args.adaptive_medium_lookback_bars,
            long_lookback_bars=args.adaptive_long_lookback_bars,
            weak_scale=Decimal(args.adaptive_weak_scale),
            neutral_scale=Decimal(args.adaptive_neutral_scale),
            defensive_scale=Decimal(args.adaptive_defensive_scale),
            rebound_scale=Decimal(args.adaptive_rebound_scale),
            reallocate_residual=not args.no_adaptive_reallocate_residual,
        )
    if args.overlay == "relative":
        return RegimeGatedRelativeMomentumOverlay(
            medium_lookback_bars=args.relative_medium_lookback_bars,
            long_lookback_bars=args.relative_long_lookback_bars,
            calm_tilt=Decimal(args.relative_calm_tilt),
            risk_tilt=Decimal(args.relative_risk_tilt),
            max_active_weight=Decimal(args.relative_max_active_weight),
        )
    return TimeSeriesMomentumOverlay(
        lookback_bars=args.trend_lookback_bars,
        threshold=Decimal(args.trend_threshold),
        reallocate_survivors=args.reallocate_survivors,
    )


def _build_decision_tree_overlay(
    *,
    store: SQLiteStore,
    args: argparse.Namespace,
    start_date: date,
    end_date: date,
    split_date: date,
) -> DecisionTreeSignalOverlay:
    bars_by_symbol = {
        symbol: store.list_price_bars(symbol, start_date=start_date, end_date=end_date)
        for symbol in GLOBAL_ETF_UNIVERSE
    }
    trade_dates = _common_price_dates(bars_by_symbol)
    rebalance_dates = _monthly_rebalance_dates(trade_dates)
    return train_decision_tree_overlay(
        symbols=list(GLOBAL_ETF_UNIVERSE),
        bars_by_symbol=bars_by_symbol,
        trade_dates=trade_dates,
        rebalance_dates=rebalance_dates,
        split_date=split_date,
        max_depth=args.tree_max_depth,
        min_samples_leaf=args.tree_min_samples_leaf,
        tilt=Decimal(args.tree_tilt),
        max_active_weight=Decimal(args.tree_max_active_weight),
        valuation_scores=_parse_score_map(args.factor_valuation_scores),
        macro_scores=_parse_score_map(args.factor_macro_scores),
    )


def _default_output_dir(overlay: str) -> str:
    if overlay == "country-factor":
        return "var/backtests/country_factor_signal"
    if overlay == "adaptive":
        return "var/backtests/adaptive_trend_signal"
    if overlay == "relative":
        return "var/backtests/relative_momentum_signal"
    return "var/backtests/trend_signal"


def _date_range_from_store(
    store: SQLiteStore,
    start_date_arg: str | None,
    end_date_arg: str | None,
) -> tuple[date, date]:
    first_dates: list[date] = []
    last_dates: list[date] = []
    for symbol in GLOBAL_ETF_UNIVERSE:
        bars = store.list_price_bars(symbol)
        if not bars:
            raise ValueError(f"No stored bars found for {symbol}. Run scripts/run_first_backtest.py first.")
        first_dates.append(bars[0].trade_date)
        last_dates.append(bars[-1].trade_date)

    start_date = date.fromisoformat(start_date_arg) if start_date_arg else max(first_dates)
    end_date = date.fromisoformat(end_date_arg) if end_date_arg else min(last_dates)
    if end_date <= start_date:
        raise ValueError(f"Invalid backtest range: {start_date} to {end_date}.")
    return start_date, end_date


def _prices_by_symbol(store: SQLiteStore) -> dict[str, dict[date, float]]:
    return {
        symbol: {bar.trade_date: float(bar.close) for bar in store.list_price_bars(symbol)}
        for symbol in GLOBAL_ETF_UNIVERSE
    }


def _common_price_dates(bars_by_symbol: dict[str, list[object]]) -> list[date]:
    date_sets = [{bar.trade_date for bar in bars} for bars in bars_by_symbol.values()]
    return sorted(set.intersection(*date_sets)) if date_sets else []


def _monthly_rebalance_dates(trade_dates: list[date]) -> list[date]:
    dates: list[date] = []
    seen_months: set[tuple[int, int]] = set()
    for trade_date in trade_dates:
        month_key = (trade_date.year, trade_date.month)
        if month_key in seen_months:
            continue
        seen_months.add(month_key)
        dates.append(trade_date)
    return dates


def _rebalance_dates(payload: dict[str, object]) -> list[date]:
    return [date.fromisoformat(str(proposal["as_of"])) for proposal in payload.get("proposals", [])]


def _parse_int_list(value: str, *, include: int) -> list[int]:
    items = {include}
    items.update(int(item.strip()) for item in value.split(",") if item.strip())
    return sorted(items)


def _parse_decimal_list(value: str, *, include: Decimal) -> list[Decimal]:
    items = {Decimal(include)}
    items.update(Decimal(item.strip()) for item in value.split(",") if item.strip())
    return sorted(items)


def _parse_score_map(value: str) -> dict[str, Decimal]:
    scores: dict[str, Decimal] = {}
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            symbol, score = item.split("=", 1)
        else:
            symbol, score = item.split(":", 1)
        scores[symbol.strip().upper()] = Decimal(score.strip())
    return scores


def _run_robustness_grid(
    *,
    store: SQLiteStore,
    baseline_config: StoredRiskParityBacktestConfig,
    baseline_payload: dict[str, object],
    current_overlay: TimeSeriesMomentumOverlay,
    current_candidate_payload: dict[str, object],
    split_date: date,
    baseline_name: str,
    lookbacks: list[int],
    thresholds: list[Decimal],
) -> list[dict[str, object]]:
    result_cache = {
        (current_overlay.lookback_bars, current_overlay.threshold, current_overlay.reallocate_survivors): current_candidate_payload
    }
    cases: list[dict[str, object]] = []
    for lookback in lookbacks:
        for threshold in thresholds:
            for reallocate_survivors in [False, True]:
                overlay = TimeSeriesMomentumOverlay(
                    lookback_bars=lookback,
                    threshold=threshold,
                    reallocate_survivors=reallocate_survivors,
                )
                cache_key = (overlay.lookback_bars, overlay.threshold, overlay.reallocate_survivors)
                candidate_payload = result_cache.get(cache_key)
                if candidate_payload is None:
                    candidate = run_stored_risk_parity_backtest(
                        store=store,
                        instruments=GLOBAL_ETF_UNIVERSE,
                        config=baseline_config.model_copy(
                            update={"sleeve_name": f"risk-parity+{overlay.name}"}
                        ),
                        target_overlays=[overlay],
                    )
                    candidate_payload = _stable_backtest_payload(candidate.model_dump(mode="json"))
                    result_cache[cache_key] = candidate_payload
                comparison = compare_backtests(
                    baseline=baseline_payload,
                    candidate=candidate_payload,
                    split_date=split_date,
                    baseline_name=baseline_name,
                    candidate_name=f"Risk parity + {overlay.name}",
                )
                cases.append(
                    {
                        "name": overlay.name,
                        "lookbackBars": lookback,
                        "threshold": str(threshold),
                        "mode": "reallocate" if reallocate_survivors else "cash",
                        "reallocateSurvivors": reallocate_survivors,
                        "comparison": comparison,
                    }
                )
    return cases


def _run_adaptive_robustness_grid(
    *,
    store: SQLiteStore,
    baseline_config: StoredRiskParityBacktestConfig,
    baseline_payload: dict[str, object],
    current_overlay: AdaptiveTrendOverlay,
    current_candidate_payload: dict[str, object],
    split_date: date,
    baseline_name: str,
    weak_scales: list[Decimal],
    rebound_scales: list[Decimal],
) -> list[dict[str, object]]:
    result_cache = {
        (
            current_overlay.weak_scale,
            current_overlay.rebound_scale,
            current_overlay.reallocate_residual,
        ): current_candidate_payload
    }
    cases: list[dict[str, object]] = []
    for weak_scale in weak_scales:
        for rebound_scale in rebound_scales:
            for reallocate_residual in [False, True]:
                overlay = AdaptiveTrendOverlay(
                    short_lookback_bars=current_overlay.short_lookback_bars,
                    medium_lookback_bars=current_overlay.medium_lookback_bars,
                    long_lookback_bars=current_overlay.long_lookback_bars,
                    weak_scale=weak_scale,
                    neutral_scale=current_overlay.neutral_scale,
                    defensive_scale=current_overlay.defensive_scale,
                    rebound_scale=rebound_scale,
                    reallocate_residual=reallocate_residual,
                )
                cache_key = (overlay.weak_scale, overlay.rebound_scale, overlay.reallocate_residual)
                candidate_payload = result_cache.get(cache_key)
                if candidate_payload is None:
                    candidate = run_stored_risk_parity_backtest(
                        store=store,
                        instruments=GLOBAL_ETF_UNIVERSE,
                        config=baseline_config.model_copy(
                            update={"sleeve_name": f"risk-parity+{overlay.name}"}
                        ),
                        target_overlays=[overlay],
                    )
                    candidate_payload = _stable_backtest_payload(candidate.model_dump(mode="json"))
                    result_cache[cache_key] = candidate_payload
                comparison = compare_backtests(
                    baseline=baseline_payload,
                    candidate=candidate_payload,
                    split_date=split_date,
                    baseline_name=baseline_name,
                    candidate_name=f"Risk parity + {overlay.name}",
                )
                cases.append(
                    {
                        "name": overlay.name,
                        "lookbackBars": overlay.long_lookback_bars,
                        "threshold": str(overlay.long_threshold),
                        "mode": "adaptive-reallocate" if reallocate_residual else "adaptive-cash",
                        "reallocateResidual": reallocate_residual,
                        "weakScale": str(weak_scale),
                        "neutralScale": str(overlay.neutral_scale),
                        "defensiveScale": str(overlay.defensive_scale),
                        "reboundScale": str(rebound_scale),
                        "comparison": comparison,
                    }
                )
    return cases


def _run_relative_robustness_grid(
    *,
    store: SQLiteStore,
    baseline_config: StoredRiskParityBacktestConfig,
    baseline_payload: dict[str, object],
    current_overlay: RegimeGatedRelativeMomentumOverlay,
    current_candidate_payload: dict[str, object],
    split_date: date,
    baseline_name: str,
    calm_tilts: list[Decimal],
    risk_tilts: list[Decimal],
) -> list[dict[str, object]]:
    result_cache = {
        (
            current_overlay.calm_tilt,
            current_overlay.risk_tilt,
        ): current_candidate_payload
    }
    cases: list[dict[str, object]] = []
    for calm_tilt in calm_tilts:
        for risk_tilt in risk_tilts:
            overlay = RegimeGatedRelativeMomentumOverlay(
                medium_lookback_bars=current_overlay.medium_lookback_bars,
                long_lookback_bars=current_overlay.long_lookback_bars,
                fast_volatility_bars=current_overlay.fast_volatility_bars,
                slow_volatility_bars=current_overlay.slow_volatility_bars,
                drawdown_lookback_bars=current_overlay.drawdown_lookback_bars,
                calm_tilt=calm_tilt,
                risk_tilt=risk_tilt,
                drawdown_trigger=current_overlay.drawdown_trigger,
                volatility_ratio_trigger=current_overlay.volatility_ratio_trigger,
                max_active_weight=current_overlay.max_active_weight,
            )
            cache_key = (overlay.calm_tilt, overlay.risk_tilt)
            candidate_payload = result_cache.get(cache_key)
            if candidate_payload is None:
                candidate = run_stored_risk_parity_backtest(
                    store=store,
                    instruments=GLOBAL_ETF_UNIVERSE,
                    config=baseline_config.model_copy(
                        update={"sleeve_name": f"risk-parity+{overlay.name}"}
                    ),
                    target_overlays=[overlay],
                )
                candidate_payload = _stable_backtest_payload(candidate.model_dump(mode="json"))
                result_cache[cache_key] = candidate_payload
            comparison = compare_backtests(
                baseline=baseline_payload,
                candidate=candidate_payload,
                split_date=split_date,
                baseline_name=baseline_name,
                candidate_name=f"Risk parity + {overlay.name}",
            )
            cases.append(
                {
                    "name": overlay.name,
                    "lookbackBars": overlay.long_lookback_bars,
                    "threshold": str(overlay.threshold),
                    "mode": "relative-regime",
                    "calmTilt": str(calm_tilt),
                    "riskTilt": str(risk_tilt),
                    "maxActiveWeight": str(overlay.max_active_weight),
                    "comparison": comparison,
                }
            )
    return cases


def _run_country_factor_robustness_grid(
    *,
    store: SQLiteStore,
    baseline_config: StoredRiskParityBacktestConfig,
    baseline_payload: dict[str, object],
    current_overlay: CountryCompositeFactorOverlay,
    current_candidate_payload: dict[str, object],
    split_date: date,
    baseline_name: str,
    tilts: list[Decimal],
    mean_reversion_weights: list[Decimal],
) -> list[dict[str, object]]:
    result_cache = {
        (
            current_overlay.tilt,
            current_overlay.mean_reversion_weight,
        ): current_candidate_payload
    }
    cases: list[dict[str, object]] = []
    for tilt in tilts:
        for mean_reversion_weight in mean_reversion_weights:
            overlay = CountryCompositeFactorOverlay(
                short_momentum_bars=current_overlay.short_momentum_bars,
                medium_momentum_bars=current_overlay.medium_momentum_bars,
                long_momentum_bars=current_overlay.long_momentum_bars,
                reversal_bars=current_overlay.reversal_bars,
                mean_reversion_bars=current_overlay.mean_reversion_bars,
                volume_bars=current_overlay.volume_bars,
                slow_volume_bars=current_overlay.slow_volume_bars,
                trend_weight=current_overlay.trend_weight,
                volume_weight=current_overlay.volume_weight,
                mean_reversion_weight=mean_reversion_weight,
                valuation_weight=current_overlay.valuation_weight,
                macro_weight=current_overlay.macro_weight,
                tilt=tilt,
                max_active_weight=current_overlay.max_active_weight,
                valuation_scores=current_overlay.valuation_scores,
                macro_scores=current_overlay.macro_scores,
            )
            cache_key = (overlay.tilt, overlay.mean_reversion_weight)
            candidate_payload = result_cache.get(cache_key)
            if candidate_payload is None:
                candidate = run_stored_risk_parity_backtest(
                    store=store,
                    instruments=GLOBAL_ETF_UNIVERSE,
                    config=baseline_config.model_copy(
                        update={"sleeve_name": f"risk-parity+{overlay.name}"}
                    ),
                    target_overlays=[overlay],
                )
                candidate_payload = _stable_backtest_payload(candidate.model_dump(mode="json"))
                result_cache[cache_key] = candidate_payload
            comparison = compare_backtests(
                baseline=baseline_payload,
                candidate=candidate_payload,
                split_date=split_date,
                baseline_name=baseline_name,
                candidate_name=f"Risk parity + {overlay.name}",
            )
            cases.append(
                {
                    "name": overlay.name,
                    "lookbackBars": overlay.lookback_bars,
                    "threshold": str(overlay.threshold),
                    "mode": "country-factor",
                    "tilt": str(tilt),
                    "meanReversionWeight": str(mean_reversion_weight),
                    "trendWeight": str(overlay.trend_weight),
                    "volumeWeight": str(overlay.volume_weight),
                    "valuationWeight": str(overlay.valuation_weight),
                    "macroWeight": str(overlay.macro_weight),
                    "comparison": comparison,
                }
            )
    return cases


def _run_decision_tree_robustness_grid(
    *,
    store: SQLiteStore,
    baseline_config: StoredRiskParityBacktestConfig,
    baseline_payload: dict[str, object],
    current_overlay: DecisionTreeSignalOverlay,
    current_candidate_payload: dict[str, object],
    split_date: date,
    baseline_name: str,
    tilts: list[Decimal],
) -> list[dict[str, object]]:
    result_cache = {current_overlay.tilt: current_candidate_payload}
    cases: list[dict[str, object]] = []
    for tilt in tilts:
        overlay = DecisionTreeSignalOverlay(
            model=current_overlay.model,
            tilt=tilt,
            max_active_weight=current_overlay.max_active_weight,
            valuation_scores=current_overlay.valuation_scores,
            macro_scores=current_overlay.macro_scores,
        )
        candidate_payload = result_cache.get(overlay.tilt)
        if candidate_payload is None:
            candidate = run_stored_risk_parity_backtest(
                store=store,
                instruments=GLOBAL_ETF_UNIVERSE,
                config=baseline_config.model_copy(
                    update={"sleeve_name": f"risk-parity+{overlay.name}"}
                ),
                target_overlays=[overlay],
            )
            candidate_payload = _stable_backtest_payload(candidate.model_dump(mode="json"))
            result_cache[overlay.tilt] = candidate_payload
        comparison = compare_backtests(
            baseline=baseline_payload,
            candidate=candidate_payload,
            split_date=split_date,
            baseline_name=baseline_name,
            candidate_name=f"Risk parity + {overlay.name}",
        )
        cases.append(
            {
                "name": overlay.name,
                "lookbackBars": overlay.lookback_bars,
                "threshold": str(overlay.threshold),
                "mode": "decision-tree",
                "tilt": str(tilt),
                "maxDepth": str(overlay.model.max_depth),
                "minSamplesLeaf": str(overlay.model.min_samples_leaf),
                "comparison": comparison,
            }
        )
    return cases


def _stable_backtest_payload(payload: dict[str, object]) -> dict[str, object]:
    for proposal in payload.get("proposals", []):
        as_of = str(proposal["as_of"])
        sleeve = str(proposal["sleeve"])
        proposal["proposal_id"] = hashlib.sha1(f"{sleeve}:{as_of}".encode("utf-8")).hexdigest()[:12]
        proposal["created_at"] = f"{as_of}T00:00:00Z"
    return payload


def _ensure_benchmark_data(store: SQLiteStore, start_date: date, end_date: date) -> None:
    provider = YahooChartProvider()
    for instrument in BENCHMARK_INSTRUMENTS.values():
        bars = store.list_price_bars(instrument.symbol, start_date=start_date, end_date=end_date)
        if bars:
            continue
        store.upsert_instrument(instrument)
        for bar in provider.fetch_daily_bars(instrument.symbol, start_date, end_date):
            store.upsert_price_bar(instrument.symbol, bar)


if __name__ == "__main__":
    main()
