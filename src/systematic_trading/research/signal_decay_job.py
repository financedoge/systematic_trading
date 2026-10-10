"""App-owned signal-decay job.

Builds point-in-time signal series from published audited histories, measures
their forward rank IC, and publishes the decay evidence plus the status that the
dashboard and the allocation-aware warning read.

This is a diagnostic. It never changes a monitored strategy, a target, an
allocation, an approval or a broker record.
"""
from __future__ import annotations

from decimal import Decimal as D
import json

import numpy as np

from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.research.signal_decay import (
    HORIZONS, MIN_NAMES, forward_return, rank_ic, row_value, summarise_signal,
)
from systematic_trading.signals.trend import _rank_metric

SOURCE = "signal-decay/measurements"
DOCUMENT = "signal-decay/report"

# Signal registry. ``key`` marks the signals a strategy's selection depends on.
SIGNALS = {
    "m1_total": dict(label="M1 selection score", key=True,
                     detail="75% momentum / 25% volume, the score M1/14 and FR25 rank on"),
    "m1_trend": dict(label="M1 momentum component", key=False,
                     detail="0.20*rank(21) + 0.35*rank(63) + 0.45*rank(126)"),
    "m1_volume": dict(label="M1 volume component", key=False,
                      detail="0.65*rank(up-volume share) + 0.35*rank(signed volume pressure)"),
    "momentum_21": dict(label="21-session momentum", key=False, detail="Close-to-close return"),
    "momentum_63": dict(label="63-session momentum", key=False, detail="Close-to-close return"),
    "momentum_126": dict(label="126-session momentum", key=True,
                         detail="Longest leg of the M1 trend score and its positive gate"),
    "momentum_252": dict(label="252-session momentum", key=False, detail="Close-to-close return"),
    "drawdown_252": dict(label="252-session drawdown", key=False,
                         detail="Close against its trailing 252-session high"),
    "realized_vol_63": dict(label="63-session realised volatility", key=False,
                            detail="Daily return standard deviation"),
}

# Which signals each monitored strategy's selection depends on.
KEY_SIGNALS = {
    "research_m1_14_v1": ["m1_total", "momentum_126"],
    "research_fr25_14_v1": ["m1_total", "momentum_126"],
    "research_fallback_f3_v1": ["m1_total"],
    "research_rolling_xgboost_1y_lag20_v1_usd_v1": ["m1_total"],
    "research_etf_activity_lag20_v1_usd_v1": ["m1_total"],
    "research_economic_context_ridge_v1": ["m1_total"],
}

# Signals the strategies consume that this diagnostic cannot yet reproduce.
# Published explicitly rather than silently omitted.
COVERAGE_GAPS = [
    dict(name="financial_ridge_forecast", used_by=["research_fr25_14_v1"],
         reason="FR25's per-decision ridge forecasts are not published; reproducing them "
                "requires re-running the frozen monthly model schedule."),
    dict(name="context_ridge_forecast", used_by=["research_economic_context_ridge_v1"],
         reason="CR's per-decision ridge forecasts are not published; same reason."),
    dict(name="rolling_xgboost_forecast",
         used_by=["research_rolling_xgboost_1y_lag20_v1_usd_v1", "research_fallback_f3_v1"],
         reason="The monthly one-year XGBoost forecasts are not published per decision."),
    dict(name="usd_ridge_forecast", used_by=["research_etf_activity_lag20_v1_usd_v1"],
         reason="The USD allocation ridge forecasts are not published per decision."),
]


def _decimal(value) -> D:
    return D(str(value))


def _momentum(history, lookback):
    if len(history) < lookback + 1:
        return None
    reference = _decimal(row_value(history[-(lookback + 1)], "close"))
    if reference <= 0:
        return None
    return _decimal(row_value(history[-1], "close")) / reference - 1


def _up_volume_share(history, lookback=21):
    window = history[-(lookback + 1):]
    if len(window) < lookback + 1:
        return None
    up = total = D(0)
    for index in range(1, len(window)):
        volume = _decimal(row_value(window[index], "volume"))
        total += volume
        if _decimal(row_value(window[index], "close")) > _decimal(row_value(window[index - 1], "close")):
            up += volume
    return None if total <= 0 else up / total


def _average_volume(history, lookback):
    if len(history) < lookback:
        return None
    window = history[-lookback:]
    return sum((_decimal(row_value(bar, "volume")) for bar in window), D(0)) / D(len(window))


def _signed_volume_pressure(history, fast=21, slow=126):
    fast_average, slow_average = _average_volume(history, fast), _average_volume(history, slow)
    momentum = _momentum(history, fast)
    if fast_average is None or slow_average is None or slow_average <= 0 or momentum is None:
        return None
    pressure = (fast_average / slow_average) - 1
    return pressure if momentum >= 0 else -pressure


