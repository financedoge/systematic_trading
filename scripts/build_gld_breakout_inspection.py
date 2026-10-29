"""Visual drilldown of the original GLD fits, with audited corrected execution.

No fitting or strategy mutation. The stop trace is reconstructed independently
from episode records and must match every held close of the pinned simulator.
"""
from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
import fit_breakout_signal_audit as audit  # noqa: E402
from systematic_trading.research import breakout_revisit as br  # noqa: E402
from systematic_trading.research import range_lifecycle as rl  # noqa: E402

OUT = ROOT / "research/gld-breakout-inspection-20261021-v1"
TEMPLATE = ROOT / "scripts/assets/gld-breakout-inspection.html"
TRACE_FIELDS = ("initial", "band", "floor", "activation", "peak", "trail", "stop")


def clean(value):
    """JSON display precision only; validation always uses unrounded arrays."""
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return round(float(value), 7) if np.isfinite(value) else None
    return value


def range_box(f, prepared, crossing):
    """The prior close window, frozen as of its crossing; never includes it."""
    t, p, spec = int(crossing), prepared["parameters"], f.spec
    length, tail = int(prepared["L"][t]), spec.tails[int(p[1])]
    if not length:
        raise ValueError("Crossing has no qualifying prior range")
    candidates = []
    for window in spec.windows:
        width = f.width[tail][window][t]
        drift = f.drift[window][t]
        vol = f.shortvol[window][t] / f.longvol[window][t]
        available = bool(np.isfinite([width, drift, vol]).all() and width > 0)
        candidates.append(dict(length=window, width=width, drift_ratio=drift / width if available else None,
            vol_ratio=vol, qualifies=bool(available and width <= p[0] and drift <= p[2] * width and vol <= p[3])))
    return dict(start=t - length, end=t - 1, known=t, length=length,
        upper=float(prepared["upper"][t]), lower=float(prepared["lower"][t]),
        trigger=float(prepared["boundary"][t]), width=float(prepared["width"][t]),
        drift_ratio=float(prepared["drift"][t] / prepared["width"][t]),
        vol_ratio=float(prepared["vol_ratio"][t]), candidates=candidates)


def stop_trace(f, prepared, sim):
    """Reconstruct risk components, preserving the binding queued-order state."""
    n, p = len(f.close), prepared["parameters"]
    trace = {name: np.full(n, np.nan) for name in TRACE_FIELDS}
    trace.update(armed=np.zeros(n, bool), heated=np.zeros(n, bool), episode=np.full(n, -1, int))
    episodes = []
    for ident, original in enumerate(sim["episodes"]):
        e = dict(original)
        if e["reentry"]:
            raise ValueError("This inspection requires original GLD fits without continuation re-entry")
        start, end = e["entry_index"], e["exit_index"] or n
        initial = e["entry"] - p[10] * e["atr"]
        band = e["u"] - p[11] * e["atr"] if p[11] >= 0 else np.nan
        floor = max(initial, band) if np.isfinite(band) else initial
        activation = e["entry"] + p[15] * e["atr"]
        stop, peak, heated, candidate, armed = floor, float(f.close[start]), False, np.nan, False
        first_arm, first_heat = None, None
        for t in range(start, end):
            # An exit decision is binding; later closes while awaiting its fill
            # do not update the trail or peak (relevant to delayed replay tests).
            if t <= e.get("exit_signal", n):
                peak = max(peak, float(f.close[t]))
                atr = prepared["atr"][t]
                if (p[16] and np.isfinite(atr) and f.close[t] >= e["u"] + p[17] * e["atr"]
                        and f.volume[t] >= p[18] * prepared["volmed"][t] and f.close[t] >= peak - p[19] * atr):
                    heated = True
                    first_heat = t if first_heat is None else first_heat
                if peak >= activation and np.isfinite(atr):
                    armed = True
                    first_arm = t if first_arm is None else first_arm
                    mult = p[20] if heated else 1.
                    candidate = peak - p[13] * mult * atr if p[12] == 0 else peak * (1 - p[14] * mult)
                    stop = max(stop, candidate)
            for key, value in dict(initial=initial, band=band, floor=floor, activation=activation,
                                   peak=peak, trail=candidate, stop=stop).items():
                trace[key][t] = value
            trace["armed"][t], trace["heated"][t], trace["episode"][t] = armed, heated, ident
        e.update(id=ident, box=range_box(f, prepared, e["crossing"]), first_arm=first_arm,
            first_heat=first_heat, initial=initial, band=band, floor=floor, activation=activation,
            confirmation_count=int(e["count"]), confirmation_volume_ratio=float(f.volume[e["confirmation"]] / prepared["volmed"][e["confirmation"]]))
        e["net_trade_return"] = (e["exit_price"] / e["entry"] * (1 - .0005) / (1 + .0005) - 1
                                  if e["exit_index"] is not None else None)
        episodes.append(e)
    np.testing.assert_array_equal(np.isfinite(trace["stop"]), sim["held"])
    np.testing.assert_allclose(trace["stop"], sim["stop"], rtol=0, atol=1e-12, equal_nan=True)
    return trace, episodes


