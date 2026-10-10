from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from systematic_trading.market_data.analytics_store import encode
from systematic_trading.recorders.energy import EnergyInputs, PREFIX, catalog, load_product, refresh_energy
from systematic_trading.recorders.energy_parsers import natural_gas, petroleum, release_time
from systematic_trading.web import energy_data
from systematic_trading.web.platform import market_data_audit_portal

FIXTURES = Path(__file__).parent / "fixtures" / "energy"
NOW = datetime(2026, 10, 8, 16, tzinfo=UTC)


class MemoryAnalytics:
    def __init__(self):
        self.publications = {}
        self.fail = False

    def latest(self, source):
        return self.publications.get(source)

    def publish(self, source, version, observations, documents, *, provenance):
        if self.fail:
            raise OSError("simulated publication failure")
        assert len({r["point_key"] for r in observations}) == len(observations)
        self.publications[source] = dict(version=version, provenance=encode(provenance))
        return True


@pytest.fixture
def setup(tmp_path):
    config = json.loads(Path("config/energy-recorders.json").read_text(encoding="utf-8"))
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    settings = SimpleNamespace(energy_recorder_config_path=path, data_dir=tmp_path, governed_refresh_enabled=True)
    files = {url: (FIXTURES / name).read_bytes() for p in config["products"] for name, url in p["files"].items()}
    return settings, MemoryAnalytics(), files


def fixtures(product):
    names = ["stocks.json", "balance.csv", "estimates.csv"] if product == "petroleum" else ["storage.json", "release.html"]
    return {name: (FIXTURES/name).read_bytes() for name in names}


def test_parsers_preserve_units_release_clock_and_signed_context():
    oil, gas = petroleum(fixtures("petroleum")), natural_gas(fixtures("gas"))
    metrics = {m["id"]: m for m in oil["metrics"]}
    assert oil["source_release_at"] == "2026-10-07T14:30:00+00:00"
    assert metrics["crude-ex-spr"]["value"] == "424.134"
    assert metrics["crude-ex-spr"]["change"] == "-3.186"
    assert metrics["production"]["value"] == "13979"
    assert metrics["production"]["units"] == "thousand barrels/day"
    assert metrics["products-supplied"]["four_week_average"] == "21050"
    assert metrics["utilization"]["value"] == "92.7"
    assert oil["reference_history"]["rows"][-1]["value"] == "424.134"
    assert gas["source_release_at"] == "2026-10-08T14:30:00+00:00"
    assert gas["metrics"][0]["value"] == "3500"
    assert gas["metrics"][3]["value"] == "3432"
    assert gas["metrics"][4]["value"] == "2.0"
    assert release_time("2026-01-22", "12:00 p.m.").isoformat() == "2026-01-22T17:00:00+00:00"


@pytest.mark.parametrize("file,old,new", [("balance.csv", b'"10/2/26"', b'"10/9/26"'),
    ("balance.csv", b'"424.134"', b'"999.000"'), ("balance.csv", b'"13,979"', b'"NaN"'),
    ("estimates.csv", b'"Percent Utilization"', b'"Unknown"')])
def test_petroleum_rejects_mixed_release_identity_and_invalid_values(file, old, new):
    files = fixtures("petroleum")
    files[file] = files[file].replace(old, new)
    with pytest.raises(ValueError):
        petroleum(files)


def test_missing_value_stays_missing():
    files = fixtures("petroleum")
    files["balance.csv"] = files["balance.csv"].replace(b'"13,979"', b'"--"')
    parsed = petroleum(files)
    metric = next(m for m in parsed["metrics"] if m["id"] == "production")
    assert metric["value"] is None and metric["change"] is None


def test_averaging_dates_and_rolling_gaps_are_not_silently_accepted():
    files = fixtures("petroleum")
    files["estimates.csv"] = files["estimates.csv"].replace(b'"10/2/26","10/3/25"', b'"10/9/26","10/3/25"')
    with pytest.raises(ValueError, match="window"):
        petroleum(files)
    files = fixtures("petroleum")
    stocks = json.loads(files["stocks.json"])
    stocks["data"]["U.S."]["time_series"].pop(1)
    files["stocks.json"] = json.dumps(stocks).encode()
    with pytest.raises(ValueError, match="gaps"):
        petroleum(files)


def test_gas_rejects_midnight_placeholder_and_mixed_release():
    files = fixtures("gas")
    for page in [b"No release time", files["release.html"].replace(b"October 8", b"October 9")]:
        with pytest.raises(ValueError):
            natural_gas(dict(files, **{"release.html": page}))


