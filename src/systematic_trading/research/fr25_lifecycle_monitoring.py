"""Monitored-family calculation for the FR25 conditional candidate.

Called by the application tracked runtime for the registered key. Produces the standard
detail/report documents and NAV/allocation observations from the frozen app-module
calculation. Research/paper candidate only; no broker authority.
"""
from __future__ import annotations

from datetime import datetime, UTC
from decimal import Decimal
import json

import numpy as np

from systematic_trading.research import fr25_lifecycle_conditional as candidate
from systematic_trading.market_data.analytics_store import encode
from systematic_trading.backtest.accounting import quantize_money

SOURCE = "tracked-strategies/calculations"


def current_allocation(calculation):
    """Report actual filled holdings separately from adopted and indicative targets."""
    end = calculation["nav_series"][-1]
    nav, cash = float(end["nav_cnh"]), float(end["cash_cnh"])
    latest = {r["symbol"]: float(r["target_weight"]) for r in calculation["latest_targets"]}
    proposals = calculation["proposals"]
    scheduled = {r["symbol"]: float(r["target_weight"]) for r in proposals[-1]["targets"]} if proposals else {}
    positions = {r["symbol"]: r for r in calculation["final_snapshot"]["positions"]}
    holdings = []
    for symbol in sorted(positions.keys() | latest.keys() | scheduled.keys()):
        position = positions.get(symbol, {})
        quantity = position.get("quantity", 0)
        value = quantity * float(position.get("market_price", 0))
        holdings.append(dict(symbol=symbol, quantity=quantity, value_cnh=value, weight=value / nav,
                             target_weight=latest.get(symbol, 0), scheduled_weight=scheduled.get(symbol, 0)))
    holdings.append(dict(symbol="Cash", quantity=None, value_cnh=cash, weight=cash / nav,
                         target_weight=1-sum(latest.values()), scheduled_weight=1-sum(scheduled.values())))
    return dict(holdings=holdings, targets=calculation["latest_targets"],
                valuation_date=end["trade_date"], target_known_through=end["trade_date"],
                target_session="Unavailable beyond frozen input",
                last_rebalance=proposals[-1]["intended_trade_date"] if proposals else None,
                next_rebalance="Unavailable beyond frozen input", nav_cnh=nav, cash_cnh=cash,
                gross_exposure_cnh=float(end["gross_exposure_cnh"]),
                country_exposure_cnh={k: float(v) for k, v in calculation["final_snapshot"]["country_exposure_cnh"].items()},
                currency_exposure_cnh={"USD": nav},
                notes="USD historical replay through 2026-10-12. Cash and holdings use actual simulated fills. "
                      "Indicative targets differ from last adopted targets; current signal extension is pending.")


