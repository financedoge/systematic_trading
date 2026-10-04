import copy
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from systematic_trading.backtest.reporting import render_backtest_report_html, render_saved_backtest_report_html
from systematic_trading.research import instruments_for_definition, current_sota_definition
from systematic_trading.web.asset_names import registered_asset_names, with_asset_names
from systematic_trading.web.operator import operator_dashboard


def test_registered_names_cover_strategy_and_benchmark_assets():
    names = registered_asset_names()
    for symbol, instrument in instruments_for_definition(current_sota_definition()).items():
        assert names[symbol] == instrument.name
    assert names['URTH'] == 'iShares MSCI World ETF'
    assert names['CASH'] == 'Cash balance'


def test_report_labels_are_standalone_and_leave_calculations_unchanged():
    report = {'currentAllocation': {'holdings': [{'symbol': 'GLD', 'weight': .3}]}}
    before = copy.deepcopy(report)
    html = render_backtest_report_html(report)
    assert report == before
    assert json.loads(re.search(r'const report = (.*);', html)[1]) == before
    assert with_asset_names(html) == html
    assert html.index('const AssetNames') < html.index('const report')
    assert 'SPDR Gold Shares' in html
    assert '<script src=' not in html


def test_saved_report_refresh_preserves_frozen_payload_and_unknown_formats():
    report = dict(chart=[], summary={'finalNav': 123456}, allocationOrder=['GLD'])
    original = '<html><head></head><body><script>const report = ' + json.dumps(report) + ';</script></body></html>'
    refreshed = render_saved_backtest_report_html(original)
    assert json.loads(re.search(r'const report = (.*);', refreshed)[1]) == report
    assert 'Asset name' in refreshed and 'SPDR Gold Shares' in refreshed
    assert render_saved_backtest_report_html('<p>Legacy custom report</p>') == '<p>Legacy custom report</p>'


def test_portfolio_order_and_report_name_columns_render_correctly():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required for rendered table checks')
    report = dict(
        monitoring={}, allocationOrder=['GLD', 'Cash'], colors={},
        currentAllocation=dict(holdings=[dict(symbol='GLD', quantity=42, weight=.3,
            scheduled_weight=.25, target_weight=.35, value_cnh=12345), dict(symbol='Cash', weight=.7)],
            country_exposure_cnh={}),
        usdModel=dict(snapshot=dict(features={}), predictions={'GLD': .1}),
        modelTraining=dict(training={}, forecasts=[dict(symbol='GLD', forecast=.2, inputs={'x': 1})],
            allocationStages=[dict(name='final', weights={'GLD': .3})],
            features=[dict(featureId='x')], trees=['<svg></svg>']),
        holdingContributions=dict(monthly=[dict(period='2026-09', holdings=[dict(symbol='GLD',
            startWeight=.25, averageWeight=.28, endWeight=.3, assetReturn=.1,
            contribution=.03, daysHeld=20, observations=21)])]),
    )
    result = subprocess.run([node, str(Path(__file__).with_name('asset_names_checks.cjs'))],
        input=json.dumps(dict(operator=operator_dashboard().body.decode(),
                             report=render_backtest_report_html(report))),
        text=True, encoding='utf-8', capture_output=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
