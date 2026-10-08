from datetime import UTC, datetime
import json
from pathlib import Path
from types import SimpleNamespace

from systematic_trading.market_data.analytics_store import encode
from systematic_trading.recorders.positioning import (
    FAMILY, SOURCE, normalize, refresh_positioning,
)
from systematic_trading.web.platform import market_data_audit_portal


class MemoryAnalytics:
    def __init__(self):
        self.publications = {}
        self.rows = {}

    def latest(self, source):
        return self.publications.get(source)

    def publish(self, source, version, observations, documents=(), provenance=None):
        self.publications[source] = {"version": version, "provenance": encode(provenance or {})}
        self.rows[source] = observations
        return True

    def observations(self, source, *, family=None, limit=1000):
        rows = self.rows.get(source, [])
        return [r for r in rows if family is None or r["family"] == family][:limit]


def cot_row(day="2026-09-29T00:00:00.000", *, long="52000", short="31000"):
    return {
        "cftc_contract_market_code": "067411", "report_date_as_yyyy_mm_dd": day,
        "contract_market_name": "CRUDE OIL, LIGHT SWEET-WTI", "contract_units": "1000 barrels",
        "open_interest_all": "400000", "m_money_positions_long_all": long,
        "m_money_positions_short_all": short, "prod_merc_positions_long": "150000",
        "prod_merc_positions_short": "210000", "swap_positions_long_all": "100000",
        "swap__positions_short_all": "90000", "change_in_m_money_long_all": "1200",
        "change_in_m_money_short_all": "900",
    }


def test_normalize_net_position_is_signed_share_of_open_interest():
    config = json.loads(Path("config/positioning-recorders.json").read_text(encoding="utf-8"))
    market = next(m for m in config["markets"] if m["code"] == "067411")
    result = normalize(cot_row(), market, "2026-10-08T12:00:00+00:00")
    assert result["managed_money_net_pct_oi"] == "0.0525"
    assert result["producer_merchant_net_pct_oi"] == "-0.15"
    assert result["report_date"] == "2026-09-29"


def test_market_data_portal_exposes_fund_positioning_view():
    response = market_data_audit_portal()
    assert response.status_code == 200
    assert "Fund Positioning" in response.body.decode("utf-8")
    assert "/api/v1/market-data/positioning/catalog" in response.body.decode("utf-8")


def test_recorder_preserves_first_seen_for_unchanged_rows_and_versions_revisions(tmp_path):
    config = json.loads(Path("config/positioning-recorders.json").read_text(encoding="utf-8"))
    config["markets"] = [m for m in config["markets"] if m["code"] == "067411"]
    config_path = tmp_path / "positioning.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    settings = SimpleNamespace(positioning_recorder_config_path=config_path,
                               governed_refresh_enabled=True, data_dir=tmp_path)
    analytics = MemoryAnalytics()
    now1 = datetime(2026, 10, 8, 12, tzinfo=UTC)
    source = [cot_row("2026-09-22T00:00:00.000"), cot_row()]
    refresh_positioning(settings, analytics, now=now1, fetch=lambda _: source)
    first = [json.loads(r["payload"]) for r in analytics.observations(SOURCE, family=FAMILY)]
    assert {r["first_seen_at"] for r in first} == {now1.isoformat()}

    now2 = datetime(2026, 10, 9, 12, tzinfo=UTC)
    source.append(cot_row("2026-10-06T00:00:00.000"))
    refresh_positioning(settings, analytics, now=now2, fetch=lambda _: source)
    second = [json.loads(r["payload"]) for r in analytics.observations(SOURCE, family=FAMILY)]
    by_date = {r["report_date"]: r["first_seen_at"] for r in second}
    assert by_date["2026-09-22"] == now1.isoformat()
    assert by_date["2026-09-29"] == now1.isoformat()
    assert by_date["2026-10-06"] == now2.isoformat()

    now3 = datetime(2026, 10, 10, 12, tzinfo=UTC)
    source[1] = cot_row("2026-09-29T00:00:00.000", long="53000")
    refresh_positioning(settings, analytics, now=now3, fetch=lambda _: source)
    revised = [json.loads(r["payload"]) for r in analytics.observations(SOURCE, family=FAMILY)]
    by_date = {r["report_date"]: r["first_seen_at"] for r in revised}
    assert by_date["2026-09-22"] == now1.isoformat()
    assert by_date["2026-09-29"] == now3.isoformat()

    assert refresh_positioning(settings, analytics, now=now3.replace(minute=5),
                               fetch=lambda _: (_ for _ in ()).throw(AssertionError("unexpected frequent fetch"))) is False
