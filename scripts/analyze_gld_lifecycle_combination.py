"""Compare the sealed short-range and long-range GLD lifecycle strategies.

Primary question: is the long-range strategy's return correlated with the sealed
short-range strategy's return, and does a 50/50 combination improve the net
risk-adjusted outcome without tuning the combination on 2023+ data?

The two parent studies are fitted and sealed independently on pre-2023 data. This
script only loads their sealed parameters, re-simulates both under the same audited
inputs and accounting, and evaluates predeclared combinations:

- primary: two independent half-accounts (capital split 50/50, no between-sleeve
  rebalancing; each sleeve carries its own internal trading costs),
- daily and monthly rebalanced 50/50 controls with explicit extra rebalancing cost,
- a fixed capital-split grid as sensitivity (0/25/50/75/100% to the short sleeve),
- cost/delay stress at 5/10/20bp and one extra execution session.

All combination rules are fixed by design; no 2023+ outcome selects a weight.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\projects\systematic_trading")
SHORT_VAR = ROOT / "var" / "research" / "gld-lifecycle-20261019-v1"
LONG_VAR = ROOT / "var" / "research" / "gld-longrange-lifecycle-20261019-v1"
OUT_VAR = ROOT / "var" / "research" / "gld-lifecycle-combination-20261019-v1"
OUT_PUB = ROOT / "research" / "gld-lifecycle-combination-20261019-v1"
AUDITED = SHORT_VAR / "inputs" / "gld-audited.npz"
WARMUP = 252
IS_END = "2022-12-30"
OOS_START = "2023-01-01"
FRICTIONS = ((5.0, 0), (10.0, 0), (20.0, 0), (5.0, 1), (10.0, 1))
WEIGHTS_SHORT = (0.0, 0.25, 0.50, 0.75, 1.0)

sys.path.insert(0, str(ROOT / "src"))
from systematic_trading.research import range_lifecycle as rl  # noqa: E402


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False, default=_jsonable),
                          encoding="utf-8")


def _jsonable(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return str(value)
    raise TypeError(type(value))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_data():
    d = np.load(AUDITED, allow_pickle=True)
    return {k: np.asarray(d[k]) for k in ("open", "high", "low", "close", "volume", "days")}


def load_selection(root, kind):
    selection = read_json(Path(root) / "selection.json")["chosen"]
    vector = list(selection["parameter_vector"])
    spec = rl.LONG_SPEC if kind == "long" else rl.SHORT_SPEC
    if len(vector) == len(spec.parameters) - 3:
        vector = vector + [0, 0.0, 0]
    return spec.canonical(vector), selection


def simulate_friction(features, params, cost_bp, delay):
    prepared = rl.prepare(features, params)
    sim = rl.simulate(features, prepared, start=WARMUP, cost_bp=cost_bp, delay=delay, trace=True)
    return sim


def stats_for(nav, start, end):
    return rl.stats(nav, np.ones_like(nav), start, end)


def period_indices(days):
    is_idx = int(np.flatnonzero(days <= np.datetime64(IS_END))[-1])
    oos_idx = int(np.flatnonzero(days >= np.datetime64(OOS_START))[0])
    return dict(IS=(WARMUP, is_idx + 1), OOS=(oos_idx, len(days)),
                FULL=(WARMUP, len(days)))


def metric_dict(nav, periods, weight=None):
    out = {}
    if weight is None:
        weight = np.ones_like(nav)
    for name, (s, e) in periods.items():
        out[name] = rl.stats(nav, weight, s, e)
    return out


def combination_stats(nav_short, nav_long, exposure_short, exposure_long, weight_short,
                      periods):
    nav = weight_short * (nav_short / nav_short[WARMUP]) + (1.0 - weight_short) * (
        nav_long / nav_long[WARMUP])
    combined_exposure = weight_short * exposure_short + (1.0 - weight_short) * exposure_long
    return metric_dict(nav, periods, combined_exposure), nav, combined_exposure


def active_stats(weight_short, weight_long):
    s = weight_short > 0
    l = weight_long > 0
    return dict(
        short_only=int(np.sum(s & ~l)), long_only=int(np.sum(~s & l)),
        both=int(np.sum(s & l)), neither=int(np.sum(~s & ~l)),
        short_active=float(np.mean(s)), long_active=float(np.mean(l)),
        overlap_given_short=float(np.sum(s & l) / max(1, np.sum(s))),
        overlap_given_long=float(np.sum(s & l) / max(1, np.sum(l))))


def correlation_stats(nav_short, nav_long, days, periods, weight_short, weight_long):
    ret_s = np.diff(nav_short) / nav_short[:-1]
    ret_l = np.diff(nav_long) / nav_long[:-1]
    rows = {}
    for name, (s, e) in periods.items():
        a = ret_s[s - 1:e - 1]
        b = ret_l[s - 1:e - 1]
        mask = np.isfinite(a) & np.isfinite(b)
        corr = float(np.corrcoef(a[mask], b[mask])[0, 1]) if mask.sum() > 2 else None
        both = (weight_short[s - 1:e - 1] > 0) & (weight_long[s - 1:e - 1] > 0)
        corr_both = None
        if both.sum() > 2:
            corr_both = float(np.corrcoef(a[both], b[both])[0, 1])
        rows[name] = dict(correlation=corr, correlation_when_both_active=corr_both,
                          n_sessions=int(mask.sum()),
                          exposure_correlation=float(np.corrcoef(
                              weight_short[s - 1:e - 1], weight_long[s - 1:e - 1])[0, 1]))
    return rows


def rolling_correlation(nav_short, nav_long, window=252):
    ret_s = pd.Series(np.r_[np.nan, np.diff(nav_short) / nav_short[:-1]])
    ret_l = pd.Series(np.r_[np.nan, np.diff(nav_long) / nav_long[:-1]])
    return ret_s.rolling(window).corr(ret_l)


def rebalanced_combination(nav_short, nav_long, days, freq, cost_bp, start=WARMUP):
    """Half-capital sleeves rebalanced to 50/50 at the chosen frequency.

    Each sleeve is marked with its own parent NAV (which already contains the
    parent's internal trading costs). Rebalancing trades between sleeves cost
    ``2*cost_bp`` of the traded amount. Frequencies: daily or month-start.
    """
    cost = 2.0 * cost_bp / 10000.0
    n = len(nav_short)
    value_short = 0.5
    value_long = 0.5
    combined = np.full(n, np.nan)
    combined[start] = 1.0
    previous_month = pd.Timestamp(str(days[start])).month
    for t in range(start + 1, n):
        value_short *= nav_short[t] / nav_short[t - 1]
        value_long *= nav_long[t] / nav_long[t - 1]
        month = pd.Timestamp(str(days[t])).month
        rebalance = freq == "daily" or (freq == "monthly" and month != previous_month)
        previous_month = month
        if rebalance:
            total = value_short + value_long
            target = 0.5 * total
            trade = target - value_short
            fee = cost * abs(trade)
            value_short = target - fee
            value_long = total - value_short
        combined[t] = value_short + value_long
    return combined


def main(stage="all"):
    OUT_VAR.mkdir(parents=True, exist_ok=True)
    OUT_PUB.mkdir(parents=True, exist_ok=True)
    data = load_data()
    days = pd.to_datetime(data["days"]).to_numpy()
    short_params, short_selection = load_selection(SHORT_VAR, "short")
    long_params, long_selection = load_selection(LONG_VAR, "long")
    features_short = rl.Features.build(data, rl.SHORT_SPEC)
    features_long = rl.Features.build(data, rl.LONG_SPEC)
    periods = period_indices(days)
    # Parent strategies at every friction.
    parents = {}
    for cost, delay in FRICTIONS:
        sim_s = simulate_friction(features_short, short_params, cost, delay)
        sim_l = simulate_friction(features_long, long_params, cost, delay)
        parents[(cost, delay)] = dict(short=sim_s, long=sim_l)
    base = parents[(5.0, 0)]
    nav_s = base["short"]["nav"]
    nav_l = base["long"]["nav"]
    weight_s = base["short"]["weight"]
    weight_l = base["long"]["weight"]
    # Correlations and overlap (independent sleeves).
    corr_rows = correlation_stats(nav_s, nav_l, days, periods, weight_s, weight_l)
    overlap = {name: active_stats(weight_s[s:e], weight_l[s:e])
               for name, (s, e) in periods.items()}
    roll = rolling_correlation(nav_s, nav_l)
    # Combination grid, independent sleeves.
    grid_rows = []
    for w in WEIGHTS_SHORT:
        metrics, _, _ = combination_stats(nav_s, nav_l, weight_s, weight_l, w, periods)
        grid_rows.append(dict(weight_short=w, **metrics))
    primary_metrics, primary_nav, combined_weight = combination_stats(
        nav_s, nav_l, weight_s, weight_l, 0.5, periods)
    daily_rebalanced = rebalanced_combination(nav_s, nav_l, days, "daily", 5.0)
    monthly_rebalanced = rebalanced_combination(nav_s, nav_l, days, "monthly", 5.0)
    controls = dict(
        short_only=metric_dict(nav_s, periods),
        long_only=metric_dict(nav_l, periods),
        equal_weight_independent=primary_metrics,
        equal_weight_daily_rebalanced=metric_dict(daily_rebalanced, periods, combined_weight),
        equal_weight_monthly_rebalanced=metric_dict(monthly_rebalanced, periods, combined_weight),
        buyhold=metric_dict(rl.buy_hold(features_short, WARMUP, cost_bp=5.0)["nav"], periods),
    )
    # Friction stress for the equal-weight independent combination.
    friction_rows = []
    for cost, delay in FRICTIONS:
        sim_s = parents[(cost, delay)]["short"]
        sim_l = parents[(cost, delay)]["long"]
        nav_sf = sim_s["nav"]
        nav_lf = sim_l["nav"]
        metrics, _, _ = combination_stats(nav_sf, nav_lf, sim_s["weight"], sim_l["weight"],
                                          0.5, periods)
        row = dict(cost_bp=cost, delay=delay,
                   short=metric_dict(nav_sf, periods), long=metric_dict(nav_lf, periods),
                   combined=metrics)
        friction_rows.append(row)
    # Long study performance evidence in the same accounting.
    long_evidence = dict(
        selected=long_selection.get("decoded"),
        parameter_vector=long_params.tolist(),
        periods=metric_dict(nav_l, periods, weight_l),
        trade_stats=_trade_stats(base["long"]["episodes"]),
        episodes=_episode_rows(base["long"]["episodes"], days),
    )
    short_evidence = dict(
        selected=short_selection.get("decoded"),
        parameter_vector=short_params.tolist(),
        periods=metric_dict(nav_s, periods, weight_s),
        trade_stats=_trade_stats(base["short"]["episodes"]),
    )
    payload = dict(
        identity="gld-lifecycle-combination-20261019-v1",
        question=("Is the long-range GLD lifecycle return sufficiently uncorrelated with "
                  "the sealed short-range lifecycle return to combine the two sleeves?"),
        authority="Research only; no monitoring, promotion, funding or broker action.",
        design=dict(
            parents=dict(short=str(SHORT_VAR), long=str(LONG_VAR),
                         short_selection_sha256=sha256(SHORT_VAR / "selection.json"),
                         long_selection_sha256=sha256(LONG_VAR / "selection.json")),
            primary_combination="independent half-accounts: NAV = 0.5*NAV_short/NAV_short[0] "
                                "+ 0.5*NAV_long/NAV_long[0]; each parent keeps its own cash and "
                                "internal trading costs, no between-sleeve rebalancing.",
            controls=["short only", "long only", "daily-rebalanced 50/50 with 2x5bp x traded "
                      "amount", "monthly-rebalanced 50/50", "buy-and-hold"],
            weight_grid=[float(w) for w in WEIGHTS_SHORT],
            frictions=[dict(cost_bp=c, delay=d) for c, d in FRICTIONS],
            correlation="Pearson correlation of daily NAV returns; exposure correlation of "
                        "daily weights; overlap counts of active sleeves.",
            no_oos_tuning="weights, controls and stress cases are fixed by design; 2023+ outcomes "
                          "are not used to choose a combination.",
        ),
        chronology=dict(warmup=WARMUP, is_end=IS_END, oos_start=OOS_START,
                        first_session=str(days[0]), last_session=str(days[-1])),
        correlations=corr_rows,
        overlap=overlap,
        controls=controls,
        weight_grid=grid_rows,
        frictions=friction_rows,
        long_strategy=long_evidence,
        short_strategy=short_evidence,
        daily=dict(days=days.astype("datetime64[D]").astype(str).tolist(),
                   series_file="combined-daily.csv"),
        limitations=[
            "Both strategies trade the same GLD ETF, so correlation cannot be diversified away "
            "by construction; the question is whether different horizons/time-in-market reduce it "
            "enough to improve the sleeve trade-off.",
            "The 2023+ interval has been inspected; OOS results are development retests.",
            "Parent NAVs are close/next-open decisions with constant costs; cash earns zero.",
        ],
    )
    write_json(OUT_VAR / "combination.json", payload)
    # Compact daily series and long-strategy artifacts for the public folder.
    pd.DataFrame(dict(date=payload["daily"]["days"], nav_short=nav_s, nav_long=nav_l,
                      weight_short=weight_s, weight_long=weight_l, nav_combined=primary_nav,
                      rolling_corr=roll.to_numpy())).to_csv(
        OUT_VAR / "combined-daily.csv", index=False, float_format="%.6f")
    pd.DataFrame(long_evidence["episodes"]).to_csv(OUT_VAR / "long-episodes.csv", index=False)
    _long_ledger(features_long, long_params, base["long"]).to_csv(
        OUT_VAR / "long-daily-ledger.csv", index=False, float_format="%.6f")
    print(json.dumps(dict(
        correlations={k: {kk: (None if vv is None else round(vv, 3)) for kk, vv in v.items()}
                      for k, v in corr_rows.items()},
        overlap=overlap,
        short=short_evidence["periods"]["OOS"],
        long=long_evidence["periods"]["OOS"],
        combined=primary_metrics["OOS"],
    ), indent=1), flush=True)
    return payload


def _trade_stats(episodes):
    closed = [e for e in episodes if e["exit_signal"] is not None]
    if not closed:
        return dict(n=0)
    ret = np.array([e["exit_price"] / e["entry"] - 1.0 for e in closed])
    holds = np.array([e["hold_sessions"] for e in closed])
    return dict(n=len(closed), win_rate=float((ret > 0).mean()), mean_gross=float(ret.mean()),
                median_gross=float(np.median(ret)), mean_hold=float(holds.mean()),
                median_hold=float(np.median(holds)), max_hold=int(holds.max()),
                exposure=None)


def _episode_rows(episodes, days):
    rows = []
    for e in episodes:
        rows.append(dict(crossing=str(days[e["crossing"]]),
                         confirmation=str(days[e["confirmation"]]),
                         entry=str(days[e["entry_index"]]),
                         entry_price=float(e["entry"]),
                         exit=str(days[e["exit_index"]]) if e["exit_index"] is not None else None,
                         exit_price=float(e["exit_price"]) if e["exit_price"] is not None else None,
                         exit_reason={1: "stop", 3: "time"}.get(e["exit_reason"],
                                                                 "open at end"),
                         hold_sessions=int(e["hold_sessions"]),
                         gross_return=(float(e["exit_price"] / e["entry"] - 1.0)
                                       if e["exit_price"] is not None else None)))
    return rows


def _long_ledger(features, params, sim):
    prepared = rl.prepare(features, params)
    return pd.DataFrame({
        "date": features.days.astype("datetime64[D]").astype(str),
        "close": features.close, "range_lookback": prepared["L"],
        "range_upper": prepared["upper"], "range_lower": prepared["lower"],
        "range_width_log": prepared["width"], "range_drift": prepared["drift"],
        "trigger": prepared["boundary"], "atr": prepared["atr"],
        "state": sim["state"], "trigger_level": sim["level"], "entry_price": sim["entry"],
        "stop": sim["stop"], "initial_stop": sim["stop_initial"],
        "band_stop": sim["stop_band"], "trail_stop": sim["stop_trail"],
        "peak": sim["peak"], "drawdown_from_peak": sim["drawdown"],
        "heated": sim["heat"], "hold_sessions": sim["hold"], "exit_reason": sim["reason"],
        "nav": sim["nav"], "weight": sim["weight"],
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", nargs="?", default="all", choices=["all"])
    args = parser.parse_args()
    main(args.stage)
