"""Synthetic source shapes: no issuer workbook/content is redistributed in tests."""
from datetime import UTC, datetime, timedelta
from html import escape
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from systematic_trading.market_data.analytics_store import encode
from systematic_trading.recorders.issuer_etfs import IssuerInputs, PREFIX, catalog, load_fund, refresh_issuer_etfs
from systematic_trading.recorders.issuer_parsers import parse_snapshot
from systematic_trading.web import issuer_data
from systematic_trading.web.platform import market_data_audit_portal

NOW = datetime(2026, 10, 9, 16, tzinfo=UTC)


def workbook(fund, *, weight="49.9", formula=False, duplicate=False, shared=False):
    rows = [["Fund Name:", fund["name"]], ["Ticker Symbol:", fund["symbol"]], ["Holdings:", "As of 08-Oct-2026"],
            ["Name", "Ticker", "Identifier", "SEDOL", "Weight", "Sector", "Shares Held", "Local Currency"],
            ["Synthetic One", "AAA", "ID-A", "SED-A", "50", "-", "200", "USD"],
            ["Synthetic Two", "BBB", "ID-A" if duplicate else "ID-B", "SED-B", weight, "-", "2E3", "USD"],
            ["US DOLLAR", "-", "CASH", "-", "0.1", "-", "2E4", "USD"], [], ["Synthetic footer"]]
    strings, xml = [], []
    for i, row in enumerate(rows, 1):
        cells = []
        for j, value in enumerate(row):
            ref = f'{chr(65+j)}{i}'
            f = '<f>1+1</f>' if formula and ref == "E5" else ""
            if shared:
                strings.append(value)
                cells.append(f'<c r="{ref}" t="s">{f}<v>{len(strings)-1}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr">{f}<is><t>{escape(value)}</t></is></c>')
        xml.append(f'<row r="{i}">'+''.join(cells)+'</row>')
    raw = BytesIO()
    with ZipFile(raw, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+''.join(xml)+'</sheetData></worksheet>')
        if shared:
            z.writestr("xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'+''.join('<si><t>'+escape(s)+'</t></si>' for s in strings)+'</sst>')
    return raw.getvalue()


def page(fund):
    def table(title, rows):
        return '<h3>'+title+' as of Oct 08 2026</h3><table>'+''.join('<tr>'+''.join('<th>'+escape(c)+'</th>' for c in row)+'</tr>' for row in rows)+'</table>'
    text = table("Listing Information", [["Exchange", "Listing Date", "Trading Currency", "Ticker", "CUSIP", "ISIN"],
                 [fund["exchange"], "Dec 22 1998", "USD", fund["symbol"], fund["cusip"], fund["isin"]]])
    text += table("Fund Net Asset Value", [["NAV", "$10.00"], ["Shares Outstanding", "2.00 M"], ["Assets Under Management", "$20.00 M"]])
    text += table("Fund Characteristics", [["Est. 3-5 Year EPS Growth", "-2.50%"], ["Number of Holdings", "2"], ["Price/Book Ratio", "1.50"], ["Price/Earnings Ratio FY1", "12.13"], ["Weighted Average Market Cap", "$50.00 M"]])
    text += table("Fund Industry Allocation", [["Sector", "Weight"], ["Synthetic industry A", "60.00%"], ["Synthetic industry B", "40.00%"]])
    # Tooltip text must not become a field label; index section must not be fund data.
    text = text.replace('NAV</th>', 'NAV<span class="info"><svg><use/></svg><div>Glossary NAV</div></span></th>')
    text += table("Index Characteristics", [["Price/Earnings Ratio FY1", "99.99"]])
    return text.encode()


class MemoryAnalytics:
    def __init__(self):
        self.publications, self.fail = {}, False

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
    config = json.loads(Path("config/issuer-etf-recorders.json").read_text(encoding="utf-8"))
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    settings = SimpleNamespace(issuer_etf_recorder_config_path=path, data_dir=tmp_path, governed_refresh_enabled=True)
    files = {f["files"][name]: raw for f in config["funds"] for name, raw in {"fund.html": page(f), "holdings.xlsx": workbook(f)}.items()}
    return settings, MemoryAnalytics(), files, config


@pytest.mark.parametrize("shared", [True, False])
def test_parser_identity_units_signed_values_missing_sectors_and_distinct_dates(setup, shared):
    _, _, _, config = setup
    fund = config["funds"][0]
    parsed = parse_snapshot({"fund.html": page(fund).replace(b'Fund Industry Allocation as of Oct 08', b'Fund Industry Allocation as of Oct 07'), "holdings.xlsx": workbook(fund, shared=shared)}, fund)
    values = {m["id"]: m["value"] for m in parsed["metrics"]}
    assert values["nav"] == "10.00" and values["shares"] == "2000000.00"
    assert values["aum"] == "20000000.00" and values["eps_growth"] == "-2.50"
    assert values["forward_pe"] == "12.13" and parsed["nav_reconciled"]
    assert parsed["dates"]["allocation"] == "2026-10-07" and parsed["dates"]["nav"] == "2026-10-08"
    assert parsed["holdings"]["weights_reconciled"]
    assert parsed["holdings"]["rows"][-1]["ticker"] is None
    assert all(r["sector"] is None for r in parsed["holdings"]["rows"])


@pytest.mark.parametrize("old,new", [(b'US81369Y5069', b'US0000000000'), (b'$20.00 M', b'$21.00 M'),
    (b'2.00 M', b'2.00 B'), (b'12.13', b'NaN'), (b'40.00%', b'10.00%'),
    (b'Price/Book Ratio', b'Unknown Ratio'), (b'Number of Holdings</th><th>2', b'Number of Holdings</th><th>5')])
def test_parser_rejects_identity_schema_units_and_accounting_failures(setup, old, new):
    fund = setup[3]["funds"][0]
    with pytest.raises(ValueError):
        parse_snapshot({"fund.html": page(fund).replace(old, new), "holdings.xlsx": workbook(fund)}, fund)


@pytest.mark.parametrize("kwargs", [dict(formula=True), dict(duplicate=True), dict(weight="NaN"), dict(weight="-")])
def test_holdings_reject_formula_missing_values_and_duplicate_identity(setup, kwargs):
    fund = setup[3]["funds"][0]
    with pytest.raises(ValueError):
        parse_snapshot({"fund.html": page(fund), "holdings.xlsx": workbook(fund, **kwargs)}, fund)


def test_weight_residual_is_visible_unscaled_and_blocks_only_holdings_features(setup):
    settings, analytics, files, config = setup
    fund = config["funds"][0]
    files[fund["files"]["holdings.xlsx"]] = workbook(fund, weight="49.8")
    refresh_issuer_etfs(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW)
    data, pin = load_fund(analytics, "XLE")
    reader = IssuerInputs(**pin)
    snapshot = reader.capture(data["captures"][0]["batch"])
    assert snapshot["holdings"]["weight_sum_percent"] == "99.9" and snapshot["warnings"]
    with pytest.raises(ValueError, match="residual"):
        reader.snapshot(decision_at=NOW+timedelta(seconds=1))
    qualified = reader.snapshot(decision_at=NOW+timedelta(seconds=1), groups=["nav"])
    assert len(qualified["metrics"]) == 3 and "holdings" not in qualified


def test_first_seen_immutable_pins_dedup_revisions_and_no_lookahead(setup):
    settings, analytics, files, config = setup
    assert refresh_issuer_etfs(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW)
    _, pin = load_fund(analytics, "XLE")
    old = IssuerInputs(**pin)
    for cutoff in [NOW-timedelta(days=20), NOW]:
        with pytest.raises(ValueError, match="available"):
            old.snapshot(decision_at=cutoff)
    assert not refresh_issuer_etfs(settings, analytics, fetch=lambda _: pytest.fail("cooldown ignored"), clock=lambda: NOW+timedelta(minutes=1))
    assert not refresh_issuer_etfs(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW+timedelta(hours=7))
    assert load_fund(analytics, "XLE")[1] == pin
    url = config["funds"][0]["files"]["fund.html"]
    files[url] = files[url].replace(b'12.13', b'13.13')
    assert refresh_issuer_etfs(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW+timedelta(hours=14))
    _, new_pin = load_fund(analytics, "XLE")
    current = IssuerInputs(**new_pin)
    def pe(reader, time):
        return next(m["value"] for m in reader.snapshot(decision_at=time)["metrics"] if m["id"] == "forward_pe")
    assert pe(current, NOW+timedelta(hours=13)) == "12.13"
    assert pe(current, NOW+timedelta(hours=15)) == "13.13"
    assert pe(old, NOW+timedelta(hours=15)) == "12.13"


def test_capture_after_responses_and_independent_funds_survive_schema_failure(setup):
    settings, analytics, files, config = setup
    current = NOW
    url = config["funds"][0]["files"]["fund.html"]
    files[url] = b"bad schema"
    def fetch(url):
        nonlocal current
        current += timedelta(seconds=1)
        return files[url]
    with pytest.raises(ValueError):
        refresh_issuer_etfs(settings, analytics, fetch=fetch, clock=lambda: current)
    assert analytics.latest(PREFIX+"XLE") is None
    data, _ = load_fund(analytics, "XOP")
    assert data["captures"][0]["first_seen_at"] == (NOW+timedelta(seconds=4)).isoformat()
    roots = list((settings.data_dir/"governance/issuer-etfs/XLE/captures").iterdir())
    assert (roots[0]/"fund.html").read_bytes() == b"bad schema"
    assert (roots[0]/"failure.json").exists()


def test_publication_failure_keeps_pin_and_retries_missing_feature_is_not_imputed(setup):
    settings, analytics, files, config = setup
    refresh_issuer_etfs(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW)
    _, pin = load_fund(analytics, "XLE")
    url = config["funds"][0]["files"]["fund.html"]
    files[url] = files[url].replace(b'12.13', b'--')
    analytics.fail = True
    with pytest.raises(ValueError):
        refresh_issuer_etfs(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW+timedelta(hours=7))
    assert load_fund(analytics, "XLE")[1] == pin
    analytics.fail = False
    refresh_issuer_etfs(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW+timedelta(hours=8))
    data, pin = load_fund(analytics, "XLE")
    reader = IssuerInputs(**pin)
    assert len(data["captures"]) == 2
    assert next(m["value"] for m in reader.capture(data["captures"][-1]["batch"])["metrics"] if m["id"] == "forward_pe") is None
    with pytest.raises(ValueError, match="missing"):
        reader.snapshot(decision_at=NOW+timedelta(hours=9))


def test_tamper_fails_reader_and_cooldown_without_hiding_other_funds(setup):
    settings, analytics, files, _ = setup
    refresh_issuer_etfs(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW)
    data, pin = load_fund(analytics, "XLE")
    Path(data["captures"][0]["root"], "holdings.xlsx").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash"):
        IssuerInputs(**pin).snapshot(decision_at=NOW+timedelta(seconds=1))
    with pytest.raises(ValueError, match="hash"):
        refresh_issuer_etfs(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW+timedelta(minutes=1))
    coverage = catalog(analytics, settings, now=NOW)
    assert coverage["funds"][0]["verification_error"] and coverage["funds"][0]["latest"] is None
    assert coverage["funds"][1]["latest"] is not None


def test_future_regressing_stale_dates_and_timezone_rejected(setup):
    settings, analytics, files, config = setup
    with pytest.raises(ValueError, match="future"):
        refresh_issuer_etfs(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW-timedelta(days=2))
    refresh_issuer_etfs(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW)
    _, pin = load_fund(analytics, "XLE")
    with pytest.raises(ValueError, match="stale"):
        IssuerInputs(**pin).snapshot(decision_at=NOW+timedelta(days=10))
    with pytest.raises(ValueError, match="timezone"):
        IssuerInputs(**pin).snapshot(decision_at=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError, match="Clock"):
        refresh_issuer_etfs(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW-timedelta(seconds=1))
    url = config["funds"][0]["files"]["fund.html"]
    files[url] = files[url].replace(b'Oct 08 2026', b'Oct 07 2026')
    with pytest.raises(ValueError, match="regressed"):
        refresh_issuer_etfs(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW+timedelta(hours=7))


def test_api_pins_and_market_data_view(setup, monkeypatch):
    settings, analytics, files, _ = setup
    refresh_issuer_etfs(settings, analytics, fetch=files.__getitem__, clock=lambda: NOW)
    app = FastAPI()
    app.state.settings = settings
    app.include_router(issuer_data.router)
    monkeypatch.setattr(issuer_data, "_store", lambda _: analytics)
    client = TestClient(app)
    fund = client.get("/api/v1/market-data/issuer-etfs/catalog").json()["funds"][0]
    params = dict(symbol="XLE", capture=fund["captures"][0]["batch"], catalog_batch=fund["pin"]["batch"])
    path = "/api/v1/market-data/issuer-etfs/history"
    assert len(client.get(path, params=params).json()["metrics"]) == 8
    assert client.get(path, params=dict(params, catalog_batch="0"*64)).status_code == 409
    assert client.get(path, params=dict(params, capture="0"*64)).status_code == 503
    assert client.get(path, params=dict(params, symbol="../XLE")).status_code == 422
    assert 'data-market-view="issuer"' in market_data_audit_portal().body.decode()
