from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException

from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import encode
from systematic_trading.recorders import economics as e
from systematic_trading.runtime_io import atomic_json
from systematic_trading.web.economic_data import catalog as api_catalog, history as api_history


class Memory:
    def __init__(self):
        self.p = {}
        self.fail = False

    def latest(self, source):
        return self.p.get(source)

    def publication_index(self, prefix):
        return {k:v for k,v in self.p.items() if k.startswith(prefix)}

    def publish(self, source, version, rows, docs=(), provenance=None):
        if self.fail:
            raise ValueError("Analytical readback mismatch")
        self.p[source] = dict(version=version, provenance=encode(provenance))


NOW = datetime(2026, 10, 7, 12, tzinfo=UTC)


@pytest.fixture
def setup(tmp_path):
    config = json.loads(Path("config/economic-recorders.json").read_text())
    config["series"] = config["series"][:3]
    config.pop("compatible_config_sha256", None)
    config.pop('capture_latest_signal_vintage', None)
    config["decision_start"] = "2026-10-01"
    path = tmp_path / "config.json"
    atomic_json(path, config)
    settings = AppSettings(data_dir=tmp_path, economic_recorder_config_path=path, governed_refresh_enabled=True)
    return settings, Memory(), config


def csv_for(series, vintage, *, start="2006-01-01"):
    d = date.fromisoformat(start)
    weekly = series == "ICSA"
    if weekly:
        d += timedelta(days=(5 - d.weekday()) % 7)
    end = date.fromisoformat(vintage) - timedelta(days=10 if weekly else 40)
    lines = ["observation_date," + series + "_" + vintage.replace("-", "")]
    while d <= end:
        lines.append(str(d) + "," + ("200000" if weekly else "100"))
        d = d + timedelta(days=7) if weekly else e.next_month(d)
    return ("\n".join(lines) + "\n").encode()


def fetch(url):
    query = parse_qs(urlparse(url).query)
    return csv_for(query["id"][0], query["vintage_date"][0])


def test_publish_idempotence_pinned_reader_and_availability(setup):
    settings, store, _ = setup
    assert e.refresh_economics(settings, store, now=NOW, fetch=fetch)
    cat, pin = e.load_catalog(store)
    assert cat["completed"] == cat["expected"] == 6
    assert not e.refresh_economics(settings, store, now=NOW, fetch=lambda _:pytest.fail("refetch"))
    reader = e.EconomicInputs(**pin)
    r = reader.snapshot("ICSA", "2026-09-29")
    assert r["observations"][-1]["value"] == "200000"
    before = datetime.fromisoformat(r["archive_available_at"])
    with pytest.raises(ValueError, match="unavailable"):
        reader.snapshot("ICSA", "2026-09-29", decision_at=before, availability="archive_daily")
    assert reader.snapshot("ICSA", "2026-09-29", decision_at=before+timedelta(seconds=1), availability="archive_daily")
    with pytest.raises(ValueError, match="unavailable"):
        reader.snapshot("ICSA", "2026-09-29", decision_at=before+timedelta(seconds=1))
    with pytest.raises(ValueError, match="no substitution"):
        reader.snapshot("ICSA", "2026-09-30")
    with pytest.raises(ValueError, match="stale"):
        reader.snapshot("ICSA", "2026-09-29", decision_at=NOW+timedelta(days=50), availability="archive_daily")


@pytest.mark.parametrize("change", ["header", "duplicate", "gap", "future", "nan", "domain", "frequency", "late_start", "extra_column"])
def test_audit_rejects_schema_identity_and_calendar_errors(setup, change):
    _, _, config = setup
    spec = config["series"][1]
    lines = csv_for("PERMIT", "2026-10-06").decode().splitlines()
    if change == "header": lines[0] = lines[0].replace("20261006", "20261005")
    if change == "duplicate": lines.insert(4, lines[3])
    if change == "gap": lines.pop(4)
    if change == "future": lines.append("2026-11-01,100")
    if change == "nan": lines[4] = lines[4].replace(",100", ",NaN")
    if change == "domain": lines[4] = lines[4].replace(",100", ",10000000")
    if change == "frequency": lines[4] = lines[4].replace("-01,", "-02,")
    if change == "late_start": lines.pop(1)
    if change == "extra_column": lines[4] += ",unexpected"
    with pytest.raises((ValueError, ArithmeticError)):
        e.audit_csv("\n".join(lines).encode(), spec, "2026-10-06", "2006-01-01")


