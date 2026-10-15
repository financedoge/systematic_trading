import subprocess
import sys

import pytest

from systematic_trading.presentation.templates import load_template
from systematic_trading.web import operator, platform


@pytest.mark.parametrize("module,name,args", [
    (operator, "operator_dashboard", ()),
    (operator, "strategy_portal", ()),
    (operator, "strategy_detail_portal", ("one",)),
    (platform, "platform_health_portal", ()),
    (platform, "market_data_audit_portal", ()),
])
def test_static_pages_cache_only_html_not_mutable_responses(module, name, args):
    render = getattr(module, "_" + name + "_html")
    render.cache_clear()
    first = getattr(module, name)(*args)
    first.headers["x-private"] = "do not share"
    second = getattr(module, name)(*args)
    assert first is not second
    assert first.body == second.body
    assert "x-private" not in second.headers
    assert render.cache_info().hits == 1
    assert first.body.count(b'id="application-shell-style"') == 1


def test_presentation_import_does_not_load_api_or_broker():
    subprocess.run([sys.executable, "-c", "import sys; import systematic_trading.presentation.templates; "
                    "import systematic_trading.web.shell; "
                    "assert 'systematic_trading.web.api' not in sys.modules; "
                    "assert 'systematic_trading.execution.broker' not in sys.modules"], check=True, timeout=30)


@pytest.mark.parametrize("name", ["../config.py", "/operator.html", "web/../operator.html", "web\\operator.html", "C:/operator.html", "C:operator.html"])
def test_template_names_cannot_escape_packaged_assets(name):
    with pytest.raises(ValueError):
        load_template(name)


def test_frozen_bundle_contains_verified_report_resources(tmp_path):
    from systematic_trading.lean.fixtures import make_fixture_bundle
    from systematic_trading.lean.contracts import verify_bundle

    bundle = tmp_path / "bundle"
    make_fixture_bundle(bundle)
    manifest = verify_bundle(bundle)
    resource = "source/systematic_trading/presentation/assets/backtest/reporting_html_template.html"
    assert resource in manifest["manifest"]["files"]
    # Import the frozen copy from outside the checkout, just as an isolated worker does.
    subprocess.run([sys.executable, "-B", "-c",
                    f"import sys; sys.path.insert(0, {str(bundle / 'source')!r}); "
                    "from systematic_trading.backtest.reporting import HTML_TEMPLATE; "
                    "assert '<html' in HTML_TEMPLATE"], cwd=tmp_path, check=True, timeout=30)
    (bundle / resource).write_text("tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_bundle(bundle)


def test_report_assets_remain_in_calculation_identity():
    from systematic_trading.research.tracked_runtime import calculation_code_hashes

    hashes = {name.replace("\\", "/"): digest for name, digest in calculation_code_hashes().items()}
    assert "presentation/templates.py" in hashes
    assert "presentation/assets/backtest/reporting_html_template.html" in hashes