def test_publication_first_seen_idempotency_and_revision_asof(setup):
    settings, analytics, files = setup
    assert refresh_energy(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW)
    old, pin = load_product(analytics, "natural-gas")
    old_reader = EnergyInputs(**pin)
    for decision in [NOW-timedelta(days=10), NOW]:
        with pytest.raises(ValueError, match="available"):
            old_reader.snapshot(decision_at=decision)
    assert old_reader.snapshot(decision_at=NOW+timedelta(seconds=1))["metrics"][0]["value"] == "3500"
    assert refresh_energy(settings, analytics, fetch=lambda _: pytest.fail("cooldown ignored"), clock=lambda: NOW+timedelta(minutes=1)) is False
    assert refresh_energy(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW+timedelta(hours=2)) is False
    assert load_product(analytics, "natural-gas")[1] == pin
    # Same reported release date, revised value: only usable after the new capture.
    url = "https://ir.eia.gov/ngs/wngsr.json"
    files[url] = files[url].replace(b"3500", b"3510")
    assert refresh_energy(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW+timedelta(hours=4))
    updated, new_pin = load_product(analytics, "natural-gas")
    reader = EnergyInputs(**new_pin)
    assert len(updated["captures"]) == 2
    assert reader.snapshot(decision_at=NOW+timedelta(hours=3))["metrics"][0]["value"] == "3500"
    assert reader.snapshot(decision_at=NOW+timedelta(hours=5))["metrics"][0]["value"] == "3510"
    assert old_reader.snapshot(decision_at=NOW+timedelta(hours=5))["metrics"][0]["value"] == "3500"
    with pytest.raises(ValueError, match="stale"):
        reader.snapshot(decision_at=NOW+timedelta(days=20))
    with pytest.raises(ValueError, match="timezone"):
        reader.snapshot(decision_at=NOW.replace(tzinfo=None))


def test_raw_evidence_precedes_audit_and_independent_product_survives(setup):
    settings, analytics, files = setup
    files["https://ir.eia.gov/wpsr/table1.csv"] = b"broken schema"
    with pytest.raises(ValueError):
        refresh_energy(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW)
    assert analytics.latest(PREFIX+"petroleum") is None
    assert analytics.latest(PREFIX+"natural-gas") is not None
    roots = list((settings.data_dir/"governance/eia-energy/petroleum/captures").iterdir())
    assert (roots[0]/"balance.csv").read_bytes() == b"broken schema"
    assert (roots[0]/"failure.json").exists()


def test_capture_time_follows_all_responses(setup):
    settings, analytics, files = setup
    current = NOW
    def fetch(url):
        nonlocal current
        current += timedelta(seconds=1)
        return files[url]
    refresh_energy(settings, analytics, fetch=fetch, clock=lambda: current)
    data, _ = load_product(analytics, "petroleum")
    assert data["captures"][0]["first_seen_at"] == (NOW+timedelta(seconds=3)).isoformat()


def test_publication_failure_retains_last_good_pin_and_retries(setup):
    settings, analytics, files = setup
    refresh_energy(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW)
    _, prior = load_product(analytics, "natural-gas")
    files["https://ir.eia.gov/ngs/wngsr.json"] = files["https://ir.eia.gov/ngs/wngsr.json"].replace(b"3500", b"3510")
    analytics.fail = True
    with pytest.raises(ValueError):
        refresh_energy(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW+timedelta(hours=2))
    assert load_product(analytics, "natural-gas")[1] == prior
    analytics.fail = False
    refresh_energy(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW+timedelta(hours=3))
    data, _ = load_product(analytics, "natural-gas")
    assert len(data["captures"]) == 2


def test_reader_and_cooldown_reject_tampered_source(setup):
    settings, analytics, files = setup
    refresh_energy(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW)
    data, pin = load_product(analytics, "petroleum")
    Path(data["captures"][0]["root"], "balance.csv").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash"):
        EnergyInputs(**pin).snapshot(decision_at=NOW+timedelta(seconds=1))
    with pytest.raises(ValueError, match="hash"):
        refresh_energy(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW+timedelta(minutes=1))


def test_future_release_and_stale_or_missing_captures_cannot_enter_features(setup):
    settings, analytics, files = setup
    with pytest.raises(ValueError, match="future"):
        refresh_energy(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW-timedelta(days=10))
    files["https://ir.eia.gov/wpsr/table1.csv"] = files["https://ir.eia.gov/wpsr/table1.csv"].replace(b'"13,979"', b'"--"')
    refresh_energy(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW)
    _, pin = load_product(analytics, "petroleum")
    with pytest.raises(ValueError, match="missing"):
        EnergyInputs(**pin).snapshot(decision_at=NOW+timedelta(seconds=1))
    assert all(p["stale"] for p in catalog(analytics, settings, now=NOW+timedelta(days=20))["products"])


def test_api_requires_pinned_capture_and_portal_exposes_view(setup, monkeypatch):
    settings, analytics, files = setup
    refresh_energy(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW)
    app = FastAPI()
    app.state.settings = settings
    app.include_router(energy_data.router)
    monkeypatch.setattr(energy_data, "_store", lambda _: analytics)
    client = TestClient(app)
    response = client.get("/api/v1/market-data/energy/catalog")
    assert response.status_code == 200
    product = response.json()["products"][0]
    params = dict(product="petroleum", capture=product["captures"][0]["batch"], catalog_batch=product["pin"]["batch"])
    assert len(client.get("/api/v1/market-data/energy/history", params=params).json()["metrics"]) == 12
    assert client.get("/api/v1/market-data/energy/history", params=dict(params, catalog_batch="0"*64)).status_code == 409
    assert client.get("/api/v1/market-data/energy/history", params=dict(params, capture="0"*64)).status_code == 503
    assert 'data-market-view="energy"' in market_data_audit_portal().body.decode()
