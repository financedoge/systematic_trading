import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from systematic_trading.lean.contracts import BacktestRunSpec, sha256, write_json
from systematic_trading.research import activity_tracking as tracking
from systematic_trading.research.flow_concentration import FlowConcentrationSpec
from test_analytics_projection import MemoryAnalytics


@pytest.fixture
def frozen(tmp_path):
    config = dict(schema_version=1, strategy_id="research_test", name="Research test",
        promotion_eligible=False, execution_enabled=False, study_root=str(tmp_path),
        decision_date="2026-09-26", prospective_start="2026-09-28", historical_end="2026-09-24",
        baseline_id="existing_sota", baseline_version="Frozen model", governed_batch="audited-batch",
        flow_overlay=FlowConcentrationSpec(difference_lag=20).model_dump(), review={}, limitations=[], pair={})
    for role, trial in [("candidate", "fixed_flow20"), ("baseline", "fixed_sota")]:
        bundle, output = tmp_path / "datasets" / trial, tmp_path / "runs" / trial
        bundle.mkdir(parents=True)
        output.mkdir(parents=True)
        spec = BacktestRunSpec(start_date="2023-01-03", end_date=config["historical_end"],
            warmup_start="2012-01-05", strategy_hash=trial, source_hash="frozen_source", repository_commit="abc",
            strategy="sota_flow" if role == "candidate" else "sota",
            flow_overlay=config["flow_overlay"] if role == "candidate" else None)
        write_json(bundle / "spec.json", spec.model_dump(mode="json"))
        write_json(bundle / "manifest.json", dict(schema_version=1, files={"spec.json": sha256(bundle / "spec.json")}))
        economic = dict(complete=True, nav=[dict(date="2023-01-03", nav="999000"),
                                          dict(date=config["historical_end"], nav="1100000")])
        write_json(output / "economic.json", economic)
        write_json(output / "parity.json", dict(passed=True, differences=[], economic_sha256="econ"))
        receipt = dict(status="succeeded", promotion_eligible=False, run_id=trial, economic_sha256="econ",
            manifest_sha256=sha256(bundle / "manifest.json"),
            artifacts={name: sha256(output / name) for name in ("economic.json", "parity.json")})
        write_json(output / "run.json", receipt)
        config["pair"][role] = dict(trial=trial, run_id=trial, run_sha256=sha256(output / "run.json"),
            manifest_sha256=receipt["manifest_sha256"], strategy_hash=trial)
    metrics = dict(total_return=.1, cagr=.03, volatility=.1, sharpe=.3, max_drawdown=-.1,
                   calmar=.3, information_ratio=.2, fee_cnh=20, annual_traded_notional_over_nav=2)
    write_json(tmp_path / "summary.json", {name: {"2023_plus": metrics, "full": metrics}
               for name in ("fixed_sota", "fixed_flow20", "sota", "flow20")})
    config["summary_sha256"] = sha256(tmp_path / "summary.json")
    path = tmp_path / "tracking.json"
    write_json(path, config)
    return path, config


def test_historical_seed_never_becomes_prospective_or_sota(frozen):
    _, config = frozen
    detail = tracking.historical_detail(config)
    assert detail["is_sota"] is detail["execution_enabled"] is detail["promotion_eligible"] is False
    assert detail["tracking"]["prospective_observations"] == 0
    assert detail["tracking"]["prospective_metrics"] is None
    assert detail["monitoring_extension_count"] == 0
    assert detail["report_url"] is None
    assert detail["holdings"] == []


@pytest.mark.parametrize("changed", ["economic.json", "parity.json", "run.json"])
def test_changed_evidence_is_rejected(frozen, changed):
    _, config = frozen
    path = Path(config["study_root"]) / "runs" / "fixed_flow20" / changed
    path.write_text("{}", encoding="utf8")
    with pytest.raises(ValueError, match="changed"):
        tracking.historical_detail(config)


def test_parameter_change_and_prospective_overlap_rejected(frozen):
    _, config = frozen
    wrong = copy.deepcopy(config)
    wrong["flow_overlay"]["difference_lag"] = 10
    with pytest.raises(ValueError, match="overlay"):
        tracking.historical_detail(wrong)
    config["prospective_start"] = "2026-09-24"
    with pytest.raises(ValueError, match="overlaps"):
        tracking.historical_detail(config)


def test_reviews_do_not_fetch_raw_prices_or_extend_nav(frozen):
    path, config = frozen
    analytics = MemoryAnalytics()
    first = tracking.review_tracking(path, analytics, now=datetime(2026, 9, 26, tzinfo=UTC))
    assert first["status"] == "awaiting_first_session"
    original = analytics.document(tracking.SOURCE, "detail")[0]["payload"]
    repeat = tracking.review_tracking(path, analytics, now=datetime(2026, 9, 26, 23, tzinfo=UTC))
    assert repeat["publication_changed"] is False
    later = tracking.review_tracking(path, analytics, now=datetime(2026, 9, 29, tzinfo=UTC))
    assert later["status"] == "awaiting_audited_update"
    analytics.publish("governance/catalog", "new-audited-batch", [])
    result = tracking.review_tracking(path, analytics, now=datetime(2026, 9, 29, tzinfo=UTC))
    assert result["status"] == "audited_publication_changed_review_required"
    assert result["prospective_observations"] == 0
    assert tracking.published_trackers(analytics)[0]["nav_series"] == json.loads(original)["nav_series"]
    config["flow_overlay"]["threshold"] = 1
    write_json(path, config)
    with pytest.raises(ValueError, match="Frozen tracker definition changed"):
        tracking.review_tracking(path, analytics)


def test_strategy_publication_bypasses_holdings_marks_for_research(frozen, monkeypatch):
    from systematic_trading.research import analytics_projection as projection
    from systematic_trading.research import tracked_runtime
    from systematic_trading.web import api
    path, _ = frozen
    analytics = MemoryAnalytics()
    tracking.review_tracking(path, analytics)
    detail = tracking.published_trackers(analytics)[0]
    monkeypatch.setattr(tracked_runtime, "published_strategies", lambda a: {detail["strategy_id"]: (detail, {})})
    monkeypatch.setattr(projection, "strategy_inputs", lambda *args: "test-version")
    monkeypatch.setattr(projection, "StrategyMarketDataView", lambda store: store)
    monkeypatch.setattr(api, "strategy_catalog", lambda req: dict(strategies=[], current_sota_id="unchanged", monitoring_notes=""))
    def forbidden(*args):
        pytest.fail("Research tracker entered the normal canonical-price marking/report path")
    monkeypatch.setattr(api, "strategy_detail", forbidden)
    monkeypatch.setattr(api, "strategy_report", forbidden)
    projection.publish_strategies(SimpleNamespace(), None, analytics)
    catalog = json.loads(analytics.document("strategy-serving", "catalog")[0]["payload"])
    assert catalog["current_sota_id"] == "unchanged"
    assert catalog["strategies"][0]["is_sota"] is False
    assert analytics.document("strategy-serving", "detail/research_test")
    assert analytics.document("strategy-serving", "report/research_test") is None


def test_tracker_ui_has_separate_forward_panel_and_detail_route():
    from systematic_trading.web.operator import _STRATEGIES_HTML
    assert 'button.dataset.strategyLifecycle==="monitored"' in _STRATEGIES_HTML
    assert 'Tracked · not promoted' in _STRATEGIES_HTML
    assert 'researchTracking' not in _STRATEGIES_HTML
