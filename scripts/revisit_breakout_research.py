"""Predeclared implementation audit and unfitted full-pool breakout component study."""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from retest_fr25_lifecycle_review import digest, gate, metrics, write  # noqa: E402
from systematic_trading.research import breakout_revisit as br  # noqa: E402
from systematic_trading.research import fr25_lifecycle_conditional as frozen  # noqa: E402
from systematic_trading.research import range_lifecycle as old  # noqa: E402

OUTPUT = ROOT / "research/breakout-revisit-20261021-v1"
WORK = ROOT / "var/research/breakout-revisit-20261021-v1"
PRIMARY = "break63_trail6_dynamic"
FRICTIONS = [(c, d) for c in (5, 10, 20) for d in (0, 1)]


def protocol():
    return dict(identity=OUTPUT.name, version=br.VERSION, primary=PRIMARY,
        question="Do corrected breakout decisions and trailing exits add net portfolio value beyond momentum selection and fixed timing?",
        expected_failure="Fitted lifecycle may be persistently long, stops may whipsaw, and daily replacement may consume the apparent ranking edge.",
        data=frozen.verified_input_provenance(),
        code_hashes={p: digest(ROOT / p) for p in (
            "scripts/revisit_breakout_research.py", "scripts/retest_fr25_lifecycle_review.py",
            "src/systematic_trading/research/breakout_revisit.py",
            "src/systematic_trading/research/range_lifecycle.py",
            "src/systematic_trading/research/fr25_lifecycle_conditional.py",
            "src/systematic_trading/backtest/engine.py", "src/systematic_trading/backtest/accounting.py",
            "src/systematic_trading/portfolio/proposals.py")},
        pool="Full 52 supported ETFs. BIL participates as parking only; URTH benchmark only. No newly downloaded or uncertified instruments.",
        entry="63-session prior highest adjusted close, one confirming close. 126-session sensitivity. No volume shortcut or per-asset fit.",
        exit="Initial stop 3 ATR20 below next-open virtual entry; ratcheting highest CLOSE minus 6 current ATR20; entry close included. 3 ATR trail sensitivity; 20-close lower channel and 63-session holding ablations retain initial 3 ATR risk stop but disable trail.",
        selection="Positive 126-session log momentum divided by 63-session daily-return volatility * sqrt(126). Six fixed 98%/6 slots; unused slots BIL; residual 2% cash. Rank incumbents survive through rank 8; replace those below 8 from highest eligible scores, alphabetical tie-break. Sticky no-replacement ablation.",
        clocks="Dynamic membership changes + month-end anchors. Monthly defers entries, exits and replacements to month-end. Hybrid daily exits but month-end admissions/replacements. Adopted L1 including cash >1e-10 triggers changes; no drift rebalancing between anchors.",
        signal_execution="Corrected desired state known at close; actual portfolio next-open or +1 session. Asset regimes use a zero-delay virtual lifecycle, not actual portfolio stop orders. Delayed portfolio orders use frozen decisions and original reference closes. Asset-level delay audit separately changes both entry and exit clocks.",
        legacy_comparison="Same frozen pre-2023 fitted SHORT parameters; old held state, corrected held state, corrected close-decision state under the SAME new selector. This separates implementation from selection; does not reproduce old Rule A portfolio.",
        scenarios=["legacy_held_dynamic", "corrected_held_dynamic", "corrected_decision_dynamic",
                   PRIMARY, "break63_trail6_monthly", "break63_trail6_hybrid", "break63_trail6_sticky",
                   "break63_trail3_dynamic", "break126_trail6_dynamic", "break63_channel_dynamic",
                   "break63_channel_monthly", "break63_hold_dynamic", "break63_hold_monthly",
                   "momentum_dynamic", "momentum_monthly", "equal52", "URTH", "FR25"],
        periods=dict(late="2023-01-03 through 2026-10-12: six frictions for all 18 scenarios",
                     early="2019-01-02 through 2022-12-30: 5bp with 0/1 delay for 14 unfitted scenarios; no fitted lifecycle and no unavailable FR25"),
        frictions=[list(v) for v in FRICTIONS], metrics="Initial cash anchor; CAGR, Sharpe, RMS downside Sortino, max DD, Calmar, actual fill turnover and fees; calendar-year rows and full-pool P&L attribution for primary.",
        gate="Primary versus FR25: higher Sharpe/Sortino/Calmar, no worse DD, CAGR loss <=1pp at all six frictions. Component usefulness additionally requires higher Sharpe with same return/DD guards versus matched momentum and holding ablations in both chronological periods at 5bp with 0/1 delay. No replacement winner from sensitivities.",
        limitations=["Retrospective supported cohort; no historical membership/vintage certification or untouched holdout.",
                     "2023 onward was inspected in prior research; 2019-2022 is a chronological diagnostic, not unseen validation. No parameters fitted in this study.",
                     "USD adjusted units and audited raw volume. No CNH/FX claim, intraday fill, TWAP, liquidity capacity, partial-order or gap-risk certification.",
                     "All monetary accounting uses shared app engine. Native checks validate accounting, not signal truth or statistical significance.",
                     "Standalone research module only: no registration, promotion, monitoring, allocation, broker or service changes."],
        no_selection="Freeze all candidates before evaluation; no post-result tuning. Larger-pool follow-up must pass separate audited publication/admission.")


