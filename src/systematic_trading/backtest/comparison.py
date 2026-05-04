from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Sequence


TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class ComparisonArtifacts:
    json_path: Path
    markdown_path: Path


@dataclass(frozen=True)
class RobustnessArtifacts:
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
    market_data_audit: dict[str, Any] | None = None,
    decision_diagnostics: dict[str, Any] | None = None,
    forecast_diagnostics: dict[str, Any] | None = None,
    model_structure: dict[str, Any] | None = None,
) -> ComparisonArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    payload = dict(comparison)
    if signal_diagnostics is not None:
        payload["signalDiagnostics"] = signal_diagnostics
    if market_data_audit is not None:
        payload["marketDataAudit"] = market_data_audit
    if decision_diagnostics is not None:
        payload["decisionDiagnostics"] = decision_diagnostics
    if forecast_diagnostics is not None:
        payload["forecastDiagnostics"] = forecast_diagnostics
    if model_structure is not None:
        payload["modelStructure"] = model_structure
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    markdown_path.write_text(
        _comparison_markdown(
            comparison,
            signal_diagnostics,
            market_data_audit,
            decision_diagnostics,
            forecast_diagnostics,
            model_structure,
        ),
        encoding="utf-8",
    )
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
        decisions: list[dict[str, Any]] = []
        estimated_contribution = 0.0

        for symbol in symbols:
            baseline_weight = baseline_weights.get(symbol, 0.0)
            candidate_weight = candidate_weights.get(symbol, 0.0)
            weight_delta = candidate_weight - baseline_weight
            asset_return = _asset_return(prices_by_symbol, symbol, start, end)
            contribution = weight_delta * asset_return if asset_return is not None else None
            if abs(weight_delta) >= 0.0001 and contribution is not None:
                estimated_contribution += contribution
            action = _signal_action(baseline_weight, candidate_weight)
            decision = {
                "symbol": symbol,
                "action": action,
                "baselineWeight": baseline_weight,
                "candidateWeight": candidate_weight,
                "weightDelta": weight_delta,
                "active": abs(weight_delta) >= 0.0001,
                "assetReturn": asset_return,
                "estimatedContribution": contribution if abs(weight_delta) >= 0.0001 else 0.0,
                "outcome": _decision_outcome(action, asset_return),
            }
            decisions.append(decision)
            if decision["active"]:
                impacts.append(decision)

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
                        "decisions": sorted(
                            decisions,
                            key=lambda item: (item["symbol"], item["action"]),
                        ),
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


def build_market_data_audit(
    *,
    prices_by_symbol: dict[str, dict[date, float]],
    required_dates: Sequence[date],
    source_name: str,
    adjusted_prices: bool = False,
) -> dict[str, Any]:
    required = sorted(set(required_dates))
    required_set = set(required)
    symbols: list[dict[str, Any]] = []
    warnings: list[str] = []

    for symbol, prices in sorted(prices_by_symbol.items()):
        dates = sorted(prices)
        date_set = set(dates)
        missing = sorted(required_set - date_set)
        present_required = len(required_set & date_set)
        non_positive = sum(1 for value in prices.values() if value <= 0)
        stale_runs = _stale_runs(dates, prices)
        max_gap = max(
            ((dates[index] - dates[index - 1]).days for index in range(1, len(dates))),
            default=0,
        )
        coverage = present_required / len(required) if required else None
        item = {
            "symbol": symbol,
            "observations": len(dates),
            "start": dates[0].isoformat() if dates else None,
            "end": dates[-1].isoformat() if dates else None,
            "requiredCoverage": coverage,
            "missingRequiredDates": len(missing),
            "sampleMissingDates": [item.isoformat() for item in missing[:5]],
            "maxCalendarGapDays": max_gap,
            "stalePriceRuns": stale_runs,
            "nonPositivePrices": non_positive,
        }
        symbols.append(item)
        if missing:
            warnings.append(f"{symbol} is missing {len(missing)} required price dates.")
        if non_positive:
            warnings.append(f"{symbol} has {non_positive} non-positive close prices.")
        if stale_runs:
            warnings.append(f"{symbol} has {len(stale_runs)} stale close-price runs of at least 3 observations.")

    common_dates = sorted(set.intersection(*(set(prices) for prices in prices_by_symbol.values()))) if prices_by_symbol else []
    common_required = sorted(set(common_dates) & required_set)
    if not adjusted_prices:
        warnings.append(
            "Stored prices are close prices, not validated adjusted total-return prices; ETF dividends and split adjustments remain a research risk."
        )

    return {
        "source": source_name,
        "priceField": "close",
        "adjustedPrices": adjusted_prices,
        "requiredObservations": len(required),
        "requiredDateRange": {
            "start": required[0].isoformat() if required else None,
            "end": required[-1].isoformat() if required else None,
        },
        "commonCoverage": {
            "observations": len(common_required),
            "start": common_required[0].isoformat() if common_required else None,
            "end": common_required[-1].isoformat() if common_required else None,
        },
        "symbols": symbols,
        "warnings": warnings,
    }


