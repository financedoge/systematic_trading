from __future__ import annotations

from systematic_trading.presentation.templates import load_template

import json
import math
from bisect import bisect_right
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
    split_date: date | str | None = None,
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
        split_date=split_date,
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
    split_date: date | str | None = None,
    benchmark_symbol: str | None = None,
    benchmark_nav_series: list[dict[str, Any]] | None = None,
    benchmark_name: str | None = None,
    extra_benchmarks: list[dict[str, Any]] | None = None,
    signal_diagnostics: dict[str, Any] | None = None,
    market_prices: dict[str, dict[str, float]] | None = None,
    market_fx_rates: dict[str, float] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    nav_points = _nav_points(result)
    if not nav_points:
        raise ValueError("Backtest result does not contain nav_series.")

    symbols = _extract_symbols(result)
    start_date = nav_points[0]["date"]
    end_date = nav_points[-1]["date"]
    prices: dict[str, dict[str, float]] = market_prices or {}
    fx_rates: dict[str, float] = market_fx_rates or {}
    extra_benchmarks = extra_benchmarks or []
    market_symbols = sorted(set(symbols) | _benchmark_symbols(extra_benchmarks, benchmark_symbol))

    if database_path is not None and not (prices and fx_rates):
        prices, fx_rates, market_warnings = _load_market_data(
            Path(database_path),
            symbols=market_symbols,
            start_date=start_date,
            end_date=end_date,
        )
        warnings.extend(market_warnings)

    # Resolve dated FX once rather than scanning sparse history for every
    # holding in every monthly/quarterly/yearly attribution calculation.
    # This is an in-memory as-of lookup, never a synthetic database observation.
    fx_rates = dict(fx_rates)
    rate_dates = sorted(fx_rates)
    for point in nav_points:
        day = point["date"]
        index = bisect_right(rate_dates, day) - 1
        if day not in fx_rates and index >= 0:
            fx_rates[day] = fx_rates[rate_dates[index]]

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
    holding_contributions = _holding_contribution_tables(
        chart_points=chart_points,
        symbols=symbols,
        prices=prices,
        fx_rates=fx_rates,
    )
    summary = summaries_by_benchmark["primary"]
    metrics = metrics_by_benchmark["primary"]
    split_date_value = _split_date_value(split_date, signal_diagnostics)

    report = {
        "title": result_path.stem.replace("_", " ").title(),
        "sourceJson": str(result_path),
        "database": str(database_path) if database_path is not None else None,
        "splitDate": split_date_value,
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
        "holdingContributions": holding_contributions,
        "signalDiagnostics": signal_diagnostics,
        "warnings": warnings,
    }
    return report, warnings


def _split_date_value(split_date: date | str | None, signal_diagnostics: dict[str, Any] | None) -> str | None:
    if split_date is not None:
        return split_date.isoformat() if isinstance(split_date, date) else str(split_date)
    if signal_diagnostics is not None and signal_diagnostics.get("splitDate") is not None:
        return str(signal_diagnostics["splitDate"])
    return None


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
    from systematic_trading.config import AppSettings
    from systematic_trading.domain import Currency
    from systematic_trading.storage import create_trading_store

    settings = AppSettings()
    if settings.market_data_store_backend == "sqlite" and not database_path.exists():
        return prices, fx_rates, [f"Market database was not found: {database_path}"]
    try:
        store = create_trading_store(settings, database_path=database_path)
        for symbol in symbols:
            bars = store.list_price_bars(symbol, start_date=date.fromisoformat(start_date),
                                         end_date=date.fromisoformat(end_date))
            prices[symbol] = {bar.trade_date.isoformat(): float(bar.close) for bar in bars}
            if not prices[symbol]:
                warnings.append(f"No stored price bars were found for {symbol}.")
        rates = store.list_fx_rates(Currency.USD, quote_currency=Currency.CNH,
                                   end_date=date.fromisoformat(end_date))
        fx_rates = {rate.rate_date.isoformat(): float(rate.rate) for rate in rates}
        if not fx_rates:
            warnings.append("No stored USD/CNH FX rates were found.")
    except Exception as exc:
        warnings.append(f"Could not read configured market store ({type(exc).__name__}).")

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
        proposals_by_date[_proposal_execution_date_key(proposal)].append(proposal)

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
    return series, "Daily holdings reconstructed from next-session rebalance orders, stored closes, and USD/CNH FX.", warnings


