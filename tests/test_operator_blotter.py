from pathlib import Path
import shutil
import subprocess

import pytest

from systematic_trading.web.trading_workspace import WORKSPACE_HTML, WORKSPACE_JS


def test_default_blotter_keeps_todays_completed_orders_visible():
    assert '<option value="today" selected>Today</option>' in WORKSPACE_HTML
    assert '<option value="all" selected>All statuses</option>' in WORKSPACE_HTML
    assert 'id="order-date-start"' in WORKSPACE_HTML
    assert 'id="order-date-end"' in WORKSPACE_HTML


def test_blotter_filters_and_completed_order_history():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for blotter behavior checks.")
    result = subprocess.run([node, str(Path(__file__).with_name("operator_blotter_checks.cjs"))],
                            input=WORKSPACE_JS, text=True, encoding="utf-8", capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