def prepare():
    value = protocol()
    path = OUTPUT / "protocol.json"
    if path.exists() and json.loads(path.read_text()) != value:
        raise ValueError("Changed protocol: new study identity required")
    write(path, value)
    print("Frozen", digest(path), flush=True)


def signals(panel):
    n, m = panel["close"].shape
    keys = ["legacy_held", "corrected_held", "corrected_decision", "break63_trail6",
            "break63_trail3", "break126_trail6", "break63_channel", "break63_hold"]
    active = {k: np.zeros((n, m), bool) for k in keys}
    scores = np.zeros((n, m))
    audit = []
    params = frozen.frozen_parameters()["sleeve"]["short_parameters"]
    for j, symbol in enumerate(panel["symbols"]):
        with np.load(ROOT / "var/research/range-breakout-20261018-v2/assets" / f"{symbol}.npz", allow_pickle=False) as a:
            data = {k: a[k].copy() for k in ("days", "open", "high", "low", "close", "volume")}
        f = old.Features.build(data)
        index = {str(day): t for t, day in enumerate(f.days)}
        ix = [index[str(day)] for day in panel["days"]]
        prepared = old.prepare(f, params[symbol])
        legacy = old.simulate(f, prepared, start=252, trace=True)
        corrected = br.simulate(f, prepared, start=252)
        active["legacy_held"][:, j] = legacy["state"][ix] == old.STATE_LONG
        active["corrected_held"][:, j] = corrected["held"][ix]
        active["corrected_decision"][:, j] = corrected["desired"][ix]
        scores[:, j] = br.momentum_score(f.close)[ix, 0]
        row = dict(symbol=str(symbol), confirm_sessions=int(prepared["parameters"][6]),
                   legacy_episodes=len(legacy["episodes"]), corrected_episodes=len(corrected["episodes"]),
                   legacy_active=float(np.mean(active["legacy_held"][:, j])),
                   corrected_active=float(np.mean(active["corrected_decision"][:, j])),
                   entry_close_exits=sum(e.get("exit_signal") == e["entry_index"] for e in corrected["episodes"]))
        # Direct delay test uses same asset engine's decisions/fills, not portfolio lag.
        old_delay = old.simulate(f, prepared, start=252, delay=1)
        new_delay = br.simulate(f, prepared, start=252, delay=1)
        row["legacy_exit_delay_lengths"] = sorted({e["exit_index"] - e["exit_signal"] for e in old_delay["episodes"] if e.get("exit_index") is not None})
        row["corrected_exit_delay_lengths"] = sorted({e["exit_index"] - e["exit_signal"] for e in new_delay["episodes"] if e.get("exit_index") is not None})
        audit.append(row)
        for name, lookback, trail, exit_rule in (
                ("break63_trail6", 63, 6, "trail"), ("break63_trail3", 63, 3, "trail"),
                ("break126_trail6", 126, 6, "trail"), ("break63_channel", 63, 6, "channel"),
                ("break63_hold", 63, 6, "hold")):
            sim = br.simulate(f, br.simple_prepared(f, lookback, trail, exit_rule))
            active[name][:, j] = sim["desired"][ix]
        if (j + 1) % 10 == 0:
            print("Signals", j + 1, "/", m, flush=True)
    active["momentum"] = np.ones((n, m), bool)
    return active, scores, audit