def build_domain(data, spec, parameters):
    f = rl.Features.build(data, spec)
    prep = rl.prepare(f, parameters)
    sim = br.simulate(f, prep, cost_bp=5., delay=0)
    trace, episodes = stop_trace(f, prep, sim)
    accepted = {e["crossing"]: e["id"] for e in episodes}
    crossings = []
    for t in np.flatnonzero(prep["cross"]):
        t = int(t)
        if t < 252:
            status = "Warm-up; no orders permitted"
        elif t in accepted:
            status = "Accepted breakout; later confirmed and bought"
        elif sim["held"][t]:
            status = "Raw crossing while already holding; no additional entry"
        elif any(e["exit_index"] is not None and e["exit_index"] <= t < e["exit_index"] + int(prep["parameters"][23]) for e in episodes):
            status = "Raw crossing during cooldown; no entry"
        else:
            status = "Raw crossing without a completed entry; confirmation / pending-order state applies"
        crossings.append(dict(day=t, episode=accepted.get(t), status=status, box=range_box(f, prep, t)))
    # Crossings use prior-day ATR; initial risk uses confirmation-day ATR.
    for e in episodes:
        b, t = e["box"], e["crossing"]
        expected = np.exp(np.quantile(np.log(f.close[b["start"]:t]), [spec.tails[int(prep["parameters"][1])], 1 - spec.tails[int(prep["parameters"][1])]]))
        np.testing.assert_allclose([b["lower"], b["upper"]], expected, rtol=1e-12)
        assert b["end"] < t <= e["confirmation"] < e["entry_index"]
        assert e["entry_index"] == e["confirmation"] + 1
        assert e["entry"] == f.open[e["entry_index"]]
        assert e["trigger"] == prep["boundary"][t]
        if e["exit_index"] is not None:
            assert e["exit_index"] == e["exit_signal"] + 1
            assert e["exit_price"] == f.open[e["exit_index"]]
            if e["exit_reason"] == "stop":
                assert f.close[e["exit_signal"]] < trace["stop"][e["exit_signal"]]
    decoded = spec.describe(parameters)
    result = dict(recipe=decoded, trace=trace, episodes=episodes, crossings=crossings,
        ranges={k: prep[k] for k in ("L", "upper", "lower", "boundary", "width", "drift", "vol_ratio")},
        atr=prep["atr"], volume_ratio=f.volume / prep["volmed"], held=sim["held"], desired=sim["desired"])
    check = dict(episodes=len(episodes), closed=sum(e["exit_index"] is not None for e in episodes),
        held_sessions=int(sim["held"].sum()), raw_crossings=len(crossings), stop_max_absolute_error=float(np.nanmax(np.abs(trace["stop"] - sim["stop"]))),
        prior_range_quantiles_checked=True, next_open_fills_checked=True, original_parameters=parameters)
    return result, check


