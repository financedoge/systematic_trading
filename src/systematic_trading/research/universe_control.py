"""Finite price-only universe control on published, hash-verified histories."""
from datetime import UTC, date, datetime
from decimal import Decimal as D
import json
from pathlib import Path
import shutil

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.etf_admission import admission_hold
from systematic_trading.research.momentum_replay import read_json, checked_files, freeze_usd_bundle, run_usd_reference

ARMS = ["RP12", "RP14", "F3", "URTH"]
LABELS = dict(RP12="Original 12 ETFs · inverse volatility", RP14="Add XLE/XLB · inverse volatility",
              F3="Current SOTA · defensive cash", URTH="Global equities · URTH")
_DATA = None


def protocol(end):
    return dict(version="energy-materials-universe-control-v1", registered_at=datetime.now(UTC).isoformat(),
        question="Does adding the admitted energy/materials ETFs improve the unchanged price-only inverse-volatility portfolio?",
        start="2016-01-04", warmup_start="2012-01-05", end=end, evaluation_start="2021-01-04",
        arms=LABELS, additions=["XLE", "XLB"], excluded={"XOP":"Issuer/provider listing boundary unresolved"},
        primary_contrast=["RP14", "RP12"], comparison_family_size=1,
        primary_window="Full 2016–end period; 2021 split is report context only",
        initial_cash_usd="1000000", currency="USD", cash_interest="zero", risk_free="zero, scenario only",
        rule=dict(volatility_lookback=63, max_target_weight="0.45", cash_floor="0.02",
                  decisions="monthly; completed prior close", execution="next session open; whole adjusted units",
                  signal="inverse volatility only; no volume, fundamentals, forecasts or membership ranking"),
        cost_bps=[5,10,20], delayed_sessions=1, bootstrap_blocks=[3,6,12], bootstrap_replications=10000,
        seed=20261009, promotion_eligible=False,
        retention_screen=dict(min_sharpe_gain=.05, min_calmar_gain=.05, max_cagr_sacrifice=.005,
                              max_drawdown_worsening=.01, require_cost_delay_consistency=True),
        decision_rule="Report the declared screen and paired uncertainty. Inconclusive evidence does not establish diversification alpha. No tuning or automatic promotion.",
        limitations=[
            "Previously inspected 2016–2026 history; 2021 split is chronological context, not an untouched holdout.",
            "Today's ETF selection and identity verification do not establish a point-in-time historical selection process.",
            "Published adjusted prices are audited reconstructed vintages, not certified historical dissemination or a reinvestment total-return index.",
            "New universe arms consume adjusted price returns only. Source volumes are unused; no new traded-activity signal is calculated.",
            "F3 is a frozen existing-strategy benchmark with inherited source-volume proxy and model limitations; this study does not refit or broaden its signals.",
            "USD accounting only; uncertified historical USD/CNH is excluded. Zero cash interest and zero-reference Sharpe are explicit scenarios.",
            "XLE/XLB overlap SPY; more ETF names do not establish independent economic exposures. Historical holdings overlap is unavailable.",
            "XOP is excluded before performance inspection because listing-date evidence conflicts. No substitute instrument or history trimming.",
            "Issuer/EIA/CFTC first captures cannot enter earlier decisions; holdings residuals and split-aware issuance remain unresolved.",
            "Costs are 5/10/20bp per traded dollar; spread/market impact and taxes are not separately modeled. Caps apply at targets, not between rebalances.",
            "IB ISIN lookup verifies current contract identity only. Account/product permissions and settlement eligibility remain unverified; no orders.",
            "This isolates the opportunity set under inverse-volatility sizing. It does not establish the benefit of an expanded F3/XGBoost strategy.",
        ])