def test_missing_not_filled_and_stale_published_but_signal_blocked(setup):
    settings, store, config = setup
    def missing(url):
        lines = fetch(url).decode().splitlines()
        lines[-1] = lines[-1].split(",")[0] + ",."
        return "\n".join(lines).encode()
    e.refresh_economics(settings, store, now=NOW, fetch=missing)
    _, pin = e.load_catalog(store)
    reader = e.EconomicInputs(**pin)
    r = reader.snapshot("PERMIT", "2026-10-06")
    assert not r["usable"] and r["missing"] == 1 and r["observations"][-1]["value"] is None
    with pytest.raises(ValueError, match="stale or missing"):
        reader.snapshot("PERMIT", "2026-10-06", decision_at=NOW, availability="archive_daily")
    stale = e.audit_csv(csv_for("PERMIT", "2026-01-06"), config["series"][1], "2026-01-06", "2006-01-01")
    assert stale["usable"]


def test_failure_raw_evidence_retained_retry_and_catalog_recovery(setup):
    settings, store, _ = setup
    with pytest.raises(ValueError, match="header mismatch"):
        e.refresh_economics(settings, store, now=NOW, fetch=lambda _:b"blocked")
    cat, _ = e.load_catalog(store)
    assert cat["completed"] == 0
    assert len(list(settings.data_dir.glob("governance/economic-captures/*/*/*/failure.json"))) == 6
    assert len(e.recorder_status(settings)["failures"]) == 6
    assert not e.refresh_economics(settings, store, now=NOW, fetch=lambda _:pytest.fail("early retry"))
    assert e.refresh_economics(settings, store, now=NOW+timedelta(seconds=301), fetch=fetch)
    assert not e.recorder_status(settings)["failures"]
    del store.p[e.CATALOG]  # Crash after source commits, before the catalog pointer.
    assert e.refresh_economics(settings, store, now=NOW+timedelta(seconds=302), fetch=lambda _:pytest.fail("refetch"))
    assert e.load_catalog(store)[0]["completed"] == 6


def test_failed_readback_preserves_previous_publication(setup):
    settings, store, _ = setup
    e.refresh_economics(settings, store, now=NOW, fetch=fetch)
    before = store.latest(e.CATALOG)
    store.fail = True
    with pytest.raises(ValueError, match="readback"):
        e.refresh_economics(settings, store, now=NOW+timedelta(days=1), fetch=fetch)
    assert store.latest(e.CATALOG) == before


def test_mutated_published_source_blocks_reader_and_api(setup):
    settings, store, _ = setup
    e.refresh_economics(settings, store, now=NOW, fetch=fetch)
    cat, pin = e.load_catalog(store)
    entry = cat["snapshots"][0]
    (Path(entry["root"]) / "source.csv").write_text("changed")
    with pytest.raises(ValueError, match="input changed"):
        e.EconomicInputs(**pin).snapshot(entry["series"], entry["vintage"])
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=settings, analytics=store)))
    with pytest.raises(HTTPException) as exc:
        api_history(request, entry["series"], date.fromisoformat(entry["vintage"]))
    assert exc.value.status_code == 503
    assert api_catalog(request)["completed"] == 6


def test_daily_outage_catchup_and_configuration_migration_gate(setup):
    settings, store, config = setup
    e.refresh_economics(settings, store, now=NOW, fetch=fetch)
    e.refresh_economics(settings, store, now=NOW+timedelta(days=2), fetch=fetch)
    cat, _ = e.load_catalog(store)
    assert cat["expected"] == cat["completed"] == 12
    assert {r["vintage"] for r in cat["snapshots"]} >= {"2026-10-06", "2026-10-07", "2026-10-08"}
    config["series"][0]["units"] = "changed"
    atomic_json(settings.economic_recorder_config_path, config)
    with pytest.raises(ValueError, match="migration required"):
        e.refresh_economics(settings, store, now=NOW, fetch=fetch)


