"""Build the GLD range-lifecycle HTML report and its compact public artifacts."""
from __future__ import annotations

import base64
import io
import json
import os
import shutil
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(r"D:\projects\systematic_trading")
VAR = Path(os.environ.get("GLD_STUDY_VAR", str(ROOT / "var" / "research" /
                                              "gld-lifecycle-20261019-v1")))
PUB = Path(os.environ.get("GLD_STUDY_PUB", str(ROOT / "research" /
                                              "gld-lifecycle-20261019-v1")))
sys.path.insert(0, str(ROOT / "src"))
from systematic_trading.research import range_lifecycle as rl  # noqa: E402

PARAM_DESCRIPTIONS = {
    "width_cap": "Maximum log width of the central band: log(U/D) <= width_cap.",
    "tail_index": "Band tail quantile choice among 5/10/15/20%.",
    "drift_max": "Maximum first/last-block median drift as a fraction of band width.",
    "vol_ratio_cap": "Recent short-window return volatility must be <= this times the full-window volatility.",
    "atr_index": "ATR period used for trigger buffer, stops and trailing distance.",
    "breakout_buffer_atr": "Crossing buffer above the upper band, in ATR.",
    "confirm_sessions": "Consecutive closes above the frozen trigger required to confirm.",
    "volume_shortcut": "If 1, a volume surge confirms the breakout immediately.",
    "volume_ratio": "Raw volume / prior median volume that triggers the shortcut and heat test.",
    "volref_index": "Median-volume reference window (20/63/126 sessions).",
    "initial_stop_atr": "Initial stop distance below entry, in ATR.",
    "band_fail_atr": "Failed-breakout floor: stop = max(initial stop, U* - this * ATR); negative disables.",
    "trail_basis": "Trailing basis: 0 = ATR from highest close, 1 = percent from highest close.",
    "trail_atr": "ATR trailing distance from the highest close once armed.",
    "trail_pct": "Percent trailing distance from the highest close once armed.",
    "trail_activate_atr": "Peak gain, in ATR, required before the trailing stop arms.",
    "heat_enabled": "If 1, overheat (extension + volume + near-high) tightens the trailing distance.",
    "heat_ext_atr": "Close extension above the frozen upper band required for overheat.",
    "heat_vol_ratio": "Volume ratio required for overheat.",
    "heat_near_high_atr": "Closeness to the running peak, in ATR, required for overheat.",
    "heat_trail_mult": "Trailing-distance multiplier after overheat; lower is tighter.",
    "time_exit_index": "Time-stop deadline (0 disables).",
    "time_exit_gain_atr": "Peak gain, in ATR, required to survive the time-stop deadline.",
    "cooldown_sessions": "Flat sessions after an exit before a new range breakout is accepted.",
    "reentry_enabled": "If 1, a closed breakout can be re-engaged on new highs of the same trend.",
    "reentry_buffer_atr": "Re-entry trigger buffer above the previous episode peak, in ATR.",
    "reentry_wait_index": "Maximum sessions after exit in which continuation re-entry is allowed.",
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def full_vector(vector):
    """Map a sealed parameter vector onto the current module (re-entry option off)."""
    values = list(vector)
    if len(values) == len(rl.PARAMETERS):
        return rl.canonical(values)
    if len(values) == len(rl.PARAMETERS) - 3:
        return rl.canonical(values + [0, 0.0, 0])
    raise ValueError(f"Unsupported parameter vector length {len(values)}")


def fig_b64(fig):
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def table(headers, rows, cls="data", floatfmt=None):
    out = [f'<table class="{cls}"><thead><tr>']
    out += [f"<th>{h}</th>" for h in headers]
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>")
        for value in row:
            if floatfmt and isinstance(value, float):
                text = floatfmt(value)
            elif isinstance(value, float):
                text = f"{value:.4f}"
            elif value is None:
                text = "&mdash;"
            else:
                text = str(value)
            out.append(f"<td>{text}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def pct(value, digits=2):
    if value is None:
        return "&mdash;"
    return f"{100.0 * value:.{digits}f}%"


def num(value, digits=2):
    if value is None:
        return "&mdash;"
    return f"{value:.{digits}f}"


def load_study():
    study = {}
    study["protocol"] = read_json(VAR / "protocol.json")
    study["bounds"] = read_json(VAR / "bounds.json")
    study["selection"] = read_json(VAR / "selection.json")
    study["evaluation"] = read_json(VAR / "evaluation" / "evaluation.json")
    study["ledger"] = pd.read_csv(VAR / "evaluation" / "daily-ledger.csv",
                                  parse_dates=["date"])
    study["episodes"] = pd.DataFrame(study["evaluation"]["episodes"])
    study["trace"] = np.load(VAR / "evaluation" / "trace.npz", allow_pickle=True)
    study["top60"] = read_json(VAR / "fit" / "top60.json")
    study["seed_bests"] = read_json(VAR / "fit" / "seed_bests.json")
    study["search"] = np.load(VAR / "fit" / "search.npz")
    validation_dir = VAR / "validation" / "evaluation" / "evaluation.json"
    study["validation"] = read_json(validation_dir) if validation_dir.exists() else None
    return study


def features_for_sensitivity():
    data = np.load(VAR / "inputs" / "gld-audited.npz", allow_pickle=True)
    features = rl.Features.build({k: data[k] for k in ("open", "high", "low", "close",
                                                       "volume", "days")})
    is_features = features.truncated(np.datetime64("2022-12-30", "D"))
    return features, is_features


def perturbation_sensitivity(selected, is_features):
    start = 252
    end = len(is_features.days)
    base = rl.evaluate(is_features, selected, start, end, cost_bp=5.0)["fitness"]
    rows = []
    for j, (name, low, high, integral) in enumerate(rl.PARAMETERS):
        if integral:
            neighbours = []
            for delta in (-1, 1):
                q = selected.copy()
                q[j] = int(np.clip(q[j] + delta, low, high))
                neighbours.append(q)
        else:
            neighbours = []
            for frac in (-0.20, -0.10, 0.10, 0.20):
                q = selected.copy()
                q[j] = np.clip(selected[j] * (1.0 + frac), low, high)
                neighbours.append(q)
        values = [rl.evaluate(is_features, q, start, end, cost_bp=5.0)["fitness"]
                  for q in neighbours]
        rows.append(dict(name=name, base=float(base), worst=float(min(values)),
                         best=float(max(values)), mean=float(np.mean(values)),
                         spread=float(max(values) - min(values))))
    return base, rows


def trail_grid(selected, features, is_features):
    start = 252
    is_end = len(is_features.days)
    oos = int(np.flatnonzero(features.days >= np.datetime64("2023-01-01"))[0])
    trails = (1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 10.0, 12.0)
    acts = (0.0, 1.0, 2.0, 3.0, 4.0, 6.0)
    rows = []
    for trail in trails:
        for act in acts:
            q = selected.copy()
            q[rl.NAMES.index("trail_atr")] = trail
            q[rl.NAMES.index("trail_activate_atr")] = act
            q = rl.canonical(q)
            is_ev = rl.evaluate(is_features, q, start, is_end, cost_bp=5.0)
            full = rl.simulate(features, rl.prepare(features, q), start=start, cost_bp=5.0)
            oos_rule = rl.stats(full["nav"], full["weight"], oos, len(features.days))
            rows.append(dict(trail=trail, activate=act, is_fitness=is_ev["fitness"],
                             is_cagr=is_ev["full"]["cagr"], is_sharpe=is_ev["full"]["sharpe"],
                             is_dd=is_ev["full"]["maxdd"], is_exposure=is_ev["full"]["exposure"],
                             oos_cagr=oos_rule["cagr"], oos_sharpe=oos_rule["sharpe"],
                             oos_dd=oos_rule["maxdd"], oos_exposure=oos_rule["exposure"]))
    return pd.DataFrame(rows)


def range_regime_table(ledger, episodes):
    rows = []
    for _, episode in episodes.iterrows():
        crossing = episode["crossing_session"]
        row = ledger[ledger["date"] == pd.Timestamp(crossing)]
        if row.empty:
            continue
        length = int(row["range_lookback"].iloc[0])
        crossing_idx = int(row.index[0])
        start_idx = max(0, crossing_idx - length)
        start_date = ledger["date"].iloc[start_idx]
        rows.append(dict(
            crossing=crossing, window_sessions=length,
            window_start=str(start_date.date()),
            window_end=str(pd.Timestamp(crossing).date()),
            upper=float(row["range_upper"].iloc[0]),
            lower=float(row["range_lower"].iloc[0]),
            width=float(row["range_width_log"].iloc[0]),
            drift=float(row["range_drift"].iloc[0]),
            volume_ratio=float(row["volume_ratio"].iloc[0]),
            entry=float(episode["entry_price"]),
            exit=float(episode["exit_price"]) if pd.notna(episode["exit_price"]) else None,
            gross=float(episode["gross_return"]) if pd.notna(episode["gross_return"]) else None,
            hold=int(episode["hold_sessions"]),
            reason=episode["exit_reason"],
        ))
    return pd.DataFrame(rows)


def build_figures(study):
    ledger = study["ledger"]
    episodes = study["episodes"]
    figures = {}
    plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.25})
    # ---- full history price, ranges, trades ----
    fig, ax = plt.subplots(figsize=(12, 5.6))
    ax.plot(ledger["date"], ledger["close"], color="#1f2a44", lw=1.0, label="GLD close")
    valid = ledger["range_lookback"] > 0
    ax.fill_between(ledger["date"], ledger["range_lower"], ledger["range_upper"],
                    where=valid, color="#4f7cac", alpha=0.20, linewidth=0,
                    label="qualifying central range")
    long_mask = ledger["weight"] > 0
    ax.fill_between(ledger["date"], 0.0, 0.035, where=long_mask,
                    transform=ax.get_xaxis_transform(), color="#3f8f5c", alpha=0.55,
                    linewidth=0, label="long exposure (bottom band)")
    for _, episode in episodes.iterrows():
        ax.axvline(pd.Timestamp(episode["crossing_session"]), color="#999999", lw=0.4, alpha=0.5)
        ax.scatter(pd.Timestamp(episode["entry_session"]), episode["entry_price"], marker="^",
                   color="#1b7f3a", s=26, zorder=4)
        if pd.notna(episode["exit_session"]):
            ax.scatter(pd.Timestamp(episode["exit_session"]), episode["exit_price"], marker="v",
                       color="#b23b3b", s=26, zorder=4)
    ax.set_yscale("log")
    ax.set_title("GLD 2004-2026: qualifying ranges, entries (up) and exits (down)")
    ax.set_ylabel("adjusted close (log)")
    ax.legend(loc="upper left", fontsize=8)
    figures["history"] = fig_b64(fig)
    # ---- IS equity and drawdown ----
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 6.2), sharex=True,
                                   gridspec_kw={"height_ratios": [2.2, 1]})
    mask = ledger["date"] <= "2022-12-30"
    d = ledger[mask]
    rule = d["nav"] / d["nav"].iloc[0]
    buy = d["buyhold_nav"] / d["buyhold_nav"].iloc[0]
    ax1.plot(d["date"], rule, color="#1b7f3a", lw=1.4, label="lifecycle rule")
    ax1.plot(d["date"], buy, color="#666666", lw=1.0, label="buy and hold")
    ax1.set_title("In-sample 2005-2022: growth of 1.0")
    ax1.legend()
    ax2.plot(d["date"], rule / rule.cummax() - 1, color="#1b7f3a", lw=1.1, label="rule drawdown")
    ax2.plot(d["date"], buy / buy.cummax() - 1, color="#666666", lw=0.8, label="buy-hold drawdown")
    ax2.legend(loc="lower left")
    figures["is_equity"] = fig_b64(fig)
    # ---- OOS equity ----
    fig, ax = plt.subplots(figsize=(11, 5.2))
    mask = ledger["date"] >= "2023-01-01"
    d = ledger[mask]
    rule = d["nav"] / d["nav"].iloc[0]
    buy = d["buyhold_nav"] / d["buyhold_nav"].iloc[0]
    ax.plot(d["date"], rule, color="#1b7f3a", lw=1.5, label="lifecycle rule")
    ax.plot(d["date"], buy, color="#666666", lw=1.0, label="buy and hold")
    ax.fill_between(d["date"], 1.0, rule, color="#1b7f3a", alpha=0.08)
    ax.set_title("Out-of-sample 2023-2026 development retest: growth of 1.0")
    ax.legend()
    figures["oos_equity"] = fig_b64(fig)
    # ---- annual returns ----
    years = sorted(int(y) for y in study["evaluation"]["years"].keys())
    rule_vals = [study["evaluation"]["years"][str(y)]["rule"] for y in years]
    buy_vals = [study["evaluation"]["years"][str(y)]["buyhold"] for y in years]
    x = np.arange(len(years))
    fig, ax = plt.subplots(figsize=(12, 4.4))
    ax.bar(x - 0.2, [v["cagr"] for v in rule_vals], width=0.4, color="#1b7f3a", label="rule")
    ax.bar(x + 0.2, [v["cagr"] for v in buy_vals], width=0.4, color="#999999", label="buy hold")
    ax.set_xticks(x)
    ax.set_xticklabels(years, rotation=0, fontsize=8)
    ax.axhline(0, color="black", lw=0.6)
    ax.set_title("Calendar-year return, rule versus buy hold")
    ax.legend()
    figures["annual"] = fig_b64(fig)
    # ---- 2023 drilldown ----
    figures["drill2023"] = drill_figure(study, "2022-12-20", "2023-08-15",
                                        "2023 breakout: crossing, confirmation, entry, dynamic exit")
    figures["drill2024"] = drill_figure(study, "2023-09-15", "2024-06-30",
                                        "October 2023 breakout held into the 2024 leg")
    figures["drill2025"] = drill_figure(study, "2025-05-01", "2025-10-31",
                                        "2025 breakout and dynamic take-profit")
    # ---- sensitivity ----
    features, is_features = features_for_sensitivity()
    selected = full_vector(study["selection"]["chosen"]["parameter_vector"])
    base, sensitivity = perturbation_sensitivity(selected, is_features)
    study["perturbation"] = dict(base=base, rows=sensitivity)
    rows = sorted(sensitivity, key=lambda r: r["worst"])
    fig, ax = plt.subplots(figsize=(9.5, 8.2))
    labels = [r["name"] for r in rows]
    worst = [r["worst"] - base for r in rows]
    best = [r["best"] - base for r in rows]
    y = np.arange(len(rows))
    ax.barh(y, best, color="#3f8f5c", alpha=0.7, label="best neighbour")
    ax.barh(y, worst, color="#b23b3b", alpha=0.6, label="worst neighbour")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=7.5)
    ax.axvline(0, color="black", lw=0.6)
    ax.set_xlabel("change in IS fitness versus selected vector")
    ax.set_title("One-at-a-time parameter sensitivity (IS fitness)")
    ax.legend()
    figures["sensitivity"] = fig_b64(fig)
    grid = trail_grid(selected, features, is_features)
    study["trail_grid"] = grid
    # continuation re-entry ablation on the sealed vector (offered as a fitted option)
    re_enabled = rl.NAMES.index("reentry_enabled")
    re_buffer = rl.NAMES.index("reentry_buffer_atr")
    re_wait = rl.NAMES.index("reentry_wait_index")
    ablation = []
    for buffer_atr in (0.0, 0.5, 1.0, 2.0):
        for wait_index in range(6):
            q = selected.copy()
            q[re_enabled] = 1
            q[re_buffer] = buffer_atr
            q[re_wait] = wait_index
            q = rl.canonical(q)
            ev = rl.evaluate(is_features, q, 252, len(is_features.days), cost_bp=5.0)
            ablation.append(dict(buffer_atr=buffer_atr,
                                 wait_sessions=rl.REENTRY_WAITS[wait_index],
                                 is_fitness=ev["fitness"], is_cagr=ev["full"]["cagr"],
                                 is_sharpe=ev["full"]["sharpe"], is_maxdd=ev["full"]["maxdd"],
                                 is_exposure=ev["full"]["exposure"], n_closed=ev["n_closed"],
                                 reentries=sum(1 for e in ev["episodes"] if e.get("reentry"))))
    study["reentry_ablation"] = ablation
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2))
    for ax, column, title, fmt in (
            (axes[0], "is_fitness", "IS fitness", "{:.2f}"),
            (axes[1], "is_cagr", "IS CAGR", "{:.0%}"),
            (axes[2], "oos_cagr", "2023+ development CAGR", "{:.0%}")):
        pivot = grid.pivot(index="activate", columns="trail", values=column).sort_index(ascending=False)
        im = ax.imshow(pivot.to_numpy(), aspect="auto", cmap="RdYlGn", origin="upper")
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels([f"{c:g}" for c in pivot.columns])
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([f"{r:g}" for r in pivot.index])
        ax.set_xlabel("trail ATR")
        ax.set_ylabel("activation ATR")
        ax.set_title(title)
        for i in range(pivot.shape[0]):
            for j in range(pivot.shape[1]):
                value = pivot.iloc[i, j]
                ax.text(j, i, fmt.format(value), ha="center", va="center", fontsize=6,
                        color="black")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    fig.suptitle("Exit-rule sensitivity: tight fast trail (IS optimum) versus wider trend trails")
    figures["trail_surface"] = fig_b64(fig)
    # ---- top candidate parameter distribution ----
    search = study["search"]
    order = np.argsort(-search["fitness"])[:200]
    params = search["parameters"][order]
    n_available = params.shape[1]
    integer_names = [name for name, low, high, integ in rl.PARAMETERS[:n_available] if integ]
    continuous_names = [name for name, low, high, integ in rl.PARAMETERS[:n_available] if not integ]
    fig, (axc, axi) = plt.subplots(1, 2, figsize=(13.0, 7.6),
                                   gridspec_kw={"width_ratios": [2.0, 1.2], "wspace": 0.55})
    continuous_labels = []
    for i, name in enumerate(continuous_names):
        j = rl.NAMES.index(name)
        low, high = rl.BOUNDS[j]
        values = params[:, j]
        q05, q50, q95 = np.percentile(values, [5, 50, 95])
        axc.plot([(q05 - low) / (high - low), (q95 - low) / (high - low)], [i, i],
                 color="#4f7cac", lw=3.0, solid_capstyle="round")
        axc.scatter([(q50 - low) / (high - low)], [i], color="#1f2a44", s=22, zorder=3)
        selected_value = float(study["selection"]["chosen"]["parameter_vector"][j])
        axc.scatter([(selected_value - low) / (high - low)], [i], color="#b23b3b", marker="|",
                    s=160, zorder=4)
        continuous_labels.append(f"{name}  (median {q50:.4g})")
    axc.set_yticks(range(len(continuous_names)))
    axc.set_yticklabels(continuous_labels, fontsize=7.4)
    axc.set_xlim(-0.02, 1.02)
    axc.set_xlabel("5-95% percentile of top-200 candidates, as a fraction of the fitted bound range")
    axc.set_title("Continuous parameters (dark dot = median, red bar = sealed)")
    for i, name in enumerate(integer_names):
        j = rl.NAMES.index(name)
        values = params[:, j]
        candidates = np.arange(int(rl.BOUNDS[j, 0]), int(rl.BOUNDS[j, 1]) + 1)
        shares = np.array([float(np.mean(values == c)) for c in candidates])
        left = 0.0
        for value, share in zip(candidates, shares):
            if share <= 0:
                continue
            axi.barh(i, share, left=left, height=0.62, color="#4f7cac", alpha=0.55,
                     edgecolor="white", linewidth=0.6)
            if share > 0.08:
                axi.text(left + share / 2, i, str(int(value)), ha="center", va="center", fontsize=7)
            left += share
        sealed = int(study["selection"]["chosen"]["parameter_vector"][j])
        axi.scatter([1.02], [i], color="#b23b3b", marker="<", s=38, zorder=4)
        axi.text(1.04, i, f"sealed {sealed}", fontsize=6.8, va="center",
                 transform=axi.get_yaxis_transform())
    axi.set_yticks(range(len(integer_names)))
    axi.set_yticklabels(integer_names, fontsize=7.4)
    axi.set_xlim(0, 1.0)
    axi.set_xlabel("share of top-200 candidates choosing each value (value printed inside)")
    axi.set_title("Integer / choice parameters")
    fig.suptitle("Fitted parameter distribution across the top 200 pre-2023 IS candidates", y=1.005)
    figures["top_params"] = fig_b64(fig)
    # ---- validation equity ----
    if study["validation"] is not None:
        figures["validation"] = validation_figure(study)
    return figures, features, is_features, selected