def _holding_series_from_targets(
    *,
    result: dict[str, Any],
    nav_points: list[dict[str, Any]],
    symbols: list[str],
) -> tuple[list[dict[str, float]], str, list[str]]:
    proposals_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for proposal in result.get("proposals", []):
        proposals_by_date[_proposal_execution_date_key(proposal)].append(proposal)

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


def _proposal_execution_date_key(proposal: dict[str, Any]) -> str:
    return str(proposal.get("intended_trade_date") or proposal["as_of"])


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
    active = _active_return_metrics(chart_points, benchmark_id=benchmark_id)
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
        "trackingError": active["trackingError"],
        "informationRatio": active["informationRatio"],
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
        active = _active_return_metrics(
            [chart_points[index] for index in range(base_index, end_index + 1)],
            benchmark_id=benchmark_id,
        )
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
                "informationRatio": active["informationRatio"],
                "trackingError": active["trackingError"],
                "benchmarkReturn": benchmark_return,
                "maxDrawdown": max_drawdown,
                "observations": len(daily_returns),
            }
        )
    return rows


def _holding_contribution_tables(
    *,
    chart_points: list[dict[str, Any]],
    symbols: list[str],
    prices: dict[str, dict[str, float]],
    fx_rates: dict[str, float],
) -> dict[str, list[dict[str, Any]]]:
    if len(chart_points) < 2 or not symbols or not prices or not fx_rates:
        return {"yearly": [], "quarterly": [], "monthly": []}
    return {
        frequency: _holding_contributions(chart_points, symbols, prices, fx_rates, frequency)
        for frequency in ["yearly", "quarterly", "monthly"]
    }