def build_decision_diagnostics(signal_diagnostics: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for period in signal_diagnostics.get("periods", []):
        signal = period.get("signals", [{}])[0]
        decisions = signal.get("decisions") or signal.get("changes") or []
        for decision in decisions:
            rows.append(
                {
                    "period": period["period"],
                    "start": period["start"],
                    "end": period["end"],
                    "sample": period["sample"],
                    "symbol": decision["symbol"],
                    "action": decision["action"],
                    "baselineWeight": decision["baselineWeight"],
                    "candidateWeight": decision["candidateWeight"],
                    "weightDelta": decision["weightDelta"],
                    "active": decision.get("active", abs(decision["weightDelta"]) >= 0.0001),
                    "assetReturn": decision.get("assetReturn"),
                    "estimatedContribution": decision.get("estimatedContribution"),
                    "outcome": decision.get("outcome")
                    or _decision_outcome(decision["action"], decision.get("assetReturn")),
                }
            )

    windows = {
        "full": rows,
        "in_sample": [row for row in rows if row["sample"] == "in_sample"],
        "out_of_sample": [row for row in rows if row["sample"] == "out_of_sample"],
    }
    return {
        "summary": {name: _decision_window_summary(items) for name, items in windows.items()},
        "bySymbol": _decision_symbol_summary(rows),
        "worstFalseExits": _top_decisions(rows, "false_exit", reverse=False),
        "worstFalseKeeps": _top_decisions(rows, "false_keep", reverse=False, sort_key="assetReturn"),
        "worstFalseOverweights": _top_decisions(rows, "false_overweight", reverse=False),
    }


def build_signal_forecast_diagnostics(
    *,
    prices_by_symbol: dict[str, dict[date, float]],
    rebalance_dates: Sequence[date],
    split_date: date,
    lookback_bars: int,
    threshold: float,
) -> dict[str, Any]:
    periods = sorted(set(rebalance_dates))
    rows: list[dict[str, Any]] = []
    for index, start in enumerate(periods[:-1]):
        end = periods[index + 1]
        for symbol, prices in sorted(prices_by_symbol.items()):
            momentum = _price_momentum(prices, start, lookback_bars)
            forward_return = _asset_return(prices_by_symbol, symbol, start, end)
            if momentum is None or forward_return is None:
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "sample": "out_of_sample" if start >= split_date else "in_sample",
                    "momentum": momentum,
                    "signal": "positive" if momentum > threshold else "negative",
                    "forwardReturn": forward_return,
                }
            )

    windows = {
        "full": rows,
        "in_sample": [row for row in rows if row["sample"] == "in_sample"],
        "out_of_sample": [row for row in rows if row["sample"] == "out_of_sample"],
    }
    return {
        "lookbackBars": lookback_bars,
        "threshold": threshold,
        "forwardHorizon": "next_rebalance",
        "summary": {name: _forecast_summary(items) for name, items in windows.items()},
        "bySymbol": _forecast_symbol_summary(rows),
    }