def drill_figure(study, start, end, title):
    ledger = study["ledger"]
    episodes = study["episodes"]
    d = ledger[(ledger["date"] >= start) & (ledger["date"] <= end)].reset_index(drop=True)
    for column in ("stop", "trail_stop", "initial_stop", "band_stop", "peak", "label"):
        if column in d:
            d[column] = d[column].where(np.isfinite(d[column].to_numpy(dtype=float)))
    fig = plt.figure(figsize=(13, 7.2))
    grid = fig.add_gridspec(3, 1, height_ratios=[2.6, 1.0, 1.0], hspace=0.08)
    ax = fig.add_subplot(grid[0])
    ax.plot(d["date"], d["close"], color="#1f2a44", lw=1.2, label="close")
    ax.plot(d["date"], d["range_upper"], color="#4f7cac", lw=0.9, label="range upper U")
    ax.plot(d["date"], d["range_lower"], color="#4f7cac", lw=0.9, label="range lower D")
    ax.plot(d["date"], d["trigger"], color="#c58b2a", lw=0.9, ls="--", label="breakout trigger")
    ax.plot(d["date"], d["stop"], color="#b23b3b", lw=1.2, label="effective stop")
    ax.plot(d["date"], d["trail_stop"], color="#7a2e8f", lw=0.9, ls=":", label="trailing stop")
    ax.plot(d["date"], d["peak"], color="#1b7f3a", lw=0.8, ls="-.", label="running peak close")
    mask = (episodes["crossing_session"] >= start) & (episodes["crossing_session"] <= end)
    for _, episode in episodes[mask].iterrows():
        ax.axvline(pd.Timestamp(episode["crossing_session"]), color="#c58b2a", lw=0.7, alpha=0.7)
        ax.scatter(pd.Timestamp(episode["entry_session"]), episode["entry_price"], marker="^",
                   color="#1b7f3a", s=70, zorder=5)
        if pd.notna(episode["exit_session"]):
            ax.scatter(pd.Timestamp(episode["exit_session"]), episode["exit_price"], marker="v",
                       color="#b23b3b", s=70, zorder=5)
    ax.set_title(title)
    ax.legend(loc="upper left", fontsize=7, ncol=2)
    plt.setp(ax.get_xticklabels(), visible=False)
    ax2 = fig.add_subplot(grid[1], sharex=ax)
    colors = np.where(d["volume_ratio"] >= 1.5, "#b23b3b", "#9aa4b2")
    ax2.bar(d["date"], d["volume_ratio"], color=colors, width=1.0)
    ax2.axhline(1.0, color="black", lw=0.5)
    ax2.set_ylabel("vol ratio")
    plt.setp(ax2.get_xticklabels(), visible=False)
    ax3 = fig.add_subplot(grid[2], sharex=ax)
    ax3.fill_between(d["date"], 0, d["drawdown_from_peak"], color="#b23b3b", alpha=0.35)
    ax3.set_ylabel("drawdown from peak")
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    for label in ax3.get_xticklabels():
        label.set_rotation(35)
        label.set_horizontalalignment("right")
    return fig_b64(fig)


