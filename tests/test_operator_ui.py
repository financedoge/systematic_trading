from fastapi.testclient import TestClient

from systematic_trading.app import create_app
from systematic_trading.config import AppSettings


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
    assert "execution-slippage-table" in html
    assert "slippage-chart" in html
    assert "Daily Slippage" in html
    assert "Cumulative Slippage" in html
    assert "Automation" in html
    assert "Market Data" in html
    assert "Auto-updated" in html
    assert "Holdings Drift" in html
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
    assert "/api/v1/execution/interactive-brokers/proposals/" in html
    assert "/api/v1/execution/interactive-brokers/orders" in html
    assert "confirm_submit: true" in html
    assert "failed_only: true" in html
    assert 'route_order_type: "twap"' in html


def test_root_redirects_to_operator_dashboard(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "operator_root.db", data_dir=tmp_path)
    with TestClient(create_app(settings), follow_redirects=False) as client:
        response = client.get("/")

    assert response.status_code in {307, 308}
    assert response.headers["location"] == "/operator"