def _realized_volatility(history, lookback=63):
    if len(history) < lookback + 1:
        return None
    window = history[-(lookback + 1):]
    returns = []
    for index in range(1, len(window)):
        previous = _decimal(row_value(window[index - 1], "close"))
        if previous <= 0:
            return None
        returns.append(float(_decimal(row_value(window[index], "close")) / previous - 1))
    return float(np.std(returns, ddof=1)) if len(returns) > 1 else None


def _drawdown(history, lookback=252):
    if len(history) < lookback:
        return None
    window = [_decimal(row_value(bar, "close")) for bar in history[-lookback:]]
    peak = max(window)
    return None if peak <= 0 else float(window[-1] / peak - 1)


def raw_features(bars_by_symbol, day, history_cache):
    """Raw per-symbol features at ``day`` using only sessions strictly before it."""
    features = {}
    for symbol, rows in bars_by_symbol.items():
        boundary = history_cache[symbol]["boundary"].get(str(day))
        if boundary is None or boundary <= 0:
            continue
        history = rows[:boundary]
        features[symbol] = dict(
            momentum_21=_momentum(history, 21), momentum_63=_momentum(history, 63),
            momentum_126=_momentum(history, 126), momentum_252=_momentum(history, 252),
            up_volume=_up_volume_share(history), signed_volume=_signed_volume_pressure(history),
            realized_vol_63=_realized_volatility(history), drawdown_252=_drawdown(history),
        )
    return features


def _blend(parts):
    """Weighted mean of ranked components with per-symbol weights.

    Matches the strategy overlays: a symbol missing one component is normalised
    by the weights it actually has, never filled and never zero-weighted.
    """
    totals: dict[str, D] = {}
    weights: dict[str, D] = {}
    for part_weight, values in parts:
        if values is None or part_weight <= 0:
            continue
        for symbol, value in values.items():
            totals[symbol] = totals.get(symbol, D(0)) + part_weight * value
            weights[symbol] = weights.get(symbol, D(0)) + part_weight
    if not totals:
        return None
    return {s: totals[s] / weights[s] for s in totals if weights[s] > 0}


def signal_values(features):
    """Derive the registered signals for one decision date from raw features."""
    symbols = sorted(features)

    def rank(key):
        return _rank_metric({s: features[s][key] for s in symbols if features[s][key] is not None})

    outputs = {}
    for name in ("momentum_21", "momentum_63", "momentum_126", "momentum_252",
                 "drawdown_252", "realized_vol_63"):
        outputs[name] = {s: features[s][name] for s in symbols if features[s][name] is not None}
    trend = _blend([(D("0.20"), rank("momentum_21")), (D("0.35"), rank("momentum_63")),
                    (D("0.45"), rank("momentum_126"))])
    volume = _blend([(D("0.65"), rank("up_volume")), (D("0.35"), rank("signed_volume"))])
    if trend:
        outputs["m1_trend"] = trend
    if volume:
        outputs["m1_volume"] = volume
    if trend and volume:
        outputs["m1_total"] = _blend([(D("0.75"), trend), (D("0.25"), volume)])
    return outputs


def _caches(bars_by_symbol):
    """Per-symbol date index and strict-prefix boundary, built once."""
    cache = {}
    for symbol, rows in bars_by_symbol.items():
        positions = {str(row_value(bar, "trade_date")): i for i, bar in enumerate(rows)}
        cache[symbol] = dict(positions=positions, boundary={d: i for d, i in positions.items()})
    return cache


def measure(bars_by_symbol, decisions):
    """Per-signal, per-horizon IC series over the decision dates."""
    names = sorted(SIGNALS)
    series = {name: {h: [] for h in HORIZONS} for name in names}
    skipped = {name: 0 for name in names}
    cache = _caches(bars_by_symbol)
    for day in decisions:
        values = signal_values(raw_features(bars_by_symbol, day, cache))
        labels = {}
        for horizon in HORIZONS:
            per_symbol = {}
            for symbol, rows in bars_by_symbol.items():
                index = cache[symbol]["positions"].get(str(day))
                if index is None:
                    continue
                value = forward_return(rows, index, horizon)
                if value is not None:
                    per_symbol[symbol] = value
            labels[horizon] = per_symbol
        for name in names:
            signal = values.get(name)
            for horizon in HORIZONS:
                forward = labels[horizon]
                ic = rank_ic(signal, forward) if signal and len(forward) >= MIN_NAMES else None
                series[name][horizon].append(ic)
                if ic is None:
                    skipped[name] += 1
    return series, skipped


