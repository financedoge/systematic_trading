"""Independent native accounting checks for the frozen breakout research study."""
from decimal import Decimal
import json
import shutil

import numpy as np

import revisit_breakout_research as study
from systematic_trading.backtest.accounting import quantize_money
from systematic_trading.config import AppSettings
from systematic_trading.research.momentum_replay import freeze_usd_bundle, native_parity


def validate_study(study, results_name="results.json", extra_case="momentum_dynamic"):
    if AppSettings().lean_runtime_backend != "native":
        raise ValueError("Native Windows LEAN required")
    root, work, output = study.ROOT, study.WORK, study.OUTPUT
    declared = json.loads((output / "protocol.json").read_text())
    if declared != study.protocol():
        raise ValueError("Study changed")
    evidence = json.loads((output / results_name).read_text())
    if evidence["protocol_sha256"] != study.digest(output / "protocol.json"):
        raise ValueError("Result identity changed")
    contract = work / "native-contract"
    if not contract.exists():
        shutil.copytree(root / "src/systematic_trading", contract / "source/systematic_trading",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        study.write(contract / "protocol.json", dict(initial_cash_usd="1000000", limitations=declared["limitations"]))
        study.write(contract / "input_manifest.json", dict(study_protocol=study.digest(output / "protocol.json")))
    panel = study.frozen._load_panel()
    recipe = json.loads(study.frozen.RECIPE_PATH.read_text())
    replay = study.frozen._Replay(panel, recipe, "2023-01-03")
    mappings = np.load(work / "mappings.npz", allow_pickle=False)
    paths = np.load(work / "nav.npz", allow_pickle=False)
    receipts = []
    image = json.loads((root / "config/strategy-monitoring.json").read_text())["calculation"]["image"]
    close = np.column_stack([panel["close"], panel["urth_close"]])
    for name, delay in ((study.PRIMARY, 0), (study.PRIMARY, 1), (extra_case, 0)):
        key = f"late_{name}_c5d{delay}"
        weights, indices = mappings[name + "_weights"], mappings[name + "_indices"]
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
            raise ValueError(f"Native NAV mismatch {key}: {error}")
        receipts.append(dict(scenario=key, max_nav_difference=error, status=receipt["status"],
            bundle_sha256=study.digest(bundle / "manifest.json"), receipt_sha256=study.digest(target / "run.json")))
        study.write(output / "native-checks.json", receipts)
        print(key, error, flush=True)


if __name__ == "__main__":
    validate_study(study)