def prepare(root, broker_path):
    from systematic_trading.config import AppSettings
    from systematic_trading.market_data.analytics_store import AnalyticsStore
    from systematic_trading.research.governed_inputs import GovernedInputs, etf_bar
    from systematic_trading.storage.factory import create_trading_store
    from systematic_trading.portfolio.strategy_allocation import control_state
    from systematic_trading.lean.contracts import verify_bundle
    from systematic_trading.research.momentum_replay import verify_usd_bundle
    from systematic_trading.research.strategy_catalog import defensive_cash_definition
    if root.exists():
        raise FileExistsError("Frozen universe study already exists")
    settings=AppSettings(transactional_store_backend="postgres",market_data_store_backend="clickhouse")
    state=control_state(create_trading_store(settings))
    if state["sota_key"] != "research_fallback_f3_v1":
        raise ValueError("Current SOTA differs; reconsider the benchmark before outcomes")
    analytics=AnalyticsStore.from_settings(settings);pub=analytics.latest("governance/catalog")
    tracked=analytics.latest("tracked-strategies/calculations")
    app_root=settings.data_dir/"tracked_strategies"/tracked["version"]
    parent=app_root/"usd"
    baseline=parent/"bundles/research_fallback_f3_v1"
    checked_files(parent,"input_manifest.json")
    baseline_spec=verify_usd_bundle(baseline)["spec"]
    if baseline_spec.recipe != defensive_cash_definition().to_dict():
        raise ValueError("Published F3 definition differs")
    dataset=app_root/"datasets/research_rolling_xgboost_1y_lag20_v1_usd_v1"
    verify_bundle(dataset)
    p=protocol(baseline_spec.end_date)
    reader=GovernedInputs(Path(json.loads(pub["provenance"])["root"]),pub["version"])
    registry=read_json(settings.research_etf_recorder_config_path)
    broker=read_json(broker_path)
    if broker["status"] != "identity_verified" or broker["environment"] != "paper":
        raise ValueError("Read-only broker identity evidence required")
    previous=read_json(dataset/"bars.json");symbols=sorted(previous)
    if set(symbols) & set(p["additions"]):
        raise ValueError("Expanded symbols already in parent")
    bars={s:[etf_bar(r) for r in reader.rows(s,p["warmup_start"],p["end"])] for s in [*symbols,*p["additions"]]}
    if any(bars[s] != previous[s] for s in symbols):
        raise ValueError("Frozen F3 benchmark inputs differ; rebaseline before comparison")
    days=[r["trade_date"] for r in bars["SPY"]]
    if any([r["trade_date"] for r in rows] != days for rows in bars.values()):
        raise ValueError("Incomplete common-calendar input; no filling")
    audits={s:reader.audit(s) for s in bars}
    for s in p["additions"]:
        fund=next(f for f in registry["funds"] if f["symbol"]==s)
        audit=audits[s]
        if (admission_hold(s, fund.get("admission_hold")) or audit["status"] != "audited_with_limitations"
                or audit.get("research_recorder",{}).get("isin") != fund["isin"]
                or broker["funds"][s]["lookup"]["secId"] != fund["isin"]
                or broker["funds"][s]["status"] != "identity_verified"):
            raise ValueError("Fund admission evidence incomplete: "+s)
    urth=[dict(trade_date=r["trade_date"],open=str(r["adjusted_open"]),close=str(r["adjusted_close"]))
          for r in reader.rows("URTH",p["warmup_start"],p["end"])]
    root.mkdir(parents=True)
    shutil.copytree(Path(__file__).parents[1],root/"source/systematic_trading",ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    shutil.copy2(Path(__file__).parents[3]/"scripts/run_universe_control.py",root/"runner.py")
    write_json(root/"protocol.json",p);write_json(root/"bars.json",bars);write_json(root/"urth.json",urth)
    write_json(root/"control.json",read_json(baseline/"decisions.json"))
    write_json(root/"baseline_economic.json",read_json(parent/"python/research_fallback_f3_v1.json"))
    from systematic_trading.research.momentum_calculation import quotes_for_data
    current_quotes,_=quotes_for_data({s:bars[s] for s in symbols},days,p["start"])
    if current_quotes != read_json(baseline/"quotes.json"):
        raise ValueError("Published F3 execution quotes differ")
    write_json(root/"data_receipt.json",dict(batch=pub["version"],publication=pub,governed_files=reader.used,
        parent=str(parent.resolve()),parent_input_sha256=sha256(parent/"input_manifest.json"),
        parent_bundle_sha256=sha256(baseline/"manifest.json"),tracked_publication=tracked,original_symbols=symbols,
        additions_audit={s:audits[s] for s in p["additions"]},broker=broker,broker_sha256=sha256(broker_path),
        control_state=state,original_prices_exact=True,image=json.loads(tracked["provenance"])["config"]["calculation"]["image"]))
    write_json(root/"input_manifest.json",{f.relative_to(root).as_posix():sha256(f) for f in root.rglob("*") if f.is_file()})
    return dict(root=str(root),batch=pub["version"],protocol_sha256=sha256(root/"protocol.json"),arms=ARMS)


def initialize(root):
    global _DATA
    from systematic_trading.domain.market import PriceBar
    root=Path(root);checked_files(root,"input_manifest.json")
    bars=read_json(root/"bars.json")
    _DATA=dict(root=root,bars=bars,typed={s:[PriceBar.model_validate(r) for r in v] for s,v in bars.items()},
        days=[r["trade_date"] for r in bars["SPY"]],protocol=read_json(root/"protocol.json"),
        receipt=read_json(root/"data_receipt.json"),control=read_json(root/"control.json"))


def decision(day):
    from systematic_trading.backtest.stored import _target_schedule
    from systematic_trading.research.momentum_replay import usd_instruments
    data=_DATA;i=data["days"].index(day);output={}
    for arm,symbols in [("RP12",data["receipt"]["original_symbols"]),("RP14",sorted(data["bars"]))]:
        histories={s:data["typed"][s][max(0,i-500):i] for s in symbols}
        targets=_target_schedule(instruments={s:usd_instruments()[s] for s in symbols},bars_by_symbol=histories,
            trade_dates=[date.fromisoformat(day)],rebalance_frequency="daily",lookback_bars=63,
            max_weight=D(".45"),cash_reserve_weight=D(".02"),sleeve_name=arm,target_overlays=[])[date.fromisoformat(day)]
        output[arm]=dict(signal_session=day,known_through=data["days"][i-1],targets=[t.model_dump(mode="json") for t in targets])
    return day,output


def freeze_decisions(root, records):
    from systematic_trading.domain.portfolio import AllocationTarget
    values={arm:{day:records[day][arm] for day in sorted(records)} for arm in ["RP12","RP14"]}
    values["F3"]=read_json(root/"control.json")
    first=min(records)
    values["URTH"]={first:dict(signal_session=first,known_through=values["F3"][first]["known_through"],targets=[
        AllocationTarget(symbol="URTH",sleeve="benchmark",target_weight=D(1),rationale="buy and hold").model_dump(mode="json")])}
    for arm,rows in values.items():
        write_json(root/"decisions"/(arm+".json"),rows)
    write_json(root/"decision_manifest.json",{f.relative_to(root).as_posix():sha256(f) for f in (root/"decisions").glob("*.json")})


def jobs():
    return [(a,c,0) for a in ARMS for c in [5,10,20]]+[(a,5,1) for a in ["RP12","RP14"]]


def job_name(job):
    return f"{job[0]}-cost{job[1]}-delay{job[2]}"


def economics(job):
    from systematic_trading.research.momentum_calculation import quotes_for_data
    data=_DATA;root=data["root"];arm,cost,delay=job
    checked_files(root,"decision_manifest.json")
    symbols=(data["receipt"]["original_symbols"] if arm in ["RP12","F3"] else sorted(data["bars"]))
    bars={s:data["bars"][s] for s in symbols} if arm!="URTH" else {"URTH":read_json(root/"urth.json")}
    quotes,sessions=quotes_for_data(bars,data["days"],data["protocol"]["start"])
    decisions=read_json(root/"decisions"/(arm+".json"))
    if delay:
        decisions={sessions[sessions.index(d)+delay]:r for d,r in decisions.items() if sessions.index(d)+delay<len(sessions)}
    name=job_name(job);bundle=root/"bundles"/name
    freeze_usd_bundle(bundle,root,dict(id=arm,delay_sessions=delay),decisions,quotes,sessions,cost)
    output=root/"python"/(name+".json")
    if output.exists():
        raise FileExistsError("Preserve completed replay: "+name)
    write_json(output,run_usd_reference(bundle))
    write_json(output.with_suffix(".receipt.json"),dict(sha256=sha256(output),manifest_sha256=sha256(bundle/"manifest.json")))
    return name