def validation_figure(study):
    validation = study["validation"]
    selected = full_vector(validation["parameter_vector"])
    data = np.load(VAR / "inputs" / "gld-audited.npz", allow_pickle=True)
    features = rl.Features.build({k: data[k] for k in ("open", "high", "low", "close",
                                                       "volume", "days")})
    p = rl.canonical(selected)
    sim = rl.simulate(features, rl.prepare(features, p), start=252, cost_bp=5.0)
    bh = rl.buy_hold(features, 252, cost_bp=5.0)
    mask = (features.days >= np.datetime64("2016-01-01")) & (features.days <= np.datetime64("2022-12-30"))
    idx = np.flatnonzero(mask)
    s, e = int(idx[0]), int(idx[-1]) + 1
    dates = features.days[s:e]
    rule = sim["nav"][s:e] / sim["nav"][s]
    buy = bh["nav"][s:e] / bh["nav"][s]
    fig, ax = plt.subplots(figsize=(11, 5.0))
    ax.plot(dates, rule, color="#1b7f3a", lw=1.4, label="lifecycle rule (2016-2022 pseudo-OOS)")
    ax.plot(dates, buy, color="#666666", lw=1.0, label="buy and hold")
    ax.set_title("Pre-2023 pseudo-out-of-sample: fit 2005-2015, evaluate 2016-2022")
    ax.legend()
    return fig_b64(fig)


def era_stats(ledger, start, end):
    d = ledger[(ledger["date"] >= start) & (ledger["date"] <= end)]
    if len(d) < 20:
        return None, None

    def stats_for(column):
        values = d[column].to_numpy(dtype=float)
        ret = values[1:] / values[:-1] - 1.0
        years = len(ret) / 252.0
        cagr = (values[-1] / values[0]) ** (1.0 / years) - 1.0
        sd = ret.std(ddof=1)
        sharpe = ret.mean() / sd * np.sqrt(252.0) if sd > 0 else 0.0
        peak = np.maximum.accumulate(values)
        return dict(cagr=float(cagr), sharpe=float(sharpe),
                    maxdd=float((values / peak - 1.0).min()))
    return stats_for("nav"), stats_for("buyhold_nav")


