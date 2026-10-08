"""Finite macro experiment over pinned, published sources and frozen controls."""
from datetime import date, datetime, timedelta, UTC
from decimal import Decimal as D
import json
from pathlib import Path
import shutil

from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.live.trading_calendar import us_equity_market_close
from systematic_trading.recorders.economics import EconomicInputs, NY
from systematic_trading.research.economic_overlay import SPEC, signal, apply_signal, scale_spy, calibrate_spy
from systematic_trading.research.economic_models import MODEL_SPEC, fit_predict, tilt
from systematic_trading.research.momentum_replay import read_json, checked_files, freeze_usd_bundle, run_usd_reference

STRATEGIES = ["F0", "F3", "M0", "M3", "C0", "C3", "T0", "T3", "L0", "L3"]
ARMS = [*STRATEGIES, "RP", "URTH"]
COMPARISONS = [("M0", "F0"), ("M0", "C0"), ("M3", "F3"), ("M3", "C3"),
    ("T0", "F0"), ("T0", "L0"), ("T3", "F3"), ("T3", "L3"), ("L0", "F0"), ("L3", "F3")]
LABELS = dict(F0="Current SOTA", F3="Qualifying defensive ETFs + cash", M0="Current SOTA + US economic overlay",
    M3="Defensive cash + US economic overlay", C0="SOTA + calibrated constant SPY reduction",
    C3="Defensive cash + calibrated constant SPY reduction", T0="SOTA + asset-specific economic trees",
    T3="Defensive cash + asset-specific economic trees", L0="SOTA + asset-specific linear economics",
    L3="Defensive cash + asset-specific linear economics", RP="Original ETF risk parity", URTH="Global equities")
_DATA = None


def jobs():
    return ([(a,c,0,"evaluation",0) for a in ARMS for c in [5,10,20]]
        +[(a,5,1,"evaluation",0) for a in STRATEGIES]
        +[(a,5,0,"full",0) for a in ["F0","F3","M0","M3","T0","T3","L0","L3"]])


def job_name(job):
    a,c,d,p,l = job
    return f"{a}-{p}-cost{c}-delay{d}-lag{l}"


