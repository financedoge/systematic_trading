from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


TRADING_DAYS_PER_YEAR = 252
CASH_LABEL = "Cash"


@dataclass(frozen=True)
class BacktestReportResult:
    output_path: Path
    warnings: list[str]


def write_backtest_report(
    *,
    result_path: Path,
    output_path: Path | None = None,
    database_path: Path | None = None,
    benchmark_symbol: str | None = None,
    benchmark_nav_series: list[dict[str, Any]] | None = None,
    benchmark_name: str | None = None,
    extra_benchmarks: list[dict[str, Any]] | None = None,
    signal_diagnostics: dict[str, Any] | None = None,
) -> BacktestReportResult:
    result_path = Path(result_path)
    output_path = Path(output_path) if output_path is not None else result_path.with_suffix(".html")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    report, warnings = build_backtest_report_data(
        result=result,
        result_path=result_path,
        database_path=database_path,
        benchmark_symbol=benchmark_symbol,
        benchmark_nav_series=benchmark_nav_series,
        benchmark_name=benchmark_name,
        extra_benchmarks=extra_benchmarks,
        signal_diagnostics=signal_diagnostics,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_render_html(report), encoding="utf-8")
    return BacktestReportResult(output_path=output_path, warnings=warnings)


def build_backtest_report_data(
    *,
    result: dict[str, Any],
    result_path: Path,
    database_path: Path | None = None,
    benchmark_symbol: str | None = None,
    benchmark_nav_series: list[dict[str, Any]] | None = None,
    benchmark_name: str | None = None,
    extra_benchmarks: list[dict[str, Any]] | None = None,
    signal_diagnostics: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    nav_points = _nav_points(result)
    if not nav_points:
        raise ValueError("Backtest result does not contain nav_series.")

    symbols = _extract_symbols(result)
    start_date = nav_points[0]["date"]
    end_date = nav_points[-1]["date"]
    prices: dict[str, dict[str, float]] = {}
    fx_rates: dict[str, float] = {}
    extra_benchmarks = extra_benchmarks or []
    market_symbols = sorted(set(symbols) | _benchmark_symbols(extra_benchmarks, benchmark_symbol))

    if database_path is not None:
        prices, fx_rates, market_warnings = _load_market_data(
            Path(database_path),
            symbols=market_symbols,
            start_date=start_date,
            end_date=end_date,
        )
        warnings.extend(market_warnings)

    benchmark, benchmark_name, benchmark_warning = _benchmark_series(
        nav_points=nav_points,
        symbols=symbols,
        prices=prices,
        fx_rates=fx_rates,
        benchmark_symbol=benchmark_symbol,
        benchmark_nav_series=benchmark_nav_series,
        benchmark_name=benchmark_name,
    )
    if benchmark_warning is not None:
        warnings.append(benchmark_warning)
    benchmark_choices = [
        {
            "id": "primary",
            "name": benchmark_name,
            "series": benchmark,
        }
    ]
    for index, spec in enumerate(extra_benchmarks):
        choice_id = str(spec.get("id") or f"benchmark_{index + 1}")
        if choice_id == "primary" or any(choice["id"] == choice_id for choice in benchmark_choices):
            continue
        choice_series, choice_name, choice_warning = _benchmark_series(
            nav_points=nav_points,
            symbols=symbols,
            prices=prices,
            fx_rates=fx_rates,
            benchmark_symbol=spec.get("symbol"),
            benchmark_nav_series=spec.get("nav_series"),
            benchmark_name=spec.get("name"),
        )
        if choice_warning is not None:
            warnings.append(choice_warning)
        benchmark_choices.append({"id": choice_id, "name": choice_name, "series": choice_series})

    holding_series, allocation_source, allocation_warnings = _holding_series(
        result=result,
        nav_points=nav_points,
        symbols=symbols,
        prices=prices,
        fx_rates=fx_rates,
    )
    warnings.extend(allocation_warnings)

    drawdowns, periods = _drawdown_series(nav_points)
    chart_points = []
    for index, point in enumerate(nav_points):
        benchmark_nav = benchmark[index]["nav"] if benchmark else None
        point_benchmarks = {
            choice["id"]: {
                "name": choice["name"],
                "nav": choice["series"][index]["nav"] if choice["series"] else None,
                "index": choice["series"][index]["index"] if choice["series"] else None,
            }
            for choice in benchmark_choices
        }
        chart_points.append(
            {
                "date": point["date"],
                "nav": point["nav"],
                "navIndex": point["navIndex"],
                "benchmark": benchmark_nav,
                "benchmarkIndex": benchmark[index]["index"] if benchmark else None,
                "benchmarks": point_benchmarks,
                "drawdown": drawdowns[index],
                "weights": holding_series[index],
            }
        )

    colors = _color_map(symbols)
    benchmark_options = [{"id": choice["id"], "name": choice["name"]} for choice in benchmark_choices]
    summaries_by_benchmark = {
        choice["id"]: _summary_metrics(chart_points, benchmark_id=choice["id"])
        for choice in benchmark_choices
    }
    metrics_by_benchmark = {
        choice["id"]: {
            "yearly": _period_metrics(chart_points, "yearly", benchmark_id=choice["id"]),
            "quarterly": _period_metrics(chart_points, "quarterly", benchmark_id=choice["id"]),
            "monthly": _period_metrics(chart_points, "monthly", benchmark_id=choice["id"]),
        }
        for choice in benchmark_choices
    }
    summary = summaries_by_benchmark["primary"]
    metrics = metrics_by_benchmark["primary"]

    report = {
        "title": result_path.stem.replace("_", " ").title(),
        "sourceJson": str(result_path),
        "database": str(database_path) if database_path is not None else None,
        "benchmarkName": benchmark_name,
        "defaultBenchmarkId": "primary",
        "benchmarkOptions": benchmark_options,
        "summariesByBenchmark": summaries_by_benchmark,
        "metricsByBenchmark": metrics_by_benchmark,
        "allocationSource": allocation_source,
        "symbols": symbols,
        "allocationOrder": [*symbols, CASH_LABEL],
        "colors": colors,
        "summary": summary,
        "chart": chart_points,
        "drawdownPeriods": [period for period in periods if period["depth"] <= -0.02],
        "topDrawdowns": sorted(periods, key=lambda item: item["depth"])[:5],
        "metrics": metrics,
        "signalDiagnostics": signal_diagnostics,
        "warnings": warnings,
    }
    return report, warnings


def _nav_points(result: dict[str, Any]) -> list[dict[str, Any]]:
    raw_points = result.get("nav_series", [])
    if not raw_points:
        return []
    first_nav = _to_float(raw_points[0]["nav_cnh"])
    points = []
    for item in raw_points:
        nav = _to_float(item["nav_cnh"])
        points.append(
            {
                "date": str(item["trade_date"]),
                "nav": nav,
                "navIndex": (nav / first_nav) * 100 if first_nav else None,
                "cash": _to_float(item.get("cash_cnh", 0)),
            }
        )
    return points


def _extract_symbols(result: dict[str, Any]) -> list[str]:
    symbols: set[str] = set()
    for proposal in result.get("proposals", []):
        for target in proposal.get("targets", []):
            symbols.add(str(target["symbol"]))
        for order in proposal.get("orders", []):
            symbols.add(str(order["symbol"]))
    final_snapshot = result.get("final_snapshot", {})
    for position in final_snapshot.get("positions", []):
        symbols.add(str(position["symbol"]))
    return sorted(symbols)


def _benchmark_symbols(extra_benchmarks: list[dict[str, Any]], benchmark_symbol: str | None) -> set[str]:
    symbols = {benchmark_symbol} if benchmark_symbol else set()
    for spec in extra_benchmarks:
        symbol = spec.get("symbol")
        if symbol:
            symbols.add(str(symbol))
    return symbols


def _load_market_data(
    database_path: Path,
    *,
    symbols: list[str],
    start_date: str,
    end_date: str,
) -> tuple[dict[str, dict[str, float]], dict[str, float], list[str]]:
    warnings: list[str] = []
    prices: dict[str, dict[str, float]] = {}
    fx_rates: dict[str, float] = {}
    if not database_path.exists():
        return prices, fx_rates, [f"Market database was not found: {database_path}"]

    try:
        with sqlite3.connect(database_path) as connection:
            connection.row_factory = sqlite3.Row
            for symbol in symbols:
                rows = connection.execute(
                    """
                    SELECT trade_date, payload
                    FROM price_bars
                    WHERE symbol = ? AND trade_date >= ? AND trade_date <= ?
                    ORDER BY trade_date ASC
                    """,
                    (symbol, start_date, end_date),
                ).fetchall()
                prices[symbol] = {
                    str(row["trade_date"]): _to_float(json.loads(row["payload"])["close"])
                    for row in rows
                }
                if not prices[symbol]:
                    warnings.append(f"No stored price bars were found for {symbol}.")

            rows = connection.execute(
                """
                SELECT rate_date, payload
                FROM fx_rates
                WHERE base_currency = 'USD' AND quote_currency = 'CNH' AND rate_date <= ?
                ORDER BY rate_date ASC
                """,
                (end_date,),
            ).fetchall()
            fx_rates = {
                str(row["rate_date"]): _to_float(json.loads(row["payload"])["rate"])
                for row in rows
            }
            if not fx_rates:
                warnings.append("No stored USD/CNH FX rates were found.")
    except sqlite3.Error as exc:
        warnings.append(f"Could not read market database {database_path}: {exc}")

    return prices, fx_rates, warnings


def _benchmark_series(
    *,
    nav_points: list[dict[str, Any]],
    symbols: list[str],
    prices: dict[str, dict[str, float]],
    fx_rates: dict[str, float],
    benchmark_symbol: str | None,
    benchmark_nav_series: list[dict[str, Any]] | None,
    benchmark_name: str | None,
) -> tuple[list[dict[str, float | None]] | None, str, str | None]:
    if benchmark_nav_series is not None:
        return _external_benchmark_series(
            nav_points=nav_points,
            benchmark_nav_series=benchmark_nav_series,
            benchmark_name=benchmark_name or "Strategy benchmark",
        )

    if not prices or not fx_rates:
        return None, "Benchmark unavailable", "Benchmark was not plotted because stored prices or FX rates are unavailable."

    if benchmark_symbol:
        benchmark_symbols = [benchmark_symbol]
        benchmark_label = benchmark_name or f"{benchmark_symbol} buy-and-hold"
    else:
        benchmark_symbols = symbols
        benchmark_label = benchmark_name or "Equal-weight ETF universe"

    first = nav_points[0]
    initial_nav = first["nav"]
    base_index = None
    base_values: dict[str, float] = {}
    for index, point in enumerate(nav_points):
        values = {
            symbol: _price_cnh(symbol, point["date"], prices, fx_rates)
            for symbol in benchmark_symbols
        }
        values = {symbol: value for symbol, value in values.items() if value is not None and value > 0}
        if values:
            base_index = index
            base_values = values
            break
    if not base_values:
        return None, benchmark_label, f"Benchmark was not plotted because no prices were found for {', '.join(benchmark_symbols)}."

    weight = 1 / len(base_values)
    last_index = 100.0
    series = []
    for index, point in enumerate(nav_points):
        if base_index is not None and index < base_index:
            series.append({"nav": None, "index": None})
            continue
        ratio = 0.0
        covered_weight = 0.0
        for symbol, base_value in base_values.items():
            current_value = _price_cnh(symbol, point["date"], prices, fx_rates)
            if current_value is None:
                continue
            ratio += weight * (current_value / base_value)
            covered_weight += weight
        if covered_weight == 0:
            index_value = last_index
        else:
            index_value = ratio / covered_weight * 100
            last_index = index_value
        series.append({"nav": initial_nav * (index_value / 100), "index": index_value})

    missing = sorted(set(benchmark_symbols) - set(base_values))
    warning_parts = []
    if base_index is not None and base_index > 0:
        warning_parts.append(
            f"{benchmark_label} starts on {nav_points[base_index]['date']} because no earlier benchmark prices were found."
        )
    if missing:
        warning_parts.append(f"Benchmark excluded symbols with missing inception prices: {', '.join(missing)}.")
    warning = " ".join(warning_parts) if warning_parts else None
    return series, benchmark_label, warning


def _external_benchmark_series(
    *,
    nav_points: list[dict[str, Any]],
    benchmark_nav_series: list[dict[str, Any]],
    benchmark_name: str,
) -> tuple[list[dict[str, float | None]] | None, str, str | None]:
    benchmark_by_date = {
        str(item.get("trade_date")): _to_float(item["nav_cnh"])
        for item in benchmark_nav_series
        if item.get("trade_date") is not None and item.get("nav_cnh") is not None
    }
    base_index = None
    base_nav = None
    for index, point in enumerate(nav_points):
        candidate = benchmark_by_date.get(point["date"])
        if candidate is not None and candidate > 0:
            base_index = index
            base_nav = candidate
            break
    if base_nav is None:
        return None, benchmark_name, "External benchmark was not plotted because it has no overlapping dates with the strategy."

    strategy_initial_nav = nav_points[0]["nav"]
    last_index = 100.0
    series = []
    missing_dates = 0
    for index, point in enumerate(nav_points):
        if base_index is not None and index < base_index:
            series.append({"nav": None, "index": None})
            continue
        benchmark_nav = benchmark_by_date.get(point["date"])
        if benchmark_nav is None:
            missing_dates += 1
            index_value = last_index
        else:
            index_value = (benchmark_nav / base_nav) * 100
            last_index = index_value
        series.append({"nav": strategy_initial_nav * (index_value / 100), "index": index_value})

    warning_parts = []
    if base_index is not None and base_index > 0:
        warning_parts.append(
            f"{benchmark_name} starts on {nav_points[base_index]['date']} because no earlier benchmark NAV was found."
        )
    if missing_dates:
        warning_parts.append(f"External benchmark was forward-filled on {missing_dates} dates missing from the benchmark series.")
    warning = " ".join(warning_parts) if warning_parts else None
    return series, benchmark_name, warning


def _holding_series(
    *,
    result: dict[str, Any],
    nav_points: list[dict[str, Any]],
    symbols: list[str],
    prices: dict[str, dict[str, float]],
    fx_rates: dict[str, float],
) -> tuple[list[dict[str, float]], str, list[str]]:
    if prices and fx_rates:
        return _holding_series_from_orders(
            result=result,
            nav_points=nav_points,
            symbols=symbols,
            prices=prices,
            fx_rates=fx_rates,
        )
    return _holding_series_from_targets(result=result, nav_points=nav_points, symbols=symbols)


def _holding_series_from_orders(
    *,
    result: dict[str, Any],
    nav_points: list[dict[str, Any]],
    symbols: list[str],
    prices: dict[str, dict[str, float]],
    fx_rates: dict[str, float],
) -> tuple[list[dict[str, float]], str, list[str]]:
    warnings: list[str] = []
    proposals_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for proposal in result.get("proposals", []):
        proposals_by_date[str(proposal["as_of"])].append(proposal)

    positions: dict[str, float] = defaultdict(float)
    series: list[dict[str, float]] = []
    missing_prices: set[str] = set()
    for point in nav_points:
        for proposal in proposals_by_date.get(point["date"], []):
            orders = sorted(proposal.get("orders", []), key=lambda order: 0 if order.get("side") == "sell" else 1)
            for order in orders:
                symbol = str(order["symbol"])
                quantity = _to_float(order["quantity"])
                if order.get("side") == "sell":
                    positions[symbol] = max(0.0, positions[symbol] - quantity)
                else:
                    positions[symbol] += quantity

        nav = point["nav"]
        weights: dict[str, float] = {}
        for symbol in symbols:
            quantity = positions.get(symbol, 0.0)
            if quantity <= 0 or nav <= 0:
                continue
            price_cnh = _price_cnh(symbol, point["date"], prices, fx_rates)
            if price_cnh is None:
                missing_prices.add(symbol)
                continue
            weights[symbol] = (quantity * price_cnh) / nav

        cash_weight = point["cash"] / nav if nav else 0.0
        weights[CASH_LABEL] = max(0.0, cash_weight)
        total_weight = sum(weights.values())
        if total_weight < 0.995:
            weights[CASH_LABEL] += 1 - total_weight
            total_weight = 1.0
        if total_weight > 0:
            weights = {symbol: max(0.0, value / total_weight) for symbol, value in weights.items()}
        series.append(_complete_weights(weights, symbols))

    if missing_prices:
        warnings.append(f"Some holding weights could not be priced for: {', '.join(sorted(missing_prices))}.")
    return series, "Daily holdings reconstructed from rebalance orders, stored closes, and USD/CNH FX.", warnings


def _holding_series_from_targets(
    *,
    result: dict[str, Any],
    nav_points: list[dict[str, Any]],
    symbols: list[str],
) -> tuple[list[dict[str, float]], str, list[str]]:
    proposals_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for proposal in result.get("proposals", []):
        proposals_by_date[str(proposal["as_of"])].append(proposal)

    current = {CASH_LABEL: 1.0}
    series: list[dict[str, float]] = []
    for point in nav_points:
        proposals = proposals_by_date.get(point["date"], [])
        if proposals:
            latest = proposals[-1]
            current = {
                str(target["symbol"]): _to_float(target["target_weight"])
                for target in latest.get("targets", [])
            }
            current[CASH_LABEL] = max(0.0, 1 - sum(current.values()))
        series.append(_complete_weights(current, symbols))
    return series, "Allocation background uses proposal target weights because daily market data was unavailable.", []


def _complete_weights(weights: dict[str, float], symbols: list[str]) -> dict[str, float]:
    complete = {symbol: float(weights.get(symbol, 0.0)) for symbol in symbols}
    complete[CASH_LABEL] = float(weights.get(CASH_LABEL, 0.0))
    total = sum(complete.values())
    if total <= 0:
        complete[CASH_LABEL] = 1.0
        return complete
    return {symbol: value / total for symbol, value in complete.items()}


def _price_cnh(
    symbol: str,
    trade_date: str,
    prices: dict[str, dict[str, float]],
    fx_rates: dict[str, float],
) -> float | None:
    price = prices.get(symbol, {}).get(trade_date)
    fx = _latest_rate(fx_rates, trade_date)
    if price is None or fx is None:
        return None
    return price * fx


def _latest_rate(fx_rates: dict[str, float], trade_date: str) -> float | None:
    if trade_date in fx_rates:
        return fx_rates[trade_date]
    available = [rate_date for rate_date in fx_rates if rate_date <= trade_date]
    if not available:
        return None
    return fx_rates[max(available)]


def _drawdown_series(nav_points: list[dict[str, Any]]) -> tuple[list[float], list[dict[str, Any]]]:
    peak = nav_points[0]["nav"]
    peak_date = nav_points[0]["date"]
    drawdowns: list[float] = []
    periods: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None

    for point in nav_points:
        nav = point["nav"]
        if nav >= peak:
            if active is not None:
                active["end"] = point["date"]
                periods.append(active)
                active = None
            peak = nav
            peak_date = point["date"]
            drawdowns.append(0.0)
            continue

        drawdown = (nav / peak) - 1
        drawdowns.append(drawdown)
        if active is None:
            active = {
                "start": peak_date,
                "trough": point["date"],
                "end": None,
                "depth": drawdown,
            }
        elif drawdown < active["depth"]:
            active["depth"] = drawdown
            active["trough"] = point["date"]

    if active is not None:
        periods.append(active)
    return drawdowns, periods


def _summary_metrics(chart_points: list[dict[str, Any]], benchmark_id: str = "primary") -> dict[str, Any]:
    first = chart_points[0]
    last = chart_points[-1]
    nav_values = [point["nav"] for point in chart_points]
    benchmark_points = []
    for index, point in enumerate(chart_points):
        benchmark_nav = _benchmark_nav(point, benchmark_id)
        if benchmark_nav is not None:
            benchmark_points.append((index, benchmark_nav))
    returns = _returns(nav_values)
    benchmark_return = None
    benchmark_start = None
    benchmark_end = None
    strategy_comparison_return = None
    total_return = (last["nav"] / first["nav"]) - 1
    if benchmark_points:
        first_benchmark_index, first_benchmark_nav = benchmark_points[0]
        last_benchmark_index, last_benchmark_nav = benchmark_points[-1]
        benchmark_start = chart_points[first_benchmark_index]["date"]
        benchmark_end = chart_points[last_benchmark_index]["date"]
        benchmark_return = (last_benchmark_nav / first_benchmark_nav) - 1
        strategy_comparison_return = (
            chart_points[last_benchmark_index]["nav"] / chart_points[first_benchmark_index]["nav"]
        ) - 1
    return {
        "start": first["date"],
        "end": last["date"],
        "benchmarkStart": benchmark_start,
        "benchmarkEnd": benchmark_end,
        "initialNav": first["nav"],
        "finalNav": last["nav"],
        "totalReturn": total_return,
        "strategyComparisonReturn": strategy_comparison_return,
        "annualizedReturn": _annualized_return(total_return, first["date"], last["date"]),
        "maxDrawdown": min(point["drawdown"] for point in chart_points),
        "sharpe": _sharpe(returns),
        "sortino": _sortino(returns),
        "benchmarkReturn": benchmark_return,
        "alpha": (
            strategy_comparison_return - benchmark_return
            if benchmark_return is not None and strategy_comparison_return is not None
            else None
        ),
    }


def _period_metrics(chart_points: list[dict[str, Any]], frequency: str, benchmark_id: str = "primary") -> list[dict[str, Any]]:
    dates = [_parse_date(point["date"]) for point in chart_points]
    nav_values = [point["nav"] for point in chart_points]
    benchmark_values = [_benchmark_nav(point, benchmark_id) for point in chart_points]
    groups: dict[str, list[int]] = defaultdict(list)
    for index, day in enumerate(dates):
        groups[_period_key(day, frequency)].append(index)

    rows: list[dict[str, Any]] = []
    for key in sorted(groups):
        indices = groups[key]
        start_index = indices[0]
        end_index = indices[-1]
        base_index = max(0, start_index - 1)
        nav_return = (nav_values[end_index] / nav_values[base_index]) - 1
        daily_returns = [
            (nav_values[index] / nav_values[index - 1]) - 1
            for index in range(max(1, start_index), end_index + 1)
        ]
        benchmark_return = None
        strategy_comparison_return = None
        benchmark_indices = [
            index
            for index in range(base_index, end_index + 1)
            if benchmark_values[index] is not None
        ]
        if benchmark_indices:
            benchmark_start_index = benchmark_indices[0]
            benchmark_end_index = benchmark_indices[-1]
            benchmark_start_value = benchmark_values[benchmark_start_index]
            benchmark_end_value = benchmark_values[benchmark_end_index]
            if benchmark_start_value is not None and benchmark_end_value is not None:
                benchmark_return = (benchmark_end_value / benchmark_start_value) - 1
                strategy_comparison_return = (nav_values[benchmark_end_index] / nav_values[benchmark_start_index]) - 1
        max_drawdown = _max_drawdown(nav_values[base_index : end_index + 1])
        annualized = _annualized_return(nav_return, dates[base_index].isoformat(), dates[end_index].isoformat())
        calmar = None
        if annualized is not None and max_drawdown < 0:
            calmar = annualized / abs(max_drawdown)
        rows.append(
            {
                "period": _period_label(dates[end_index], frequency),
                "return": nav_return,
                "sharpe": _sharpe(daily_returns),
                "sortino": _sortino(daily_returns),
                "calmar": calmar,
                "alpha": (
                    strategy_comparison_return - benchmark_return
                    if benchmark_return is not None and strategy_comparison_return is not None
                    else None
                ),
                "benchmarkReturn": benchmark_return,
                "maxDrawdown": max_drawdown,
                "observations": len(daily_returns),
            }
        )
    return rows


def _benchmark_nav(point: dict[str, Any], benchmark_id: str) -> float | None:
    benchmark = point.get("benchmarks", {}).get(benchmark_id)
    if benchmark is not None:
        return benchmark.get("nav")
    return point.get("benchmark")


def _period_key(day: date, frequency: str) -> str:
    if frequency == "yearly":
        return f"{day.year:04d}"
    if frequency == "quarterly":
        quarter = ((day.month - 1) // 3) + 1
        return f"{day.year:04d}-Q{quarter}"
    if frequency == "monthly":
        return f"{day.year:04d}-{day.month:02d}"
    raise ValueError(f"Unsupported frequency: {frequency}")


def _period_label(day: date, frequency: str) -> str:
    return _period_key(day, frequency)


def _returns(values: list[float]) -> list[float]:
    return [(values[index] / values[index - 1]) - 1 for index in range(1, len(values)) if values[index - 1] != 0]


def _sharpe(returns: list[float]) -> float | None:
    deviation = _stddev(returns)
    if deviation is None or deviation == 0:
        return None
    return (sum(returns) / len(returns)) / deviation * math.sqrt(TRADING_DAYS_PER_YEAR)


def _sortino(returns: list[float]) -> float | None:
    if not returns:
        return None
    downside = [value for value in returns if value < 0]
    if not downside:
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


def _max_drawdown(values: list[float]) -> float:
    if not values:
        return 0.0
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        worst = min(worst, (value / peak) - 1 if peak else 0.0)
    return worst


def _annualized_return(total_return: float, start: str, end: str) -> float | None:
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    years = max((end_date - start_date).days / 365.25, 1 / 365.25)
    if total_return <= -1:
        return None
    return (1 + total_return) ** (1 / years) - 1


def _parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def _to_float(value: Any) -> float:
    return float(value)


def _color_map(symbols: list[str]) -> dict[str, str]:
    palette = ["#2563eb", "#059669", "#d97706", "#7c3aed", "#0891b2", "#dc2626", "#4b5563", "#c026d3"]
    colors = {symbol: palette[index % len(palette)] for index, symbol in enumerate(symbols)}
    colors[CASH_LABEL] = "#9ca3af"
    return colors


def _render_html(report: dict[str, Any]) -> str:
    payload = json.dumps(report, ensure_ascii=True, separators=(",", ":")).replace("</", "<\\/")
    return HTML_TEMPLATE.replace("__REPORT_DATA__", payload)


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Backtest Report</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f8fafc;
      --panel: #ffffff;
      --ink: #111827;
      --muted: #64748b;
      --line: #d7dee8;
      --line-soft: #edf2f7;
      --accent: #0f766e;
      --benchmark: #111827;
      --danger: #b91c1c;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 14px;
      letter-spacing: 0;
    }
    main {
      width: min(1480px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 24px 0 40px;
    }
    header {
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: flex-end;
      margin-bottom: 18px;
    }
    h1 {
      margin: 0 0 6px;
      font-size: 26px;
      line-height: 1.15;
      font-weight: 760;
    }
    h2 {
      margin: 0;
      font-size: 16px;
      line-height: 1.25;
      font-weight: 720;
    }
    .meta {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
      word-break: break-word;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(6, minmax(130px, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }
    .stat {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      min-height: 76px;
    }
    .stat-label {
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
      white-space: nowrap;
    }
    .stat-value {
      font-size: 20px;
      line-height: 1.1;
      font-weight: 760;
    }
    .chart-panel, .table-panel, .warning-panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    .chart-head {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      padding: 14px 16px 0;
    }
    .legend {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px 12px;
      max-width: 760px;
    }
    .legend-item {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: #334155;
      font-size: 12px;
      white-space: nowrap;
    }
    .swatch {
      width: 11px;
      height: 11px;
      border-radius: 3px;
      border: 1px solid rgba(17, 24, 39, 0.14);
      flex: 0 0 auto;
    }
    .chart-wrap {
      position: relative;
      height: 620px;
      padding: 4px 10px 10px;
    }
    svg {
      display: block;
      width: 100%;
      height: 100%;
      overflow: visible;
    }
    .tooltip {
      position: absolute;
      min-width: 230px;
      max-width: 300px;
      pointer-events: none;
      opacity: 0;
      transform: translateY(4px);
      transition: opacity 120ms ease, transform 120ms ease;
      background: rgba(255, 255, 255, 0.96);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 12px 28px rgba(15, 23, 42, 0.14);
      padding: 10px 12px;
      color: var(--ink);
      font-size: 12px;
      line-height: 1.45;
      z-index: 3;
    }
    .tooltip.visible {
      opacity: 1;
      transform: translateY(0);
    }
    .tooltip-title {
      font-weight: 720;
      margin-bottom: 6px;
    }
    .tooltip-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
    }
    .tables {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(300px, 390px);
      gap: 14px;
      margin-top: 14px;
    }
    .table-panel {
      overflow: hidden;
    }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
    }
    .segments {
      display: inline-flex;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      flex: 0 0 auto;
      background: #f8fafc;
    }
    .segments button {
      border: 0;
      border-right: 1px solid var(--line);
      background: transparent;
      color: #334155;
      padding: 8px 11px;
      min-width: 76px;
      font: inherit;
      font-size: 12px;
      cursor: pointer;
    }
    .segments button:last-child { border-right: 0; }
    .segments button.active {
      background: var(--ink);
      color: white;
    }
    .benchmark-control {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }
    .benchmark-control select {
      min-width: 220px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
      color: var(--ink);
      padding: 8px 10px;
      font: inherit;
      font-size: 12px;
    }
    .table-scroll {
      max-height: 560px;
      overflow: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-variant-numeric: tabular-nums;
    }
    th, td {
      padding: 9px 12px;
      border-bottom: 1px solid var(--line-soft);
      text-align: right;
      white-space: nowrap;
    }
    th:first-child, td:first-child { text-align: left; }
    th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f8fafc;
      color: #475569;
      font-size: 12px;
      font-weight: 720;
    }
    tr:last-child td { border-bottom: 0; }
    .negative { color: #b91c1c; }
    .positive { color: #047857; }
    .warning-panel {
      margin-top: 14px;
      padding: 12px 14px;
      color: #7c2d12;
      background: #fff7ed;
      border-color: #fed7aa;
    }
    .signal-panel {
      margin-top: 14px;
      overflow: hidden;
    }
    .signal-layout {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(300px, 420px);
      gap: 14px;
      padding: 14px;
    }
    .signal-summary {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }
    .signal-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px;
      background: #f8fafc;
    }
    .signal-card strong {
      display: block;
      margin-bottom: 6px;
      font-size: 13px;
    }
    .signal-card div {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      color: #334155;
      font-size: 12px;
      line-height: 1.8;
    }
    .signal-detail {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
      min-height: 160px;
      padding: 12px;
    }
    .signal-detail h3 {
      margin: 0 0 8px;
      font-size: 14px;
    }
    .signal-detail ul {
      margin: 8px 0 0;
      padding-left: 18px;
      color: #334155;
      line-height: 1.65;
    }
    .warning-panel ul {
      margin: 8px 0 0;
      padding-left: 18px;
    }
    @media (max-width: 1100px) {
      .summary { grid-template-columns: repeat(3, minmax(130px, 1fr)); }
      .tables { grid-template-columns: 1fr; }
      .signal-layout { grid-template-columns: 1fr; }
    }
    @media (max-width: 720px) {
      main { width: min(100vw - 20px, 1480px); padding-top: 16px; }
      header, .chart-head, .panel-head {
        flex-direction: column;
        align-items: stretch;
      }
      .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .signal-summary { grid-template-columns: 1fr; }
      .chart-wrap { height: 520px; }
      .legend { justify-content: flex-start; }
      .segments { width: 100%; }
      .segments button { flex: 1 1 0; min-width: 0; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1 id="title">Backtest Report</h1>
        <div class="meta" id="meta"></div>
      </div>
      <div class="meta" id="dataMeta"></div>
    </header>

    <section class="summary" id="summaryCards"></section>

    <section class="chart-panel">
      <div class="chart-head">
        <div>
          <h2>NAV, Benchmark, Holdings, Drawdowns</h2>
          <div class="meta" id="chartMeta"></div>
        </div>
        <div>
          <label class="benchmark-control">
            Benchmark
            <select id="benchmarkSelect"></select>
          </label>
          <div class="legend" id="legend"></div>
        </div>
      </div>
      <div class="chart-wrap" id="chartWrap">
        <svg id="chartSvg" role="img" aria-label="Backtest chart"></svg>
        <div class="tooltip" id="tooltip"></div>
      </div>
    </section>

    <section class="tables">
      <div class="table-panel">
        <div class="panel-head">
          <h2>Period Metrics</h2>
          <div class="segments" id="metricSegments">
            <button type="button" data-frequency="yearly" class="active">Yearly</button>
            <button type="button" data-frequency="quarterly">Quarterly</button>
            <button type="button" data-frequency="monthly">Monthly</button>
          </div>
        </div>
        <div class="table-scroll">
          <table id="metricsTable"></table>
        </div>
      </div>
      <div class="table-panel">
        <div class="panel-head">
          <h2>Largest Drawdowns</h2>
        </div>
        <div class="table-scroll">
          <table id="drawdownTable"></table>
        </div>
      </div>
    </section>

    <section class="table-panel signal-panel" id="signalPanel" hidden>
      <div class="panel-head">
        <div>
          <h2>Signal Attribution</h2>
          <div class="meta">Period-level diagnostics show how active signal weight changes helped or hurt versus the benchmark strategy.</div>
        </div>
      </div>
      <div class="signal-layout">
        <div>
          <div class="signal-summary" id="signalSummary"></div>
          <div class="table-scroll">
            <table id="signalTable"></table>
          </div>
        </div>
        <aside class="signal-detail" id="signalDetail"></aside>
      </div>
    </section>

    <section class="warning-panel" id="warnings" hidden></section>
  </main>

  <script>
    const report = __REPORT_DATA__;
    const state = { frequency: "yearly", benchmarkId: report.defaultBenchmarkId || "primary" };
    const strategyColor = "#0f766e";
    const benchmarkColor = "#111827";

    function fmtPct(value, digits = 2) {
      if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
      return new Intl.NumberFormat("en-US", { style: "percent", minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
    }

    function fmtNum(value, digits = 2) {
      if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
      return new Intl.NumberFormat("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
    }

    function fmtMoney(value) {
      if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
      return "CNH " + new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
    }

    function cls(value) {
      if (value === null || value === undefined || !Number.isFinite(value) || Math.abs(value) < 0.0000001) return "";
      return value < 0 ? "negative" : "positive";
    }

    function currentBenchmarkOption() {
      return (report.benchmarkOptions || []).find((item) => item.id === state.benchmarkId) || { id: "primary", name: report.benchmarkName };
    }

    function currentBenchmark(point) {
      return (point.benchmarks && point.benchmarks[state.benchmarkId]) || { nav: point.benchmark, index: point.benchmarkIndex };
    }

    function setupHeader() {
      document.getElementById("title").textContent = report.title;
      document.getElementById("meta").textContent = `${report.summary.start} to ${report.summary.end}`;
      document.getElementById("dataMeta").innerHTML = [
        `Source: ${escapeHtml(report.sourceJson)}`,
        report.database ? `Market DB: ${escapeHtml(report.database)}` : null
      ].filter(Boolean).join("<br>");
      document.getElementById("chartMeta").textContent = `${currentBenchmarkOption().name}. ${report.allocationSource}`;
    }

    function setupSummary() {
      const summary = (report.summariesByBenchmark && report.summariesByBenchmark[state.benchmarkId]) || report.summary;
      const items = [
        ["Final NAV", fmtMoney(summary.finalNav)],
        ["Total Return", fmtPct(summary.totalReturn)],
        ["Annualized", fmtPct(summary.annualizedReturn)],
        ["Max Drawdown", fmtPct(summary.maxDrawdown)],
        ["Sharpe", fmtNum(summary.sharpe)],
        ["Alpha", fmtPct(summary.alpha)]
      ];
      document.getElementById("summaryCards").innerHTML = items.map(([label, value]) => `
        <div class="stat">
          <div class="stat-label">${escapeHtml(label)}</div>
          <div class="stat-value">${escapeHtml(value)}</div>
        </div>
      `).join("");
    }

    function setupLegend() {
      const items = [
        ["Strategy NAV", strategyColor],
        [currentBenchmarkOption().name, benchmarkColor],
        ["Drawdown periods", "#b91c1c"],
        ...report.allocationOrder.map((symbol) => [symbol, report.colors[symbol]])
      ];
      document.getElementById("legend").innerHTML = items.map(([label, color]) => `
        <span class="legend-item"><span class="swatch" style="background:${escapeHtml(color)}"></span>${escapeHtml(label)}</span>
      `).join("");
    }

    function svgEl(tag, attrs = {}) {
      const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
      for (const [key, value] of Object.entries(attrs)) {
        node.setAttribute(key, value);
      }
      return node;
    }

    function renderChart() {
      const svg = document.getElementById("chartSvg");
      const wrap = document.getElementById("chartWrap");
      const tooltip = document.getElementById("tooltip");
      const width = Math.max(760, wrap.clientWidth - 20);
      const height = wrap.clientHeight - 14;
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      svg.innerHTML = "";

      const margin = { top: 24, right: 30, bottom: 54, left: 72 };
      const plotW = width - margin.left - margin.right;
      const plotH = height - margin.top - margin.bottom;
      const top = margin.top;
      const bottom = margin.top + plotH;
      const left = margin.left;
      const right = margin.left + plotW;
      const points = report.chart.map((point) => ({ ...point, day: new Date(`${point.date}T00:00:00`) }));
      const start = points[0].day.getTime();
      const end = points[points.length - 1].day.getTime();
      const x = (day) => left + ((day.getTime() - start) / Math.max(1, end - start)) * plotW;
      const values = points.flatMap((point) => [point.navIndex, currentBenchmark(point).index].filter((value) => Number.isFinite(value)));
      const minV = Math.min(...values);
      const maxV = Math.max(...values);
      const pad = Math.max(4, (maxV - minV) * 0.08);
      const yMin = Math.floor(minV - pad);
      const yMax = Math.ceil(maxV + pad);
      const y = (value) => bottom - ((value - yMin) / Math.max(1, yMax - yMin)) * plotH;
      const centers = points.map((point) => x(point.day));

      for (let index = 0; index < points.length; index += 1) {
        const point = points[index];
        const x0 = index === 0 ? left : (centers[index - 1] + centers[index]) / 2;
        const x1 = index === points.length - 1 ? right : (centers[index] + centers[index + 1]) / 2;
        let cursor = bottom;
        for (const symbol of report.allocationOrder) {
          const weight = Math.max(0, Math.min(1, point.weights[symbol] || 0));
          if (weight <= 0.0001) continue;
          const h = weight * plotH;
          svg.appendChild(svgEl("rect", {
            x: x0,
            y: cursor - h,
            width: Math.max(0.6, x1 - x0),
            height: h,
            fill: report.colors[symbol] || "#94a3b8",
            opacity: symbol === "Cash" ? 0.13 : 0.17
          }));
          cursor -= h;
        }
      }

      for (const period of report.drawdownPeriods) {
        const x0 = x(new Date(`${period.start}T00:00:00`));
        const x1 = period.end ? x(new Date(`${period.end}T00:00:00`)) : right;
        svg.appendChild(svgEl("rect", {
          x: Math.max(left, x0),
          y: top,
          width: Math.max(1, Math.min(right, x1) - Math.max(left, x0)),
          height: plotH,
          fill: "#b91c1c",
          opacity: Math.min(0.16, Math.max(0.045, Math.abs(period.depth) * 0.55))
        }));
      }

      const gridTicks = 5;
      for (let tick = 0; tick <= gridTicks; tick += 1) {
        const value = yMin + ((yMax - yMin) * tick) / gridTicks;
        const yy = y(value);
        svg.appendChild(svgEl("line", { x1: left, y1: yy, x2: right, y2: yy, stroke: "#dfe6ef", "stroke-width": "1" }));
        const label = svgEl("text", { x: left - 10, y: yy + 4, "text-anchor": "end", fill: "#64748b", "font-size": "12" });
        label.textContent = fmtNum(value, 0);
        svg.appendChild(label);
      }

      const firstYear = points[0].day.getFullYear();
      const lastYear = points[points.length - 1].day.getFullYear();
      for (let year = firstYear; year <= lastYear; year += 1) {
        const day = new Date(`${year}-01-01T00:00:00`);
        if (day < points[0].day || day > points[points.length - 1].day) continue;
        const xx = x(day);
        svg.appendChild(svgEl("line", { x1: xx, y1: top, x2: xx, y2: bottom, stroke: "#e8edf4", "stroke-width": "1" }));
        const label = svgEl("text", { x: xx, y: bottom + 24, "text-anchor": "middle", fill: "#64748b", "font-size": "12" });
        label.textContent = String(year);
        svg.appendChild(label);
      }

      svg.appendChild(svgEl("line", { x1: left, y1: bottom, x2: right, y2: bottom, stroke: "#94a3b8", "stroke-width": "1" }));
      svg.appendChild(svgEl("line", { x1: left, y1: top, x2: left, y2: bottom, stroke: "#94a3b8", "stroke-width": "1" }));

      function pathFor(key) {
        return points
          .filter((point) => Number.isFinite(point[key]))
          .map((point, index) => `${index === 0 ? "M" : "L"}${x(point.day).toFixed(2)},${y(point[key]).toFixed(2)}`)
          .join(" ");
      }

      if (points.some((point) => Number.isFinite(currentBenchmark(point).index))) {
        svg.appendChild(svgEl("path", {
          d: points
            .filter((point) => Number.isFinite(currentBenchmark(point).index))
            .map((point, index) => `${index === 0 ? "M" : "L"}${x(point.day).toFixed(2)},${y(currentBenchmark(point).index).toFixed(2)}`)
            .join(" "),
          fill: "none",
          stroke: benchmarkColor,
          "stroke-width": "2.2",
          "stroke-dasharray": "7 5",
          "stroke-linejoin": "round",
          "stroke-linecap": "round"
        }));
      }
      svg.appendChild(svgEl("path", {
        d: pathFor("navIndex"),
        fill: "none",
        stroke: strategyColor,
        "stroke-width": "2.7",
        "stroke-linejoin": "round",
        "stroke-linecap": "round"
      }));

      const focus = svgEl("g", { opacity: "0" });
      const focusLine = svgEl("line", { y1: top, y2: bottom, stroke: "#334155", "stroke-width": "1", "stroke-dasharray": "3 4" });
      const focusDot = svgEl("circle", { r: "4.5", fill: strategyColor, stroke: "#ffffff", "stroke-width": "2" });
      focus.appendChild(focusLine);
      focus.appendChild(focusDot);
      svg.appendChild(focus);

      const overlay = svgEl("rect", { x: left, y: top, width: plotW, height: plotH, fill: "transparent" });
      overlay.addEventListener("mousemove", (event) => {
        const bounds = svg.getBoundingClientRect();
        const localX = ((event.clientX - bounds.left) / bounds.width) * width;
        let nearest = 0;
        let distance = Infinity;
        for (let index = 0; index < centers.length; index += 1) {
          const current = Math.abs(centers[index] - localX);
          if (current < distance) {
            nearest = index;
            distance = current;
          }
        }
        const point = points[nearest];
        const xx = centers[nearest];
        focus.setAttribute("opacity", "1");
        focusLine.setAttribute("x1", xx);
        focusLine.setAttribute("x2", xx);
        focusDot.setAttribute("cx", xx);
        focusDot.setAttribute("cy", y(point.navIndex));

        const topHoldings = Object.entries(point.weights)
          .filter(([, value]) => value > 0.01)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 5)
          .map(([symbol, value]) => `<div class="tooltip-row"><span>${escapeHtml(symbol)}</span><strong>${fmtPct(value, 1)}</strong></div>`)
          .join("");
        tooltip.innerHTML = `
          <div class="tooltip-title">${escapeHtml(point.date)}</div>
          <div class="tooltip-row"><span>NAV index</span><strong>${fmtNum(point.navIndex)}</strong></div>
          <div class="tooltip-row"><span>${escapeHtml(currentBenchmarkOption().name)}</span><strong>${fmtNum(currentBenchmark(point).index)}</strong></div>
          <div class="tooltip-row"><span>Drawdown</span><strong>${fmtPct(point.drawdown)}</strong></div>
          ${topHoldings}
        `;
        const wrapBounds = wrap.getBoundingClientRect();
        const tooltipWidth = 270;
        const leftPos = Math.min(wrapBounds.width - tooltipWidth - 12, Math.max(12, event.clientX - wrapBounds.left + 14));
        tooltip.style.left = `${leftPos}px`;
        tooltip.style.top = `${Math.max(12, event.clientY - wrapBounds.top - 20)}px`;
        tooltip.classList.add("visible");
      });
      overlay.addEventListener("mouseleave", () => {
        focus.setAttribute("opacity", "0");
        tooltip.classList.remove("visible");
      });
      svg.appendChild(overlay);
    }

    function renderMetrics() {
      const benchmarkMetrics = (report.metricsByBenchmark && report.metricsByBenchmark[state.benchmarkId]) || report.metrics;
      const rows = benchmarkMetrics[state.frequency] || [];
      const table = document.getElementById("metricsTable");
      table.innerHTML = `
        <thead>
          <tr>
            <th>Period</th>
            <th>Return</th>
            <th>Sharpe</th>
            <th>Sortino</th>
            <th>Calmar</th>
            <th>Alpha</th>
            <th>Bench</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${escapeHtml(row.period)}</td>
              <td class="${cls(row.return)}">${fmtPct(row.return)}</td>
              <td>${fmtNum(row.sharpe)}</td>
              <td>${fmtNum(row.sortino)}</td>
              <td>${fmtNum(row.calmar)}</td>
              <td class="${cls(row.alpha)}">${fmtPct(row.alpha)}</td>
              <td class="${cls(row.benchmarkReturn)}">${fmtPct(row.benchmarkReturn)}</td>
            </tr>
          `).join("")}
        </tbody>
      `;
    }

    function renderDrawdowns() {
      const rows = report.topDrawdowns || [];
      const table = document.getElementById("drawdownTable");
      table.innerHTML = `
        <thead>
          <tr>
            <th>Start</th>
            <th>Trough</th>
            <th>Recovery</th>
            <th>Depth</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${escapeHtml(row.start)}</td>
              <td>${escapeHtml(row.trough)}</td>
              <td>${row.end ? escapeHtml(row.end) : "Open"}</td>
              <td class="negative">${fmtPct(row.depth)}</td>
            </tr>
          `).join("")}
        </tbody>
      `;
    }

    function renderSignalDiagnostics() {
      const diagnostics = report.signalDiagnostics;
      if (!diagnostics || !diagnostics.periods || !diagnostics.periods.length) return;
      document.getElementById("signalPanel").hidden = false;
      const summary = diagnostics.summary || {};
      const summaryItems = [
        ["Full", summary.full],
        ["In Sample", summary.in_sample],
        ["Out Of Sample", summary.out_of_sample]
      ];
      document.getElementById("signalSummary").innerHTML = summaryItems.map(([label, item]) => `
        <div class="signal-card">
          <strong>${escapeHtml(label)}</strong>
          <div><span>Periods</span><b>${item ? item.periods : 0}</b></div>
          <div><span>Positive / negative</span><b>${item ? `${item.positivePeriods} / ${item.negativePeriods}` : "0 / 0"}</b></div>
          <div><span>Est. contribution</span><b class="${cls(item && item.estimatedContribution)}">${fmtPct(item && item.estimatedContribution)}</b></div>
          <div><span>Compounded delta</span><b class="${cls(item && item.compoundedDelta)}">${fmtPct(item && item.compoundedDelta)}</b></div>
          <div><span>Avg. period delta</span><b class="${cls(item && item.averageRealizedDelta)}">${fmtPct(item && item.averageRealizedDelta)}</b></div>
        </div>
      `).join("");

      const rows = diagnostics.periods.map((period, index) => ({ ...period, index, signal: period.signals[0] }));
      const table = document.getElementById("signalTable");
      table.innerHTML = `
        <thead>
          <tr>
            <th>Period</th>
            <th>Sample</th>
            <th>Signal</th>
            <th>Changes</th>
            <th>Est. Contribution</th>
            <th>Realized Delta</th>
            <th>Main Positive</th>
            <th>Main Negative</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr data-signal-period="${row.index}">
              <td>${escapeHtml(row.period)}</td>
              <td>${escapeHtml(row.sample === "out_of_sample" ? "OOS" : "IS")}</td>
              <td>${escapeHtml(row.signal.name)}</td>
              <td>${row.signal.activeChanges}</td>
              <td class="${cls(row.signal.estimatedContribution)}">${fmtPct(row.signal.estimatedContribution)}</td>
              <td class="${cls(row.signal.realizedDelta)}">${fmtPct(row.signal.realizedDelta)}</td>
              <td class="${cls(row.signal.topPositive[0] && row.signal.topPositive[0].estimatedContribution)}">${impactLabel(row.signal.topPositive[0])}</td>
              <td class="${cls(row.signal.topNegative[0] && row.signal.topNegative[0].estimatedContribution)}">${impactLabel(row.signal.topNegative[0])}</td>
            </tr>
          `).join("")}
        </tbody>
      `;
      table.addEventListener("click", (event) => {
        const row = event.target.closest("tr[data-signal-period]");
        if (!row) return;
        renderSignalDetail(rows[Number(row.dataset.signalPeriod)]);
      });
      renderSignalDetail(rows[rows.length - 1]);
    }

    function renderSignalDetail(row) {
      if (!row) return;
      const detail = document.getElementById("signalDetail");
      const signal = row.signal;
      const changes = (signal.changes || []).slice(0, 12);
      detail.innerHTML = `
        <h3>${escapeHtml(row.period)}</h3>
        <div class="tooltip-row"><span>Signal</span><strong>${escapeHtml(signal.name)}</strong></div>
        <div class="tooltip-row"><span>Estimated contribution</span><strong class="${cls(signal.estimatedContribution)}">${fmtPct(signal.estimatedContribution)}</strong></div>
        <div class="tooltip-row"><span>Realized candidate-minus-baseline</span><strong class="${cls(signal.realizedDelta)}">${fmtPct(signal.realizedDelta)}</strong></div>
        <ul>
          ${changes.map((item) => `
            <li>
              ${escapeHtml(item.symbol)} ${escapeHtml(item.action)}:
              ${fmtPct(item.baselineWeight, 1)} to ${fmtPct(item.candidateWeight, 1)},
              asset ${fmtPct(item.assetReturn, 2)},
              contribution <span class="${cls(item.estimatedContribution)}">${fmtPct(item.estimatedContribution, 2)}</span>
            </li>
          `).join("") || "<li>No material signal weight changes in this period.</li>"}
        </ul>
      `;
    }

    function impactLabel(item) {
      if (!item) return "n/a";
      return `${escapeHtml(item.symbol)} ${escapeHtml(item.action)} ${fmtPct(item.estimatedContribution, 1)}`;
    }

    function setupSegments() {
      document.getElementById("metricSegments").addEventListener("click", (event) => {
        const button = event.target.closest("button[data-frequency]");
        if (!button) return;
        state.frequency = button.dataset.frequency;
        for (const item of document.querySelectorAll("#metricSegments button")) {
          item.classList.toggle("active", item === button);
        }
        renderMetrics();
      });
    }

    function setupBenchmarkSelect() {
      const select = document.getElementById("benchmarkSelect");
      const options = report.benchmarkOptions && report.benchmarkOptions.length
        ? report.benchmarkOptions
        : [{ id: "primary", name: report.benchmarkName }];
      select.innerHTML = options.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`).join("");
      select.value = state.benchmarkId;
      select.addEventListener("change", () => {
        state.benchmarkId = select.value;
        setupHeader();
        setupSummary();
        setupLegend();
        renderMetrics();
        renderChart();
      });
    }

    function setupWarnings() {
      const panel = document.getElementById("warnings");
      if (!report.warnings.length) return;
      panel.hidden = false;
      panel.innerHTML = `<strong>Report notes</strong><ul>${report.warnings.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
    }

    setupHeader();
    setupSummary();
    setupBenchmarkSelect();
    setupLegend();
    setupSegments();
    setupWarnings();
    renderMetrics();
    renderDrawdowns();
    renderSignalDiagnostics();
    renderChart();
    window.addEventListener("resize", renderChart);
  </script>
</body>
</html>
"""