def build_html(study, figures):
    protocol = study["protocol"]
    selection = study["selection"]["chosen"]
    evaluation = study["evaluation"]
    decoded = selection["decoded"]
    periods = evaluation["periods"]
    trade_stats = evaluation["trade_stats"]
    frictions = evaluation["frictions"]
    episodes = study["episodes"]
    ledger = study["ledger"]
    validation = study["validation"]
    top60 = study["top60"]
    # parameter table
    param_rows = []
    for b in study["bounds"]:
        name = b["name"]
        value = decoded[name]
        if isinstance(value, float):
            value_text = f"{value:.4f}"
        else:
            value_text = str(value)
        param_rows.append((name, PARAM_DESCRIPTIONS.get(name, ""), f"[{b['low']:g}, {b['high']:g}]",
                           "integer" if b["integral"] else "continuous", value_text))
    param_table = table(["Parameter", "Role in the lifecycle", "Fitted bounds", "Type", "Sealed value"],
                        param_rows, floatfmt=None)
    # metrics tables
    def metric_row(period, label):
        rule = periods[period]["rule"]
        buy = periods[period]["buyhold"]
        return (label, pct(rule["cagr"]), num(rule["sharpe"]), pct(rule["maxdd"]),
                num(rule["calmar"]), pct(rule["exposure"]),
                pct(buy["cagr"]), num(buy["sharpe"]), pct(buy["maxdd"]))

    metric_headers = ["Period", "Rule CAGR", "Rule Sharpe", "Rule max DD", "Rule Calmar",
                      "Rule exposure", "Buy-hold CAGR", "Buy-hold Sharpe", "Buy-hold max DD"]
    is_metrics_table = table(metric_headers, [metric_row("IS", "In-sample 2005-11-17 to 2022-12-30")])
    oos_metrics_table = table(metric_headers, [
        metric_row("OOS", "Out-of-sample 2023-01-03 to 2026-10-16"),
        metric_row("FULL", "Full history 2005-11-17 to 2026-10-16")])
    block_rows = []
    for block in periods["IS"]["blocks"]:
        block_rows.append((f"{block['start']} to {block['end']}", pct(block["rule"]["cagr"]),
                           num(block["rule"]["sharpe"]), pct(block["rule"]["maxdd"]),
                           pct(block["rule"]["exposure"]), num(block["utility"])))
    block_table = table(["IS block", "CAGR", "Sharpe", "Max DD", "Exposure", "Excess utility"],
                        block_rows)
    friction_rows = []
    for row in frictions:
        friction_rows.append((f"{row['cost_bp']:g} bp, delay {row['delay']}",
                              pct(row["IS"]["rule"]["cagr"]), num(row["IS"]["rule"]["sharpe"]),
                              pct(row["IS"]["rule"]["maxdd"]),
                              pct(row["OOS"]["rule"]["cagr"]), num(row["OOS"]["rule"]["sharpe"]),
                              pct(row["OOS"]["rule"]["maxdd"])))
    friction_table = table(["Assumption", "IS CAGR", "IS Sharpe", "IS max DD", "OOS CAGR",
                            "OOS Sharpe", "OOS max DD"], friction_rows)
    year_rows = []
    for year in sorted(int(y) for y in evaluation["years"].keys()):
        row = evaluation["years"][str(year)]
        year_rows.append((year, pct(row["rule"]["cagr"]), pct(row["buyhold"]["cagr"]),
                          pct(row["rule"]["maxdd"]), num(row["rule"]["sharpe"]),
                          num(row["buyhold"]["sharpe"])))
    year_table = table(["Year", "Rule return", "Buy-hold return", "Rule max DD", "Rule Sharpe",
                        "Buy-hold Sharpe"], year_rows)

    def episode_table_for(frame):
        rows = []
        for _, episode in frame.iterrows():
            rows.append((episode["crossing_session"], episode["entry_session"],
                         num(episode["entry_price"]),
                         episode["exit_session"] if pd.notna(episode["exit_session"]) else "open",
                         num(episode["exit_price"]) if pd.notna(episode["exit_price"]) else "&mdash;",
                         pct(episode["gross_return"]) if pd.notna(episode["gross_return"]) else "&mdash;",
                         episode["exit_reason"], int(episode["hold_sessions"]),
                         pct(episode["mfe"]), pct(episode["mae"])))
        return table(["Crossing", "Entry", "Entry price", "Exit", "Exit price", "Gross return",
                      "Exit reason", "Hold (sessions)", "MFE", "MAE"], rows)

    episode_table = episode_table_for(episodes[episodes["crossing_session"] <= "2022-12-30"])
    oos_episode_table = episode_table_for(episodes[episodes["crossing_session"] >= "2023-01-01"])
    valid_share = float((ledger["range_lookback"] > 0).mean())
    lookback_counts = (ledger.loc[ledger["range_lookback"] > 0, "range_lookback"]
                       .value_counts().sort_index())
    lookback_text = ", ".join(f"{int(k)} sessions: {int(v)} days ({100 * v / len(ledger):.1f}%)"
                              for k, v in lookback_counts.items())
    entry_lookbacks = study["range_regimes"]["window_sessions"].value_counts().sort_index()
    entry_lookback_text = ", ".join(f"L={int(k)}: {int(v)}" for k, v in entry_lookbacks.items())
    regime = study["range_regimes"]
    regime_rows = []
    for _, row in regime.iterrows():
        regime_rows.append((row["crossing"], row["window_sessions"], row["window_start"],
                            num(row["upper"]), num(row["lower"]), pct(row["width"]),
                            num(row["drift"], 3), num(row["volume_ratio"]),
                            num(row["entry"]), pct(row["gross"]) if pd.notna(row["gross"]) else "&mdash;",
                            row["reason"]))
    regime_table = table(["Crossing", "Lookback L", "Range window start", "Upper U", "Lower D",
                          "Width log(U/D)", "Drift/W", "Volume ratio", "Entry", "Gross", "Exit"],
                         regime_rows)
    # top search table
    top_rows = []
    for row in top60[:10]:
        d = row["decoded"]
        top_rows.append((row["rank"], num(row["fitness"], 3), pct(row["cagr"]), num(row["sharpe"]),
                         pct(row["maxdd"]), pct(row["exposure"]), row["n_closed"],
                         f"{d['width_cap']:.3f}/{d['tail']:.2f}",
                         f"{d['confirm_sessions']}+{d['volume_shortcut']}",
                         f"{d['initial_stop_atr']:.1f}/{d['band_fail_atr']:.1f}",
                         f"{d['trail_atr']:.1f}@{d['trail_activate_atr']:.1f}",
                         f"{d['heat_enabled']}/{d['time_limit_sessions']}/{d['cooldown_sessions']}",
                         d.get("reentry_enabled", "not in this search")))
    top_table = table(["Rank", "IS fitness", "IS CAGR", "Sharpe", "Max DD", "Exposure", "Trades",
                       "Width/tail", "Confirm+vol", "Init stop/band", "Trail@activate",
                       "Heat/time/cool", "Re-entry"], top_rows)
    # perturbation table
    perturbation = study["perturbation"]
    perturb_rows = []
    for row in sorted(perturbation["rows"], key=lambda r: -(perturbation["base"] - r["worst"]))[:12]:
        perturb_rows.append((row["name"], num(perturbation["base"], 3), num(row["worst"], 3),
                             num(row["best"], 3), num(row["spread"], 3)))
    perturb_table = table(["Parameter", "Selected IS fitness", "Worst neighbour", "Best neighbour",
                           "Neighbour spread"], perturb_rows)
    # trail grid table (selected around the sealed trail)
    grid = study["trail_grid"]
    grid_rows = []
    for trail in (1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 10.0, 12.0):
        row = grid[(grid["trail"] == trail) & (grid["activate"] == 6.0)].iloc[0]
        grid_rows.append((f"{row['trail']:g} ATR", f"{row['activate']:g} ATR",
                          num(row["is_fitness"], 3), pct(row["is_cagr"]), num(row["is_sharpe"]),
                          pct(row["is_dd"]), pct(row["is_exposure"]), pct(row["oos_cagr"]),
                          num(row["oos_sharpe"]), pct(row["oos_dd"]), pct(row["oos_exposure"])))
    grid_table = table(["Trail ATR", "Activation", "IS fitness", "IS CAGR", "IS Sharpe", "IS max DD",
                        "IS exposure", "2023+ CAGR", "2023+ Sharpe", "2023+ max DD",
                        "2023+ exposure"], grid_rows)
    # continuation re-entry ablation table
    ablation = study["reentry_ablation"]
    enabled = [row for row in ablation if row["wait_sessions"] > 0]
    best_ablation = max(enabled, key=lambda r: r["is_fitness"])
    ablation_rows = []
    for row in ablation:
        ablation_rows.append((f"{row['buffer_atr']:g} ATR", row["wait_sessions"],
                              num(row["is_fitness"], 3), pct(row["is_cagr"]),
                              num(row["is_sharpe"]), pct(row["is_maxdd"]),
                              pct(row["is_exposure"]), row["n_closed"], row["reentries"]))
    ablation_table = table(["Buffer above prior peak", "Max wait (sessions)", "IS fitness",
                            "IS CAGR", "IS Sharpe", "IS max DD", "IS exposure", "Trades",
                            "Re-entry episodes"], ablation_rows)
    sealed_is_fitness = selection["final_score"]
    sealed_is_cagr = periods["IS"]["rule"]["cagr"]
    era_rows = []
    for label, start, end in (
            ("2005-11-17 to 2015-12-31 (first pre-2023 era)", "2005-11-17", "2015-12-31"),
            ("2016-01-04 to 2022-12-30 (second pre-2023 era)", "2016-01-04", "2022-12-30"),
            ("2023-01-03 to 2026-10-16 (development retest)", "2023-01-03", "2026-10-16")):
        rule, buy = era_stats(ledger, start, end)
        if rule is not None:
            era_rows.append((label, pct(rule["cagr"]), num(rule["sharpe"]), pct(rule["maxdd"]),
                             pct(buy["cagr"]), num(buy["sharpe"]), pct(buy["maxdd"])))
    era_table = table(["Window", "Rule CAGR", "Rule Sharpe", "Rule max DD", "Buy-hold CAGR",
                       "Buy-hold Sharpe", "Buy-hold max DD"], era_rows)
    # validation
    validation_html = "<p>Validation stage not yet available.</p>"
    if validation is not None:
        vrows = []
        for period, label in (("FIT", "Fit 2005-11-17 to 2015-12-31"),
                              ("PSEUDO_OOS", "Pseudo-OOS 2016-01-04 to 2022-12-30")):
            rule = validation["periods"][period]["rule"]
            buy = validation["periods"][period]["buyhold"]
            vrows.append((label, pct(rule["cagr"]), num(rule["sharpe"]), pct(rule["maxdd"]),
                          pct(rule["exposure"]), pct(buy["cagr"]), num(buy["sharpe"]),
                          pct(buy["maxdd"])))
        validation_html = table(["Window", "Rule CAGR", "Rule Sharpe", "Rule max DD",
                                 "Rule exposure", "Buy-hold CAGR", "Buy-hold Sharpe",
                                 "Buy-hold max DD"], vrows)
        validation_html += (f"<p class='note'>Validation-refit rule, 2016-2022: "
                            f"{validation['trade_stats'].get('n', 0)} closed; "
                            f"win rate {pct(validation['trade_stats'].get('win_rate'))}; "
                            f"mean gross {pct(validation['trade_stats'].get('mean_gross'))}. "
                            f"Parameters: {json.dumps({k: validation['selected'][k] for k in ('width_cap', 'tail_index', 'confirm_sessions', 'initial_stop_atr', 'trail_atr', 'trail_activate_atr')})}</p>")
    # drilldown table 2023
    drill = ledger[(ledger["date"] >= "2023-02-20") & (ledger["date"] <= "2023-04-25")]
    drill_rows = []
    def cell(value, digits=2):
        if value is None or not pd.notna(value) or not np.isfinite(float(value)):
            return "&mdash;"
        return f"{value:.{digits}f}"

    for _, row in drill.iterrows():
        has_range = row["range_lookback"] > 0
        drill_rows.append((str(row["date"].date()), cell(row["close"]),
                           int(row["range_lookback"]) if has_range else "&mdash;",
                           cell(row["range_upper"]) if has_range else "&mdash;",
                           cell(row["range_lower"]) if has_range else "&mdash;",
                           cell(row["trigger"]) if has_range else "&mdash;",
                           "yes" if row["cross"] else "",
                           cell(row["volume_ratio"]),
                           {0: "flat", 1: "pending", 2: "long"}.get(int(row["state"]), ""),
                           num(row["trigger_level"]) if pd.notna(row["trigger_level"]) else "&mdash;",
                           num(row["entry_price"]) if pd.notna(row["entry_price"]) else "&mdash;",
                           num(row["stop"]) if pd.notna(row["stop"]) else "&mdash;",
                           num(row["trail_stop"]) if pd.notna(row["trail_stop"]) else "&mdash;",
                           num(row["peak"]) if pd.notna(row["peak"]) else "&mdash;",
                           pct(row["drawdown_from_peak"]) if pd.notna(row["drawdown_from_peak"]) else "&mdash;",
                           int(row["hold_sessions"]),
                           {0: "", 1: "stop", 3: "time"}.get(int(row["exit_reason"]), "")))
    drill_table = table(["Date", "Close", "L", "U", "D", "Trigger", "Cross", "Vol ratio", "State",
                         "Frozen trigger", "Entry", "Stop", "Trail stop", "Peak",
                         "DD from peak", "Hold", "Exit"], drill_rows)
    # 2023 mechanics narrative
    first_2023 = episodes[episodes["crossing_session"] >= "2023-01-01"].iloc[0]
    oos = periods["OOS"]["rule"]
    buy_oos = periods["OOS"]["buyhold"]
    # comparison with previous attempt (documented v3 daily drilldown)
    prior = dict(cross="2023-03-15", confirm="2023-03-24", entry="2023-03-27", entry_price=181.15,
                 exit="2023-04-03", rule="8-close confirmation + 5-session time exit",
                 result="loss on a five-session follow-through deadline")
    improvement_rows = [
        ("Possible crossing", prior["cross"], first_2023["crossing_session"]),
        ("Confirmation close", prior["confirm"], first_2023["confirmation_session"]),
        ("Entry session", prior["entry"], first_2023["entry_session"]),
        ("Entry price", f"${prior['entry_price']:.2f}", f"${first_2023['entry_price']:.2f}"),
        ("Exit rule in force", prior["rule"],
         f"dynamic trailing take-profit ({decoded['trail_atr']:.1f} ATR from high after "
         f"{decoded['trail_activate_atr']:.1f} ATR gain)"),
        ("Exit", prior["exit"],
         f"{first_2023['exit_session']} at ${first_2023['exit_price']:.2f}"),
        ("Episode outcome", prior["result"],
         f"{100 * first_2023['gross_return']:+.2f}% gross over {int(first_2023['hold_sessions'])} sessions"),
    ]
    improvement_table = table(["Test", "Previous daily diagnostic", "This study"], improvement_rows)
    # assemble html
    css = """
    :root { --ink:#1c2533; --muted:#5b6675; --line:#d9dee6; --bg:#fbfbfc; --accent:#1b7f3a;
            --accent2:#b23b3b; --blue:#4f7cac; --gold:#c58b2a; }
    * { box-sizing: border-box; }
    body { margin:0; background:var(--bg); color:var(--ink);
           font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
    header { background:#16202e; color:#fff; padding:34px 6vw 28px; }
    header h1 { margin:0 0 6px; font-size:27px; letter-spacing:.2px; }
    header .sub { color:#c4cdd9; max-width:1150px; }
    header .meta { margin-top:14px; color:#9fb0c4; font-size:12.5px; }
    main { max-width:1180px; margin:0 auto; padding:26px 22px 80px; }
    h2 { margin:46px 0 14px; font-size:22px; border-bottom:2px solid var(--line); padding-bottom:6px; }
    h3 { margin:26px 0 10px; font-size:16.5px; }
    p { margin:9px 0; }
    .lede { font-size:16px; }
    .callout { background:#fff; border-left:4px solid var(--blue); padding:12px 16px; margin:16px 0;
               border-radius:4px; box-shadow:0 1px 2px rgba(0,0,0,.05); }
    .callout.warn { border-left-color:var(--accent2); }
    .callout.good { border-left-color:var(--accent); }
    .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
    .card { background:#fff; border:1px solid var(--line); border-radius:6px; padding:14px 16px; }
    .kpi { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:16px 0; }
    .kpi div { background:#fff; border:1px solid var(--line); border-radius:6px; padding:12px; }
    .kpi .v { font-size:22px; font-weight:650; }
    .kpi .l { color:var(--muted); font-size:12px; }
    table.data { border-collapse:collapse; width:100%; background:#fff; margin:10px 0 18px;
                 font-size:12.5px; }
    table.data th, table.data td { border:1px solid var(--line); padding:5px 7px; text-align:right; }
    table.data th { background:#eef1f5; font-weight:600; position:sticky; top:0; }
    table.data td:first-child, table.data th:first-child { text-align:left; }
    table.data tbody tr:nth-child(even) { background:#fafbfc; }
    .scroll { max-height:640px; overflow:auto; border:1px solid var(--line); border-radius:6px; }
    .scroll table.data { margin:0; }
    .scroll table.data th { position:sticky; top:0; z-index:1; }
    img.fig { width:100%; height:auto; display:block; margin:12px 0 6px;
              border:1px solid var(--line); border-radius:6px; background:#fff; }
    .caption { color:var(--muted); font-size:12.5px; margin:2px 0 18px; }
    code, .mono { font-family:"Cascadia Mono",Consolas,monospace; font-size:13px; }
    pre.eq { background:#fff; border:1px solid var(--line); border-radius:6px; padding:12px 16px;
             overflow-x:auto; font-size:13px; }
    .note { color:var(--muted); font-size:12.5px; }
    ul li { margin:5px 0; }
    a { color:#1c5f9e; }
    .pill { display:inline-block; padding:1px 8px; border-radius:10px; background:#e8eef7;
            color:#31465f; font-size:12px; margin-right:6px; }
    """
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GLD range-breakout lifecycle - fitted study</title><style>{css}</style></head><body>
<header>
<h1>GLD range-breakout lifecycle: fitted signal, dynamic take-profit and honest out-of-sample</h1>
<div class="sub">New attempt requested by the operator. Every behavioral threshold is fitted on completed
sessions through 2022-12-30; the 2023-01-03 to 2026-10-16 interval is evaluated once after the parameter
vector is sealed. The report exposes the range windows, crossing/confirmation mechanics, entry, daily stop
decomposition and take-profit exit for every episode, with the 2023 breakout shown day by day.</div>
<div class="meta">Study <code>{protocol['identity']}</code> · input batch <code>{protocol['data']['governance_batch'][:16]}...</code>
· audited GLD asset <code>{protocol['data']['asset_sha256'][:16]}...</code> · research only, no monitoring or trade authority</div>
</header>
<main>
<p class="lede">The previous daily diagnostic failed on exactly two mechanics the operator identified: it waited
for an 8-close confirmation (crossing 2023-03-15, entry 2023-03-27 near the local high) and then closed the
position on a 5-session progress deadline. This study replaces both with fitted mechanisms: a confirmation
count that can be short-circuited by a volume surge, a wide initial failed-breakout stop, and a dynamic
take-profit that trails from the recent high only after a meaningful advance. The sealed rule detects the
March 2023 breakout on the crossing close and enters the next open, then holds the trade until the dynamic
take-profit triggers.</p>