def prepare(root, parent, economic_pin):
    from systematic_trading.config import AppSettings
    from systematic_trading.market_data.analytics_store import AnalyticsStore
    from systematic_trading.portfolio.strategy_allocation import control_state
    from systematic_trading.storage.factory import create_trading_store
    from systematic_trading.research.governed_inputs import GovernedInputs, etf_bar
    if root.exists():
        raise FileExistsError("Frozen study already exists")
    checked_files(parent,"input_manifest.json");checked_files(parent,"decision_manifest.json")
    old=read_json(parent/"protocol.json")
    settings=AppSettings();analytics=AnalyticsStore.from_settings(settings)
    state=control_state(create_trading_store(settings))
    if state["sota_key"] != old["baseline"]:
        raise ValueError("Current SOTA changed; register a new experiment")
    published=analytics.latest("governance/catalog")
    source=GovernedInputs(Path(json.loads(published["provenance"])["root"]),published["version"])
    original=read_json(parent/"bars.json")
    # The prior bill study includes BIL; this experiment preserves the original twelve.
    symbols=sorted(s for s in original if s != "BIL")
    bars={s:[etf_bar(r) for r in source.rows(s,old["warmup_start"],old["end"])] for s in symbols}
    if any(bars[s] != original[s] for s in symbols):
        raise ValueError("Published prices differ from frozen controls")
    urth=[dict(trade_date=r["trade_date"],open=str(r["adjusted_open"]),close=str(r["adjusted_close"]))
          for r in source.rows("URTH",old["warmup_start"],old["end"])]
    if urth != read_json(parent/"urth.json"):
        raise ValueError("Benchmark prices differ")
    pin=read_json(economic_pin)
    macro=EconomicInputs(pin["root"],pin["batch"])
    if macro.catalog["completed"] != macro.catalog["expected"]:
        raise ValueError("Incomplete economic publication panel")
    protocol=dict(version="us-economic-overlay-v1",registered_at=datetime.now(UTC).isoformat(),baseline=old["baseline"],
        calibration_start="2016-01-04",calibration_end="2020-12-31",evaluation_start="2021-01-04",end=old["end"],
        initial_cash_usd="1000000",accounting_currency="USD",cash_interest="zero",arms=LABELS,economic_rule=SPEC,model_rule=MODEL_SPEC,
        hypothesis="Compare fixed US equity risk reduction with nonlinear asset-specific responses that can reward economic beneficiaries; isolate nonlinear value against linear models and unchanged parent gross.",
        calibration="C0/C3 scale = sum corresponding M0/M3 SPY targets / sum parent SPY targets in sixty 2016–2020 decisions, frozen thereafter.",
        stale_policy="Verified but stale/missing measurements: abstain, use unmodified parent targets. Corrupt, unpublished or future inputs: abort.",
        robustness="5/10/20bp costs; one extra execution session for ten strategies; annual and 2021–2022/2023–2026 subperiods. No extra macro lag variant because available monthly archives would make weekly claims stale.",
        cost_bps=[5,10,20],comparisons=COMPARISONS,family_size=len(COMPARISONS),bootstrap_blocks=[3,6,12],bootstrap_replications=20000,seed=2026100704,
        screen=dict(min_sharpe_gain=0,min_calmar_gain=0,max_cagr_sacrifice=.005,max_drawdown_worsening=.005,
            rule="At 5bp both ratios must beat the parent and (M: constant SPY control; T: same-input linear control). At 20bp CAGR sacrifice versus parent <=0.5pp and primary DD worsening <=0.5pp. Delayed-execution Sharpe/Calmar must both beat delayed parent. Linear variants need only beat parent. All checks required to retain for further evidence, never automatic promotion."),
        sample_policy="2021–2026 evaluation restarts every arm in USD 1m cash; 2016–2020 calibrates constant exposure and supplies initial tree/linear training; full-history context remains causal with abstention until 36 completed labels.",
        budget="Twelve primary arms, ten paired comparisons, 54 total replays, twelve primary native checks. No thresholds, weights, features or hyperparameter search.",
        promotion_eligible=False,limitations=[*old["limitations"],*macro.catalog["limitations"],
            "The fixed macro rule reduces SPY only. Tree/linear models estimate separate responses for all twelve ETFs to US activity as a possible global factor, not a proxy for each country's domestic economy.",
            "The economic layer is optional: stale observations revert to the still-valid price/model parent, potentially restoring SPY exposure. This is a declared policy, not a data repair.",
            "Both calibration and evaluation years were previously inspected in earlier strategy research; no untouched out-of-sample claim.",
            "Constant controls match training target SPY exposure, not future realized risk. Evaluation may have different average exposure.",
            "Same-vintage seasonal adjustments and historical methodology remain those of ALFRED; no contemporaneous app-capture claim.",
            "Ten paired mean-return contrasts use Holm correction. Ratio intervals are marginal; Calmar bootstrap uses 252 sessions/year; partial October 2026 is included.",
            "Economic features measure activity changes, not consensus surprises or identified causal shocks. Estimated sensitivities can change over time.",
            "Trees and linear models tilt only positive existing targets and preserve each parent's exact invested budget. Raw 1.10/0.90 factors are normalized, so individual final relative changes can exceed 10%; inherited concentration can drift.",
            "Monthly labels are next-rebalance open-to-open returns. A label ending at the current decision open is not yet known at its prior-close cutoff and is excluded from that fit.",
            "No new instruments or data feeds. Active strategies, monitoring, capital and broker authority remain unchanged."])
    root.mkdir(parents=True)
    write_json(root/"protocol.json",protocol)
    shutil.copytree(Path(__file__).parents[1],root/"source/systematic_trading",ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    write_json(root/"bars.json",bars);write_json(root/"urth.json",urth)
    for arm in ["F0","F3","RP"]:
        write_json(root/"controls"/(arm+".json"),read_json(parent/"decisions"/(arm+".json")))
    controls=read_json(root/"controls/F0.json")
    vintages=sorted({str(date.fromisoformat(r["known_through"])-timedelta(days=1)) for r in controls.values()})
    entries=[]
    for entry in macro.catalog["snapshots"]:
        if entry["vintage"] not in vintages:
            continue
        macro.snapshot(entry["series"],entry["vintage"])
        destination=root/"economic"/entry["series"]/entry["vintage"]
        destination.mkdir(parents=True)
        for name in read_json(Path(entry["root"])/"manifest.json"):
            shutil.copy2(Path(entry["root"])/name,destination/name)
        shutil.copy2(Path(entry["root"])/"manifest.json",destination/"manifest.json")
        entries.append(dict(entry,root=str(destination.resolve())))
    # The original catalog stays pinned; a separate hashed locator translates
    # published snapshot roots to identical verified local copies for offline replay.
    write_json(root/"economic_catalog.json",macro.catalog)
    write_json(root/"economic_locations.json",entries)
    write_json(root/"data_receipt.json",dict(price_batch=published["version"],publication=published,governed_files=source.used,
        parent=str(parent.resolve()),parent_input_sha256=sha256(parent/"input_manifest.json"),
        parent_decision_sha256=sha256(parent/"decision_manifest.json"),baseline_price_parity=True,
        economic_pin=dict(root=pin["root"],batch=pin["batch"]),economic_pin_file_sha256=sha256(economic_pin),
        control_revision=state["revision"],image=read_json(parent/"data_receipt.json")["image"]))
    write_json(root/"input_manifest.json",{f.relative_to(root).as_posix():sha256(f) for f in sorted(root.rglob("*")) if f.is_file()})
    return dict(root=str(root),protocol_sha256=sha256(root/"protocol.json"),replays=len(jobs()),arms=ARMS)


def initialize(root):
    global _DATA
    root=Path(root);checked_files(root,"input_manifest.json")
    # Use the same reader contract with frozen locators; each original manifest
    # remains byte-identical and the study's input manifest binds this locator map.
    reader=object.__new__(EconomicInputs)
    reader.catalog=read_json(root/"economic_catalog.json")
    original={(r["series"],r["vintage"]):r for r in reader.catalog["snapshots"]}
    entries=read_json(root/"economic_locations.json")
    for entry in entries:
        prior=original[(entry["series"],entry["vintage"])]
        if {k:v for k,v in entry.items() if k!="root"} != {k:v for k,v in prior.items() if k!="root"}:
            raise ValueError("Economic publication locator changed identity")
    reader.catalog=dict(reader.catalog,snapshots=entries)
    reader.batch=read_json(root/"data_receipt.json")["economic_pin"]["batch"]
    _DATA=dict(root=root,protocol=read_json(root/"protocol.json"),bars=read_json(root/"bars.json"),reader=reader,
        controls={a:read_json(root/"controls"/(a+".json")) for a in ["F0","F3","RP"]})
    _DATA["opens"]={s:{r["trade_date"]:r["open"] for r in rows} for s,rows in _DATA["bars"].items()}
    if (root/"features.json").exists():
        checked_files(root,"feature_manifest.json")
        _DATA["features"]=read_json(root/"features.json")


def decision(day):
    data=_DATA;parent=data["controls"];known=date.fromisoformat(parent["F0"][day]["known_through"])
    if any(parent[a][day]["known_through"] != str(known) for a in parent):
        raise ValueError("Parent control cutoffs differ")
    cutoff=datetime.combine(known,us_equity_market_close(known),NY)
    vintage=str(known-timedelta(days=1))
    state=signal(data["reader"],vintage=vintage,known_at=cutoff)
    rows={"state":state}
    for arm,base in [("M0","F0"),("M3","F3")]:
        for suffix,s in [("",state)]:
            targets=apply_signal([AllocationTarget.model_validate(t) for t in parent[base][day]["targets"]],s)
            rows[arm+suffix]=dict(parent[base][day],targets=[t.model_dump(mode="json") for t in targets],
                economic=dict(s,parent=base,spy_removed=str(sum(D(t["target_weight"]) for t in parent[base][day]["targets"] if t["symbol"]=="SPY")-sum(t.target_weight for t in targets if t.symbol=="SPY"))))
    return day,rows


def freeze_features(root, rows):
    write_json(root/"features.json",rows)
    write_json(root/"feature_manifest.json",{"features.json":sha256(root/"features.json")})


def model_decision(day):
    data=_DATA
    model=fit_predict(day,data["controls"]["F0"][day]["known_through"],data["features"],data["opens"])
    output=dict(model=model)
    for base in ["F0","F3"]:
        r=data["controls"][base][day]
        for kind,prefix in [("tree","T"),("linear","L")]:
            targets=tilt([AllocationTarget.model_validate(t) for t in r["targets"]],model,kind)
            output[prefix+base[-1]]=dict(r,targets=[t.model_dump(mode="json") for t in targets],
                economic=dict(kind=kind,ready=model["ready"],reason=model["reason"],training_rows=model["training_rows"],
                              last_label_end=model["last_label_end"],training_sha256=model["training_sha256"]))
    return day,output


def freeze_decisions(root, rows, models):
    p=read_json(root/"protocol.json")
    values={a:read_json(root/"controls"/(a+".json")) for a in ["F0","F3","RP"]}
    values.update({a:{d:rows[d][a] for d in sorted(rows)} for a in ["M0","M3"]})
    values.update({a:{d:models[d][a] for d in sorted(models)} for a in ["T0","T3","L0","L3"]})
    calibration={}
    for arm,parent,candidate in [("C0","F0","M0"),("C3","F3","M3")]:
        c=calibrate_spy(values[parent],values[candidate],evaluation_start=p["evaluation_start"]);calibration[arm]=c
        values[arm]={d:dict(r,targets=[t.model_dump(mode="json") for t in scale_spy(
            [AllocationTarget.model_validate(t) for t in r["targets"]],D(c["scale"]))],economic=dict(constant_scale=c["scale"]))
            for d,r in values[parent].items() if d>=p["evaluation_start"]}
    for arm,r in values.items():write_json(root/"decisions"/(arm+".json"),r)
    write_json(root/"calibration.json",calibration)
    write_json(root/"economic_diagnostics.json",{d:rows[d]["state"] for d in sorted(rows)})
    write_json(root/"models.json",{d:models[d]["model"] for d in sorted(models)})
    paths=[*sorted((root/"decisions").glob("*.json")),root/"calibration.json",root/"economic_diagnostics.json",root/"models.json"]
    write_json(root/"decision_manifest.json",{f.relative_to(root).as_posix():sha256(f) for f in paths})


def economics(job):
    from systematic_trading.research.momentum_calculation import quotes_for_data
    data=_DATA;root=data["root"];p=data["protocol"];arm,cost,delay,period,lag=job
    checked_files(root,"decision_manifest.json")
    start=p["calibration_start"] if period=="full" else p["evaluation_start"]
    bars={"URTH":read_json(root/"urth.json")} if arm=="URTH" else data["bars"]
    days=[r["trade_date"] for r in data["bars"]["SPY"]]
    quotes,sessions=quotes_for_data(bars,days,start)
    if arm=="URTH":
        decisions={sessions[0]:dict(signal_session=sessions[0],known_through=days[days.index(sessions[0])-1],targets=[
            AllocationTarget(symbol="URTH",sleeve="benchmark",target_weight=D(1),rationale="buy and hold").model_dump(mode="json")])}
    else:decisions={d:r for d,r in read_json(root/"decisions"/(arm+("L" if lag else "")+".json")).items() if d>=start}
    if delay:decisions={sessions[sessions.index(d)+delay]:r for d,r in decisions.items() if sessions.index(d)+delay<len(sessions)}
    name=job_name(job);bundle=root/"bundles"/name
    recipe=dict(id=arm,name=LABELS[arm],period=period,delay_sessions=delay,macro_lag_rebalances=lag,
        economic_rule=SPEC if arm.startswith("M") else None,model_rule=MODEL_SPEC if arm.startswith(("T","L")) else None,
        calibration=read_json(root/"calibration.json").get(arm),version=p["version"])
    freeze_usd_bundle(bundle,root,recipe,decisions,quotes,sessions,cost)
    path=root/"python"/(name+".json")
    if path.exists():raise FileExistsError("Replay already exists: "+name)
    write_json(path,run_usd_reference(bundle))
    write_json(path.with_suffix(".receipt.json"),dict(sha256=sha256(path),manifest_sha256=sha256(bundle/"manifest.json")))
    return name
