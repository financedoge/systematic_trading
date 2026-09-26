"""App-owned monitored strategy calculations and immutable native LEAN evidence.

No broker, proposal persistence, agent scheduler, or production promotion path.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import json
import math
from pathlib import Path
from statistics import stdev

from systematic_trading.backtest.accounting import quantize_money
from systematic_trading.backtest.comparison import build_signal_diagnostics
from systematic_trading.backtest.reporting import build_backtest_report_data
from systematic_trading.lean.bundle import freeze_bundle
from systematic_trading.lean.contracts import sha256, verify_bundle
from systematic_trading.lean.registry import register_run
from systematic_trading.lean.runner import run_bundle, run_python_bundle
from systematic_trading.lean.strategy import targets_for_day
from systematic_trading.live.trading_calendar import is_us_trading_day
from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.research import current_sota_definition, instruments_for_definition
from systematic_trading.research.strategy_catalog import registered_strategy_definition, risk_parity_definition
from systematic_trading.research.tracked_inputs import load_tracked_inputs

SOURCE = "tracked-strategies/calculations"


def next_session(day):
    day = date.fromisoformat(str(day)) + timedelta(days=1)
    while not is_us_trading_day(day):
        day += timedelta(days=1)
    return day


def calculation_code_hashes():
    root = Path(__file__).resolve().parents[1]
    paths = [root / "research" / n for n in ("tracked_runtime.py", "tracked_inputs.py", "flow_concentration.py",
             "strategy_catalog.py", "sota_models.py", "chronological_tree.py")]
    paths += [p for folder in ("lean", "signals", "portfolio", "backtest")
              for p in (root / folder).glob("*.py") if p.name not in ("reporting.py", "comparison.py")]
    return {str(p.relative_to(root)): sha256(p) for p in paths}


_LOADED_CODE_HASHES = calculation_code_hashes()


def calculation_revision(config, inputs, definitions):
    if calculation_code_hashes() != _LOADED_CODE_HASHES:
        raise ValueError("Calculation source changed; restart the application before calculating the new version")
    return digest(encode(dict(runtime_contract=2, config=config, provenance=inputs["provenance"],
        definitions=[d.to_dict() for d in definitions], code=_LOADED_CODE_HASHES)))


def verified_run(bundle, output, image, engine="lean"):
    if engine not in ("lean", "python"):
        raise ValueError("Unsupported tracked calculation engine")
    if not (output / "run.json").exists():
        if engine == "lean":
            run_bundle(bundle=bundle, output=output, image=image)
        else:
            run_python_bundle(bundle=bundle, output=output)
    verified = verify_bundle(bundle)
    receipt = json.loads((output / "run.json").read_text(encoding="utf8"))
    if receipt["status"] != "succeeded" or receipt["manifest_sha256"] != sha256(bundle / "manifest.json"):
        raise ValueError("Tracked native run is incomplete or changed; keep last publication")
    for name, expected in receipt["artifacts"].items():
        if sha256(output / name) != expected:
            raise ValueError("Tracked run artifact changed: " + name)
    if engine == "lean":
        parity = json.loads((output / "parity.json").read_text(encoding="utf8"))
        if not parity["passed"] or parity["differences"]:
            raise ValueError("Tracked LEAN parity failed")
    elif receipt.get("engine") != "python":
        raise ValueError("Python calculation receipt has a different engine")
    return json.loads((output / "economic.json").read_text(encoding="utf8")), verified, receipt


def report_result(economic, quotes, initial, anchor):
    """Use actual simulated fills, never requested orders, for daily held weights."""
    fills = {}
    for fill in economic["fills"]:
        fills.setdefault(fill["date"], []).append(dict(symbol=fill["symbol"],
            side="buy" if fill["quantity"] > 0 else "sell", quantity=abs(fill["quantity"])))
    proposals = [dict(as_of=d, intended_trade_date=d, known_through=row["known_through"],
                      targets=row["targets"], orders=fills.get(d, [])) for d, row in economic["decisions"].items()]
    nav = [dict(trade_date=anchor, nav_cnh=initial, cash_cnh=initial, gross_exposure_cnh="0")]
    nav += [dict(trade_date=r["date"], nav_cnh=r["nav"], cash_cnh=r["cash"],
                 gross_exposure_cnh=str(Decimal(r["nav"]) - Decimal(r["cash"]))) for r in economic["nav"]]
    end = economic["nav"][-1]["date"]
    positions = [dict(symbol=s, quantity=n, market_price=quotes[s][end]["close"])
                 for s, n in economic["final_positions"].items() if n]
    return dict(nav_series=nav, proposals=proposals, final_snapshot=dict(nav_cnh=nav[-1]["nav_cnh"], positions=positions))


def buy_hold_benchmark(rows, fx, sessions, initial, anchor, cost_bps):
    by_day = {r["trade_date"]: r for r in rows}
    if any(day not in by_day for day in [anchor, *sessions]):
        raise ValueError("URTH benchmark is missing audited sessions")
    if any(not Decimal(by_day[d][k]).is_finite() or Decimal(by_day[d][k]) <= 0
           for d in [anchor, *sessions] for k in ("open", "close")):
        raise ValueError("URTH benchmark has unsupported adjusted prices")
    opening = quantize_money(Decimal(by_day[sessions[0]]["open"]) * Decimal(fx[anchor]))
    cash, cost = Decimal(initial), Decimal(cost_bps) / 10000
    quantity = int(cash / (opening * (1 + cost)))
    cash -= quantity * opening + quantize_money(quantity * opening * cost)
    return [dict(trade_date=anchor, nav_cnh=float(initial))] + [dict(trade_date=d,
        nav_cnh=float(cash + quantity * quantize_money(Decimal(by_day[d]["close"]) * Decimal(fx[d])))) for d in sessions]


def latest_allocation(definition, inputs, economic, quotes):
    known = inputs["provenance"]["price_through"]
    hypothetical_day = next_session(known)
    latest = targets_for_day(inputs["latest_bars"], hypothetical_day, definition=definition)
    last_day = max(economic["decisions"])
    scheduled = {t["symbol"]: float(t["target_weight"]) for t in economic["decisions"][last_day]["targets"]}
    target = {t.symbol: float(t.target_weight) for t in latest}
    end = economic["nav"][-1]
    nav = Decimal(end["nav"])
    instruments = instruments_for_definition(definition)
    holdings, countries, currencies = [], {}, {}
    for s in sorted(instruments):
        quantity = economic["final_positions"].get(s, 0)
        value = quantity * Decimal(quotes[s][end["date"]]["close"])
        holdings.append(dict(symbol=s, quantity=quantity, value_cnh=float(value), weight=float(value / nav),
            target_weight=target.get(s, 0), scheduled_weight=scheduled.get(s, 0)))
        country = str(instruments[s].country)
        countries[country] = countries.get(country, 0) + float(value)
        currencies["CNH"] = currencies.get("CNH", 0) + float(value)
    holdings.append(dict(symbol="Cash", quantity=None, value_cnh=float(end["cash"]), weight=float(Decimal(end["cash"])/nav),
        target_weight=1-sum(target.values()), scheduled_weight=1-sum(scheduled.values())))
    rebalance = hypothetical_day
    while rebalance.month == date.fromisoformat(known).month:
        rebalance = next_session(rebalance)
    return dict(holdings=holdings, targets=[t.model_dump(mode="json") for t in latest],
        valuation_date=end["date"], target_known_through=known, target_session=str(hypothetical_day),
        last_rebalance=last_day, next_rebalance=str(rebalance), nav_cnh=float(nav),
        cash_cnh=float(end["cash"]), gross_exposure_cnh=float(nav-Decimal(end["cash"])),
        country_exposure_cnh=countries, currency_exposure_cnh=currencies,
        notes="Held weights follow filled monthly rebalances and daily marks. Latest signal targets are indicative until the next scheduled rebalance; no order is placed.")


def refresh_tracked_strategies(settings, store, analytics):
    path = settings.strategy_monitoring_config_path
    config = json.loads(path.read_text(encoding="utf8")) if path.exists() else {}
    if config.get("schema_version") != 2:
        return False
    p = config["calculation"]
    keys = list(dict.fromkeys(config["monitored_strategy_ids"]))
    definitions = [registered_strategy_definition(k) for k in keys]
    if any(d.universe_key != "multi_asset" or d.scheduler != "static_monthly" for d in definitions):
        raise ValueError("Tracked definitions must implement the monthly multi-asset contract")
    sota = current_sota_definition()
    risk = replace(risk_parity_definition(), universe_key="multi_asset")
    all_definitions = {d.key: d for d in [sota, risk, *definitions]}
    inputs = load_tracked_inputs(settings, analytics, config)
    revision = calculation_revision(config, inputs, definitions)
    current = analytics.latest(SOURCE)
    if current and current["version"] == revision:
        return False
    root = settings.data_dir / "tracked_strategies" / revision
    economics, results, receipts, quotes_by_key = {}, {}, {}, {}
    days = [r["trade_date"] for r in next(iter(inputs["bars"].values()))]
    sessions = [d for d in days if d >= p["start"]]
    anchor = days[days.index(sessions[0])-1]
    for key, definition in all_definitions.items():
        bundle, output = root / "datasets" / key, root / "runs" / key
        tree = any(o.kind == "decision_tree" for o in definition.overlays)
        if not bundle.exists():
            freeze_bundle(root=bundle, bars=inputs["bars"], fx=inputs["fx"], provenance=inputs["provenance"],
                base_tree_models=inputs["models"] if tree else None,
                spec_values=dict(strategy="registered", strategy_definition=definition.to_dict(), mode="shared",
                    start_date=p["start"], end_date=sessions[-1], warmup_start=p["warmup_start"],
                    initial_cash_cnh=p["initial_cash_cnh"], transaction_cost_bps=p["transaction_cost_bps"],
                    slippage_bps=p["slippage_bps"], base_tree_model_schedule=tree,
                    fixed_model_from=p["fixed_model_from"] if tree else None,
                    fx_policy="legacy_carry_max7", limitations=p["limitations"]))
        economic, _, receipt = verified_run(bundle, output, p["image"], p.get("engine", "lean"))
        transactional = getattr(store, "transactional_store", store)
        if transactional.__class__.__name__ == "PostgresStore" and p.get("engine", "lean") == "lean":
            register_run(transactional, output)
        quotes = json.loads((bundle / "quotes.json").read_text(encoding="utf8"))
        economics[key], receipts[key], quotes_by_key[key] = economic, receipt, quotes
        results[key] = report_result(economic, quotes, p["initial_cash_cnh"], anchor)
        (root / (key + ".json")).write_text(encode(results[key]), encoding="utf8")
    urth = buy_hold_benchmark(inputs["urth"], inputs["fx"], sessions, p["initial_cash_cnh"], anchor, p["transaction_cost_bps"])
    documents, observations = [], []
    for definition in definitions:
        key = definition.key
        prices = {s: {d: float(q["close"]) for d, q in values.items()} for s, values in quotes_by_key[key].items()}
        for s in prices:
            prices[s][anchor] = float(quantize_money(Decimal(next(r for r in inputs["bars"][s] if r["trade_date"] == anchor)["close"])*Decimal(inputs["fx"][anchor])))
        attribution_baseline = risk.key if key == sota.key else sota.key
        diagnostics = build_signal_diagnostics(baseline=results[attribution_baseline], candidate=results[key],
            prices_by_symbol={s: {date.fromisoformat(d): v for d, v in rows.items()} for s, rows in prices.items()},
            split_date=date.fromisoformat(p["fixed_model_from"]), signal_name="Lag-20 activity tilt" if key != sota.key else "SOTA allocation and alpha overlays")
        report, warnings = build_backtest_report_data(result=results[key], result_path=root / (key+".json"),
            split_date=p["fixed_model_from"], benchmark_name="Risk parity · matched ETF universe",
            benchmark_nav_series=results[risk.key]["nav_series"],
            extra_benchmarks=[dict(id="urth", name="URTH · MSCI World", nav_series=urth),
                              dict(id="sota", name="Current SOTA · matched model history", nav_series=results[sota.key]["nav_series"])],
            market_prices=prices, market_fx_rates={d: 1.0 for d in [anchor, *sessions]}, signal_diagnostics=diagnostics)
        current_allocation = latest_allocation(definition, inputs, economics[key], quotes_by_key[key])
        from systematic_trading.research.strategy_diagram import decision_diagrams
        report.update(title=definition.name, database="Published audited histories / ClickHouse",
            signalBenchmark="Risk parity" if key == sota.key else "Current SOTA",
            modelRegime="2016–2022 causal annual fits; deployed frozen tree from 2023",
            splitLabel="Deployed frozen model begins", sampleLabels={"in_sample": "Causal reconstruction", "out_of_sample": "Frozen model"},
            currentAllocation=current_allocation, strategyDefinition=definition.to_dict(),
            decisionDiagrams=decision_diagrams(definition),
            monitoring=dict(lifecycle="monitored", method=config["method"], artifactEndDate=sessions[-1],
                monitoredThrough=sessions[-1], calculationOwner="application", computedAt=datetime.now(UTC).isoformat(),
                engine=p.get("engine", "lean"),
                priceThrough=inputs["provenance"]["price_through"], revision=revision, prospectiveStart=p["prospective_start"],
                prospectiveObservations=sum(d >= p["prospective_start"] for d in sessions)),
            warnings=[*warnings, *p["limitations"], current_allocation["notes"],
                "The first chart point is initial capital before the first simulated trade.",
                "CNH weights are adjusted-unit accounting exposures; the underlying ETFs quote in USD."])
        if inputs["provenance"]["first_missing_fx"]:
            report["warnings"].append("Valuation stops before missing supported FX on " + inputs["provenance"]["first_missing_fx"])
        summary = report["summary"]
        nav = [float(r["nav_cnh"]) for r in results[key]["nav_series"]]
        volatility = stdev([b/a-1 for a, b in zip(nav, nav[1:])])*math.sqrt(252)
        detail = dict(strategy_id=key, name=definition.name, is_sota=key == sota.key, lifecycle="monitored",
            app_tracking=True, report_available=True, report_url=f"/api/v1/strategies/{key}/report",
            artifact_path=str(root), artifact_end_date=sessions[-1], start_date=sessions[0], end_date=sessions[-1],
            observations=len(sessions), initial_nav_cnh=float(p["initial_cash_cnh"]),
            final_nav_cnh=current_allocation["nav_cnh"], total_return=summary["totalReturn"],
            annualized_return=summary["annualizedReturn"], annualized_volatility=volatility,
            sharpe=summary["sharpe"], max_drawdown=summary["maxDrawdown"],
            calmar=summary["annualizedReturn"]/abs(summary["maxDrawdown"]) if summary["maxDrawdown"] else None,
            allocation=current_allocation["holdings"], holdings=current_allocation["holdings"],
            current_allocation=current_allocation, monitoring_method=config["method"], monitoring_notes=config["notes"],
            promotion_eligible=False, execution_enabled=False, strategy_definition=definition.to_dict(),
            nav_series=results[key]["nav_series"], benchmark_series=results[risk.key]["nav_series"],
            warnings=report["warnings"], input_provenance=inputs["provenance"], lean_receipts=receipts)
        documents += [dict(point_key="detail/"+key, media_type="application/json", payload=encode(detail)),
                      dict(point_key="report/"+key, media_type="application/json", payload=encode(report))]
        observations += [dict(point_key=key+"/"+row["trade_date"], family="tracked_strategy_nav", entity=key,
            observed_at=row["trade_date"], available_at=datetime.now(UTC).isoformat(), payload=encode(row)) for row in results[key]["nav_series"]]
        observations += [dict(point_key=key+"/allocation", family="tracked_strategy_allocation", entity=key,
            observed_at=current_allocation["target_known_through"], available_at=datetime.now(UTC).isoformat(), payload=encode(current_allocation))]
    # Commit all strategies and benchmarks together. Readers retain the previous
    # complete version on failure; an incomplete native run never becomes NAV.
    if analytics.latest("governance/catalog")["version"] != inputs["provenance"]["batch"]:
        raise ValueError("Audited batch changed during calculation; retry against the new publication")
    if calculation_revision(config, inputs, definitions) != revision:
        raise ValueError("Calculation implementation changed before publication")
    documents.append(dict(point_key="catalog", media_type="application/json", payload=encode(keys)))
    return analytics.publish(SOURCE, revision, observations, documents,
        provenance=dict(owner="application", inputs=inputs["provenance"], config=config,
                        native_runs={k: r["run_id"] for k, r in receipts.items()}))


def published_strategies(analytics):
    catalog = analytics.document(SOURCE, "catalog")
    if not catalog:
        return {}
    publication = catalog[1]
    result = {}
    for key in json.loads(catalog[0]["payload"]):
        detail, dp = analytics.document(SOURCE, "detail/"+key)
        report, rp = analytics.document(SOURCE, "report/"+key)
        if dp["version"] != publication["version"] or rp["version"] != publication["version"]:
            raise ValueError("Tracked publication changed while reading")
        result[key] = (json.loads(detail["payload"]), json.loads(report["payload"]))
    return result
