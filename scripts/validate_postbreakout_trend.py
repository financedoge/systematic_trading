"""Independent native accounting and frozen-baseline regression checks."""
from decimal import Decimal
import json
import shutil

import numpy as np

import retest_postbreakout_trend as study
from systematic_trading.backtest.accounting import quantize_money
from systematic_trading.config import AppSettings
from systematic_trading.research.momentum_replay import freeze_usd_bundle, native_parity


def main():
    study.verified()
    source = json.loads((study.source.OUTPUT / "asset-results.json").read_text())["rows"]
    lookup = {(r["symbol"], r["domain"], r["era"], r["cost_bp"], r["delay"]): r
              for r in source if r["method"] == "corrected_refit"}
    rows = json.loads((study.OUT / "asset-results.json").read_text())
    count, maximum = 0, 0.
    for r in rows:
        if r["variant"] != "baseline":
            continue
        b = lookup[(r["symbol"], r["domain"], r["era"], r["cost_bp"], r["delay"])]
        for k in ("cagr", "sharpe", "maxdd", "exposure"):
            maximum = max(maximum, abs(r[k] - b[k]))
        count += 1
    if maximum > 1e-10:
        raise ValueError("Frozen baseline mismatch")
    regime = json.loads((study.OUT / "regime-attribution.json").read_text())
    attribution = {}
    for r in regime:
        key = (r["symbol"], r["domain"], r["era"], r["variant"])
        attribution[key] = attribution.get(key, 0.) + r["strategy_log_return"]
    regime_error = max(abs(attribution[(r["symbol"], r["domain"], r["era"], r["variant"])] - np.log1p(r["cumulative"]))
                       for r in rows if r["cost_bp"] == 5 and r["delay"] == 0)
    if regime_error > 1e-10:
        raise ValueError("Regime contributions do not sum to NAV")
    study.write(study.OUT / "baseline-validation.json", dict(cases=count, max_metric_error=maximum,
        regime_log_return_max_error=regime_error))
    if AppSettings().lean_runtime_backend != "native":
        raise ValueError("Native Windows LEAN required")
    root, work, output = study.ROOT, study.WORK, study.OUT
    contract = work / "native-contract"
    if not contract.exists():
        shutil.copytree(root / "src/systematic_trading", contract / "source/systematic_trading",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        study.write(contract / "protocol.json", dict(initial_cash_usd="1000000",
            limitations=["USD adjusted units; daily next-open research, no intraday/TWAP or broker authority."]))
        study.write(contract / "input_manifest.json", dict(study_protocol=study.study.digest(output / "protocol.json")))
    panel = study.study.frozen._load_panel()
    recipe = json.loads(study.study.frozen.RECIPE_PATH.read_text())
    replay = study.study.frozen._Replay(panel, recipe, "2023-01-03")
    with np.load(work / "native-mappings.npz", allow_pickle=False) as a:
        mappings = {k: a[k] for k in a.files}
    with np.load(work / "native-nav.npz", allow_pickle=False) as a:
        paths = {k: a[k] for k in a.files}
    receipts = []
    image = json.loads((root / "config/strategy-monitoring.json").read_text())["calculation"]["image"]
    close = np.column_stack([panel["close"], panel["urth_close"]])
    for name, delay in (("trend_fit_overlay_dynamic", 0), ("trend_fit_overlay_dynamic", 1), ("trend_fit_selection_dynamic", 0)):
        key = f"{name}_c5d{delay}"
        weights, indices = mappings[key + "_weights"], mappings[key + "_indices"]
        schedule = replay.decisions(weights, indices, delay)
        ix = {str(panel["days"][t + 1 + delay]): int(t) for t in indices if t + 1 + delay < len(panel["days"])}
        decisions = {str(day): dict(signal_session=str(panel["days"][ix[str(day)]]),
            known_through=str(panel["days"][ix[str(day)]]), targets=[t.model_dump(mode="json") for t in targets])
            for day, targets in schedule.items()}
        quotes = {}
        for j, symbol in enumerate(replay.symbols):
            quotes[symbol] = {}
            for day in replay.days:
                t = ix.get(str(day))
                reference = quantize_money(Decimal(str(close[t, j]))) if t is not None else replay.reference[day][symbol]
                quotes[symbol][str(day)] = dict(open=str(replay.open[day][symbol]), close=str(replay.close[day][symbol]), reference=str(reference))
        bundle, target = work / "native-bundles" / key, work / "native" / key
        freeze_usd_bundle(bundle, contract, recipe, decisions, quotes, list(map(str, replay.days)), 5)
        receipt = native_parity(bundle, target, image, cpus="2")
        actual = json.loads((target / "economic.json").read_text())
        error = float(np.max(np.abs(np.array([float(r["nav"]) for r in actual["nav"]]) - paths[key][1:])))
        if error > .011:
            raise ValueError(f"Native mismatch {key}: {error}")
        receipts.append(dict(scenario=key, max_nav_difference=error, status=receipt["status"],
            bundle_sha256=study.study.digest(bundle / "manifest.json"), receipt_sha256=study.study.digest(target / "run.json")))
        study.write(output / "native-checks.json", receipts)
        print(key, error, flush=True)


if __name__ == "__main__":
    main()