def _holding_contributions(
    chart_points: list[dict[str, Any]],
    symbols: list[str],
    prices: dict[str, dict[str, float]],
    fx_rates: dict[str, float],
    frequency: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for index in range(1, len(chart_points)):
        previous = chart_points[index - 1]
        current = chart_points[index]
        key = _period_key(_parse_date(current["date"]), frequency)
        group = grouped.setdefault(
            key,
            {
                "period": key,
                "start": previous["date"],
                "end": current["date"],
                "baseNav": previous["nav"],
                "endNav": current["nav"],
                "symbols": {},
            },
        )
        group["end"] = current["date"]
        group["endNav"] = current["nav"]
        base_nav = group["baseNav"]
        if not base_nav:
            continue

        for symbol in symbols:
            previous_weight = float(previous["weights"].get(symbol, 0.0))
            current_weight = float(current["weights"].get(symbol, 0.0))
            previous_price = _price_cnh(symbol, previous["date"], prices, fx_rates)
            current_price = _price_cnh(symbol, current["date"], prices, fx_rates)
            if previous_price is None or current_price is None or previous_price <= 0:
                continue
            asset_return = (current_price / previous_price) - 1
            symbol_state = group["symbols"].setdefault(
                symbol,
                {
                    "symbol": symbol,
                    "startWeight": previous_weight,
                    "endWeight": current_weight,
                    "weightSum": 0.0,
                    "observations": 0,
                    "daysHeld": 0,
                    "contribution": 0.0,
                    "assetGrowth": 1.0,
                },
            )
            symbol_state["endWeight"] = current_weight
            symbol_state["weightSum"] += previous_weight
            symbol_state["observations"] += 1
            if previous_weight > 0.0001 or current_weight > 0.0001:
                symbol_state["daysHeld"] += 1
            symbol_state["contribution"] += previous_weight * previous["nav"] * asset_return / base_nav
            symbol_state["assetGrowth"] *= 1 + asset_return

    rows: list[dict[str, Any]] = []
    for key in sorted(grouped):
        group = grouped[key]
        base_nav = group["baseNav"]
        end_nav = group["endNav"]
        period_return = (end_nav / base_nav) - 1 if base_nav else None
        holdings = []
        for item in group["symbols"].values():
            observations = item["observations"]
            average_weight = item["weightSum"] / observations if observations else 0.0
            contribution = item["contribution"]
            start_weight = item["startWeight"]
            end_weight = item["endWeight"]
            include = (
                max(abs(start_weight), abs(end_weight), abs(average_weight)) >= 0.005
                or abs(contribution) >= 0.0005
            )
            if not include:
                continue
            holdings.append(
                {
                    "symbol": item["symbol"],
                    "startWeight": start_weight,
                    "averageWeight": average_weight,
                    "endWeight": end_weight,
                    "assetReturn": item["assetGrowth"] - 1,
                    "contribution": contribution,
                    "daysHeld": item["daysHeld"],
                    "observations": observations,
                }
            )
        rows.append(
            {
                "period": group["period"],
                "start": group["start"],
                "end": group["end"],
                "return": period_return,
                "totalContribution": sum(item["contribution"] for item in holdings),
                "holdings": sorted(
                    holdings,
                    key=lambda item: (abs(item["contribution"]), abs(item["averageWeight"]), item["symbol"]),
                    reverse=True,
                ),
            }
        )
    return rows


def _active_return_metrics(chart_points: list[dict[str, Any]], benchmark_id: str = "primary") -> dict[str, float | None]:
    active_returns: list[float] = []
    for index in range(1, len(chart_points)):
        previous = chart_points[index - 1]
        current = chart_points[index]
        previous_benchmark = _benchmark_nav(previous, benchmark_id)
        current_benchmark = _benchmark_nav(current, benchmark_id)
        if previous["nav"] == 0 or previous_benchmark in {None, 0} or current_benchmark is None:
            continue
        strategy_return = (current["nav"] / previous["nav"]) - 1
        benchmark_return = (current_benchmark / previous_benchmark) - 1
        active_returns.append(strategy_return - benchmark_return)
    deviation = _stddev(active_returns)
    average = sum(active_returns) / len(active_returns) if active_returns else None
    return {
        "trackingError": deviation * math.sqrt(TRADING_DAYS_PER_YEAR) if deviation is not None else None,
        "informationRatio": (
            (average / deviation) * math.sqrt(TRADING_DAYS_PER_YEAR)
            if average is not None and deviation not in {None, 0}
            else None
        ),
    }


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
    from systematic_trading.chart_navigation import with_chart_navigation
    from systematic_trading.web.shell import with_app_shell
    currency = report.get("accountingCurrency", "CNH")
    if currency not in {"CNH", "USD"}:
        raise ValueError("Unsupported report accounting currency")
    template = HTML_TEMPLATE.replace("__ACCOUNTING_CURRENCY__", currency)
    return with_app_shell(with_chart_navigation(template.replace("__REPORT_DATA__", payload)), "strategies")


def render_backtest_report_html(report: dict[str, Any]) -> str:
    """Render a complete report payload without writing or mutating an artifact."""
    return _render_html(report)


def render_saved_backtest_report_html(html: str) -> str:
    """Refresh a saved report's presentation using only its embedded frozen data."""
    import re

    match = re.search(r"\bconst report\s*=\s*", html)
    if match:
        try:
            report, _ = json.JSONDecoder().raw_decode(html[match.end():])
        except (ValueError, TypeError):
            return html
        if isinstance(report, dict) and {"chart", "summary", "allocationOrder"} <= report.keys():
            return render_backtest_report_html(report)
    return html


HTML_TEMPLATE = load_template("backtest/reporting_html_template.html")
