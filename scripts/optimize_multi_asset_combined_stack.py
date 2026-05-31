from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

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
from systematic_trading.backtest.stored import StoredRiskParityBacktestConfig, run_stored_risk_parity_backtest  # noqa: E402
from systematic_trading.config import AppSettings  # noqa: E402
from systematic_trading.domain.enums import Currency  # noqa: E402
from systematic_trading.research import (  # noqa: E402
    GLOBAL_ETF_UNIVERSE,
    MSCI_WORLD_PROXY_NAME,
    MSCI_WORLD_PROXY_SYMBOL,
    MULTI_ASSET_BENCHMARK_NAME,
    MULTI_ASSET_BENCHMARK_SYMBOL,
    MULTI_ASSET_ETF_UNIVERSE,
    current_sota_definition,
    instantiate_overlays,
    risk_parity_definition,
    strategy_definition_from_overlay,
    strategy_model_card,
)
from systematic_trading.signals import AssetPoolFilterOverlay  # noqa: E402
from systematic_trading.storage.sqlite import SQLiteStore  # noqa: E402


TRADING_DAYS_PER_YEAR = 252

_WORKER_DATABASE_PATH: str | None = None
_WORKER_START_DATE: date | None = None
_WORKER_END_DATE: date | None = None
_WORKER_INITIAL_CASH_CNH: Decimal | None = None
_WORKER_VALIDATION_DATE: date | None = None
_WORKER_OOS_DATE: date | None = None
_WORKER_BASELINE_PAYLOADS: Mapping[str, dict[str, Any]] | None = None


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Optimize a combined stack of multi-asset pool filter plus current SOTA relative momentum. "
            "Parameters are selected on a pre-2023 validation window and frozen for 2023+ OOS."
        )
    )
    parser.add_argument("--database", default=None)
    parser.add_argument("--start-date", default="2012-01-01")
    parser.add_argument("--end-date", default="2026-04-29")
    parser.add_argument("--validation-date", default="2020-01-01")
    parser.add_argument("--oos-date", default="2023-01-01")
    parser.add_argument("--initial-cash-cnh", default="1000000")
    parser.add_argument("--output-dir", default="var/backtests/multi_asset_combined_stack_validation_optimization_2012")
    parser.add_argument("--max-cases", type=int, default=None, help="Optional cap for quick smoke runs.")
    parser.add_argument(
        "--workers",
        type=int,
        default=min(os.cpu_count() or 1, 8),
        help="Number of worker processes for the parameter grid. Use 1 for serial execution.",
    )
    args = parser.parse_args()

    settings = AppSettings()
    database_path = Path(args.database) if args.database else settings.database_path
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(database_path)
    store.initialize()

    all_symbols = sorted(
        set(GLOBAL_ETF_UNIVERSE)
        | set(MULTI_ASSET_ETF_UNIVERSE)
        | {MULTI_ASSET_BENCHMARK_SYMBOL, MSCI_WORLD_PROXY_SYMBOL}
    )
    start_date, end_date = _date_range_from_store(
        store=store,
        symbols=all_symbols,
        start_date_arg=args.start_date,
        end_date_arg=args.end_date,
    )
    validation_date = date.fromisoformat(args.validation_date)
    oos_date = date.fromisoformat(args.oos_date)
    if not (start_date < validation_date < oos_date < end_date):
        raise ValueError("Expected start_date < validation_date < oos_date < end_date.")
    initial_cash_cnh = Decimal(args.initial_cash_cnh)

    baseline_payloads = _baseline_payloads(
        store=store,
        start_date=start_date,
        end_date=end_date,
        initial_cash_cnh=initial_cash_cnh,
    )
    grid = list(_parameter_grid())
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
        initial_cash_cnh=initial_cash_cnh,
        validation_date=validation_date,
        oos_date=oos_date,
        baseline_payloads=baseline_payloads,
    )

    _score_rows(rows)
    ranked = sorted(rows, key=lambda row: row["validationObjectiveScore"], reverse=True)
    winner = ranked[0]
    winner_definition = _combined_definition(index=0, params=_params_from_row(winner), optimized=True)
    winner_payload = _run_candidate_payload(
        store=store,
        definition=winner_definition,
        start_date=start_date,
        end_date=end_date,
        initial_cash_cnh=initial_cash_cnh,
    )

    winner_path = output_dir / "optimized_combined_stack.json"
    winner_path.write_text(json.dumps(winner_payload, indent=2), encoding="utf-8")
    benchmark_path = output_dir / "multi_asset_risk_parity.json"
    benchmark_path.write_text(json.dumps(baseline_payloads["multi_asset_risk_parity"]["payload"], indent=2), encoding="utf-8")
    current_sota_path = output_dir / "current_sota.json"
    current_sota_path.write_text(json.dumps(baseline_payloads["current_sota"]["payload"], indent=2), encoding="utf-8")

    winner_report = write_backtest_report(
        result_path=winner_path,
        output_path=output_dir / "optimized_combined_stack.html",
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
                "id": "multi_asset_risk_parity",
                "name": "Multi-asset risk parity",
                "nav_series": baseline_payloads["multi_asset_risk_parity"]["payload"]["nav_series"],
            },
            {
                "id": "msci_world",
                "name": MSCI_WORLD_PROXY_NAME,
                "symbol": MSCI_WORLD_PROXY_SYMBOL,
            },
        ],
    )
    if winner_report.warnings:
        (output_dir / "optimized_combined_stack_report_warnings.txt").write_text(
            "\n".join(winner_report.warnings) + "\n",
            encoding="utf-8",
        )

    results = {
        "method": {
            "candidateCount": len(rows),
            "workers": workers,
            "trainingWindow": f"{start_date.isoformat()} to {(validation_date.replace(day=1) - _one_day()).isoformat()}",
            "validationWindow": f"{validation_date.isoformat()} to {(oos_date.replace(day=1) - _one_day()).isoformat()}",
            "oosWindow": f"{oos_date.isoformat()} to {end_date.isoformat()}",
            "stack": "risk parity -> asset-pool filter -> SOTA relative momentum 20/60d 20% regime tilt",
            "objective": (
                "Pre-OOS stability-adjusted score: validation annualized return, Sharpe, Calmar, "
                "information ratio versus same-universe multi-asset risk parity, and validation/train "
                f"Sharpe retention closeness to {TARGET_RETENTION_LOW:.2f}-{TARGET_RETENTION_HIGH:.2f}."
            ),
        },
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
    _write_model_card(path=model_card_path, definition=winner_definition, winner=winner)
    readme_path = output_dir / "README.md"
    readme_path.write_text(
        _readme(
            start_date=start_date,
            end_date=end_date,
            validation_date=validation_date,
            oos_date=oos_date,
            results=results,
            output_dir=output_dir,
        ),
        encoding="utf-8",
    )

    for path in [
        results_md,
        results_json,
        winner_path,
        winner_report.output_path,
        model_card_path,
        readme_path,
        benchmark_path,
        current_sota_path,
    ]:
        print(path)


def _parameter_grid() -> Sequence[dict[str, Any]]:
    lookback_sets = [
        (21, 63, 126),
        (21, 63, 252),
        (21, 126, 252),
        (63, 126, 252),
    ]
    weight_sets = [
        (Decimal("1.00"), Decimal("0.00")),
        (Decimal("0.80"), Decimal("0.20")),
        (Decimal("0.75"), Decimal("0.25")),
        (Decimal("0.50"), Decimal("0.50")),
    ]
    top_ns = [3, 4, 5, 6, 8]
    min_selected_values = [2, 3]
    cases: list[dict[str, Any]] = []
    for short, medium, long in lookback_sets:
        for trend_weight, volume_weight in weight_sets:
            for top_n in top_ns:
                for min_selected in min_selected_values:
                    if min_selected > top_n:
                        continue
                    cases.append(
                        {
                            "short_momentum_bars": short,
                            "medium_momentum_bars": medium,
                            "long_momentum_bars": long,
                            "volume_bars": 21,
                            "slow_volume_bars": 126,
                            "trend_weight": trend_weight,
                            "volume_weight": volume_weight,
                            "top_n": top_n,
                            "min_selected": min_selected,
                            "require_positive_long_momentum": True,
                            "min_long_momentum": Decimal("0"),
                            "reallocate_selected": True,
                        }
                    )
    return cases


def _run_grid(
    *,
    tasks: Sequence[tuple[int, dict[str, Any]]],
    workers: int,
    database_path: Path,
    start_date: date,
    end_date: date,
    initial_cash_cnh: Decimal,
    validation_date: date,
    oos_date: date,
    baseline_payloads: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if workers == 1:
        _init_worker(
            str(database_path),
            start_date.isoformat(),
            end_date.isoformat(),
            str(initial_cash_cnh),
            validation_date.isoformat(),
            oos_date.isoformat(),
            baseline_payloads,
        )
        return [_run_candidate_task(task) for task in tasks]

    rows: list[dict[str, Any]] = []
    completed = 0
    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_worker,
        initargs=(
            str(database_path),
            start_date.isoformat(),
            end_date.isoformat(),
            str(initial_cash_cnh),
            validation_date.isoformat(),
            oos_date.isoformat(),
            baseline_payloads,
        ),
    ) as executor:
        futures = [executor.submit(_run_candidate_task, task) for task in tasks]
        for future in as_completed(futures):
            rows.append(future.result())
            completed += 1
            if completed == 1 or completed % 10 == 0 or completed == len(tasks):
                print(f"completed {completed}/{len(tasks)} combined-stack cases with {workers} workers", flush=True)
    return rows


def _init_worker(
    database_path: str,
    start_date: str,
    end_date: str,
    initial_cash_cnh: str,
    validation_date: str,
    oos_date: str,
    baseline_payloads: Mapping[str, dict[str, Any]],
) -> None:
    global _WORKER_DATABASE_PATH
    global _WORKER_START_DATE
    global _WORKER_END_DATE
    global _WORKER_INITIAL_CASH_CNH
    global _WORKER_VALIDATION_DATE
    global _WORKER_OOS_DATE
    global _WORKER_BASELINE_PAYLOADS

    _WORKER_DATABASE_PATH = database_path
    _WORKER_START_DATE = date.fromisoformat(start_date)
    _WORKER_END_DATE = date.fromisoformat(end_date)
    _WORKER_INITIAL_CASH_CNH = Decimal(initial_cash_cnh)
    _WORKER_VALIDATION_DATE = date.fromisoformat(validation_date)
    _WORKER_OOS_DATE = date.fromisoformat(oos_date)
    _WORKER_BASELINE_PAYLOADS = baseline_payloads


def _run_candidate_task(task: tuple[int, dict[str, Any]]) -> dict[str, Any]:
    if (
        _WORKER_DATABASE_PATH is None
        or _WORKER_START_DATE is None
        or _WORKER_END_DATE is None
        or _WORKER_INITIAL_CASH_CNH is None
        or _WORKER_VALIDATION_DATE is None
        or _WORKER_OOS_DATE is None
        or _WORKER_BASELINE_PAYLOADS is None
    ):
        raise RuntimeError("Optimization worker was not initialized.")

    index, params = task
    store = SQLiteStore(Path(_WORKER_DATABASE_PATH))
    definition = _combined_definition(index=index, params=params)
    payload = _run_candidate_payload(
        store=store,
        definition=definition,
        start_date=_WORKER_START_DATE,
        end_date=_WORKER_END_DATE,
        initial_cash_cnh=_WORKER_INITIAL_CASH_CNH,
    )
    comparisons = _comparisons(
        candidate_payload=payload,
        candidate_name=definition.name,
        baseline_payloads=_WORKER_BASELINE_PAYLOADS,
        validation_date=_WORKER_VALIDATION_DATE,
        oos_date=_WORKER_OOS_DATE,
    )
    return _row(definition=definition, params=params, comparisons=comparisons)


def _combined_definition(index: int, params: Mapping[str, Any], *, optimized: bool = False) -> Any:
    pool_overlay = AssetPoolFilterOverlay(**params)
    pool_definition = strategy_definition_from_overlay(pool_overlay)
    sota_definition = current_sota_definition()
    if optimized:
        key = "optimized_multi_asset_combined_stack"
        name = "Optimized multi-asset combined stack"
        sleeve_name = "optimized-multi-asset-combined-stack"
        description = (
            "Validation-selected multi-asset asset-pool ranking strategy followed by the current SOTA "
            "relative-momentum overlay."
        )
    else:
        key = f"combined_stack_{_case_key(params)}"
        name = f"Combined stack {index:03d}: {_case_name(params)}"
        sleeve_name = f"combined-stack-candidate-{index:03d}"
        description = (
            "Grid candidate using multi-asset asset-pool filtering followed by the current SOTA "
            "relative-momentum overlay."
        )
    return replace(
        pool_definition,
        key=key,
        name=name,
        sleeve_name=sleeve_name,
        state="research",
        description=description,
        overlays=pool_definition.overlays + sota_definition.overlays,
    )


def _run_candidate_payload(
    *,
    store: SQLiteStore,
    definition: Any,
    start_date: date,
    end_date: date,
    initial_cash_cnh: Decimal,
) -> dict[str, Any]:
    config = StoredRiskParityBacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_cash_cnh=initial_cash_cnh,
        sleeve_name=definition.sleeve_name,
    )
    result = run_stored_risk_parity_backtest(
        store=store,
        instruments=MULTI_ASSET_ETF_UNIVERSE,
        config=config,
        target_overlays=instantiate_overlays(definition),
    )
    return _stable_backtest_payload(result.model_dump(mode="json"))


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
        config=StoredRiskParityBacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_cash_cnh=initial_cash_cnh,
            sleeve_name=current_sota.sleeve_name,
        ),
        target_overlays=instantiate_overlays(current_sota),
    )
    multi_asset_rp_definition = replace(
        risk_parity_definition(),
        key="multi_asset_risk_parity",
        name="Multi-asset risk parity",
        sleeve_name="multi-asset-risk-parity",
    )
    multi_asset_rp = run_stored_risk_parity_backtest(
        store=store,
        instruments=MULTI_ASSET_ETF_UNIVERSE,
        config=StoredRiskParityBacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_cash_cnh=initial_cash_cnh,
            sleeve_name=multi_asset_rp_definition.sleeve_name,
        ),
    )
    return {
        "current_sota": {
            "name": current_sota.name,
            "payload": _stable_backtest_payload(current_sota_result.model_dump(mode="json")),
        },
        "multi_asset_risk_parity": {
            "name": multi_asset_rp_definition.name,
            "payload": _stable_backtest_payload(multi_asset_rp.model_dump(mode="json")),
        },
        "aor": {
            "name": MULTI_ASSET_BENCHMARK_NAME,
            "payload": _buy_and_hold_payload(
                store=store,
                symbol=MULTI_ASSET_BENCHMARK_SYMBOL,
                start_date=start_date,
                end_date=end_date,
                initial_cash_cnh=initial_cash_cnh,
            ),
        },
        "msci_world": {
            "name": MSCI_WORLD_PROXY_NAME,
            "payload": _buy_and_hold_payload(
                store=store,
                symbol=MSCI_WORLD_PROXY_SYMBOL,
                start_date=start_date,
                end_date=end_date,
                initial_cash_cnh=initial_cash_cnh,
            ),
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


def _windowed_compare(
    *,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    baseline_name: str,
    candidate_name: str,
    validation_date: date,
    oos_date: date,
) -> dict[str, Any]:
    baseline_points = _nav_by_date(baseline)
    candidate_points = _nav_by_date(candidate)
    common_dates = sorted(set(baseline_points) & set(candidate_points))
    windows = {
        "full": common_dates,
        "train": [item for item in common_dates if item < validation_date],
        "validation": [item for item in common_dates if validation_date <= item < oos_date],
        "out_of_sample": [item for item in common_dates if item >= oos_date],
    }
    return {
        "baselineName": baseline_name,
        "candidateName": candidate_name,
        "validationDate": validation_date.isoformat(),
        "oosDate": oos_date.isoformat(),
        "dateRange": {"start": common_dates[0].isoformat(), "end": common_dates[-1].isoformat()},
        "metrics": {
            name: {
                "baseline": _window_metrics(baseline_points, window_dates),
                "candidate": _window_metrics(candidate_points, window_dates),
                "delta": _metric_delta(
                    _window_metrics(candidate_points, window_dates),
                    _window_metrics(baseline_points, window_dates),
                ),
                "active": _active_metrics(
                    baseline_points=baseline_points,
                    candidate_points=candidate_points,
                    window_dates=window_dates,
                ),
            }
            for name, window_dates in windows.items()
        },
    }


def _row(
    *,
    definition: Any,
    params: Mapping[str, Any],
    comparisons: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    vs_aor = comparisons["aor"]
    vs_multi_rp = comparisons["multi_asset_risk_parity"]
    vs_sota = comparisons["current_sota"]
    train = vs_aor["metrics"]["train"]["candidate"]
    validation = vs_aor["metrics"]["validation"]["candidate"]
    oos = vs_aor["metrics"]["out_of_sample"]["candidate"]
    validation_to_train = sharpe_retention_ratio(train["sharpe"], validation["sharpe"])
    out_to_validation = sharpe_retention_ratio(validation["sharpe"], oos["sharpe"])
    return {
        "key": definition.key,
        "name": definition.name,
        "parameters": _json_params(params),
        "trainAnnualizedReturn": train["annualizedReturn"],
        "trainSharpe": train["sharpe"],
        "trainCalmar": train["calmar"],
        "trainInformationRatioVsMultiAssetRiskParity": vs_multi_rp["metrics"]["train"]["active"]["informationRatio"],
        "validationAnnualizedReturn": validation["annualizedReturn"],
        "validationSharpe": validation["sharpe"],
        "validationCalmar": validation["calmar"],
        "validationMaxDrawdown": validation["maxDrawdown"],
        "validationToTrainSharpeRatio": validation_to_train,
        "validationToTrainSharpeBandDistance": retention_band_distance(validation_to_train),
        "validationToTrainSharpeBandPass": retention_band_pass(validation_to_train),
        "validationInformationRatioVsMultiAssetRiskParity": vs_multi_rp["metrics"]["validation"]["active"]["informationRatio"],
        "validationInformationRatioVsCurrentSota": vs_sota["metrics"]["validation"]["active"]["informationRatio"],
        "validationInformationRatioVsAor": vs_aor["metrics"]["validation"]["active"]["informationRatio"],
        "oosAnnualizedReturn": oos["annualizedReturn"],
        "oosReturn": oos["return"],
        "oosSharpe": oos["sharpe"],
        "oosCalmar": oos["calmar"],
        "oosMaxDrawdown": oos["maxDrawdown"],
        "outToValidationSharpeRatio": out_to_validation,
        "outToValidationSharpeBandDistance": retention_band_distance(out_to_validation),
        "outToValidationSharpeBandPass": retention_band_pass(out_to_validation),
        "oosInformationRatioVsMultiAssetRiskParity": vs_multi_rp["metrics"]["out_of_sample"]["active"]["informationRatio"],
        "oosInformationRatioVsCurrentSota": vs_sota["metrics"]["out_of_sample"]["active"]["informationRatio"],
        "oosInformationRatioVsAor": vs_aor["metrics"]["out_of_sample"]["active"]["informationRatio"],
        "oosAlphaVsCurrentSota": vs_sota["metrics"]["out_of_sample"]["delta"]["return"],
        "oosAlphaVsMultiAssetRiskParity": vs_multi_rp["metrics"]["out_of_sample"]["delta"]["return"],
        "oosAlphaVsAor": vs_aor["metrics"]["out_of_sample"]["delta"]["return"],
    }


def _score_rows(rows: list[dict[str, Any]]) -> None:
    score_specs = [
        ("validationAnnualizedReturn", Decimal("0.15")),
        ("validationSharpe", Decimal("0.25")),
        ("validationCalmar", Decimal("0.20")),
        ("validationInformationRatioVsMultiAssetRiskParity", Decimal("0.15")),
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
    if not present:
        return {}
    ranked = sorted(present, key=lambda row: (float(row[key]), row["key"]))
    if len(ranked) == 1:
        return {ranked[0]["key"]: 1.0}
    denominator = len(ranked) - 1
    return {row["key"]: index / denominator for index, row in enumerate(ranked)}


def _nav_by_date(result: dict[str, Any]) -> dict[date, float]:
    return {date.fromisoformat(str(point["trade_date"])): float(point["nav_cnh"]) for point in result["nav_series"]}


def _window_metrics(points: dict[date, float], window_dates: list[date]) -> dict[str, Any]:
    if len(window_dates) < 2:
        return {
            "start": window_dates[0].isoformat() if window_dates else None,
            "end": window_dates[-1].isoformat() if window_dates else None,
            "observations": len(window_dates),
            "return": None,
            "annualizedReturn": None,
            "maxDrawdown": None,
            "sharpe": None,
            "sortino": None,
            "calmar": None,
        }
    values = [points[item] for item in window_dates]
    total_return = (values[-1] / values[0]) - 1
    annualized = _annualized_return(total_return, window_dates[0], window_dates[-1])
    max_drawdown = _max_drawdown(values)
    daily_returns = _returns(values)
    return {
        "start": window_dates[0].isoformat(),
        "end": window_dates[-1].isoformat(),
        "observations": len(window_dates),
        "return": total_return,
        "annualizedReturn": annualized,
        "maxDrawdown": max_drawdown,
        "sharpe": _sharpe(daily_returns),
        "sortino": _sortino(daily_returns),
        "calmar": annualized / abs(max_drawdown) if annualized is not None and max_drawdown < 0 else None,
    }


def _metric_delta(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    keys = ["return", "annualizedReturn", "maxDrawdown", "sharpe", "sortino", "calmar"]
    return {
        key: (
            candidate[key] - baseline[key]
            if isinstance(candidate.get(key), int | float) and isinstance(baseline.get(key), int | float)
            else None
        )
        for key in keys
    }


def _active_metrics(
    *,
    baseline_points: dict[date, float],
    candidate_points: dict[date, float],
    window_dates: list[date],
) -> dict[str, Any]:
    active_returns: list[float] = []
    for index in range(1, len(window_dates)):
        previous = window_dates[index - 1]
        current = window_dates[index]
        if baseline_points[previous] == 0 or candidate_points[previous] == 0:
            continue
        baseline_return = (baseline_points[current] / baseline_points[previous]) - 1
        candidate_return = (candidate_points[current] / candidate_points[previous]) - 1
        active_returns.append(candidate_return - baseline_return)
    deviation = _stddev(active_returns)
    average = sum(active_returns) / len(active_returns) if active_returns else None
    return {
        "observations": len(active_returns),
        "averageActiveReturn": average,
        "annualizedActiveReturn": average * TRADING_DAYS_PER_YEAR if average is not None else None,
        "trackingError": deviation * math.sqrt(TRADING_DAYS_PER_YEAR) if deviation is not None else None,
        "informationRatio": (
            (average / deviation) * math.sqrt(TRADING_DAYS_PER_YEAR)
            if average is not None and deviation not in {None, 0}
            else None
        ),
    }


def _returns(values: Sequence[float]) -> list[float]:
    return [(values[index] / values[index - 1]) - 1 for index in range(1, len(values)) if values[index - 1] != 0]


def _annualized_return(total_return: float, start: date, end: date) -> float | None:
    years = (end - start).days / 365.25
    if years <= 0:
        return None
    return (1 + total_return) ** (1 / years) - 1


def _max_drawdown(values: Sequence[float]) -> float:
    peak = values[0]
    drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak:
            drawdown = min(drawdown, (value / peak) - 1)
    return drawdown


def _sharpe(returns: Sequence[float]) -> float | None:
    deviation = _stddev(returns)
    if deviation in {None, 0}:
        return None
    return (sum(returns) / len(returns)) / deviation * math.sqrt(TRADING_DAYS_PER_YEAR)


def _sortino(returns: Sequence[float]) -> float | None:
    downside = [item for item in returns if item < 0]
    deviation = _stddev(downside)
    if deviation in {None, 0}:
        return None
    return (sum(returns) / len(returns)) / deviation * math.sqrt(TRADING_DAYS_PER_YEAR)


def _stddev(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    variance = sum((item - mean) ** 2 for item in values) / (len(values) - 1)
    return math.sqrt(variance)


def _params_from_row(row: Mapping[str, Any]) -> dict[str, Any]:
    params = row["parameters"]
    return {
        "short_momentum_bars": int(params["shortMomentumBars"]),
        "medium_momentum_bars": int(params["mediumMomentumBars"]),
        "long_momentum_bars": int(params["longMomentumBars"]),
        "volume_bars": int(params["volumeBars"]),
        "slow_volume_bars": int(params["slowVolumeBars"]),
        "trend_weight": Decimal(str(params["trendWeight"])),
        "volume_weight": Decimal(str(params["volumeWeight"])),
        "top_n": int(params["topN"]),
        "min_selected": int(params["minSelected"]),
        "require_positive_long_momentum": bool(params["requirePositiveLongMomentum"]),
        "min_long_momentum": Decimal(str(params["minLongMomentum"])),
        "reallocate_selected": bool(params["reallocateSelected"]),
    }


def _case_key(params: Mapping[str, Any]) -> str:
    return (
        "pool_filter"
        f"_s{params['short_momentum_bars']}"
        f"_m{params['medium_momentum_bars']}"
        f"_l{params['long_momentum_bars']}"
        f"_tw{_label(params['trend_weight'])}"
        f"_vw{_label(params['volume_weight'])}"
        f"_top{params['top_n']}"
        f"_min{params['min_selected']}"
    )


def _case_name(params: Mapping[str, Any]) -> str:
    return (
        "Pool filter "
        f"{params['short_momentum_bars']}/{params['medium_momentum_bars']}/{params['long_momentum_bars']}d "
        f"trend {params['trend_weight']} volume {params['volume_weight']} "
        f"top {params['top_n']} min {params['min_selected']}"
    )


def _label(value: Any) -> str:
    return str(Decimal(str(value)).normalize()).replace("-", "m").replace(".", "p")


def _json_params(params: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "shortMomentumBars": params["short_momentum_bars"],
        "mediumMomentumBars": params["medium_momentum_bars"],
        "longMomentumBars": params["long_momentum_bars"],
        "volumeBars": params["volume_bars"],
        "slowVolumeBars": params["slow_volume_bars"],
        "trendWeight": str(params["trend_weight"]),
        "volumeWeight": str(params["volume_weight"]),
        "topN": params["top_n"],
        "minSelected": params["min_selected"],
        "requirePositiveLongMomentum": params["require_positive_long_momentum"],
        "minLongMomentum": str(params["min_long_momentum"]),
        "reallocateSelected": params["reallocate_selected"],
    }


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
        raise ValueError(f"Missing stored bars for {', '.join(missing)}.")

    start_date = date.fromisoformat(start_date_arg) if start_date_arg else max(first_dates)
    end_date = date.fromisoformat(end_date_arg) if end_date_arg else min(last_dates)
    if end_date <= start_date:
        raise ValueError(f"Invalid backtest range: {start_date} to {end_date}.")
    return start_date, end_date


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
    shares = initial_cash_cnh / (bars[0].close * first_rate)
    nav_series = []
    for bar in bars:
        nav = shares * bar.close * _latest_rate(rates_by_date, bar.trade_date)
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


def _one_day():
    from datetime import timedelta

    return timedelta(days=1)


def _results_markdown(results: Mapping[str, Any]) -> str:
    winner = results["winner"]
    lines = [
        "# Multi-Asset Combined Stack Optimization",
        "",
        f"- Candidate count: {results['method']['candidateCount']}",
        f"- Worker processes: {results['method']['workers']}",
        f"- Stack: {results['method']['stack']}",
        f"- Training window: {results['method']['trainingWindow']}",
        f"- Validation window: {results['method']['validationWindow']}",
        f"- OOS window: {results['method']['oosWindow']}",
        f"- Objective: {results['method']['objective']}",
        "",
        "## Validation-Selected Winner",
        "",
        f"- Strategy: {winner['name']}",
        f"- Validation objective score: {_fmt_num(winner['validationObjectiveScore'])}",
        f"- Train Sharpe: {_fmt_num(winner['trainSharpe'])}",
        f"- Validation Sharpe: {_fmt_num(winner['validationSharpe'])}",
        f"- Validation/train Sharpe ratio: {_fmt_num(winner['validationToTrainSharpeRatio'])}",
        f"- Validation Calmar: {_fmt_num(winner['validationCalmar'])}",
        f"- Validation IR vs multi-asset risk parity: {_fmt_num(winner['validationInformationRatioVsMultiAssetRiskParity'])}",
        f"- OOS annualized return: {_fmt_pct(winner['oosAnnualizedReturn'])}",
        f"- OOS Sharpe: {_fmt_num(winner['oosSharpe'])}",
        f"- OOS/validation Sharpe ratio: {_fmt_num(winner['outToValidationSharpeRatio'])}",
        f"- OOS Calmar: {_fmt_num(winner['oosCalmar'])}",
        f"- OOS max drawdown: {_fmt_pct(winner['oosMaxDrawdown'])}",
        f"- OOS IR vs current SOTA: {_fmt_num(winner['oosInformationRatioVsCurrentSota'])}",
        f"- OOS IR vs multi-asset risk parity: {_fmt_num(winner['oosInformationRatioVsMultiAssetRiskParity'])}",
        f"- OOS IR vs AOR: {_fmt_num(winner['oosInformationRatioVsAor'])}",
        "",
        "## Top 15 By Validation Objective",
        "",
        "| Rank | Strategy | Val Score | Train Sharpe | Val Sharpe | Val/Train | Val Calmar | OOS Sharpe | OOS/Val | OOS IR vs SOTA | OOS IR vs RP |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for index, row in enumerate(results["rankedCandidates"][:15], start=1):
        lines.append(_summary_row(index, row, validation=True))
    lines.extend(
        [
            "",
            "## Top 15 By OOS IR vs Current SOTA",
            "",
            "| Rank | Strategy | Val Score | Train Sharpe | Val Sharpe | Val/Train | Val Calmar | OOS Sharpe | OOS/Val | OOS IR vs SOTA | OOS IR vs RP |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for index, row in enumerate(results["bestOosByCurrentSotaIR"], start=1):
        lines.append(_summary_row(index, row, validation=True))
    lines.append("")
    return "\n".join(lines)


def _summary_row(index: int, row: Mapping[str, Any], *, validation: bool) -> str:
    score_key = "validationObjectiveScore" if validation else "trainObjectiveScore"
    return (
        "| "
        + " | ".join(
            [
                str(index),
                str(row["name"]),
                _fmt_num(row.get(score_key)),
                _fmt_num(row["trainSharpe"]),
                _fmt_num(row["validationSharpe"]),
                _fmt_num(row["validationToTrainSharpeRatio"]),
                _fmt_num(row["validationCalmar"]),
                _fmt_num(row["oosSharpe"]),
                _fmt_num(row["outToValidationSharpeRatio"]),
                _fmt_num(row["oosInformationRatioVsCurrentSota"]),
                _fmt_num(row["oosInformationRatioVsMultiAssetRiskParity"]),
            ]
        )
        + " |"
    )


def _write_model_card(
    *,
    path: Path,
    definition: Any,
    winner: Mapping[str, Any],
) -> None:
    card = strategy_model_card(definition)
    content = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Optimized Multi-Asset Combined Stack</title>
  <script type="module">import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs'; mermaid.initialize({{startOnLoad: true}});</script>
  <style>
    body {{ margin: 0; font-family: Segoe UI, Arial, sans-serif; color: #172033; background: #f7f9fc; }}
    main {{ max-width: 1160px; margin: 0 auto; padding: 28px; }}
    h1, h2, h3 {{ margin: 0; }}
    h1 {{ font-size: 30px; }}
    h2 {{ margin-top: 28px; font-size: 21px; }}
    h3 {{ margin-top: 18px; font-size: 16px; }}
    .subtle {{ color: #607089; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 18px; }}
    .stat, .panel {{ background: #fff; border: 1px solid #dce4ef; border-radius: 8px; }}
    .stat {{ padding: 14px 16px; }}
    .stat span {{ display: block; color: #607089; font-size: 12px; margin-bottom: 6px; }}
    .stat strong {{ font-size: 22px; }}
    .panel {{ padding: 18px; margin-top: 16px; overflow-x: auto; }}
    pre {{ background: #101828; color: #e5edf8; padding: 14px; border-radius: 6px; overflow-x: auto; }}
    .mermaid {{ background: #fff; border: 1px solid #e6edf5; border-radius: 6px; padding: 12px; margin-top: 10px; }}
  </style>
</head>
<body>
<main>
  <h1>{_esc(definition.name)}</h1>
  <p class="subtle">Pool-filter parameters selected on validation data before 2023; SOTA relative momentum then applied as a second overlay.</p>
  <section class="grid">
    <div class="stat"><span>Validation Objective</span><strong>{_fmt_num(winner['validationObjectiveScore'])}</strong></div>
    <div class="stat"><span>Validation Sharpe</span><strong>{_fmt_num(winner['validationSharpe'])}</strong></div>
    <div class="stat"><span>Val/Train Sharpe</span><strong>{_fmt_num(winner['validationToTrainSharpeRatio'])}</strong></div>
    <div class="stat"><span>OOS Sharpe</span><strong>{_fmt_num(winner['oosSharpe'])}</strong></div>
    <div class="stat"><span>OOS/Val Sharpe</span><strong>{_fmt_num(winner['outToValidationSharpeRatio'])}</strong></div>
  </section>
  <section class="panel">
    <h2>Layer Diagram</h2>
    <div class="mermaid">{_esc(card['layerDiagram'])}</div>
    <h3>Decision Graphs</h3>
    <div class="mermaid">{_esc(card['decisionTree'])}</div>
    <h3>Raw Decision Graphs</h3>
    <pre>{_esc(card['decisionTree'])}</pre>
  </section>
</main>
</body>
</html>
"""
    path.write_text(content, encoding="utf-8")


def _readme(
    *,
    start_date: date,
    end_date: date,
    validation_date: date,
    oos_date: date,
    results: Mapping[str, Any],
    output_dir: Path,
) -> str:
    winner = results["winner"]
    return "\n".join(
        [
            "# Multi-Asset Combined Stack Optimization",
            "",
            f"- Range: {start_date.isoformat()} to {end_date.isoformat()}",
            f"- Training/audit window: before {validation_date.isoformat()}",
            f"- Validation/selection window: {validation_date.isoformat()} to before {oos_date.isoformat()}",
            f"- OOS window: {oos_date.isoformat()} onward",
            f"- Candidate count: {results['method']['candidateCount']}",
            f"- Worker processes: {results['method']['workers']}",
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
            f"- Result data: `{output_dir / 'optimization_results.json'}`",
            f"- Winner report: `{output_dir / 'optimized_combined_stack.html'}`",
            f"- Winner model card: `{output_dir / 'optimized_model_card.html'}`",
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