def turnover_and_sigma(bars_by_symbol, decisions, signal_name="m1_total", slots=6, horizon=21):
    """Measured top-slot churn and forward-return dispersion for the cost gate."""
    cache = _caches(bars_by_symbol)
    previous, changes, periods = None, 0.0, 0
    returns = []
    for day in decisions:
        values = signal_values(raw_features(bars_by_symbol, day, cache)).get(signal_name)
        if not values:
            continue
        selected = {s for s, _ in sorted(values.items(), key=lambda kv: (-kv[1], kv[0]))[:slots]}
        if previous is not None:
            changes += len(selected ^ previous) / (2 * slots)
            periods += 1
        previous = selected
        for symbol, rows in bars_by_symbol.items():
            index = cache[symbol]["positions"].get(str(day))
            if index is None:
                continue
            value = forward_return(rows, index, horizon)
            if value is not None:
                returns.append(value)
    turnover = (changes / periods * 12) if periods else None
    sigma = float(np.std(returns, ddof=1)) if len(returns) > 1 else None
    return turnover, sigma


def build(settings, analytics, config):
    """Build the complete decay record from published audited inputs."""
    from systematic_trading.research.m1_monitoring import load_inputs
    from systematic_trading.research.momentum_signals import decision_sessions

    inputs = load_inputs(settings, analytics, config)
    bars = inputs["bars"]
    days = [str(row["trade_date"]) for row in bars["SPY"]]
    decisions = [str(d) for d in decision_sessions(days, config["calculation"]["start"], "monthly")]
    series, skipped = measure(bars, decisions)
    turnover, sigma = turnover_and_sigma(bars, decisions)

    records = []
    for name in sorted(SIGNALS):
        records.append(summarise_signal(
            name=name, label=SIGNALS[name]["label"], ic_by_horizon=series[name],
            turnover=turnover if SIGNALS[name]["key"] else None, sigma=sigma,
            period_sessions=21))
    return dict(
        version="signal-decay-v1",
        method="point-in-time monthly signals against next-open forward returns; rank IC across "
               "the candidate pool; circular block bootstrap intervals over decision dates",
        horizons=list(HORIZONS),
        decisions=len(decisions),
        first_decision=decisions[0] if decisions else None,
        last_decision=decisions[-1] if decisions else None,
        universe=sorted(bars),
        batch=inputs["provenance"]["batch"],
        price_basis=inputs["provenance"]["price_basis"],
        turnover=dict(annual_one_way=turnover, slots=6,
                      note="Measured top-six membership churn, annualised at the monthly cadence."),
        forward_return_sigma_21=sigma,
        cost_bps=5,
        skipped_cells=skipped,
        signals=records,
        key_signals=KEY_SIGNALS,
        coverage_gaps=COVERAGE_GAPS,
        limitations=[
            "IC uses forward returns as labels; this is a diagnostic, not a tradable signal.",
            "Forward windows overlap at the 21- and 63-session horizons, so intervals come from a "
            "circular block bootstrap over decision dates, never a naive t-statistic.",
            "A 14-asset pool makes each single-date rank IC coarse; the averaged statistic is the "
            "finding and per-date dispersion is published alongside it.",
            "The pool mixes asset classes (equity regions, bonds, gold, commodities, credit), so a "
            "cross-sectional rank partly measures asset-class differences rather than selection "
            "skill within a homogeneous universe. Read the IC as a ranking diagnostic for this "
            "pool, not as stock-selection alpha.",
            "half_life_sessions is null when the IC curve does not decline monotonically over the "
            "measured horizons, which means no decay was detected in this window rather than a "
            "very long half-life.",
            "Historical inputs are revised provider vintages; historical publication availability "
            "is not certified.",
        ],
    )


def refresh_signal_decay(settings, analytics):
    """Compute and publish the decay record. Returns True when published.

    This is a diagnostic, so a missing prerequisite is reported as "not yet
    measurable" rather than raising into the research lane: before the first
    audited batch is published there is simply nothing to measure. Any other
    failure still raises, so a real data fault is never hidden.
    """
    from systematic_trading.research.analytics_projection import observation

    if not analytics.latest("governance/catalog"):
        return False
    config = json.loads(settings.strategy_monitoring_config_path.read_text(encoding="utf8"))
    report = build(settings, analytics, config)
    # The version covers the measured values, so a changed IC republishes and an
    # unchanged one is skipped. Hashing only the inputs would strand stale results.
    version = digest(encode(report))
    observations = []
    for record in report["signals"]:
        for horizon, value in record["ic_curve"].items():
            observations.append(observation(
                f"{record['name']}/{horizon}", "signal_decay_ic", record["name"],
                dict(signal=record["name"], horizon=horizon, ic=value, status=record["status"],
                     long_run_ic=record["long_run_ic"], recent_ic=record["recent_ic"],
                     observations=record["observations"].get(str(horizon), record["observations"].get(horizon))),
                observed_at=report["last_decision"]))
    documents = [dict(point_key="report", media_type="application/json", payload=encode(report))]
    return analytics.publish(DOCUMENT, version, observations, documents,
        provenance=dict(owner="application", batch=report["batch"], decisions=report["decisions"],
                        price_basis=report["price_basis"], diagnostic=True))