def decision_diagrams():
    from systematic_trading.research.strategy_diagram import label
    steps = [
        ("Verify the frozen 52-ETF panel and published source hashes", "Adjusted OHLC for returns; audited raw volume for lifecycle signals; USD accounting."),
        ("FR25 core and Rule A short-entry sleeve", "Preserve core cash; six slots; extension-score ties; BIL parking when empty."),
        ("Monthly condition: stable union breadth at least 36/52", "Pre-2023 threshold; ON = 80% FR25 + 20% sleeve; OFF = FR25."),
        ("Month-end anchor or target L1 change at least 10%", "Compare theoretical versus last adopted target, including residual cash."),
        ("Size at decision close; fill next-session open; charge every trade", "Opening price is a daily-data proxy, not observed TWAP; test +1 session separately."),
        ("Mark actual filled quantities and cash; compare with matched controls", "Frozen panel ends 2026-10-12. No current signal, allocation or execution authority."),
    ]
    body = []
    for i, (title, note) in enumerate(steps):
        y = 15 + i * 85
        body.append(f'<rect x="10" y="{y}" width="880" height="70" rx="8" fill="#eef4fa"/>')
        body.append(label([title, note], 25, y + 25))
    return [dict(title="Conditional FR25 lifecycle decision flow",
                 note="Implementation v" + candidate.VERSION,
                 svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 530">' + "".join(body) + "</svg>")]


def calculate_monitored(settings, analytics, config, definitions, selected_sota, root,
                        code_hashes, inputs=None):
    key = candidate.KEY
    p = config["calculation"]
    if float(p.get("slippage_bps", 0)) != 0:
        raise ValueError("Conditional replay does not implement a separate slippage model")
    cost = float(p["transaction_cost_bps"])
    calculation = candidate.calculate_tracked(cost_bp=cost, delay=0)
    if inputs is not None and inputs["provenance"].get("fr25_conditional") != calculation["input_provenance"]:
        raise ValueError("Conditional input identity differs from the calculation revision")
    nav_rows = calculation["nav_series"]
    nav = np.array([float(row["nav_cnh"]) for row in nav_rows])
    sessions = [row["trade_date"] for row in nav_rows]
    initial = float(nav[0])
    result = {k: calculation[k] for k in ("nav_series", "proposals", "final_snapshot")}
    definition = definitions[0]
    (root / (key + ".json")).write_text(json.dumps(result, indent=1), encoding="utf-8")
    # Market prices for the report charts (pinned audited panel, same batch as calculation).
    panel = candidate._load_panel()
    days = [str(np.datetime64(d, "D")) for d in panel["days"]]
    window = {d for d in days if d >= sessions[0]}
    symbols = [str(s) for s in panel["symbols"]]
    prices = {s: {d: float(quantize_money(Decimal(str(panel["close"][i, j]))))
                  for i, d in enumerate(days) if d in window}
              for j, s in enumerate(symbols)}
    prices["URTH"] = {d: float(quantize_money(Decimal(str(panel["urth_close"][i]))))
                      for i, d in enumerate(days) if d in window}
    # Benchmarks from the same engine: FR25 monthly and URTH buy-hold.
    benchmark = candidate._Replay(panel, json.loads(candidate.RECIPE_PATH.read_text(encoding="utf-8")),
                                  candidate.OOS_START)
    fr25 = np.column_stack([panel["fr25"], np.zeros(panel["close"].shape[0])])
    monthly = candidate._monthly_indices(panel)
    fr25_result, fr25_fills = benchmark.run_result(fr25, monthly, cost, 0)
    fr25_series = candidate.report_payload(benchmark, fr25_result, fr25_fills)["nav_series"]
    urth_targets = np.zeros((panel["close"].shape[0], len(symbols) + 1))
    urth_targets[monthly[0], -1] = 0.98
    urth_result, urth_fills = benchmark.run_result(urth_targets, monthly[:1], cost, 0)
    urth_series = candidate.report_payload(benchmark, urth_result, urth_fills)["nav_series"]
    from systematic_trading.backtest.reporting import build_backtest_report_data
    report, warnings = build_backtest_report_data(
        result=result, result_path=root / (key + ".json"), split_date="2023-01-01",
        benchmark_nav_series=fr25_series, benchmark_name="Frozen FR25 · matched USD",
        extra_benchmarks=[dict(id="urth", name="URTH", nav_series=urth_series)],
        market_prices=prices, market_fx_rates={d: 1.0 for d in [sessions[0], *sessions]})
    current = current_allocation(calculation)
    report.update(
        title=definition.name,
        accountingCurrency="USD",
        database="Published audited histories",
        modelRegime="Frozen FR25 + conditional Rule A; implementation " + candidate.VERSION,
        splitLabel="Inspected development boundary",
        sampleLabels={"in_sample": "Initial cash anchor", "out_of_sample": "2023–2026 inspected development"},
        decisionDiagrams=decision_diagrams(),
        strategyDefinition=definition.to_dict(),
        monitoring=dict(
            lifecycle="monitored", method="app_verified_frozen_usd_replay",
            artifactEndDate=sessions[-1], monitoredThrough=sessions[-1],
            calculationOwner="application",
            computedAt=datetime.now(UTC).isoformat(), engine="python",
            priceThrough=sessions[-1],
            revision=root.name,
            prospectiveStart="2026-10-20", prospectiveObservations=0,
            generation=config.get("monitoring_generations", {}).get(key, 0),
            status="historical_only", currentSignalAvailable=False,
        ),
        currentAllocation=current,
        warnings=[*warnings, *calculation["input_provenance"]["limitations"],
                  "USD replay, not CNH. Legacy internal money-field names do not imply FX conversion.",
                  "Monitoring implementation is incomplete: frozen FR25 and breadth inputs cannot catch up "
                  "when new prices arrive. Current targets and runtime verification of their extension remain unavailable.",
                  "2023-2026 is an inspected development retest. Earlier candidate metrics are superseded "
                  "by the implementation review and corrected timing/cost retest."],
    )
    returns = nav[1:] / nav[:-1] - 1.0
    annualized = (nav[-1] / nav[0]) ** (252.0 / max(1, len(nav) - 1)) - 1.0
    volatility = float(returns.std(ddof=1) * np.sqrt(252.0))
    sharpe = float(returns.mean() / returns.std(ddof=1) * np.sqrt(252.0)) if returns.std(ddof=1) > 0 else 0.0
    peak = np.maximum.accumulate(nav)
    max_drawdown = float((nav / peak - 1.0).min())
    summary = dict(totalReturn=float(nav[-1] / nav[0] - 1.0), annualizedReturn=float(annualized),
                   annualizedVolatility=volatility, sharpe=sharpe, maxDrawdown=max_drawdown)
    detail = dict(
        strategy_id=key, name=definition.name, is_sota=key == selected_sota.key,
        lifecycle="monitored", accounting_currency="USD", app_tracking=True,
        tracking_status="historical_only", current_signal_available=False,
        monitoring_generation=config.get("monitoring_generations", {}).get(key, 0),
        report_available=True, report_url=f"/api/v1/strategies/{key}/report",
        artifact_path=str(root), artifact_end_date=sessions[-1], start_date=sessions[0],
        end_date=sessions[-1], observations=len(nav)-1, initial_nav_cnh=initial,
        final_nav_cnh=float(nav[-1]), total_return=summary["totalReturn"],
        annualized_return=summary["annualizedReturn"], sharpe=summary["sharpe"],
        annualized_volatility=summary["annualizedVolatility"],
        max_drawdown=summary["maxDrawdown"],
        calmar=float(summary["annualizedReturn"] / abs(summary["maxDrawdown"])) if summary["maxDrawdown"] else None,
        allocation=current["targets"], holdings=current["holdings"],
        current_allocation=current, monitoring_method="app_verified_frozen_usd_replay",
        monitoring_notes=config["notes"], promotion_eligible=False, execution_enabled=False,
        strategy_definition=definition.to_dict(), nav_series=result["nav_series"],
        benchmark_series=fr25_series, warnings=report["warnings"],
        input_provenance=calculation["input_provenance"],
        lean_receipts={}, model_training=None, usd_model=None,
    )
    documents = [dict(point_key="detail/" + key, media_type="application/json",
                      payload=encode(detail)),
                 dict(point_key="report/" + key, media_type="application/json",
                      payload=encode(report))]
    observations = [dict(point_key=key + "/" + row["trade_date"], family="tracked_strategy_nav",
                         entity=key, observed_at=row["trade_date"],
                         available_at=datetime.now(UTC).isoformat(),
                         payload=encode(row))
                    for row in result["nav_series"]]
    observations.append(dict(point_key=key + "/latest", family="tracked_strategy_allocation", entity=key,
                             observed_at=sessions[-1], available_at=datetime.now(UTC).isoformat(),
                             payload=encode(current)))
    provenance = dict(calculation["input_provenance"], owner="application", family="fr25_lifecycle_conditional")
    return documents, observations, provenance
