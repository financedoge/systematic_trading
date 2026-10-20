"""Monitored-family calculation for the FR25 conditional candidate.

Called by the application tracked runtime for the registered key. Produces the standard
detail/report documents and NAV/allocation observations from the frozen app-module
calculation. Research/paper candidate only; no broker authority.
"""
from __future__ import annotations

from datetime import datetime, UTC
import json

import numpy as np

from systematic_trading.research import fr25_lifecycle_conditional as candidate

SOURCE = "tracked-strategies/calculations"


def calculate_monitored(settings, analytics, config, definitions, selected_sota, root,
                        code_hashes, inputs=None):
    key = candidate.KEY
    calculation = candidate.calculate_tracked(cost_bp=5.0, delay=0)
    nav_rows = calculation["nav_series"]
    nav = np.array([float(row["nav_cnh"]) for row in nav_rows])
    sessions = [row["trade_date"] for row in nav_rows]
    initial = float(nav[0])
    result = dict(
        nav_series=[dict(trade_date=d, nav_cnh=str(nav[i]), cash_cnh=str(nav[i] * 0.02),
                         gross_exposure_cnh=str(nav[i] * 0.98))
                    for i, d in enumerate(sessions)],
        proposals=calculation["proposals"],
        final_snapshot=dict(nav_cnh=str(nav[-1]), positions=calculation["final_snapshot"]["positions"]),
    )
    definition = definitions[0]
    (root / (key + ".json")).write_text(json.dumps(result, indent=1), encoding="utf-8")
    # Market prices for the report charts (pinned audited panel, same batch as calculation).
    panel = dict(np.load(candidate.INPUTS_PATH, allow_pickle=True))
    days = [str(np.datetime64(d, "D")) for d in panel["days"]]
    window = [d for d in days if d >= sessions[0]]
    symbols = [str(s) for s in panel["symbols"]]
    prices = {s: {d: float(panel["close"][i, j]) for i, d in enumerate(days) if d in set(window)}
              for j, s in enumerate(symbols)}
    prices["URTH"] = {d: float(panel["urth_close"][i]) for i, d in enumerate(days) if d in set(window)}
    # Benchmarks from the same engine: FR25 monthly and URTH buy-hold.
    benchmark = candidate._Replay(panel, json.loads(candidate.RECIPE_PATH.read_text(encoding="utf-8")),
                                  candidate.OOS_START)
    fr25 = np.column_stack([panel["fr25"], np.zeros(panel["close"].shape[0])])
    monthly = candidate._monthly_indices(panel)
    fr25_nav, _ = benchmark.run(fr25, monthly, 5.0, 0)
    fr25_series = [dict(trade_date=str(d), nav_cnh=str(float(fr25_nav[i])))
                   for i, d in enumerate(benchmark.days)]
    urth_targets = np.zeros((panel["close"].shape[0], len(symbols) + 1))
    urth_targets[monthly[0], -1] = 0.98
    urth_nav, _ = benchmark.run(urth_targets, monthly[:1], 5.0, 0)
    urth_series = [dict(trade_date=str(d), nav_cnh=str(float(urth_nav[i])))
                   for i, d in enumerate(benchmark.days)]
    from systematic_trading.backtest.reporting import build_backtest_report_data
    report, warnings = build_backtest_report_data(
        result=result, result_path=root / (key + ".json"), split_date="2023-01-01",
        benchmark_nav_series=fr25_series, benchmark_name="FR25 SOTA",
        extra_benchmarks=[dict(id="urth", name="URTH", nav_series=urth_series)],
        market_prices=prices, market_fx_rates={d: 1.0 for d in [sessions[0], *sessions]})
    current = dict(
        target_known_through=sessions[-1], nav_cnh=str(nav[-1]),
        holdings=calculation["final_snapshot"]["positions"],
        targets=calculation["latest_targets"] if "latest_targets" in calculation else [],
        notes=("Frozen FR25 core plus conditional short life-cycle sleeve; candidate monitoring "
               "calculation from the app-owned module and pinned audited inputs."),
    )
    report.update(
        title=definition.name,
        database="Published audited histories",
        strategyDefinition=definition.to_dict(),
        monitoring=dict(
            lifecycle="monitored", method=config["method"],
            artifactEndDate=sessions[-1], monitoredThrough=sessions[-1],
            calculationOwner="application",
            computedAt=datetime.now(UTC).isoformat(), engine="python",
            priceThrough=sessions[-1],
            revision=str(code_hashes.get("source", ""))[:16],
            prospectiveStart=config["calculation"].get("prospective_start"),
        ),
        currentAllocation=current,
        warnings=[*warnings, *config["calculation"].get("limitations", []),
                  "Candidate calculation: 2023-2026 is an inspected development retest; "
                  "+1-session delay weakness disclosed on the candidate page."],
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
        lifecycle="monitored", accounting_currency="CNH", app_tracking=True,
        report_available=True, report_url=f"/api/v1/strategies/{key}/report",
        artifact_path=str(root), artifact_end_date=sessions[-1], start_date=sessions[0],
        end_date=sessions[-1], observations=len(nav), initial_nav_cnh=initial,
        final_nav_cnh=float(nav[-1]), total_return=summary["totalReturn"],
        annualized_return=summary["annualizedReturn"], sharpe=summary["sharpe"],
        annualized_volatility=summary["annualizedVolatility"],
        max_drawdown=summary["maxDrawdown"],
        calmar=float(summary["annualizedReturn"] / abs(summary["maxDrawdown"])) if summary["maxDrawdown"] else None,
        allocation=[], holdings=[],
        current_allocation=current, monitoring_method=config["method"],
        monitoring_notes=config["notes"], promotion_eligible=False, execution_enabled=False,
        strategy_definition=definition.to_dict(), nav_series=result["nav_series"],
        benchmark_series=fr25_series, warnings=report["warnings"],
        input_provenance=dict(panel=str(candidate.INPUTS_PATH),
                              panel_sha256=json.loads(candidate.PARAMETERS_PATH.read_text(encoding="utf-8"))["source"]["panel_sha256"],
                              parameters_sha256=__import__("hashlib").sha256(candidate.PARAMETERS_PATH.read_bytes()).hexdigest()),
        lean_receipts={}, model_training=None, usd_model=None,
    )
    documents = [dict(point_key="detail/" + key, media_type="application/json",
                      payload=__import__("systematic_trading.market_data.analytics_store", fromlist=["encode"]).encode(detail)),
                 dict(point_key="report/" + key, media_type="application/json",
                      payload=__import__("systematic_trading.market_data.analytics_store", fromlist=["encode"]).encode(report))]
    observations = [dict(point_key=key + "/" + row["trade_date"], family="tracked_strategy_nav",
                         entity=key, observed_at=row["trade_date"],
                         available_at=datetime.now(UTC).isoformat(),
                         payload=__import__("systematic_trading.market_data.analytics_store", fromlist=["encode"]).encode(row))
                    for row in result["nav_series"]]
    provenance = dict(owner="application", family="fr25_lifecycle_conditional",
                      panel_sha256=detail["input_provenance"]["panel_sha256"],
                      parameters_sha256=detail["input_provenance"]["parameters_sha256"])
    return documents, observations, provenance