def write_robustness_artifacts(
    *,
    cases: list[dict[str, Any]],
    output_dir: Path,
    stem: str = "robustness",
) -> RobustnessArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    ranked = sorted(cases, key=_robustness_sort_key, reverse=True)
    payload = {
        "caseCount": len(ranked),
        "rankedBy": "out_of_sample_delta_return",
        "cases": ranked,
    }
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    markdown_path.write_text(_robustness_markdown(payload), encoding="utf-8")
    return RobustnessArtifacts(json_path=json_path, markdown_path=markdown_path)


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
    if candidate_weight > 0:
        return "keep"
    return "flat"


def _decision_outcome(action: str, asset_return: float | None) -> str:
    if asset_return is None:
        return "missing_forward_return"
    if abs(asset_return) < 0.0000001:
        return "neutral"
    if action in {"cut", "underweight"}:
        return "good_exit" if asset_return < 0 else "false_exit"
    if action == "overweight":
        return "good_overweight" if asset_return > 0 else "false_overweight"
    if action == "keep":
        return "good_keep" if asset_return > 0 else "false_keep"
    return "neutral"


def _decision_window_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    outcomes = _count_by_key(rows, "outcome")
    active_rows = [row for row in rows if row["active"]]
    helped = sum(1 for row in active_rows if row["outcome"] in {"good_exit", "good_overweight"})
    hurt = sum(1 for row in active_rows if row["outcome"] in {"false_exit", "false_overweight"})
    contribution = [
        row["estimatedContribution"]
        for row in active_rows
        if isinstance(row.get("estimatedContribution"), int | float)
    ]
    return {
        "decisions": len(rows),
        "activeDecisions": len(active_rows),
        "activeHelped": helped,
        "activeHurt": hurt,
        "activeHitRate": helped / (helped + hurt) if helped + hurt else None,
        "falseExits": outcomes.get("false_exit", 0),
        "goodExits": outcomes.get("good_exit", 0),
        "falseKeeps": outcomes.get("false_keep", 0),
        "goodKeeps": outcomes.get("good_keep", 0),
        "falseOverweights": outcomes.get("false_overweight", 0),
        "goodOverweights": outcomes.get("good_overweight", 0),
        "estimatedContribution": sum(contribution),
    }


def _decision_symbol_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for symbol in sorted({row["symbol"] for row in rows}):
        symbol_rows = [row for row in rows if row["symbol"] == symbol]
        summary = _decision_window_summary(symbol_rows)
        summary["symbol"] = symbol
        summaries.append(summary)
    return sorted(summaries, key=lambda item: item["estimatedContribution"])


def _top_decisions(
    rows: list[dict[str, Any]],
    outcome: str,
    *,
    reverse: bool,
    sort_key: str = "estimatedContribution",
    limit: int = 10,
) -> list[dict[str, Any]]:
    filtered = [
        row
        for row in rows
        if row["outcome"] == outcome and isinstance(row.get(sort_key), int | float)
    ]
    return sorted(filtered, key=lambda item: item[sort_key], reverse=reverse)[:limit]


def _count_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key))
        counts[value] = counts.get(value, 0) + 1
    return counts


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


def _stale_runs(dates: list[date], prices: dict[date, float]) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    if not dates:
        return runs

    start = dates[0]
    previous = dates[0]
    previous_price = prices[previous]
    length = 1
    for current in dates[1:]:
        current_price = prices[current]
        if current_price == previous_price:
            length += 1
        else:
            if length >= 3:
                runs.append(
                    {
                        "start": start.isoformat(),
                        "end": previous.isoformat(),
                        "observations": length,
                        "price": previous_price,
                    }
                )
            start = current
            length = 1
        previous = current
        previous_price = current_price

    if length >= 3:
        runs.append(
            {
                "start": start.isoformat(),
                "end": previous.isoformat(),
                "observations": length,
                "price": previous_price,
            }
        )
    return runs


def _price_momentum(prices: dict[date, float], as_of: date, lookback_bars: int) -> float | None:
    history = [(trade_date, price) for trade_date, price in sorted(prices.items()) if trade_date < as_of]
    if len(history) < lookback_bars + 1:
        return None
    latest = history[-1][1]
    reference = history[-(lookback_bars + 1)][1]
    if reference == 0:
        return None
    return (latest / reference) - 1


