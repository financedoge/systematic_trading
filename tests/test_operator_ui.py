import re

from fastapi.testclient import TestClient

from systematic_trading.app import create_app
from systematic_trading.config import AppSettings
from systematic_trading.research import current_sota_definition


EXPECTED_HEADER_LINKS = [
    ("/operator", "Trading"),
    ("/strategies", "Strategies"),
    ("/platform", "System"),
    ("/platform/market-data-audit", "Market Data"),
]


def _header_links(html: str) -> list[tuple[str, str]]:
    header = re.search(r"<header(?:\s[^>]*)?>(.*?)</header>", html, re.DOTALL)
    assert header is not None
    return re.findall(r'<a class="button" href="([^"]+)">([^<]+)</a>', header.group(1))


def test_operator_dashboard_is_served(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "operator.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.get("/operator")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    html = response.text
    assert "Trading Operator" in html
    assert "proposal-list" in html
    assert "Trading" in html
    assert "rail-panel" in html
    assert "Execution summary" in html
    assert "metric-completion" in html
    assert "Filled Qty" in html
    assert "Broker Records" in html
    assert "Done" in html
    assert "Approve" in html
    assert "Reject" in html
    assert "Resubmit Failed/Missing" in html
    assert "Validate IB" not in html
    assert "Submit TWAP Paper" not in html
    assert "Approved and submitted" in html
    assert "Performance" in html
    assert "Backtest theoretical vs actual account" in html
    assert "/strategies" in html
    assert '>Strategies</a>' in html
    assert "performance-range-buttons" in html
    assert "perf-range-start" in html
    assert "perf-range-end" in html
    assert "performance-analysis" in html
    assert "Sharpe" in html
    assert "Calmar" in html
    assert "Live PnL" in html
    assert "PnL Attribution" in html
    assert "Reference Fill PnL" in html
    assert "Execution Gain" in html
    assert "Missed Orders" in html
    assert "Missed Notional" in html
    assert "Missed Rebalances" in html
    assert "Not eligible for resubmission" in html
    assert "proposal-row.missed" in html
    assert "Execution Deadline" in html
    assert "execution-slippage-table" in html
    assert "slippage-chart" in html
    assert "Daily Slippage" in html
    assert "Cumulative Slippage" in html
    assert "Automation" in html
    assert "Market Data" in html
    assert "Auto-updated" in html
    assert "IB Holdings vs Strategy" in html
    assert "IB Portfolio Reconciliation" in html
    assert "Refresh IB" in html
    assert "Reset local to IB" in html
    assert "/dashboard/reconciliation/interactive-brokers" in html
    assert "/reset-to-broker" in html
    assert "confirm_reset_to_ib: true" in html
    assert "Refresh IB Account" not in html
    assert "Sync IB Fills" not in html
    assert "Save Snapshot" not in html
    assert "Collapse History" not in html
    assert "/api/v1/proposals" in html
    assert "/approve-and-submit" in html
    assert "/api/v1/automation/status" in html
    assert "/api/v1/dashboard/performance" in html
    assert "/api/v1/dashboard/holdings" in html
    assert "/api/v1/dashboard/pnl" in html
    assert "/api/v1/dashboard/pnl/snapshots" in html
    assert "/api/v1/dashboard/execution-quality" in html
    assert "history_limit=1" in html
    assert "/api/v1/execution/interactive-brokers/proposals/" in html
    assert "/api/v1/execution/interactive-brokers/orders" in html
    assert "/operator" in html
    assert 'href="/strategies">Strategies</a>' in html
    assert "/platform" in html
    assert "/platform/market-data-audit" in html
    assert "confirm_submit: true" in html
    assert "failed_only: true" in html
    assert 'route_order_type: "twap"' in html


def test_root_redirects_to_operator_dashboard(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "operator_root.db", data_dir=tmp_path)
    with TestClient(create_app(settings), follow_redirects=False) as client:
        response = client.get("/")

    assert response.status_code in {307, 308}
    assert response.headers["location"] == "/operator"


def test_strategy_catalog_portal_and_api_are_served(tmp_path) -> None:
    backtests = tmp_path / "backtests" / "sota_current"
    backtests.mkdir(parents=True)
    (backtests / "sota_price_volume_technical_tree_relative_adaptive_top6.json").write_text(
        '{"nav_series":[{"trade_date":"2025-01-02","nav_cnh":"100"},'
        '{"trade_date":"2025-01-03","nav_cnh":"101"}]}',
        encoding="utf-8",
    )
    settings = AppSettings(database_path=tmp_path / "strategies.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        page = client.get("/strategies")
        payload = client.get("/api/v1/strategies")
        detail_page = client.get("/strategies/sota_price_volume_technical_tree_relative_adaptive_top6")
        report_page = client.get(
            "/api/v1/strategies/sota_price_volume_technical_tree_relative_adaptive_top6/report"
        )
        detail = client.get("/api/v1/strategies/sota_price_volume_technical_tree_relative_adaptive_top6")

    assert page.status_code == 200
    assert "Strategy Registry" in page.text
    assert payload.status_code == 200
    assert payload.json()["registry_type"] == "artifact_catalog"
    assert payload.json()["strategies"][0]["is_sota"] is True
    assert payload.json()["strategies"][0]["lifecycle"] == "monitored"
    assert "Monitored" in page.text
    assert "Archived" in page.text
    assert detail_page.status_code == 200
    assert "location.replace(d.report_url)" in detail_page.text
    assert 'button.dataset.strategyLifecycle==="monitored"' in page.text
    assert report_page.status_code == 200
    assert "NAV, Benchmark, Holdings, Drawdowns" in report_page.text
    assert "Period Metrics" in report_page.text
    assert "Holdings And Contribution" in report_page.text
    assert '"monitoredThrough":"2025-01-03"' in report_page.text
    assert "Performance vs Benchmark" not in report_page.text
    assert detail.status_code == 200
    assert detail.json()["lifecycle"] == "monitored"
    assert detail.json()["artifact_end_date"] == "2025-01-03"


def test_platform_health_portal_is_served(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "platform.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.get("/platform")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    html = response.text
    assert "Platform Health" in html
    assert "Service Map" in html
    assert "Service Status" in html
    assert "Health Details" in html
    assert "/api/v1/platform/service-graph" in html
    assert "/health" in html
    assert "/operator" in html
    assert 'href="/strategies">Strategies</a>' in html
    assert "/platform" in html
    assert "/platform/market-data-audit" in html
    assert "/api/v1/platform/service-actions" in html
    assert "/api/v1/platform/services/" in html


def test_market_data_audit_portal_is_served(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "platform_audit.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.get("/platform/market-data-audit")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    html = response.text
    assert "Market Data" in html
    assert "Intraday Bars" in html
    assert "Daily Bars" in html
    assert "OHLCV" in html
    assert "Raw Evidence" in html
    assert '<select id="golden-symbol"' in html
    assert "<datalist id=\"golden-symbol-options\"" not in html
    assert "/api/v1/market-data/daily-symbols" in html
    assert "/api/v1/market-data/daily-bars" in html
    assert "/api/v1/market-data/audit" in html
    assert "latest_recorder_date" in html
    assert "Start Session" in html
    assert "End Session" in html
    assert 'data-sessions="1"' in html
    assert 'data-sessions="5"' in html
    assert 'data-sessions="10"' in html
    assert 'params.set("recorder_start_date"' in html
    assert 'params.set("recorder_end_date"' in html
    assert "/platform" in html
    assert "/operator" in html


def test_operational_pages_share_one_control_free_header(tmp_path) -> None:
    strategy_key = current_sota_definition().key
    backtests = tmp_path / "backtests" / "sota_current"
    backtests.mkdir(parents=True)
    (backtests / f"{strategy_key}.json").write_text(
        '{"nav_series":[{"trade_date":"2025-01-02","nav_cnh":"100"},'
        '{"trade_date":"2025-01-03","nav_cnh":"101"}]}',
        encoding="utf-8",
    )
    settings = AppSettings(database_path=tmp_path / "unified_headers.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        pages = [
            client.get(path).text
            for path in [
                "/operator",
                "/strategies",
                f"/strategies/{strategy_key}",
                "/platform",
                "/platform/market-data-audit",
            ]
        ]

    for html in pages:
        assert _header_links(html) == EXPECTED_HEADER_LINKS
        header = re.search(r"<header(?:\s[^>]*)?>(.*?)</header>", html, re.DOTALL)
        assert header is not None
        assert "<button" not in header.group(1)
        assert "status-line" not in header.group(1)