def monthly_indices(panel, start):
    from systematic_trading.live.trading_calendar import next_us_trading_day
    anchor = int(np.flatnonzero(panel["days"] < start)[-1])
    return np.array([anchor] + [t for t in range(anchor + 1, len(panel["days"]))
        if next_us_trading_day(date.fromisoformat(str(panel["days"][t]))).month != int(str(panel["days"][t])[5:7])])


def mappings(panel, active, scores, start, include_fitted):
    monthly = monthly_indices(panel, start)
    result = {}
    for name in protocol_scenarios():
        if not include_fitted and (name.startswith(("legacy", "corrected")) or name == "FR25"):
            continue
        if name in {"FR25", "equal52", "URTH"}:
            w = np.zeros((len(panel["days"]), len(panel["symbols"]) + 1))
            indices = monthly
            if name == "FR25":
                w[:, :-1] = panel["fr25"]
            elif name == "equal52":
                w[monthly, :-1] = .98 / len(panel["symbols"])
            else:
                w[monthly[0], -1] = .98
                indices = monthly[:1]
            result[name] = w, indices, None
        else:
            key, clock = name.rsplit("_", 1)
            result[name] = br.select_targets(panel, active[key], scores, monthly,
                clock="dynamic" if clock == "sticky" else clock, replace=clock != "sticky")
    return result


def protocol_scenarios():
    return json.loads((OUTPUT / "protocol.json").read_text())["scenarios"]


def attribution(replay, fills):
    q = {s: 0 for s in replay.symbols}
    pnl = {s: 0. for s in replay.symbols}
    fees = pnl.copy()
    by_day = {}
    for f in fills:
        by_day.setdefault(f["date"], []).append(f)
    previous = {s: float(replay.reference[replay.days[0]][s]) for s in q}
    for day in replay.days:
        prices = {s: float(replay.close[day][s]) for s in q}
        for s in q:
            pnl[s] += q[s] * (prices[s] - previous[s])
        for f in by_day.get(str(day), []):
            s, quantity, fee = f["symbol"], f["quantity"], float(f["fee"])
            pnl[s] += quantity * (prices[s] - float(f["price"])) - fee
            fees[s] += fee
            q[s] += quantity
        previous = prices
    return [dict(symbol=s, net_pnl_usd=pnl[s], fees_usd=fees[s], final_units=q[s]) for s in q]