def _forecast_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positive = [row for row in rows if row["signal"] == "positive"]
    negative = [row for row in rows if row["signal"] == "negative"]
    positive_returns = [row["forwardReturn"] for row in positive]
    negative_returns = [row["forwardReturn"] for row in negative]
    avg_positive = _mean(positive_returns)
    avg_negative = _mean(negative_returns)
    return {
        "observations": len(rows),
        "positiveSignals": len(positive),
        "negativeSignals": len(negative),
        "avgForwardReturnPositiveSignal": avg_positive,
        "avgForwardReturnNegativeSignal": avg_negative,
        "spread": avg_positive - avg_negative if avg_positive is not None and avg_negative is not None else None,
        "positiveSignalHitRate": _rate(row["forwardReturn"] > 0 for row in positive),
        "negativeSignalHitRate": _rate(row["forwardReturn"] < 0 for row in negative),
        "directionalAccuracy": _rate(
            (row["signal"] == "positive" and row["forwardReturn"] > 0)
            or (row["signal"] == "negative" and row["forwardReturn"] < 0)
            for row in rows
        ),
        "informationCoefficient": _pearson(
            [row["momentum"] for row in rows],
            [row["forwardReturn"] for row in rows],
        ),
    }


def _forecast_symbol_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for symbol in sorted({row["symbol"] for row in rows}):
        summary = _forecast_summary([row for row in rows if row["symbol"] == symbol])
        summary["symbol"] = symbol
        summaries.append(summary)
    return sorted(
        summaries,
        key=lambda item: item["spread"] if item["spread"] is not None else float("-inf"),
        reverse=True,
    )


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _rate(values: Sequence[bool]) -> float | None:
    items = list(values)
    return sum(1 for item in items if item) / len(items) if items else None


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right, strict=True))
    left_ss = sum((x - left_mean) ** 2 for x in left)
    right_ss = sum((y - right_mean) ** 2 for y in right)
    denominator = math.sqrt(left_ss * right_ss)
    if denominator == 0:
        return None
    return numerator / denominator


def _is_positive(value: Any) -> bool:
    return isinstance(value, int | float) and value > 0


def _is_negative(value: Any) -> bool:
    return isinstance(value, int | float) and value < 0


def _comparison_markdown(
    comparison: dict[str, Any],
    signal_diagnostics: dict[str, Any] | None,
    market_data_audit: dict[str, Any] | None,
    decision_diagnostics: dict[str, Any] | None,
    forecast_diagnostics: dict[str, Any] | None,
    model_structure: dict[str, Any] | None,
) -> str:
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
    if model_structure:
        lines.extend(_model_structure_markdown(model_structure))
    if market_data_audit:
        lines.extend(_market_data_audit_markdown(market_data_audit))
    if forecast_diagnostics:
        lines.extend(_forecast_markdown(forecast_diagnostics))
    if signal_diagnostics:
        lines.extend(_signal_markdown(signal_diagnostics))
    if decision_diagnostics:
        lines.extend(_decision_markdown(decision_diagnostics))
    return "\n".join(lines)


def _model_structure_markdown(model_structure: dict[str, Any]) -> list[str]:
    lines = ["", "## Model Structure"]
    for key, label in [("baseline", "Baseline / SOTA"), ("candidate", "Research Candidate")]:
        card = model_structure.get(key)
        if not card:
            continue
        definition = card["definition"]
        lines.extend(
            [
                "",
                f"### {label}",
                "",
                f"- Name: {definition['name']}",
                f"- State: {definition['state']}",
            ]
        )
        if definition.get("promotedOn"):
            lines.append(f"- Promoted on: {definition['promotedOn']}")
        lines.extend(
            [
                f"- Description: {definition['description']}",
                "",
                "#### Layers",
                "",
                "```mermaid",
                card["layerDiagram"],
                "```",
                "",
                "#### Decision Tree",
                "",
                "```mermaid",
                card["decisionTree"],
                "```",
            ]
        )
    return lines


