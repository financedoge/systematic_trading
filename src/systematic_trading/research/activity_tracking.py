"""Read-only research watchlist; never an execution or promotion registry.

The initial publication freezes historical evidence. Reviews detect new audited
inputs; they do not fabricate prospective PnL from unchanged final holdings.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from systematic_trading.lean.contracts import sha256, verify_bundle
from systematic_trading.market_data.analytics_store import digest, encode

SOURCE = "research-tracking/etf-activity-lag20-v1"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def checked_run(root, pin):
    output, bundle = root / "runs" / pin["trial"], root / "datasets" / pin["trial"]
    if sha256(output / "run.json") != pin["run_sha256"]:
        raise ValueError("Tracking run receipt changed")
    receipt = read(output / "run.json")
    if receipt["status"] != "succeeded" or receipt["promotion_eligible"] is not False:
        raise ValueError("Tracking requires successful research-only LEAN runs")
    if sha256(bundle / "manifest.json") != pin["manifest_sha256"] or receipt["manifest_sha256"] != pin["manifest_sha256"]:
        raise ValueError("Tracking bundle manifest changed")
    spec = verify_bundle(bundle)["spec"].model_dump(mode="json")
    if spec["strategy_hash"] != pin["strategy_hash"] or receipt["run_id"] != pin["run_id"]:
        raise ValueError("Tracking strategy identity changed")
    for name in ("economic.json", "parity.json"):
        if sha256(output / name) != receipt["artifacts"][name]:
            raise ValueError("Tracking evidence changed: " + name)
    parity, economic = read(output / "parity.json"), read(output / "economic.json")
    if not parity["passed"] or parity["differences"] or not economic["complete"]:
        raise ValueError("Tracking evidence lacks complete LEAN parity")
    if parity["economic_sha256"] != receipt["economic_sha256"]:
        raise ValueError("Tracking parity receipt mismatch")
    return spec, economic


def comparison_metrics(candidate, baseline):
    return dict(candidate=dict(return_=candidate["total_return"], sharpe=candidate["sharpe"],
                               maxDrawdown=candidate["max_drawdown"]),
                baseline=dict(return_=baseline["total_return"]),
                delta=dict(return_=candidate["total_return"] - baseline["total_return"]),
                active=dict(informationRatio=candidate["information_ratio"]))


def historical_detail(config):
    if config["promotion_eligible"] is not False or config["execution_enabled"] is not False:
        raise ValueError("Research tracker cannot promote or execute")
    root = Path(config["study_root"])
    pair = {role: checked_run(root, pin) for role, pin in config["pair"].items()}
    candidate_spec, candidate = pair["candidate"]
    baseline_spec, baseline = pair["baseline"]
    if candidate_spec["flow_overlay"] != config["flow_overlay"] or baseline_spec["flow_overlay"] is not None:
        raise ValueError("Tracking overlay differs from frozen decision")
    # Pair economics and the deployed model must match; only the overlay and
    # native/shared implementation mode may differ between the two runs.
    differences = {"strategy", "strategy_hash", "flow_overlay", "mode"}
    if {k: v for k, v in candidate_spec.items() if k not in differences} != {
            k: v for k, v in baseline_spec.items() if k not in differences}:
        raise ValueError("Unmatched tracking comparator")
    if candidate_spec["base_tree_model_schedule"] or candidate_spec["end_date"] != config["historical_end"]:
        raise ValueError("Expected frozen deployed model and historical interval")
    dates = [r["date"] for r in candidate["nav"]]
    if dates != sorted(set(dates)) or dates != [r["date"] for r in baseline["nav"]]:
        raise ValueError("Unmatched or duplicate NAV dates")
    if dates[-1] != config["historical_end"] or dates[-1] >= config["prospective_start"]:
        raise ValueError("Historical evidence overlaps prospective interval")
    if sha256(root / "summary.json") != config["summary_sha256"]:
        raise ValueError("Historical summary changed")
    summary = read(root / "summary.json")
    cm = summary[config["pair"]["candidate"]["trial"]]["2023_plus"]
    bm = summary[config["pair"]["baseline"]["trial"]]["2023_plus"]
    comparisons = {}
    for label, a, b, key in [("Historical frozen model (2023–2026)", "fixed_flow20", "fixed_sota", "2023_plus"),
                           ("Historical annual refits (2016–2026)", "flow20", "sota", "full")]:
        item = comparison_metrics(summary[a][key], summary[b][key])
        for group in ("candidate", "baseline", "delta"):
            item[group]["return"] = item[group].pop("return_")
        comparisons[label] = item
    return dict(
        strategy_id=config["strategy_id"], name=config["name"], is_sota=False, lifecycle="monitored",
        promotion_eligible=False, execution_enabled=False, research_tracking=True,
        artifact_path=str(root), artifact_end_date=dates[-1], start_date=dates[0], end_date=dates[-1],
        observations=len(dates), initial_nav_cnh=float(candidate_spec["initial_cash_cnh"]),
        final_nav_cnh=float(candidate["nav"][-1]["nav"]), total_return=cm["total_return"],
        annualized_return=cm["cagr"], annualized_volatility=cm["volatility"], sharpe=cm["sharpe"],
        max_drawdown=cm["max_drawdown"], calmar=cm["calmar"], information_ratio=cm["information_ratio"],
        allocation=[], holdings=[], country_exposure_cnh={}, currency_exposure_cnh={}, leverage=None,
        nav_series=[dict(trade_date=r["date"], nav_cnh=float(r["nav"])) for r in candidate["nav"]],
        benchmark_series=[dict(trade_date=r["date"], nav_cnh=float(r["nav"])) for r in baseline["nav"]],
        comparison=dict(baseline_name=config["baseline_version"], metrics=comparisons),
        report_available=False, report_url=None, monitoring_extension_count=0,
        monitoring_method="frozen_candidate_research_reviews",
        monitoring_notes="Research tracker. Performance below is historical LEAN evidence through " + dates[-1]
            + ". Forward tracking starts " + config["prospective_start"] + ". No trading allocation.",
        tracking=dict(decision_date=config["decision_date"], prospective_start=config["prospective_start"],
            prospective_observations=0, prospective_through=None, prospective_metrics=None,
            baseline_id=config["baseline_id"], flow_overlay=config["flow_overlay"],
            review=config["review"], governed_batch=config["governed_batch"],
            frozen_pair=config["pair"], candidate_cost_cnh=cm["fee_cnh"], baseline_cost_cnh=bm["fee_cnh"],
            candidate_turnover=cm["annual_traded_notional_over_nav"],
            baseline_turnover=bm["annual_traded_notional_over_nav"]),
        warnings=config["limitations"],
    )


def review_status(config, analytics, now):
    publication = analytics.latest("governance/catalog")
    batch = publication["version"] if publication else None
    changed = bool(batch and batch != config["governed_batch"])
    before_start = now.date().isoformat() < config["prospective_start"]
    return dict(
        status="awaiting_first_session" if before_start else
               "audited_publication_changed_review_required" if changed else "awaiting_audited_update",
        latest_governed_batch=batch, new_audited_publication=changed,
        blockers=["No matched prospective native LEAN replay has been accepted.",
                  "Fresh audited ETF prices and supported, versioned FX are required for forward CNH results."],
        next_action="Review the new audited publication and its overlap/revisions before a matched LEAN replay."
            if changed else "Wait for audited inputs covering the forward interval; preserve missing results.",
    )


def review_tracking(config_path, analytics, *, now=None):
    """Persist a daily review, retaining any accepted forward data unchanged."""
    now = now or datetime.now(UTC)
    config = read(config_path)
    config_hash = sha256(config_path)
    saved = analytics.document(SOURCE, "detail")
    if saved:
        detail = json.loads(saved[0]["payload"])
        if detail["tracking"]["config_sha256"] != config_hash:
            raise ValueError("Frozen tracker definition changed; create a separately versioned tracker")
    else:
        detail = historical_detail(config)
        detail["tracking"]["config_sha256"] = config_hash
    # Reviews never overwrite/extend the observed NAV or prospective metric fields.
    status = review_status(config, analytics, now)
    detail["tracking"].update(status, last_review_date=now.date().isoformat())
    version = digest(encode(detail))
    previous = (saved[1]["version"] if saved else None)
    documents = [dict(point_key="detail", media_type="application/json", payload=encode(detail)),
                 dict(point_key="definition", media_type="application/json", payload=encode(config))]
    rows = [dict(point_key=r["trade_date"], family="research_tracker_historical_nav", entity=config["strategy_id"],
                 observed_at=r["trade_date"], available_at=None, payload=encode({**r,
                 "baseline_nav_cnh": b["nav_cnh"], "sample": "historical"}))
            for r, b in zip(detail["nav_series"], detail["benchmark_series"], strict=True)]
    analytics.publish(SOURCE, version, rows, documents, provenance=dict(config_sha256=config_hash,
        state="research_tracking", promotion_eligible=False, execution_enabled=False,
        method="verified_historical_evidence_and_audited_input_reviews"))
    return dict(source=SOURCE, version=version, publication_changed=version != previous,
                strategy_id=config["strategy_id"], **detail["tracking"])


def published_trackers(analytics):
    """Include verified research documents in the UI without marking holdings."""
    saved = analytics.document(SOURCE, "detail")
    if not saved:
        return []
    detail = json.loads(saved[0]["payload"])
    if detail.get("is_sota") is not False or detail.get("execution_enabled") is not False:
        raise ValueError("Research tracker must not enter the production registry")
    return [detail]
