import json
from pathlib import Path
import shutil
import subprocess

import pytest

from systematic_trading.chart_navigation import CHART_NAVIGATION_HTML, with_chart_navigation
from systematic_trading.backtest.reporting import HTML_TEMPLATE
from systematic_trading.web.operator import operator_dashboard, strategy_detail_portal
from systematic_trading.web.platform import market_data_audit_portal


def test_chart_navigation_and_page_scripts():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required for interaction checks')
    pages = [operator_dashboard().body.decode(), strategy_detail_portal('test').body.decode(),
             market_data_audit_portal().body.decode(),
             with_chart_navigation(HTML_TEMPLATE.replace('__REPORT_DATA__', '{}'))]
    result = subprocess.run([node, str(Path(__file__).with_name('chart_navigation_checks.cjs'))],
        input=json.dumps(dict(helper=CHART_NAVIGATION_HTML,pages=pages)),text=True,capture_output=True,timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_navigation_embedding_is_standalone_and_idempotent():
    html = with_chart_navigation('<html><head></head><body><script>render()</script></body></html>')
    assert with_chart_navigation(html) == html
    assert html.index('globalThis.ChartNavigation') < html.index('render()')
    assert '<script src=' not in html