def _market_data_audit_markdown(audit: dict[str, Any]) -> list[str]:
    lines = [
        "",
        "## Market Data Audit",
        "",
        f"- Source: {audit['source']}",
        f"- Price field: {audit['priceField']}",
        f"- Adjusted prices validated: {'yes' if audit['adjustedPrices'] else 'no'}",
        f"- Required observations: {audit['requiredObservations']}",
        f"- Common required observations: {audit['commonCoverage']['observations']}",
        "",
        "| Symbol | Obs. | Required Coverage | Missing Required | Max Gap Days | Stale Runs | Non-Positive |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in audit["symbols"]:
        lines.append(
            f"| {item['symbol']} | {item['observations']} | {_fmt_pct(item['requiredCoverage'])} | "
            f"{item['missingRequiredDates']} | {item['maxCalendarGapDays']} | {len(item['stalePriceRuns'])} | "
            f"{item['nonPositivePrices']} |"
        )
    if audit["warnings"]:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in audit["warnings"][:10])
    return lines


def _forecast_markdown(forecast: dict[str, Any]) -> list[str]:
    lines = [
        "",
        "## Signal Forecast Quality",
        "",
        f"- Lookback bars: {forecast['lookbackBars']}",
        f"- Threshold: {_fmt_pct(forecast['threshold'])}",
        f"- Forward horizon: {forecast['forwardHorizon']}",
        "",
        "| Window | Obs. | Positive Signals | Negative Signals | Positive Avg Fwd | Negative Avg Fwd | Spread | Accuracy | IC |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, label in [("full", "Full"), ("in_sample", "In Sample"), ("out_of_sample", "Out Of Sample")]:
        item = forecast["summary"][key]
        lines.append(
            f"| {label} | {item['observations']} | {item['positiveSignals']} | {item['negativeSignals']} | "
            f"{_fmt_pct(item['avgForwardReturnPositiveSignal'])} | "
            f"{_fmt_pct(item['avgForwardReturnNegativeSignal'])} | {_fmt_pct(item['spread'])} | "
            f"{_fmt_pct(item['directionalAccuracy'])} | {_fmt_num(item['informationCoefficient'])} |"
        )
    lines.extend(
        [
            "",
            "### Forecast By Symbol",
            "",
            "| Symbol | Obs. | Positive Avg Fwd | Negative Avg Fwd | Spread | Accuracy | IC |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in forecast["bySymbol"]:
        lines.append(
            f"| {item['symbol']} | {item['observations']} | "
            f"{_fmt_pct(item['avgForwardReturnPositiveSignal'])} | "
            f"{_fmt_pct(item['avgForwardReturnNegativeSignal'])} | {_fmt_pct(item['spread'])} | "
            f"{_fmt_pct(item['directionalAccuracy'])} | {_fmt_num(item['informationCoefficient'])} |"
        )
    return lines


def _decision_markdown(decision_diagnostics: dict[str, Any]) -> list[str]:
    lines = [
        "",
        "## Decision Quality",
        "",
        "| Window | Active Decisions | Helped | Hurt | Hit Rate | False Exits | Good Exits | False Keeps | Est. Contribution |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, label in [("full", "Full"), ("in_sample", "In Sample"), ("out_of_sample", "Out Of Sample")]:
        item = decision_diagnostics["summary"][key]
        lines.append(
            f"| {label} | {item['activeDecisions']} | {item['activeHelped']} | {item['activeHurt']} | "
            f"{_fmt_pct(item['activeHitRate'])} | {item['falseExits']} | {item['goodExits']} | "
            f"{item['falseKeeps']} | {_fmt_pct(item['estimatedContribution'])} |"
        )
    lines.extend(
        [
            "",
            "### Decision Quality By Symbol",
            "",
            "| Symbol | Active | Helped | Hurt | Hit Rate | False Exits | False Keeps | Est. Contribution |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in decision_diagnostics["bySymbol"]:
        lines.append(
            f"| {item['symbol']} | {item['activeDecisions']} | {item['activeHelped']} | {item['activeHurt']} | "
            f"{_fmt_pct(item['activeHitRate'])} | {item['falseExits']} | {item['falseKeeps']} | "
            f"{_fmt_pct(item['estimatedContribution'])} |"
        )
    lines.extend(
        [
            "",
            "### Worst False Exits",
            "",
            "| Period | Symbol | Action | Asset Return | Est. Contribution |",
            "| --- | --- | --- | ---: | ---: |",
        ]
    )
    for item in decision_diagnostics["worstFalseExits"][:5]:
        lines.append(
            f"| {item['period']} | {item['symbol']} | {item['action']} | "
            f"{_fmt_pct(item['assetReturn'])} | {_fmt_pct(item['estimatedContribution'])} |"
        )
    lines.extend(
        [
            "",
            "### Worst False Keeps",
            "",
            "| Period | Symbol | Asset Return |",
            "| --- | --- | ---: |",
        ]
    )
    for item in decision_diagnostics["worstFalseKeeps"][:5]:
        lines.append(f"| {item['period']} | {item['symbol']} | {_fmt_pct(item['assetReturn'])} |")
    return lines


def _robustness_markdown(payload: dict[str, Any]) -> str:
    show_adaptive_scales = any("weakScale" in case or "reboundScale" in case for case in payload["cases"])
    show_relative_tilts = any("calmTilt" in case or "riskTilt" in case for case in payload["cases"])
    lines = [
        "# Parameter Robustness",
        "",
        f"- Cases: {payload['caseCount']}",
        f"- Ranked by: {payload['rankedBy']}",
        "",
    ]
    if show_adaptive_scales:
        lines.extend(
            [
                "| Rank | Strategy | Lookback | Threshold | Mode | Weak Scale | Rebound Scale | OOS Alpha | OOS Delta Sharpe | OOS Delta Max DD | Full Alpha | In-Sample Alpha |",
                "| ---: | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
    elif show_relative_tilts:
        lines.extend(
            [
                "| Rank | Strategy | Lookback | Threshold | Mode | Calm Tilt | Risk Tilt | OOS Alpha | OOS Delta Sharpe | OOS Delta Max DD | Full Alpha | In-Sample Alpha |",
                "| ---: | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
    else:
        lines.extend(
            [
                "| Rank | Strategy | Lookback | Threshold | Mode | OOS Alpha | OOS Delta Sharpe | OOS Delta Max DD | Full Alpha | In-Sample Alpha |",
                "| ---: | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
    for rank, case in enumerate(payload["cases"], start=1):
        comparison = case["comparison"]
        base = (
            f"| {rank} | {case['name']} | {case['lookbackBars']} | {_fmt_pct(float(case['threshold']))} | "
            f"{case['mode']} | "
        )
        if show_adaptive_scales:
            base += f"{case.get('weakScale', 'n/a')} | {case.get('reboundScale', 'n/a')} | "
        elif show_relative_tilts:
            base += f"{case.get('calmTilt', 'n/a')} | {case.get('riskTilt', 'n/a')} | "
        lines.append(
            base
            + f"{_fmt_pct(_robustness_delta(comparison, 'out_of_sample', 'return'))} | "
            + f"{_fmt_num(_robustness_delta(comparison, 'out_of_sample', 'sharpe'))} | "
            + f"{_fmt_pct(_robustness_delta(comparison, 'out_of_sample', 'maxDrawdown'))} | "
            + f"{_fmt_pct(_robustness_delta(comparison, 'full', 'return'))} | "
            + f"{_fmt_pct(_robustness_delta(comparison, 'in_sample', 'return'))} |"
        )
    return "\n".join(lines)


def _robustness_sort_key(case: dict[str, Any]) -> float:
    value = _robustness_delta(case["comparison"], "out_of_sample", "return")
    return value if isinstance(value, int | float) else float("-inf")


def _robustness_delta(comparison: dict[str, Any], window: str, key: str) -> float | None:
    value = comparison["metrics"][window]["delta"].get(key)
    return value if isinstance(value, int | float) else None


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
