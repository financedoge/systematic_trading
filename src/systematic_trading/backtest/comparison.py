from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class ComparisonArtifacts:
    json_path: Path
    markdown_path: Path


def compare_backtests(
    *,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    split_date: date,
    baseline_name: str = "Baseline risk parity",
    candidate_name: str = "Candidate strategy",
) -> dict[str, Any]:
    baseline_points = _nav_by_date(baseline)
    candidate_points = _nav_by_date(candidate)
    common_dates = sorted(set(baseline_points) & set(candidate_points))
    if not common_dates:
        raise ValueError("Baseline and candidate have no overlapping NAV dates.")

    windows = {
        "full": common_dates,
        "in_sample": [item for item in common_dates if item < split_date],
        "out_of_sample": [item for item in common_dates if item >= split_date],
    }
    metrics: dict[str, dict[str, Any]] = {}
    for name, window_dates in windows.items():
        baseline_metrics = _window_metrics(baseline_points, window_dates)
        candidate_metrics = _window_metrics(candidate_points, window_dates)
        metrics[name] = {
            "baseline": baseline_metrics,
            "candidate": candidate_metrics,
            "delta": _metric_delta(candidate_metrics, baseline_metrics),
        }

    return {
        "baselineName": baseline_name,
        "candidateName": candidate_name,
        "splitDate": split_date.isoformat(),
        "dateRange": {"start": common_dates[0].isoformat(), "end": common_dates[-1].isoformat()},
        "observations": {
            "full": len(windows["full"]),
            "in_sample": len(windows["in_sample"]),
            "out_of_sample": len(windows["out_of_sample"]),
        },
        "metrics": metrics,
    }


def write_comparison_artifacts(
    *,
    comparison: dict[str, Any],
    output_dir: Path,
    stem: str,
    signal_diagnostics: dict[str, Any] | None = None,
) -> ComparisonArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    payload = dict(comparison)
    if signal_diagnostics is not None:
        payload["signalDiagnostics"] = signal_diagnostics
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    markdown_path.write_text(_comparison_markdown(comparison, signal_diagnostics), encoding="utf-8")
    return ComparisonArtifacts(json_path=json_path, markdown_path=markdown_path)


def build_signal_diagnostics(
    *,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    prices_by_symbol: dict[str, dict[date, float]],
    split_date: date,
    signal_name: str,
) -> dict[str, Any]:
    baseline_nav = _nav_by_date(baseline)
    candidate_nav = _nav_by_date(candidate)
    common_nav_dates = sorted(set(baseline_nav) & set(candidate_nav))
    baseline_targets = _targets_by_date(baseline)
    candidate_targets = _targets_by_date(candidate)
    rebalance_dates = sorted(set(baseline_targets) & set(candidate_targets))
    periods: list[dict[str, Any]] = []

    for index, start in enumerate(rebalance_dates):
        if start not in baseline_nav or start not in candidate_nav:
            continue
        end = _period_end(start, rebalance_dates[index + 1] if index + 1 < len(rebalance_dates) else None, common_nav_dates)
        if end is None or end <= start:
            continue

        baseline_return = (baseline_nav[end] / baseline_nav[start]) - 1
        candidate_return = (candidate_nav[end] / candidate_nav[start]) - 1
        realized_delta = candidate_return - baseline_return
        baseline_weights = baseline_targets[start]
        candidate_weights = candidate_targets[start]
        symbols = sorted(set(baseline_weights) | set(candidate_weights))
        impacts: list[dict[str, Any]] = []
        estimated_contribution = 0.0

        for symbol in symbols:
            baseline_weight = baseline_weights.get(symbol, 0.0)
            candidate_weight = candidate_weights.get(symbol, 0.0)
            weight_delta = candidate_weight - baseline_weight
            if abs(weight_delta) < 0.0001:
                continue
            asset_return = _asset_return(prices_by_symbol, symbol, start, end)
            contribution = weight_delta * asset_return if asset_return is not None else None
            if contribution is not None:
                estimated_contribution += contribution
            impacts.append(
                {
                    "symbol": symbol,
                    "action": _signal_action(baseline_weight, candidate_weight),
                    "baselineWeight": baseline_weight,
                    "candidateWeight": candidate_weight,
                    "weightDelta": weight_delta,
                    "assetReturn": asset_return,
                    "estimatedContribution": contribution,
                }
            )

        periods.append(
            {
                "period": f"{start.isoformat()} to {end.isoformat()}",
                "start": start.isoformat(),
                "end": end.isoformat(),
                "sample": "out_of_sample" if start >= split_date else "in_sample",
                "baselineReturn": baseline_return,
                "candidateReturn": candidate_return,
                "signals": [
                    {
                        "name": signal_name,
                        "realizedDelta": realized_delta,
                        "estimatedContribution": estimated_contribution,
                        "activeChanges": len(impacts),
                        "positiveChanges": sum(
                            1
                            for item in impacts
                            if isinstance(item["estimatedContribution"], int | float)
                            and item["estimatedContribution"] > 0
                        ),
                        "negativeChanges": sum(
                            1
                            for item in impacts
                            if isinstance(item["estimatedContribution"], int | float)
                            and item["estimatedContribution"] < 0
                        ),
                        "topPositive": sorted(
                            [item for item in impacts if _is_positive(item["estimatedContribution"])],
                            key=lambda item: item["estimatedContribution"],
                            reverse=True,
                        )[:3],
                        "topNegative": sorted(
                            [item for item in impacts if _is_negative(item["estimatedContribution"])],
                            key=lambda item: item["estimatedContribution"],
                        )[:3],
                        "changes": sorted(
                            impacts,
                            key=lambda item: abs(item["estimatedContribution"] or 0),
                            reverse=True,
                        ),
                    }
                ],
            }
        )

    return {
        "splitDate": split_date.isoformat(),
        "periods": periods,
        "summary": _signal_summary(periods),
    }


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
    calmar = annualized / abs(max_drawdown) if annualized is not None and max_drawdown < 0 else None
    return {
        "start": window_dates[0].isoformat(),
        "end": window_dates[-1].isoformat(),
        "observations": len(window_dates),
        "return": total_return,
        "annualizedReturn": annualized,
        "maxDrawdown": max_drawdown,
        "sharpe": _sharpe(daily_returns),
        "sortino": _sortino(daily_returns),
        "calmar": calmar,
    }