def run():
    declared = json.loads((OUTPUT / "protocol.json").read_text())
    if declared != protocol() or (OUTPUT / "results.json").exists():
        raise ValueError("Changed inputs/protocol or completed study")
    panel = frozen._load_panel()
    active, scores, audit = signals(panel)
    write(OUTPUT / "implementation-audit.json", audit)
    recipe = json.loads(frozen.RECIPE_PATH.read_text())
    rows, paths = [], {}
    WORK.mkdir(parents=True, exist_ok=True)
    for period, start, end, frictions in (
            ("late", "2023-01-03", "2026-10-12", FRICTIONS),
            ("early", "2019-01-02", "2022-12-30", [(5, 0), (5, 1)])):
        count = int(np.sum(panel["days"] <= end))
        a = {k: v if k == "symbols" else v[:count] for k, v in panel.items()}
        replay = frozen._Replay(a, recipe, start)
        dates = [str(a["days"][replay.indices[0] - 1]), *map(str, replay.days)]
        scenarios = mappings(a, {k: v[:count] for k, v in active.items()}, scores[:count], start, period == "late")
        if period == "late":
            np.savez_compressed(WORK / "mappings.npz", **{k + "_weights": v[0] for k, v in scenarios.items()},
                                **{k + "_indices": v[1] for k, v in scenarios.items()})
        for name, (weights, indices, theoretical) in scenarios.items():
            for cost, delay in frictions:
                result, fills = replay.run_result(weights, indices, cost, delay)
                payload = frozen.report_payload(replay, result, fills)
                nav = np.array([float(r["nav_cnh"]) for r in payload["nav_series"]])
                row = dict(period=period, scenario=name, cost_bp=cost, delay=delay,
                    **metrics(nav, dates, fills), rebalances=len(result.proposals), fills=len(fills), yearly={})
                for year in sorted({d[:4] for d in dates[1:]}):
                    ix = [t for t, d in enumerate(dates) if d.startswith(year) and t > 0]
                    lo, hi = ix[0] - 1, ix[-1] + 1
                    row["yearly"][year] = metrics(nav[lo:hi], dates[lo:hi], fills)
                if theoretical is not None:
                    row["mean_target_bill"] = float(np.mean(theoretical[replay.indices, list(a["symbols"]).index("BIL")]))
                rows.append(row)
                key = f"{period}_{name}_c{cost}d{delay}"
                paths[key] = nav
                if period == "late" and cost == 5 and delay == 0 and name in {PRIMARY, "FR25", "URTH", "momentum_monthly"}:
                    write(WORK / (name + "-calculation.json"), dict(payload, accounting_currency="USD",
                          latest_targets=[] if theoretical is None else [dict(symbol=s, target_weight=str(w))
                              for s, w in zip(replay.symbols, theoretical[-1], strict=True) if w > 0]))
                if name == PRIMARY and cost == 5 and delay == 0:
                    contributions = attribution(replay, fills)
                    error = abs(sum(c["net_pnl_usd"] for c in contributions) - (nav[-1] - nav[0]))
                    if error > .02:
                        raise ValueError(f"Attribution does not reconcile: {error}")
                    write(OUTPUT / f"{period}-attribution.json", dict(rows=contributions, reconciliation_error=error))
                print(f"{key}: {row['cagr']:.2%} / {row['sharpe']:.3f} / {row['max_drawdown']:.2%}", flush=True)
        paths[period + "_dates"] = np.array(dates)
    gates, components = [], []
    def find(period, name, cost, delay):
        return next(r for r in rows if (r["period"], r["scenario"], r["cost_bp"], r["delay"]) == (period, name, cost, delay))
    for cost, delay in FRICTIONS:
        gates.append(dict(cost_bp=cost, delay=delay, **gate(find("late", PRIMARY, cost, delay), find("late", "FR25", cost, delay))))
    for period in ("early", "late"):
        for delay in (0, 1):
            for control in ("momentum_dynamic", "break63_hold_dynamic"):
                candidate, base = find(period, PRIMARY, 5, delay), find(period, control, 5, delay)
                comparisons = dict(sharpe=candidate["sharpe"] > base["sharpe"],
                    return_guard=candidate["cagr"] >= base["cagr"] - .01,
                    drawdown=candidate["max_drawdown"] >= base["max_drawdown"])
                components.append(dict(period=period, delay=delay, control=control, **comparisons, passed=all(comparisons.values())))
    if declared != protocol():
        raise ValueError("Study inputs changed during run")
    write(OUTPUT / "results.json", dict(protocol_sha256=digest(OUTPUT / "protocol.json"), results=rows,
        gates=gates, components=components, decision="research_gate_pass" if all(g["passed"] for g in gates + components) else "do_not_promote"))
    np.savez_compressed(WORK / "nav.npz", **paths)
    print("Complete", len(rows), "replays", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("prepare", "run"))
    {"prepare": prepare, "run": run}[parser.parse_args().stage]()