def static_plot(payload):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    import matplotlib.dates as dates

    day = np.array(payload["prices"]["days"], dtype="datetime64[D]")
    px = payload["prices"]
    fig, axes = plt.subplots(2, 1, figsize=(15, 10.5), layout="constrained")
    for ax, name in zip(axes, ("short", "long"), strict=True):
        d = payload["domains"][name]
        # Default examples are the first new entries after the pre-2023 fit.
        e = next(e for e in d["episodes"] if day[e["entry_index"]] >= np.datetime64("2023-01-01"))
        b = e["box"]
        start, end = max(0, b["start"] - 12), min(len(day) - 1, (e["exit_index"] or len(day) - 1) + 14)
        ix = np.arange(start, end + 1)
        ax.plot(day[ix], np.array(px["close"])[ix], color="#27364b", lw=1.3, label="GLD close")
        x0, x1 = dates.date2num(day[b["start"]]), dates.date2num(day[b["end"]])
        ax.add_patch(Rectangle((x0, b["lower"]), x1 - x0, b["upper"] - b["lower"], facecolor="#d9eaf9", edgecolor="#3980b4", lw=1, alpha=.65))
        ax.text(day[b["start"]], b["upper"], f" {b['length']}-session prior range · 5–95% of closes", color="#245a80", fontsize=9, va="bottom")
        ax.hlines(e["trigger"], day[e["crossing"]], day[e["exit_index"] or len(day) - 1], colors="#c58412", linestyles="--", lw=1, label="Frozen breakout trigger")
        trace = d["trace"]
        for key, color, style, label in [("stop", "#b93250", "-", "Effective closing exit level"),
            ("activation", "#9673c1", "--", "Trail activation (not a fixed TP)")]:
            values = np.array([np.nan if v is None else v for v in trace[key]], float)
            values[np.array(trace["episode"]) != e["id"]] = np.nan
            ax.plot(day[ix], values[ix], color=color, ls=style, lw=1.5 if key == "stop" else 1, label=label)
        markers = [(e["crossing"], px["close"][e["crossing"]], "D", "#c58412", "Breakout", (-20, 34)),
            (e["confirmation"], px["close"][e["confirmation"]], "o", "#148f92", "Confirm / buy decision", (-90, 58)),
            (e["entry_index"], e["entry"], "^", "#16844f", "Buy at next open", (10, -45))]
        if e["exit_index"] is not None:
            markers += [(e["exit_signal"], px["close"][e["exit_signal"]], "x", "#bd3650", "Exit decision", (-105, -45)),
                (e["exit_index"], e["exit_price"], "v", "#bd3650", "Sell at next open", ((-175, 5) if name == "long" else (8, 35)))]
        for t, price, marker, color, label, offset in markers:
            ax.scatter(day[t], price, marker=marker, s=75, facecolors="none" if marker == "o" else color,
                       edgecolors=color if marker != "x" else None, zorder=6)
            ax.annotate(f"{label}\n{day[t]} · ${price:.2f}", (day[t], price), xytext=offset,
                textcoords="offset points", fontsize=8, color=color,
                arrowprops=dict(arrowstyle="-", color=color, lw=.7))
        if e["first_arm"] is not None:
            t = e["first_arm"]
            ax.axvline(day[t], color="#9673c1", alpha=.4, lw=1)
            ax.text(day[t], ax.get_ylim()[0], " Trail armed", color="#805baf", fontsize=8, va="bottom")
        ax.set_title(f"Original GLD {name}-range fit · first post-2022 entry · corrected execution", loc="left", fontsize=12, pad=14)
        ax.set_ylabel("GLD price (USD)")
        ax.set_xlim(day[start], day[end])
        locator = dates.WeekdayLocator(byweekday=dates.MO, interval=2) if name == "short" else dates.MonthLocator(interval=6)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(dates.DateFormatter("%d %b" if name == "short" else "%Y-%m"))
        ax.grid(alpha=.15)
        ax.legend(loc="upper left", fontsize=8, ncol=2)
    fig.suptitle("GLD: range → breakout → confirmation → buy → dynamic exit", fontsize=16, x=.5)
    fig.savefig(OUT / "gld-inspection.png", dpi=160)
    plt.close(fig)