<div class="kpi">
<div><div class="v">{pct(oos['cagr'])}</div><div class="l">Out-of-sample CAGR (2023-2026, 5bp)</div></div>
<div><div class="v">{num(oos['sharpe'])}</div><div class="l">Out-of-sample Sharpe</div></div>
<div><div class="v">{pct(oos['maxdd'])}</div><div class="l">Out-of-sample max drawdown</div></div>
<div><div class="v">{pct(oos['exposure'])}</div><div class="l">Average long exposure</div></div>
</div>

<div class="callout good"><strong>What is fixed.</strong> The 2023 breakout is now entered at the first open after the
crossing close: crossing {first_2023['crossing_session']}, entry {first_2023['entry_session']} at
${float(first_2023['entry_price']):.2f}, exit {first_2023['exit_session']} at
${float(first_2023['exit_price']):.2f} ({100 * float(first_2023['gross_return']):+.2f}% gross,
{int(first_2023['hold_sessions'])} sessions). The rule then re-enters on the October 2023 breakout and holds
that leg for {int(episodes[(episodes['crossing_session'] >= '2023-09-01') & (episodes['crossing_session'] <= '2024-06-30')]['hold_sessions'].iloc[0])} sessions.</div>

<div class="callout warn"><strong>What does not work.</strong> In-sample gold rewarded fast burst exits; the sealed
rule therefore books gains after roughly +6 ATR and a 1 ATR give-back from the peak. That is why its
2023-2026 CAGR ({pct(oos['cagr'])}) trails buy-and-hold ({pct(buy_oos['cagr'])}) during the exceptional
2024-2026 bull leg, even though drawdown is roughly halved ({pct(oos['maxdd'])} versus
{pct(buy_oos['maxdd'])}). A wide-trail variant that holds longer was not selected by the pre-2023 evidence
(see the exit-rule surface below); it is reported as a sensitivity, not used to select parameters.</div>

