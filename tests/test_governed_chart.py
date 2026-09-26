"""Run the actual inline chart handlers against a small deterministic DOM fixture."""
import shutil
import subprocess
from pathlib import Path

import pytest

from systematic_trading.web.governed_panel import GOVERNED_HTML


def test_governed_chart_interactions():
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node.js is required for UI behavior checks.')
    result = subprocess.run(
        [node, str(Path(__file__).with_name('governed_chart_checks.cjs'))],
        input=GOVERNED_HTML, text=True, encoding='utf-8', capture_output=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