def main():
    declared = json.loads((audit.OUTPUT / "protocol.json").read_text())
    if audit.protocol() != declared:
        raise ValueError("Pinned audited inputs, recipes or corrected engine changed")
    data = audit.load_asset("GLD")
    payload = dict(prices={k: (v.astype(str).tolist() if k == "days" else v) for k, v in data.items()}, domains={})
    checks = {}
    for kind, spec in (("short", rl.SHORT_SPEC), ("long", rl.LONG_SPEC)):
        payload["domains"][kind], checks[kind] = build_domain(data, spec, declared["gld_anchors"][kind + "_original"]["parameters"])
    OUT.mkdir(parents=True, exist_ok=True)
    payload = clean(payload)
    page = TEMPLATE.read_text(encoding="utf-8").replace("__INSPECTION_DATA__", json.dumps(payload, separators=(",", ":"), allow_nan=False))
    (OUT / "index.html").write_text(page, encoding="utf-8")
    static_plot(payload)
    with (OUT / "episodes.csv").open("w", newline="", encoding="utf-8") as target:
        fields = ["domain", "trade", "range_start", "range_end", "range_sessions", "lower", "upper", "trigger", "breakout", "confirmation", "buy", "entry_price", "initial_stop", "band_floor", "effective_initial_floor", "trail_activation", "first_trail", "first_heat", "exit_decision", "sell", "exit_price", "net_trade_return"]
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        days = payload["prices"]["days"]
        for name, domain in payload["domains"].items():
            for e in domain["episodes"]:
                day = lambda t: days[t] if t is not None else ""
                b = e["box"]
                writer.writerow(dict(domain=name, trade=e["id"] + 1, range_start=day(b["start"]), range_end=day(b["end"]),
                    range_sessions=b["length"], lower=b["lower"], upper=b["upper"], trigger=b["trigger"], breakout=day(e["crossing"]),
                    confirmation=day(e["confirmation"]), buy=day(e["entry_index"]), entry_price=e["entry"], initial_stop=e["initial"],
                    band_floor=e["band"], effective_initial_floor=e["floor"], trail_activation=e["activation"], first_trail=day(e["first_arm"]),
                    first_heat=day(e["first_heat"]), exit_decision=day(e.get("exit_signal")), sell=day(e["exit_index"]), exit_price=e["exit_price"], net_trade_return=e["net_trade_return"]))
    audit.write(OUT / "validation.json", dict(created_utc=datetime.now(UTC).isoformat(), domains=checks,
        engine=br.VERSION, protocol_sha256=audit.digest(audit.OUTPUT / "protocol.json"),
        display="Original GLD pre-2023 fits, corrected research engine, 5bp/side, next-open fills, full-history state; no refit",
        data_end=payload["prices"]["days"][-1], price_basis="Published audited adjusted OHLC; audited raw volume; no online inputs",
        limitations="Retrospective audited history does not prove historical publication availability. Inspected 2023+ data is not a fresh holdout. Boxes are known at their crossing, not throughout the earlier window."))
    audit.write(OUT / "manifest.json", dict(inputs=dict(protocol_sha256=audit.digest(audit.OUTPUT / "protocol.json"),
        gld_sha256=declared["data"]["files"]["var/research/range-breakout-20261018-v2/assets/GLD.npz"]),
        outputs={p.name: audit.digest(p) for p in OUT.iterdir() if p.name != "manifest.json" and p.is_file()},
        sources={str(p.relative_to(ROOT)): audit.digest(p) for p in (Path(__file__), TEMPLATE)}))
    print(json.dumps(dict(report=str(OUT / "index.html"), checks=checks), indent=2))


if __name__ == "__main__":
    main()
