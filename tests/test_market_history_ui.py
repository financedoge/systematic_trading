import json
import shutil
import subprocess
from pathlib import Path

import pytest

from systematic_trading.web.market_history_ui import MARKET_HISTORY_UI_HTML
from systematic_trading.web.platform import market_data_audit_portal
from systematic_trading.web.research_archive_panel import RESEARCH_ARCHIVE_HTML


def test_market_history_debug_navigation_and_lazy_archives():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required for UI behavior checks')
    result = subprocess.run(
        [node, str(Path(__file__).with_name('market_history_ui_checks.cjs'))],
        input=json.dumps(dict(controller=MARKET_HISTORY_UI_HTML, archive=RESEARCH_ARCHIVE_HTML,
                              page=market_data_audit_portal().body.decode())),
        text=True, encoding='utf-8', capture_output=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