def test_navigation_and_api_are_read_only():
    from systematic_trading.web.platform import market_data_audit_portal
    html = market_data_audit_portal().body.decode()
    assert 'id="economic-tab"' in html and 'data-market-view="economics"' in html
    assert "economics:['economic-panel','economic-tab']" in html
    assert "Archive cutoff:" in html and "First captured by this app:" in html
    assert "window.MarketHistory.register('economics'" in html


def test_claims_saturdays_and_pandemic_spike_are_valid(setup):
    _, _, config = setup
    raw = csv_for("ICSA", "2026-10-06").replace(b"200000", b"6800000")
    assert e.audit_csv(raw, config["series"][0], "2026-10-06", "2006-01-01")["usable"]


def test_economic_panel_interactions():
    import shutil
    import subprocess
    from systematic_trading.web.economic_panel import ECONOMIC_HTML
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required for UI behavior checks")
    result = subprocess.run([node, str(Path(__file__).with_name("economic_panel_checks.cjs"))],
        input=ECONOMIC_HTML, text=True, encoding="utf8", capture_output=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_additive_registry_migration_reuses_existing_publications(setup):
    settings, store, config = setup
    e.refresh_economics(settings, store, now=NOW, fetch=fetch)
    old, pin = e.load_catalog(store)
    old_entries = {r["series"]+"/"+r["vintage"]:r for r in old["snapshots"]}
    old_hash = e.sha256(settings.economic_recorder_config_path)
    config["version"] += "-expanded"
    config["compatible_config_sha256"] = [old_hash]
    config["series"].append(dict(config["series"][1], id="PAYEMS", name="Payroll", max=1000000))
    atomic_json(settings.economic_recorder_config_path, config)
    requested = []
    def new_only(url):
        requested.append(parse_qs(urlparse(url).query)["id"][0])
        return fetch(url)
    e.refresh_economics(settings, store, now=NOW, fetch=new_only)
    catalog, _ = e.load_catalog(store)
    assert requested == ["PAYEMS", "PAYEMS"]
    assert catalog["completed"] == catalog["expected"] == 8
    for r in catalog["snapshots"]:
        key = r["series"]+"/"+r["vintage"]
        if key in old_entries:
            assert r == old_entries[key]
    assert e.EconomicInputs(**pin).snapshot("ICSA", "2026-09-29")
    assert not e.refresh_economics(settings, store, now=NOW, fetch=lambda _:pytest.fail("refetch"))


@pytest.mark.parametrize("change", ["remove", "units", "freshness", "start", "same_version", "unnamed_hash"])
def test_migration_never_reinterprets_old_series(setup, change):
    settings, store, config = setup
    e.refresh_economics(settings, store, now=NOW, fetch=fetch)
    old_hash = e.sha256(settings.economic_recorder_config_path)
    config["compatible_config_sha256"] = [old_hash]
    config["series"].append(dict(config["series"][1], id="PAYEMS"))
    if change != "same_version": config["version"] += "-expanded"
    if change == "remove": config["series"].pop(0)
    if change == "units": config["series"][0]["units"] = "different"
    if change == "freshness": config["series"][0]["max_age_days"] += 100
    if change == "start": config["observation_start"] = "2010-01-01"
    if change == "unnamed_hash": config["compatible_config_sha256"] = []
    atomic_json(settings.economic_recorder_config_path, config)
    with pytest.raises(ValueError, match="migration required"):
        e.refresh_economics(settings, store, now=NOW, fetch=lambda _:pytest.fail("fetch"))


def test_expanded_registry_signed_survey_indices_and_distinct_roles():
    config = e.configuration(AppSettings())
    series = {s["id"]:s for s in config["series"]}
    assert len(series) == 16
    assert not any("GDP" in s for s in series)
    spec = series["NOFDFSA066MSFRBPHI"]
    raw = csv_for(spec["id"], "2026-10-06").replace(b",100", b",-23.5")
    audit = e.audit_csv(raw, spec, "2026-10-06", "2006-01-01")
    assert audit["observations"][-1]["value"] == "-23.5"
    assert "regional" in spec["role"] and "not national PMI" in spec["role"]
    assert "Lagging" in series["CPIAUCSL"]["role"]
    assert "Coincident" in series["PAYEMS"]["role"]
    with pytest.raises(ValueError, match="domain"):
        e.audit_csv(raw.replace(b"-23.5", b"-101"), spec, "2026-10-06", "2006-01-01")