def _metric_delta(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    keys = ["return", "annualizedReturn", "maxDrawdown", "sharpe", "sortino", "calmar"]
    delta = {}
    for key in keys:
        candidate_value = candidate.get(key)
        baseline_value = baseline.get(key)
        delta[key] = (
            candidate_value - baseline_value
            if isinstance(candidate_value, int | float) and isinstance(baseline_value, int | float)
            else None
        )
    return delta


def _targets_by_date(result: dict[str, Any]) -> dict[date, dict[str, float]]:
    targets: dict[date, dict[str, float]] = {}
    for proposal in result.get("proposals", []):
        as_of = date.fromisoformat(str(proposal["as_of"]))
        targets[as_of] = {
            str(target["symbol"]): float(target["target_weight"])
            for target in proposal.get("targets", [])
        }
    return targets


def _period_end(start: date, next_start: date | None, nav_dates: list[date]) -> date | None:
    if next_start is not None and next_start in nav_dates:
        return next_start
    candidates = [item for item in nav_dates if item > start and (next_start is None or item < next_start)]
    if candidates:
        return candidates[-1]
    return nav_dates[-1] if nav_dates and nav_dates[-1] > start else None


def _asset_return(prices_by_symbol: dict[str, dict[date, float]], symbol: str, start: date, end: date) -> float | None:
    prices = prices_by_symbol.get(symbol, {})
    start_price = prices.get(start)
    end_price = prices.get(end)
    if start_price is None or end_price is None or start_price == 0:
        return None
    return (end_price / start_price) - 1


def _signal_action(baseline_weight: float, candidate_weight: float) -> str:
    if baseline_weight > 0 and candidate_weight <= 0.0001:
        return "cut"
    if candidate_weight > baseline_weight:
        return "overweight"
    if candidate_weight < baseline_weight:
        return "underweight"
    return "unchanged"


def _signal_summary(periods: list[dict[str, Any]]) -> dict[str, Any]:
    windows = {
        "full": periods,
        "in_sample": [period for period in periods if period["sample"] == "in_sample"],
        "out_of_sample": [period for period in periods if period["sample"] == "out_of_sample"],
    }
    return {name: _signal_window_summary(items) for name, items in windows.items()}


def _signal_window_summary(periods: list[dict[str, Any]]) -> dict[str, Any]:
    signals = [period["signals"][0] for period in periods if period.get("signals")]
    estimated = [signal["estimatedContribution"] for signal in signals]
    realized = [signal["realizedDelta"] for signal in signals]
    baseline_compounded = _compound_returns([period["baselineReturn"] for period in periods])
    candidate_compounded = _compound_returns([period["candidateReturn"] for period in periods])
    return {
        "periods": len(periods),
        "positivePeriods": sum(1 for value in realized if value > 0),
        "negativePeriods": sum(1 for value in realized if value < 0),
        "estimatedContribution": sum(estimated),
        "realizedDeltaSum": sum(realized),
        "compoundedDelta": candidate_compounded - baseline_compounded if periods else None,
        "averageEstimatedContribution": sum(estimated) / len(estimated) if estimated else None,
        "averageRealizedDelta": sum(realized) / len(realized) if realized else None,
    }


def _compound_returns(returns: list[float]) -> float:
    value = 1.0
    for item in returns:
        value *= 1 + item
    return value - 1


def _is_positive(value: Any) -> bool:
    return isinstance(value, int | float) and value > 0


def _is_negative(value: Any) -> bool:
    return isinstance(value, int | float) and value < 0


def _comparison_markdown(comparison: dict[str, Any], signal_diagnostics: dict[str, Any] | None) -> str:
    lines = [
        "# Signal Comparison",
        "",
        f"- Baseline: {comparison['baselineName']}",
        f"- Candidate: {comparison['candidateName']}",
        f"- Out-of-sample split: {comparison['splitDate']}",
        f"- Range: {comparison['dateRange']['start']} to {comparison['dateRange']['end']}",
        "",
        "| Window | Strategy | Return | Ann. Return | Max DD | Sharpe | Sortino | Calmar | Alpha vs Baseline |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for window in ["full", "in_sample", "out_of_sample"]:
        label = window.replace("_", " ").title()
        metrics = comparison["metrics"][window]
        baseline = metrics["baseline"]
        candidate = metrics["candidate"]
        delta = metrics["delta"]
        lines.append(_metric_row(label, comparison["baselineName"], baseline, None))
        lines.append(_metric_row(label, comparison["candidateName"], candidate, delta["return"]))
    lines.append("")
    lines.append("Alpha here is candidate return minus baseline return over the same window.")
    if signal_diagnostics:
        lines.extend(_signal_markdown(signal_diagnostics))
    return "\n".join(lines)


def _signal_markdown(signal_diagnostics: dict[str, Any]) -> list[str]:
    lines = [
        "",
        "## Signal Attribution",
        "",
        "| Window | Periods | Positive | Negative | Est. Contribution | Compounded Delta | Avg. Period Delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, label in [("full", "Full"), ("in_sample", "In Sample"), ("out_of_sample", "Out Of Sample")]:
        item = signal_diagnostics["summary"][key]
        lines.append(
            f"| {label} | {item['periods']} | {item['positivePeriods']} | {item['negativePeriods']} | "
            f"{_fmt_pct(item['estimatedContribution'])} | {_fmt_pct(item['compoundedDelta'])} | "
            f"{_fmt_pct(item['averageRealizedDelta'])} |"
        )
    periods = signal_diagnostics.get("periods", [])
    worst = sorted(periods, key=lambda period: period["signals"][0]["realizedDelta"])[:5]
    best = sorted(periods, key=lambda period: period["signals"][0]["realizedDelta"], reverse=True)[:5]
    lines.extend(["", "### Worst Signal Periods", "", "| Period | Realized Delta | Est. Contribution | Main Negative |", "| --- | ---: | ---: | --- |"])
    for period in worst:
        signal = period["signals"][0]
        main_negative = signal["topNegative"][0] if signal["topNegative"] else None
        lines.append(
            f"| {period['period']} | {_fmt_pct(signal['realizedDelta'])} | "
            f"{_fmt_pct(signal['estimatedContribution'])} | {_impact_label(main_negative)} |"
        )
    lines.extend(["", "### Best Signal Periods", "", "| Period | Realized Delta | Est. Contribution | Main Positive |", "| --- | ---: | ---: | --- |"])
    for period in best:
        signal = period["signals"][0]
        main_positive = signal["topPositive"][0] if signal["topPositive"] else None
        lines.append(
            f"| {period['period']} | {_fmt_pct(signal['realizedDelta'])} | "
            f"{_fmt_pct(signal['estimatedContribution'])} | {_impact_label(main_positive)} |"
        )
    return lines


def _impact_label(item: dict[str, Any] | None) -> str:
    if not item:
        return "n/a"
    return (
        f"{item['symbol']} {item['action']} "
        f"({_fmt_pct(item['estimatedContribution'])}, asset {_fmt_pct(item['assetReturn'])})"
    )


def _metric_row(label: str, strategy: str, metrics: dict[str, Any], alpha: float | None) -> str:
    return (
        f"| {label} | {strategy} | {_fmt_pct(metrics['return'])} | {_fmt_pct(metrics['annualizedReturn'])} | "
        f"{_fmt_pct(metrics['maxDrawdown'])} | {_fmt_num(metrics['sharpe'])} | {_fmt_num(metrics['sortino'])} | "
        f"{_fmt_num(metrics['calmar'])} | {_fmt_pct(alpha)} |"
    )


def _returns(values: list[float]) -> list[float]:
    return [(values[index] / values[index - 1]) - 1 for index in range(1, len(values)) if values[index - 1] != 0]


def _annualized_return(total_return: float, start: date, end: date) -> float | None:
    if total_return <= -1:
        return None
    years = max((end - start).days / 365.25, 1 / 365.25)
    return (1 + total_return) ** (1 / years) - 1


def _max_drawdown(values: list[float]) -> float:
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        worst = min(worst, (value / peak) - 1 if peak else 0.0)
    return worst


def _sharpe(returns: list[float]) -> float | None:
    deviation = _stddev(returns)
    if deviation is None or deviation == 0:
        return None
    return (sum(returns) / len(returns)) / deviation * math.sqrt(TRADING_DAYS_PER_YEAR)


def _sortino(returns: list[float]) -> float | None:
    downside = [value for value in returns if value < 0]
    if not returns or not downside:
        return None
    downside_deviation = math.sqrt(sum(value * value for value in downside) / len(downside))
    if downside_deviation == 0:
        return None
    return (sum(returns) / len(returns)) / downside_deviation * math.sqrt(TRADING_DAYS_PER_YEAR)


def _stddev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance)


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def _fmt_num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"