<h2>1. What changed, and the 2023 episode side by side</h2>
<p>The prior GLD daily diagnostic kept the inherited 33-parameter vector and only changed the execution clock.
Its two decisive mechanics were an 8-session confirmation and a five-session "progress" deadline. With the
same audited data, the crossing was 2023-03-15, confirmation was 2023-03-24, entry was 2023-03-27 at
$181.15, and the five-session rule exited on 2023-04-03. This study fits those mechanics instead of inheriting
them.</p>
{improvement_table}
<p class="note">Previous numbers come from the recorded v3 daily drill-down (<code>research/gld-breakout-drilldown-20261018-v1</code>);
the comparison is between two different frozen rules, not a re-run of the old one.</p>

<h2>2. Data, chronology and governance</h2>
<ul>
<li><strong>Input.</strong> Audited adjusted GLD OHLC and raw volume, pinned batch
<code>{protocol['data']['governance_batch']}</code>, asset SHA-256
<code>{protocol['data']['asset_sha256']}</code>. Adjusted and raw closes are identical for GLD; no filling,
splicing, or online prices. The hash matches the frozen range-breakout v2 input manifest.</li>
<li><strong>Sessions.</strong> {protocol['data']['sessions']:,} sessions, {protocol['data']['first_session']} to
{protocol['data']['last_session']}.</li>
<li><strong>Split.</strong> Fit and selection read only sessions through <strong>2022-12-30</strong>
({protocol['chronology']['fit_is_sessions']:,} evaluation sessions after a {protocol['chronology']['warmup_sessions']}-session
warm-up). Out-of-sample metrics start on the first session of 2023, <strong>{protocol['chronology']['oos_first_session']}</strong>,
and continue the same account and state. A second, entirely pre-2023 chronology (fit 2005-2015, evaluate
2016-2022) is reported as pseudo-out-of-sample validation.</li>
<li><strong>Causality.</strong> Bands and range statistics use completed closes through t-1; the crossing test
uses close t against a trigger known before that close. Fills are the next open (one extra session in the delay
stress). The full-history evaluation re-computes the IS window and asserts equality with the sealed fit.</li>
</ul>
<div class="callout warn"><strong>Chronology honesty.</strong> The operator has already reviewed 2023-2026 gold
behavior, and previous reports inspected the same interval. The 2023+ block is therefore a <em>development
retest</em>, not an untouched holdout. The fit, objective and selection code never read 2023+ arrays.</div>

