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
    _date_range_from_store,
    _sort_value,
    _stable_backtest_payload,
    _windowed_compare,
)
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
from systematic_trading.research import (  # noqa: E402
    ALL_WEATHER_ETF_SPECS,
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
    risk_parity_definition,
)
from systematic_trading.signals import BalancedAssetGroupOverlay  # noqa: E402
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
        description="Run all-weather-style balanced ETF pool research with momentum filters and SOTA tilt."
    )
    parser.add_argument("--database", default=None)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default="2026-04-29")
    parser.add_argument("--validation-date", default="2020-01-01")
    parser.add_argument("--oos-date", default="2023-01-01")
    parser.add_argument("--initial-cash-cnh", default="1000000")
    parser.add_argument("--output-dir", default="var/backtests/all_weather_balanced_research")
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--workers", type=int, default=min(os.cpu_count() or 1, 8))
    args = parser.parse_args()

    settings = AppSettings()
    database_path = Path(args.database) if args.database else settings.database_path
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(database_path)
    store.initialize()

    all_symbols = sorted(set(ALL_WEATHER_ETF_UNIVERSE) | {MULTI_ASSET_BENCHMARK_SYMBOL, MSCI_WORLD_PROXY_SYMBOL})
    start_date, end_date = _date_range_from_store(
        store=store,
        symbols=all_symbols,
        start_date_arg=args.start_date,
        end_date_arg=args.end_date,
    )
    validation_date = date.fromisoformat(args.validation_date)
    oos_date = date.fromisoformat(args.oos_date)
    initial_cash_cnh = Decimal(args.initial_cash_cnh)

    counts_path = output_dir / "all_weather_universe_counts.md"
    counts_path.write_text(_counts_markdown(), encoding="utf-8")

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
        validation_date=validation_date,
        oos_date=oos_date,
        initial_cash_cnh=initial_cash_cnh,
        baseline_payloads=baseline_payloads,
    )

    _score_rows(rows)
    ranked = sorted(rows, key=lambda row: row["validationObjectiveScore"], reverse=True)
    winner = ranked[0]
    winner_payload = _run_candidate_payload(
        store=store,
        case=_case_from_row(winner, optimized=True),
        start_date=start_date,
        end_date=end_date,
        initial_cash_cnh=initial_cash_cnh,
    )
    winner_path = output_dir / "optimized_all_weather_balanced_stack.json"
    winner_path.write_text(json.dumps(winner_payload, indent=2), encoding="utf-8")
    (output_dir / "current_sota.json").write_text(json.dumps(baseline_payloads["current_sota"]["payload"], indent=2), encoding="utf-8")
    (output_dir / "all_weather_risk_parity.json").write_text(json.dumps(baseline_payloads["all_weather_risk_parity"]["payload"], indent=2), encoding="utf-8")

    report = write_backtest_report(
        result_path=winner_path,
        output_path=output_dir / "optimized_all_weather_balanced_stack.html",
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
                "id": "all_weather_risk_parity",
                "name": "All-weather expanded-pool risk parity",
                "nav_series": baseline_payloads["all_weather_risk_parity"]["payload"]["nav_series"],
            },
            {
                "id": "msci_world",
                "name": MSCI_WORLD_PROXY_NAME,
                "symbol": MSCI_WORLD_PROXY_SYMBOL,
            },
        ],
    )
    if report.warnings:
        (output_dir / "optimized_all_weather_balanced_stack_report_warnings.txt").write_text(
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
            "stack": "all-weather sleeve budgets -> sleeve momentum filter -> SOTA relative momentum tilt",
            "objective": (
                "Pre-OOS stability-adjusted score: validation annualized return, Sharpe, Calmar, "
                "information ratio versus expanded-pool risk parity, and validation/train Sharpe "
                f"retention closeness to {TARGET_RETENTION_LOW:.2f}-{TARGET_RETENTION_HIGH:.2f}."
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
        counts_path,
        results_md,
        results_json,
        winner_path,
        report.output_path,
        model_card_path,
        readme_path,
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
    ]
    cases: list[dict[str, Any]] = []
    for budget_profile in _budget_profiles():
        for short, medium, long in lookback_sets:
            for trend_weight, volume_weight in weight_sets:
                for top_n in [1, 2]:
                    cases.append(
                        {
                            "budget_profile": budget_profile["name"],
                            "asset_class_budgets": budget_profile["asset_class_budgets"],
                            "short_momentum_bars": short,
                            "medium_momentum_bars": medium,
                            "long_momentum_bars": long,
                            "trend_weight": trend_weight,
                            "volume_weight": volume_weight,
                            "top_n_per_sleeve": top_n,
                            "require_positive_long_momentum": True,
                        }
                    )
    return cases


def _budget_profiles() -> list[dict[str, Any]]:
    return [
        {
            "name": "bridgewater_style",
            "asset_class_budgets": {"equity": Decimal("0.30"), "rates": Decimal("0.45"), "credit": Decimal("0.10"), "commodity": Decimal("0.15")},
        },
        {
            "name": "equal_asset_class",
            "asset_class_budgets": {"equity": Decimal("0.25"), "rates": Decimal("0.25"), "credit": Decimal("0.25"), "commodity": Decimal("0.25")},
        },
        {
            "name": "inflation_aware",
            "asset_class_budgets": {"equity": Decimal("0.25"), "rates": Decimal("0.30"), "credit": Decimal("0.15"), "commodity": Decimal("0.30")},
        },
        {
            "name": "growth_income",
            "asset_class_budgets": {"equity": Decimal("0.35"), "rates": Decimal("0.30"), "credit": Decimal("0.20"), "commodity": Decimal("0.15")},
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
            if completed == 1 or completed % 10 == 0 or completed == len(tasks):
                print(f"completed {completed}/{len(tasks)} all-weather cases with {workers} workers", flush=True)
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
        raise RuntimeError("All-weather worker was not initialized.")
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
    key = "optimized_all_weather_balanced_stack" if optimized else f"all_weather_case_{index:03d}_{params['budget_profile']}"
    name = "Optimized all-weather balanced stack" if optimized else (
        f"All-weather {index:03d}: {params['budget_profile']} "
        f"{params['short_momentum_bars']}/{params['medium_momentum_bars']}/{params['long_momentum_bars']}d "
        f"top {params['top_n_per_sleeve']}"
    )
    sleeve_budgets = _sleeve_budgets(params["asset_class_budgets"])
    overlay = BalancedAssetGroupOverlay(
        sleeve_by_symbol={symbol: spec.sleeve for symbol, spec in ALL_WEATHER_SPEC_BY_SYMBOL.items()},
        sleeve_budgets=sleeve_budgets,
        top_n_per_sleeve=int(params["top_n_per_sleeve"]),
        min_selected_per_sleeve=1,
        short_momentum_bars=int(params["short_momentum_bars"]),
        medium_momentum_bars=int(params["medium_momentum_bars"]),
        long_momentum_bars=int(params["long_momentum_bars"]),
        trend_weight=Decimal(str(params["trend_weight"])),
        volume_weight=Decimal(str(params["volume_weight"])),
        require_positive_long_momentum=bool(params["require_positive_long_momentum"]),
        name=key,
    )
    return {
        "key": key,
        "name": name,
        "sleeve_name": key.replace("_", "-"),
        "balanced_overlay": overlay,
        "params": _json_params(params),
        "sleeveBudgets": {sleeve: str(weight) for sleeve, weight in sleeve_budgets.items()},
    }


def _case_from_row(row: Mapping[str, Any], *, optimized: bool) -> dict[str, Any]:
    params = row["rawParameters"]
    parsed = {
        "budget_profile": params["budgetProfile"],
        "asset_class_budgets": {key: Decimal(str(value)) for key, value in params["assetClassBudgets"].items()},
        "short_momentum_bars": int(params["shortMomentumBars"]),
        "medium_momentum_bars": int(params["mediumMomentumBars"]),
        "long_momentum_bars": int(params["longMomentumBars"]),
        "trend_weight": Decimal(str(params["trendWeight"])),
        "volume_weight": Decimal(str(params["volumeWeight"])),
        "top_n_per_sleeve": int(params["topNPerSleeve"]),
        "require_positive_long_momentum": bool(params["requirePositiveLongMomentum"]),
    }
    return _case(0, parsed, optimized=optimized)


def _sleeve_budgets(asset_class_budgets: Mapping[str, Decimal]) -> dict[str, Decimal]:
    sleeves_by_class: dict[str, set[str]] = {}
    for spec in ALL_WEATHER_ETF_SPECS:
        sleeves_by_class.setdefault(spec.asset_class_group, set()).add(spec.sleeve)
    budgets: dict[str, Decimal] = {}
    for asset_class, class_budget in asset_class_budgets.items():
        sleeves = sorted(sleeves_by_class.get(asset_class, set()))
        if not sleeves:
            continue
        sleeve_budget = Decimal(str(class_budget)) / Decimal(len(sleeves))
        for sleeve in sleeves:
            budgets[sleeve] = sleeve_budget
    return budgets


def _run_candidate_payload(
    *,
    store: SQLiteStore,
    case: Mapping[str, Any],
    start_date: date,
    end_date: date,
    initial_cash_cnh: Decimal,
) -> dict[str, Any]:
    result = run_stored_risk_parity_backtest(
        store=store,
        instruments=ALL_WEATHER_ETF_UNIVERSE,
        config=StoredRiskParityBacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_cash_cnh=initial_cash_cnh,
            sleeve_name=str(case["sleeve_name"]),
        ),
        target_overlays=[case["balanced_overlay"], *instantiate_overlays(current_sota_definition())],
    )
    payload = _stable_backtest_payload(result.model_dump(mode="json"))
    payload["researchCase"] = {
        "name": case["name"],
        "params": case["params"],
        "sleeveBudgets": case["sleeveBudgets"],
        "stack": "risk parity -> balanced all-weather sleeve filter -> SOTA relative momentum",
    }
    return payload


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
    all_weather_rp = run_stored_risk_parity_backtest(
        store=store,
        instruments=ALL_WEATHER_ETF_UNIVERSE,
        config=StoredRiskParityBacktestConfig(start_date=start_date, end_date=end_date, initial_cash_cnh=initial_cash_cnh, sleeve_name="all-weather-risk-parity"),
    )
    return {
        "current_sota": {"name": current_sota.name, "payload": _stable_backtest_payload(current_sota_result.model_dump(mode="json"))},
        "all_weather_risk_parity": {"name": "All-weather expanded-pool risk parity", "payload": _stable_backtest_payload(all_weather_rp.model_dump(mode="json"))},
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
    vs_rp = comparisons["all_weather_risk_parity"]
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
        "sleeveBudgets": case["sleeveBudgets"],
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
        ("validationAnnualizedReturn", Decimal("0.15")),
        ("validationSharpe", Decimal("0.25")),
        ("validationCalmar", Decimal("0.20")),
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
    return {
        "budgetProfile": params["budget_profile"],
        "assetClassBudgets": {key: str(value) for key, value in params["asset_class_budgets"].items()},
        "shortMomentumBars": params["short_momentum_bars"],
        "mediumMomentumBars": params["medium_momentum_bars"],
        "longMomentumBars": params["long_momentum_bars"],
        "trendWeight": str(params["trend_weight"]),
        "volumeWeight": str(params["volume_weight"]),
        "topNPerSleeve": params["top_n_per_sleeve"],
        "requirePositiveLongMomentum": params["require_positive_long_momentum"],
    }


def _counts_markdown() -> str:
    counts = grouped_counts()
    lines = ["# All-Weather ETF Universe Counts", ""]
    for title, values in counts.items():
        lines.extend([f"## {title}", "", "| Group | Count |", "| --- | ---: |"])
        for group, count in sorted(values.items()):
            lines.append(f"| {group} | {count} |")
        lines.append("")
    lines.extend(["## Constituents", "", "| Symbol | Name | Asset Class | Region | Sleeve | Segment |", "| --- | --- | --- | --- | --- | --- |"])
    for spec in ALL_WEATHER_ETF_SPECS:
        lines.append(f"| {spec.symbol} | {spec.name} | {spec.asset_class_group} | {spec.region_group} | {spec.sleeve} | {spec.segment} |")
    lines.append("")
    return "\n".join(lines)


def _results_markdown(results: Mapping[str, Any]) -> str:
    winner = results["winner"]
    lines = [
        "# All-Weather Balanced Pool Research",
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
        f"- Validation Calmar: {_fmt_num(winner['validationCalmar'])}",
        f"- OOS annualized return: {_fmt_pct(winner['oosAnnualizedReturn'])}",
        f"- OOS Sharpe: {_fmt_num(winner['oosSharpe'])}",
        f"- OOS/validation Sharpe ratio: {_fmt_num(winner['outToValidationSharpeRatio'])}",
        f"- OOS Calmar: {_fmt_num(winner['oosCalmar'])}",
        f"- OOS IR vs current SOTA: {_fmt_num(winner['oosInformationRatioVsCurrentSota'])}",
        f"- OOS IR vs expanded-pool risk parity: {_fmt_num(winner['oosInformationRatioVsRiskParity'])}",
        "",
        "## Top 15 By Validation Objective",
        "",
        "| Rank | Strategy | Val Score | Train Sharpe | Val Sharpe | Val/Train | Val Calmar | OOS Sharpe | OOS/Val | OOS IR vs SOTA | OOS IR vs RP |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for index, row in enumerate(results["rankedCandidates"][:15], start=1):
        lines.append(_summary_row(index, row))
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
                _fmt_num(row["validationCalmar"]),
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
  <title>Optimized All-Weather Balanced Stack</title>
  <style>
    body {{ margin: 0; font-family: Segoe UI, Arial, sans-serif; color: #172033; background: #f7f9fc; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 28px; }}
    h1, h2 {{ margin: 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin: 18px 0; }}
    .stat, .panel {{ background: #fff; border: 1px solid #dce4ef; border-radius: 8px; padding: 16px; }}
    .stat span {{ display: block; color: #607089; font-size: 12px; margin-bottom: 6px; }}
    .stat strong {{ font-size: 22px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ border-bottom: 1px solid #e6edf5; padding: 8px 10px; text-align: left; }}
    th {{ color: #607089; font-size: 12px; text-transform: uppercase; }}
  </style>
</head>
<body>
<main>
  <h1>Optimized All-Weather Balanced Stack</h1>
  <section class="grid">
    <div class="stat"><span>Validation Score</span><strong>{_fmt_num(winner['validationObjectiveScore'])}</strong></div>
    <div class="stat"><span>Val/Train Sharpe</span><strong>{_fmt_num(winner['validationToTrainSharpeRatio'])}</strong></div>
    <div class="stat"><span>OOS Sharpe</span><strong>{_fmt_num(winner['oosSharpe'])}</strong></div>
    <div class="stat"><span>OOS/Val Sharpe</span><strong>{_fmt_num(winner['outToValidationSharpeRatio'])}</strong></div>
  </section>
  <section class="panel">
    <h2>Decision Stack</h2>
    <ol>
      <li>Start from the expanded all-weather ETF universe.</li>
      <li>Split target budgets by asset class, then equally across regional/category sleeves.</li>
      <li>Within each sleeve, rank assets by point-in-time momentum and volume signals.</li>
      <li>Allocate each sleeve budget to selected assets using base inverse-volatility weights.</li>
      <li>Apply the current SOTA 20/60d regime-gated relative momentum tilt.</li>
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
            "# All-Weather Balanced Pool Research",
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
            f"- Universe counts: `{output_dir / 'all_weather_universe_counts.md'}`",
            f"- Results: `{output_dir / 'optimization_results.md'}`",
            f"- Winner report: `{output_dir / 'optimized_all_weather_balanced_stack.html'}`",
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
