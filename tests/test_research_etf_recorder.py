from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from systematic_trading.lean.contracts import sha256
from systematic_trading.recorders import research_etfs as recorder
from systematic_trading.research import governed_refresh as producer
from systematic_trading.research.governed_inputs import GovernedInputs
from test_governed_refresh import governed  # noqa: F401


@pytest.fixture
def setup(governed):
    settings, analytics, fetch, written = governed
    fund = dict(symbol="BIL", name="BIL Example ETF", isin="TESTID", inception="2026-01-02", required_start="2026-01-02",
                purpose="test admission", issuer_url="https://issuer.example/BIL", issuer_required_text=["TESTID", "BIL"])
    path = settings.data_dir / "research-recorders.json"
    producer._write(path.parent, path.name, dict(enabled=True, funds=[fund]))
    settings = settings.model_copy(update=dict(research_etf_recorder_config_path=path, governed_refresh_enabled=True))
    return settings, analytics, fetch, written


def run(setup, **kwargs):
    settings, analytics, fetch, _ = setup
    return recorder.refresh_research_etfs(settings, analytics, fetch=fetch, issuer_fetch=lambda u:b"<p>BIL TESTID</p>",
                                         now=datetime(2026,8,4,22,tzinfo=UTC), **kwargs)


def test_admission_publishes_and_repeated_capture_is_noop(setup):
    settings, analytics, _, written = setup
    assert run(setup)
    p = analytics.latest("governance/catalog")
    reader = GovernedInputs(Path(json.loads(p["provenance"])["root"]), p["version"])
    assert reader.rows("BIL", "2026-01-02", "2026-08-04")[-1]["trade_date"] == "2026-08-04"
    assert reader.rows("X", "2026-01-02", "2026-08-04")[-1]["trade_date"] < "2026-08-04"
    assert recorder.recorder_status(settings)["funds"][0]["status"] == "published"
    assert any(d["point_key"] == "issuer_reference" for d in analytics.docs["governance-batch/"+p["version"]+"/BIL"])
    assert len(written) == 2
    assert not run(setup)


def test_active_refresh_preserves_new_research_series_and_source_hashes(setup):
    settings, analytics, fetch, _ = setup
    run(setup)
    first = analytics.latest("governance/catalog")
    reader = GovernedInputs(Path(json.loads(first["provenance"])["root"]), first["version"])
    expected = reader.rows("BIL", "2026-01-02", "2026-08-04")
    assert producer.refresh_governed_etfs(settings, analytics, fetch=fetch, now=datetime(2026,8,4,22,tzinfo=UTC))
    p = analytics.latest("governance/catalog")
    after = GovernedInputs(Path(json.loads(p["provenance"])["root"]), p["version"])
    assert after.rows("BIL", "2026-01-02", "2026-08-04") == expected
    assert after.parent.parent is None
    assert after.audit("BIL")["research_recorder"]["isin"] == "TESTID"
    assert next(json.loads(r["payload"]) for r in analytics.rows["governance/catalog"] if r["entity"]=="BIL")["storage_batch"] == first["version"]


def test_issuer_failure_is_visible_and_does_not_commit(setup):
    settings, analytics, fetch, written = setup
    before = analytics.latest("governance/catalog")
    now = datetime(2026,8,4,22,tzinfo=UTC)
    with pytest.raises(ValueError, match="Issuer reference"):
        recorder.refresh_research_etfs(settings, analytics, fetch=fetch, issuer_fetch=lambda u:b"blocked", now=now)
    assert analytics.latest("governance/catalog") == before and not written
    status = recorder.recorder_status(settings)["funds"][0]
    assert status["status"] == "quarantined"
    assert (Path(status["evidence_root"])/"issuer/BIL.html").read_bytes() == b"blocked"
    with pytest.raises(ValueError, match="Issuer reference"):
        run(setup)
    assert recorder.refresh_research_etfs(settings, analytics, fetch=fetch, issuer_fetch=lambda u:b"BIL TESTID",
                                          now=now+timedelta(seconds=301))


@pytest.mark.parametrize("mutation", ["currency", "name", "gap", "factor", "listing"])
def test_unsupported_sources_remain_quarantined(setup, mutation):
    settings, analytics, fetch, _ = setup
    before = analytics.latest("governance/catalog")
    def bad(symbol, now):
        obj = json.loads(fetch(symbol, now));r = obj["chart"]["result"][0]
        if mutation == "currency": r["meta"]["currency"] = "EUR"
        if mutation == "name": r["meta"]["longName"] = "Unrelated Gold Securities"
        if mutation == "gap": r["indicators"]["quote"][0]["close"][70] = None
        if mutation == "factor": r["indicators"]["adjclose"][0]["adjclose"][70] *= .9
        if mutation == "listing": r["meta"]["firstTradeDate"] -= 86400 * 30
        return json.dumps(obj).encode()
    with pytest.raises(ValueError):
        recorder.refresh_research_etfs(settings, analytics, fetch=bad, issuer_fetch=lambda u:b"BIL TESTID",
                                      now=datetime(2026,8,4,22,tzinfo=UTC))
    assert analytics.latest("governance/catalog") == before
    assert recorder.recorder_status(settings)["funds"][0]["status"] == "quarantined"


def test_status_endpoint_reads_local_recorder_without_acquisition(setup):
    from systematic_trading.web.governed_data import recorders
    settings, _, _, _ = setup
    assert recorders(SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=settings))))["funds"][0]["status"] == "pending"


def test_carry_forward_hash_failure_stops_publication(setup):
    _, analytics, _, _ = setup
    run(setup)
    p = analytics.latest("governance/catalog")
    root = Path(json.loads(p["provenance"])["root"])
    r = GovernedInputs(root, p["version"])
    (root/"bars/BIL.jsonl.gz").write_bytes(b"changed")
    with pytest.raises(ValueError, match="Changed or unmanifested"):
        producer.inherit_series(r, root.parent/"bad-copy", [dict(symbol="BIL")])
    assert sha256(root/"manifest.json") == p["version"]