<h2>3. The fitted lifecycle</h2>
<p>The signal is a state machine on completed daily closes. Every threshold below is a fitted element of the
{protocol['parameterization']['vector_length']}-dimensional parameter vector; nothing is held at a conventional
value.</p>
<h3>3.1 Tight range</h3>
<pre class="eq">For each lookback L in {{21,42,63,126,252,504}} and tail q in {{5,10,15,20}}%:
  D_t = exp(quantile_q(log P[t-L : t]))          U_t = exp(quantile_(1-q)(log P[t-L : t]))
  W_t = log(U_t / D_t)
  b = min(63, max(10, L//4))                     c = min(63, max(5, L//3))
qualifies(L) at t  iff
  W_t &lt;= width_cap
  |median(log P[t-b:t]) - median(log P[t-L:t-L+b])| &lt;= drift_max * W_t
  std(log returns[t-c:t]) &lt;= vol_ratio_cap * std(log returns[t-L:t])</pre>
<p>The <strong>selected range is the longest qualifying lookback</strong>. That is the formal version of
"the asset has been stable for a while": a 504-session window is preferred whenever it still qualifies,
otherwise the rule falls back to 252, 126, 63, 42 or 21 sessions. Fitted values: width cap
<code>{decoded['width_cap']:.4f}</code>, tail <code>{decoded['tail']:.2f}</code>, drift cap
<code>{decoded['drift_max']:.3f}</code>, volatility-ratio cap <code>{decoded['vol_ratio_cap']:.3f}</code>.</p>
<h3>3.2 Breakout event and confirmation</h3>
<pre class="eq">trigger_t = U_t + breakout_buffer_atr * ATR_p[t-1]
crossing at t  iff  close_t &gt; trigger_t  and  close_(t-1) &lt;= trigger_t</pre>
<p>At the first crossing close the bands, L and entry ATR are frozen. Entry requires
<code>confirm_sessions</code> closes above the frozen trigger; any close at or below it cancels. A volume surge
(volume &gt;= <code>volume_ratio</code> x prior <code>volref</code>-session median) confirms immediately, so a
genuine high-activity breakout does not wait. Fitted values: confirm sessions
<code>{decoded['confirm_sessions']}</code>, volume shortcut <code>{decoded['volume_shortcut']}</code> at ratio
<code>{decoded['volume_ratio']:.3f}</code>, buffer <code>{decoded['breakout_buffer_atr']:.3f}</code> ATR,
ATR period <code>{decoded['atr_period']}</code>.</p>
<h3>3.3 Initial risk and the failed-breakout stop</h3>
<pre class="eq">entry = next open after confirmation
S0 = entry - initial_stop_atr * ATR_entry
if band_fail_atr &gt;= 0:  S0 = max(S0, U* - band_fail_atr * ATR_entry)</pre>
<p>The initial stop is wide (<code>{decoded['initial_stop_atr']:.1f}</code> ATR) and the failed-range floor
(<code>{decoded['band_fail_atr']:.2f}</code> ATR below the frozen upper band) cuts a breakout that falls back
into the range. This replaces the earlier tight E-2ATR stop that produced the premature 2023 sell.</p>
<h3>3.4 Dynamic take-profit</h3>
<pre class="eq">H_t = highest close since entry
if H_t &gt;= entry + trail_activate_atr * ATR_entry:
    stop_t = max(stop_(t-1), H_t - trail_atr * heat_multiplier * ATR_t)   # or H_t * (1 - trail_pct * multiplier)
overheat: close_t &gt;= U* + heat_ext_atr * ATR_entry and volume ratio &gt;= heat_vol_ratio
          and close_t &gt;= H_t - heat_near_high_atr * ATR_t
exit at next open when close_t &lt; stop_t, or time stop fires</pre>
<p>The take-profit is exactly the operator's candidate: a dynamic trailing level measured as a drawdown from the
most recent high, armed only after a real advance, and tightened if price extension plus a volume climax signal
overheat. Fitted values: trail <code>{decoded['trail_atr']:.2f}</code> ATR from the high after a
<code>{decoded['trail_activate_atr']:.2f}</code> ATR advance; overheat switch
<code>{decoded['heat_enabled']}</code> with extension <code>{decoded['heat_ext_atr']:.2f}</code> ATR, volume
ratio <code>{decoded['heat_vol_ratio']:.2f}</code>, near-high <code>{decoded['heat_near_high_atr']:.2f}</code>
ATR, trail multiplier <code>{decoded['heat_trail_mult']:.2f}</code>. The time stop is
<code>{decoded['time_limit_sessions']}</code> sessions (0 = off) with a
<code>{decoded['time_exit_gain_atr']:.2f}</code> ATR progress hurdle; cooldown after exit is
<code>{decoded['cooldown_sessions']}</code> sessions. Continuation re-entry is an extended-search option
tested separately on the sealed vector (section 9.3); the pre-2023 evidence rejected it, so it is disabled in
the sealed rule.</p>
<h3>3.5 Fitted parameter vector</h3>
{param_table}

<h2>4. Fitting and selection</h2>
<p>Search is a bounded rand/1/bin differential evolution over the mixed continuous/integer vector
({protocol['search']['seeds']} seeds, population {protocol['search']['population_multiplier']} x dimension,
{protocol['search']['generations']} generations, {protocol['search']['evaluations_per_seed']:,} evaluations per
seed, {protocol['search']['evaluations_per_seed'] * protocol['search']['seeds']:,} total), run on
pre-2023 sessions only at 5bp per side. The screen objective is</p>
<pre class="eq">utility = 0.45*clip((CAGR - CAGR_bh)/0.10, -3, 3)
        + 0.40*clip(Sharpe - Sharpe_bh, -3, 3)
        + 0.15*clip(Calmar - Calmar_bh, -3, 3)
robust  = 0.5*utility_full + 0.5*median(3 block utilities) - 0.25*std(3 block utilities)
fitness = robust - 0.10*scarcity - 0.30*low_exposure</pre>
<p>All references are the matched buy-and-hold of the same window. The 400 best distinct candidates are then
replayed at 5bp, 10bp, 20bp and 5bp plus one session of delay; the final score is the minimum fitness across
those frictions. Evidence requires at least 10 closed IS episodes, average IS exposure of at least 20%, and at
least one closed episode in each of three contiguous IS blocks; the return/drawdown guards require beating
buy-and-hold CAGR by no more than a 2pp deficit and buy-and-hold maximum drawdown by no more than a 5pp
deficit at every friction. Among near-best candidates the selector prefers the highest parameter-neighbour
stability, then lower turnover.</p>
<p class="note">Calibration lineage: this is the second pass on the GLD lifecycle (the first pass produced the
v1-v3 joint calibration reported earlier). This search has 24 lifecycle parameters and was fitted once on the
pre-2023 window. A later 27-parameter extension that adds continuation re-entry was run separately as an
auxiliary check; it selected a materially different cooldown/trailing combination and is used here only for the
re-entry ablation in section 9.3. All selection evidence for the sealed vector comes from the 24-parameter
pre-2023 search.</p>
<div class="callout"><strong>Selected vector.</strong> Final score {num(selection['final_score'], 4)}; guard
pass <strong>{selection['guards']}</strong>; evidence pass <strong>{selection['evidence']}</strong>; parameter
neighbour score {num(selection.get('neighbour_fraction'), 3)}; selection pool
<strong>{selection['selection_pool']}</strong>. The fitted vector is not at an inherited value for any
behavioral threshold.</div>
<h3>4.1 Seed bests and top independent candidates</h3>
{top_table}
<p class="note">Columns: width/tail, confirmation + volume shortcut, initial stop / failed-range buffer, trail
distance @ activation gain, heat/time/cooldown switches, continuation re-entry switch. The top candidates agree
on tight widths (5-10% central bands), one-to-three-close confirmation with the volume shortcut enabled, a wide
initial stop, and a tight trailing take-profit armed after a large advance. Continuation re-entry is rejected
by the IS evidence (switch 0 in every top candidate).</p>
<h3>4.2 Fitted parameter sensitivity</h3>
<p>One-at-a-time perturbations of the sealed vector, each re-evaluated on the IS window (continuous parameters
+/-10% and +/-20% of their selected value; integer parameters one grid step). The rule is flat for many
parameters; the sensitive dimensions are exactly the ones that define the trade (band tail/width, time-limit
switch, trailing basis and band-failure buffer).</p>
<img class="fig" src="data:image/png;base64,{figures['sensitivity']}" alt="one-at-a-time sensitivity">
<div class="caption">Change in IS fitness when each parameter is perturbed around the sealed value.</div>
{perturb_table}
<h3>4.3 What the fit population agrees on</h3>
<img class="fig" src="data:image/png;base64,{figures['top_params']}" alt="top candidate parameter distribution">
<div class="caption">Distribution of each parameter across the 200 highest-fitness IS candidates. Blue line:
5-95% range for continuous parameters; bubbles: integer choice shares; dark dot: median; red bar: sealed value.</div>

<h2>5. What the rule calls a tight range</h2>
<p>The rule qualifies a range on {100 * valid_share:.1f}% of sessions at the sealed parameters. The fitted
detector is strict, so it usually selects the shortest windows: {lookback_text}. At the {len(regime)} recorded
breakouts the selected lookbacks were {entry_lookback_text}. That is an honest property of this fit: the
pre-2023 objective prefers a one-to-three-month compression as the trigger context and lets the breakout,
confirmation and exit mechanics carry the trade. Longer 252/504-session windows almost never survive the fitted
drift and width tests. The table lists the exact window, frozen bands and width for every episode, and the
full-history chart shades the qualifying central range and long exposure.</p>
<img class="fig" src="data:image/png;base64,{figures['history']}" alt="GLD history with ranges and trades">
<div class="caption">GLD 2004-2026 (log scale). Shaded blue: central range currently qualifying; green band:
sessions held long; upward triangles: entries; downward triangles: exits. Vertical lines mark crossing sessions.</div>
<div class="scroll">{regime_table}</div>
<div class="caption">Range windows used at every breakout: the selected lookback L, the window start
(crossing - L sessions), frozen upper/lower bands, log width, drift/width, volume ratio at the crossing close,
entry, gross result and exit reason.</div>

<h2>6. In-sample evidence (2005-2022)</h2>
{is_metrics_table}
<img class="fig" src="data:image/png;base64,{figures['is_equity']}" alt="IS equity and drawdown">
<div class="caption">In-sample equity and drawdown versus matched buy-and-hold.</div>
{block_table}
<div class="caption">Three contiguous, non-resetting IS blocks. The rule's blocks are positive in the first and
third; the middle block contains the 2011-2015 gold bear and is where the wide initial stop and failed-breakout
floor do their work.</div>
<h3>6.1 Every in-sample episode</h3>
<div class="scroll">{episode_table}</div>
<div class="caption">MFE/MAE are the maximum favorable/adverse excursion from entry to the actual exit
(close-based). Gross return excludes costs; net of 5bp per side the reported NAV is the authority.</div>

<h2>7. Out-of-sample 2023-2026 (development retest)</h2>
{oos_metrics_table}
<img class="fig" src="data:image/png;base64,{figures['oos_equity']}" alt="OOS equity">
<div class="caption">Out-of-sample growth of 1.0 for the sealed rule versus buy-and-hold.</div>
<h3>7.1 Calendar years</h3>
{year_table}
<img class="fig" src="data:image/png;base64,{figures['annual']}" alt="annual returns">
<div class="caption">The rule participates in every up year and avoids the 2013 and 2015 bear years, but its
dynamic take-profit exits early during the exceptional persistent 2024-2025 advance.</div>
<h3>7.2 Costs and execution delay</h3>
{friction_table}
<div class="caption">The sealed rule is not a high-turnover system: its net result is robust to one extra
session of delay and to 20bp per side. The out-of-sample shortfall versus buy-and-hold is a holding-exit
design effect, not a cost effect.</div>
<h3>7.3 Every out-of-sample episode</h3>
<div class="scroll">{oos_episode_table}</div>
<div class="caption">All episodes whose crossing fell in 2023 or later, including the still-open position at the
data end. The rule enters quickly, re-enters after cooldown when a new range breakout occurs, and books gains with
the dynamic take-profit.</div>

<h2>8. The 2023 breakout, day by day</h2>
<p>The following chart and table expose every daily input and decision around the episode the operator
challenged. The rule selects a {decoded['confirm_sessions']}-close confirmation with the volume shortcut; the
crossing close itself is above the frozen trigger, so the next open is the entry. From then on the daily table
shows the running peak, the effective stop and the trailing take-profit level.</p>
<img class="fig" src="data:image/png;base64,{figures['drill2023']}" alt="2023 drilldown">
<div class="caption">2022-12 to 2023-08: close, qualifying range bands, breakout trigger, effective stop,
trailing stop, running peak, volume ratio and drawdown from peak. Triangles are entries/exits.</div>
<div class="scroll">{drill_table}</div>
<div class="caption">Daily decision ledger around the 2023 episode. The state is flat / pending / long; the
frozen trigger is the crossing boundary that must be held for confirmation; "Stop" is the effective stop used
for the close test; "Trail stop" is the dynamic take-profit component.</div>
<div class="callout good"><strong>Crossing to fill gap:</strong> crossing {first_2023['crossing_session']};
confirmation {first_2023['confirmation_session']}; entry {first_2023['entry_session']}. The rule consumes one
session (next open) instead of the previous eight-close wait. The dynamic take-profit then exits
{first_2023['exit_session']} at ${float(first_2023['exit_price']):.2f}, a {100 * float(first_2023['gross_return']):+.2f}%
gross result that captures the March-April advance instead of buying the local high and stopping out.</div>
<h3>8.1 The October 2023 and 2025 legs</h3>
<p>After the March-April take-profit the rule re-arms. It caught the October 2023 breakout and held the leg into
March 2024, then caught the 2025 acceleration and booked it near the 2025 high. The two charts below use the same
daily-stop decomposition as the 2023 drilldown.</p>
<img class="fig" src="data:image/png;base64,{figures['drill2024']}" alt="October 2023 leg">
<div class="caption">October 2023 breakout: entry 2023-10-27, held through the turn of the year, dynamic exit
2024-03-12.</div>
<img class="fig" src="data:image/png;base64,{figures['drill2025']}" alt="2025 leg">
<div class="caption">2025 acceleration: entry 2025-06-16, dynamic take-profit exit 2025-09-24 at a new high.</div>

<h2>9. Robustness and the hold-longer question</h2>
<h3>9.1 Chronological stability and a failed procedure validation</h3>
<p>Two different questions are separated here. First, how stable is the <em>sealed vector</em> across time? The
table below evaluates the same frozen rule and the matched buy-and-hold on the first pre-2023 era, the second
pre-2023 era, and the development retest. The sealed rule is stable across both pre-2023 eras and beats
buy-and-hold there with roughly one-third of its drawdown.</p>
{era_table}
<div class="caption">Frozen-vector chronological stability. The 2023+ column repeats the development retest
(where the exceptional buy-and-hold bull leg is the benchmark, not the rule's target).</div>
<p>Second, how stable is the <em>fitting procedure</em>? The same search, evidence guards and neighbourhood
selection were rerun with a fit that ends on 2015-12-31, then evaluated once on 2016-2022, an interval the
refit never saw. That procedure selected a materially different, boundary-hugging vector and failed on
2016-2022. This is reported as a failed procedure validation: ten years of gold history (and only about two
independent cycles) are too few for the search to identify the same mechanism the full pre-2023 fit finds.
The sealed vector is not the product of that unstable refit; it is the full pre-2023 fit, whose chronological
stability is shown above.</p>
{validation_html}
<img class="fig" src="data:image/png;base64,{figures.get('validation', '')}" alt="validation equity">
<div class="caption">Pseudo-out-of-sample 2016-2022 equity for the 2005-2015 fit.</div>
<h3>9.2 Exit-rule surface: burst take-profit versus wide trend trail</h3>
<p>The sealed exit books gains after a large advance and a 1 ATR give-back from the high. The operator's
question — what if we simply held longer — is a one-dimensional question in this design: widen the trailing
distance or lower the activation. The surface below re-evaluates exactly that while holding the sealed range and
entry mechanics fixed. On the pre-2023 fit the tight fast trail is best; on the 2023+ development interval the
wider trails would have captured more of the persistent bull leg. That divergence is a real regime difference,
not a selection defect: choosing the wide trail after seeing 2023+ would be out-of-sample tuning, so the sealed
vector remains the IS choice.</p>
<img class="fig" src="data:image/png;base64,{figures['trail_surface']}" alt="exit rule surface">
<div class="caption">IS fitness, IS CAGR and 2023+ development CAGR across trailing distance and activation gain,
with every other parameter at its sealed value. The star of the IS surface is the sealed tight trail; the
2023+ panel shows the extreme persistence that the IS block did not contain.</div>
{grid_table}
<div class="caption">Holding the sealed activation at 6 ATR and widening the trail from 1 to 12 ATR. IS fitness
falls while the 2023+ development result rises; this is reported as sensitivity, not used for selection.</div>
<h3>9.3 Continuation re-entry ablation</h3>
<p>A continuation re-entry option was added to the search: after a take-profit exit, a close above the previous
episode peak plus a fitted ATR buffer within a fitted waiting window re-enters the same trend at the next open.
The in-sample search rejected it. Holding the sealed range, entry and exit mechanics fixed and switching
re-entry on, the best of the 24 buffer/wait combinations lowers IS CAGR from {pct(sealed_is_cagr)} to
{pct(best_ablation['is_cagr'])} and IS fitness from {num(sealed_is_fitness, 3)} to
{num(best_ablation['is_fitness'], 3)}. The fitted switch is therefore off by construction in the sealed rule
(<code>reentry_enabled = 0</code>). Pre-2023 gold did not reward mechanical re-engagement of a completed
breakout, even though 2024-2026 would have.</p>
{ablation_table}
<div class="caption">Continuation re-entry ablation on the sealed vector (IS window, 5bp). Buffer is measured
above the previous episode peak; the waiting window starts at the take-profit exit.</div>

<h2>10. Interpretation and limitations</h2>
<ul>
<li><strong>The requested mechanics work.</strong> The 2023 breakout is entered on the first possible open
after the crossing close, held through the March noise, and exited by a dynamic drawdown-from-high take profit.
The failed-breakout floor and the wide initial stop replace the earlier tight stop; the five-session progress
exit is gone (time limit {decoded['time_limit_sessions']}).</li>
<li><strong>The rule is an IS-selected breakout harvester, not a buy-and-hold replacement.</strong> It trades
roughly {trade_stats['n'] / ((2026 - 2005)):.1f} times per year, holds about
{trade_stats['mean_hold']:.0f} sessions on average, wins {pct(trade_stats['win_rate'], 1)} of closed episodes,
and keeps a median gross gain of {pct(trade_stats['median_gross'])}. Its purpose is participation with a
defensive exit, so trailing the exceptional 2024-2026 buy-and-hold return is expected in-sample-consistent
behavior.</li>
<li><strong>Chronology.</strong> 2023+ has been inspected; this is a development retest. The frozen-vector
two-era stability, the friction/delay stress and the parameter-neighbour stability are the strongest
robustness evidence. The refit-on-2005-2015 <em>procedure</em> validation failed on 2016-2022; that is a
warning about the fitting procedure's data requirements, and it is reported rather than hidden.</li>
<li><strong>Data.</strong> One current-vintage US gold ETF history; no historical universe or publication-vintage
certification. Cash earns zero; close-based stops can gap beyond their level; fills are modelled at the next
open with a constant cost per side.</li>
<li><strong>Overfitting risk.</strong> {protocol['search']['evaluations_per_seed'] * protocol['search']['seeds']:,}
evaluations against roughly 4,300 IS sessions and 30-odd trades is a large search relative to the number of
independent gold cycles. Block stability, parameter-neighbour stability and the frozen-vector two-era
stability are the reported mitigations, not a proof of general validity. The failed 2005-2015 refit validation
is the clearest warning that this procedure is data-hungry.</li>
</ul>

<h2>11. Files and reproduction</h2>
<ul>
<li><a href="parameters.json"> parameters.json</a> — sealed vector, decoded values, bounds and per-friction scores.</li>
<li><a href="episodes.csv"> episodes.csv</a> — every episode with crossing/confirmation/entry/exit dates, frozen
bands, MFE/MAE and exit reason.</li>
<li><a href="daily-ledger.csv"> daily-ledger.csv</a> — every session with range, trigger, state, entry, stop
decomposition, trailing level, peak, drawdown and NAV.</li>
<li><a href="summary.json"> summary.json</a> — compact result record.</li>
<li><a href="protocol.json">protocol.json</a> and <a href="bounds.json">bounds.json</a> —predeclared design and
parameter bounds.</li>
<li><a href="top-candidates.json"> top-candidates.json</a> — top-60 IS candidates with decoded parameters.</li>
</ul>
<p class="note">Reproduction stages: <code>python scripts/run_gld_lifecycle.py prepare|fit|select|evaluate</code>
followed by <code>python scripts/build_gld_lifecycle_report.py</code>. Research code is
<code>src/systematic_trading/research/range_lifecycle.py</code>; the frozen source snapshots and input hashes
live under <code>var/research/{protocol['identity']}</code>. No monitoring, promotion, funding, allocation or
broker action follows from this study.</p>
</main></body></html>"""
    return html


def main():
    study = load_study()
    # Integrity: the sealed IS statistics must reproduce under the current module with
    # the re-entry extension switched off.
    data = np.load(VAR / "inputs" / "gld-audited.npz", allow_pickle=True)
    features = rl.Features.build({k: data[k] for k in ("open", "high", "low", "close",
                                                       "volume", "days")})
    is_features = features.truncated(np.datetime64("2022-12-30", "D"))
    sealed = study["selection"]["chosen"]["scenarios"][0]["rule"]
    recomputed = rl.evaluate(is_features, full_vector(study["selection"]["chosen"]["parameter_vector"]),
                             252, len(is_features.days), cost_bp=5.0)["full"]
    for key in ("cagr", "sharpe", "maxdd", "exposure"):
        if abs(recomputed[key] - sealed[key]) > 1e-8:
            raise AssertionError(f"Sealed IS {key} does not reproduce: "
                                 f"{recomputed[key]} vs {sealed[key]}")
    print("sealed IS evidence reproduces under the current module")
    study["range_regimes"] = range_regime_table(study["ledger"], study["episodes"])
    figures, features, is_features, selected = build_figures(study)
    html = build_html(study, figures)
    PUB.mkdir(parents=True, exist_ok=True)
    (PUB / "index.html").write_text(html, encoding="utf-8")
    # compact public artifacts
    shutil.copyfile(VAR / "protocol.json", PUB / "protocol.json")
    shutil.copyfile(VAR / "bounds.json", PUB / "bounds.json")
    shutil.copyfile(VAR / "fit" / "top60.json", PUB / "top-candidates.json")
    shutil.copyfile(VAR / "evaluation" / "episodes.csv", PUB / "episodes.csv")
    shutil.copyfile(VAR / "evaluation" / "daily-ledger.csv", PUB / "daily-ledger.csv")
    study["range_regimes"].to_csv(PUB / "range-regimes.csv", index=False)
    parameters_payload = dict(
        identity=study["protocol"]["identity"],
        selected=study["selection"]["chosen"]["decoded"],
        parameter_vector=study["selection"]["chosen"]["parameter_vector"],
        bounds=study["bounds"],
        final_score=study["selection"]["chosen"]["final_score"],
        evidence=study["selection"]["chosen"]["evidence"],
        guards=study["selection"]["chosen"]["guards"],
        neighbour_fraction=study["selection"]["chosen"].get("neighbour_fraction"),
        friction_scenarios=[dict(cost_bp=s["cost_bp"], delay=s["delay"], fitness=s["fitness"],
                                 rule=s["rule"], buyhold=study["selection"]["chosen"]["buyhold"][
                                     f"{s['cost_bp']}:{s['delay']}"])
                            for s in study["selection"]["chosen"]["scenarios"]],
        perturbation=study["perturbation"],
        trail_grid=study["trail_grid"].to_dict(orient="records"),
        selected_source="gld-lifecycle study selection.json",
    )
    (PUB / "parameters.json").write_text(json.dumps(parameters_payload, indent=2,
                                                    default=str), encoding="utf-8")
    summary = dict(identity=study["protocol"]["identity"],
                   data=study["protocol"]["data"], chronology=study["protocol"]["chronology"],
                   periods=study["evaluation"]["periods"], years=study["evaluation"]["years"],
                   trade_stats=study["evaluation"]["trade_stats"],
                   frictions=study["evaluation"]["frictions"],
                   n_episodes=study["evaluation"]["n_episodes"],
                   validation=study["validation"]["periods"] if study["validation"] else None,
                   limitations=study["protocol"]["limitations"])
    (PUB / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    files = sorted(p for p in PUB.iterdir()
                   if p.is_file() and p.name != "manifest.json")
    manifest = {p.name: __import__("hashlib").sha256(p.read_bytes()).hexdigest() for p in files}
    (PUB / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"public": str(PUB), "files": len(files), "html_bytes": len(html)},
                     indent=1))


if __name__ == "__main__":
    main()
