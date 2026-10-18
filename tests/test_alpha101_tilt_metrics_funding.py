"""Defect 6 — every metric must be measured on the funded account, not after its first session.

The peer review's fixtures, verbatim: a $1,000,000 account whose first end-of-day NAV is $900,000
and whose final NAV is $1,000,000 has returned 0.0% and has drawn down 10%. The defective helper
read the first NAV as capital and returned +11.111% with no drawdown. These tests pin the corrected
anchor (funding -> first NAV -> ... -> last NAV), the drawdown peak that starts at funding, the
first funded session inside the daily/monthly/Sharpe series, and the fact that two arms which differ
only in their first funded session no longer cancel in a paired contrast.
"""
import ast
import json
from pathlib import Path

import pytest
from retained_artifacts import requires_artifact

from systematic_trading.research import alpha101_tilt_study as study
from systematic_trading.research import alpha101_tilt_replay_analysis as replay_analysis
from systematic_trading.research import alpha101_tilt_daily_analysis as daily_analysis
from systematic_trading.research import alpha101_tilt_daily_study as daily_study
from systematic_trading.research import alpha101_tilt_exit_analysis as exit_analysis
from systematic_trading.research import alpha101_tilt_exit_study as exit_study
from systematic_trading.research import alpha101_tilt_surface_analysis as surface_analysis
from systematic_trading.research import alpha101_tilt_surface_study as surface_study
from systematic_trading.research.alpha101_tilt_replay_analysis import (INITIAL_CAPITAL, declared_funding,
                                                                      load_all, metrics_from)

ROOT = Path('var/research/alpha101-tilt-replay-20261011-v2')
BUILT = pytest.mark.skipif(not (ROOT / 'analysis.json').exists(), reason='frozen tilt replay not built')
LEDGER = pytest.mark.skipif(not (ROOT / 'bundles' / 'SOTA-cost5-delay0-evaluation' / 'quotes').exists(),
                            reason='frozen replay bundle not built')


# --- the review's fixtures ---------------------------------------------------

def test_the_review_counterexample_reads_zero_percent_and_minus_ten_percent():
    """$1m funded, $900k first end-of-day NAV, $1m final NAV -> 0.0% and -10%."""
    nav = [dict(date='2021-01-04', nav=900_000.0), dict(date='2021-01-05', nav=1_000_000.0)]
    metrics = metrics_from(nav, initial_capital=1_000_000.0)
    assert metrics['total_return'] == pytest.approx(0.0, abs=1e-12)
    assert metrics['max_drawdown'] == pytest.approx(-0.10, abs=1e-12)
    assert metrics['daily'][0] == pytest.approx(-0.10, abs=1e-12)          # the funded first session
    assert metrics['monthly']['2021-01'] == pytest.approx(0.0, abs=1e-12)  # loss then recovery
    assert metrics['final_nav'] == 1_000_000.0
    assert metrics['initial_capital'] == 1_000_000.0
    assert metrics['sessions'] == 2                                        # two marks, two returns


def test_the_defective_first_nav_anchor_is_what_the_review_measured():
    """Kept as the regression: anchoring on nav[0] is exactly the +11.111% / no-drawdown reading."""
    nav = [dict(date='2021-01-04', nav=900_000.0), dict(date='2021-01-05', nav=1_000_000.0)]
    broken = metrics_from(nav, initial_capital=900_000.0)
    assert broken['total_return'] == pytest.approx(1.0 / 9.0)
    assert broken['max_drawdown'] == 0.0
    assert broken['total_return'] != metrics_from(nav, initial_capital=1_000_000.0)['total_return']


def test_entry_fees_alone_are_a_loss_on_a_funded_account():
    """A flat book that only paid its entry fees is down, not unchanged."""
    nav = [dict(date='2021-01-04', nav=999_500.0)]
    metrics = metrics_from(nav, initial_capital=1_000_000.0)
    assert metrics['total_return'] == pytest.approx(-0.0005, abs=1e-12)
    assert metrics['max_drawdown'] == pytest.approx(-0.0005, abs=1e-12)
    assert metrics['daily'] == [pytest.approx(-0.0005, abs=1e-12)]
    assert metrics['sessions'] == 1
    assert metrics['sharpe_zero_cash'] is None and metrics['volatility'] is None   # one session is not a sample


def test_a_funded_loss_and_recovery_never_forgets_the_drawdown():
    """The peak starts at funding, so a recovery to a new high does not erase the loss."""
    nav = [dict(date='2021-01-04', nav=900_000.0), dict(date='2021-01-05', nav=950_000.0),
           dict(date='2021-01-06', nav=1_050_000.0)]
    metrics = metrics_from(nav, initial_capital=1_000_000.0)
    assert metrics['total_return'] == pytest.approx(0.05, abs=1e-12)
    assert metrics['final_nav'] == 1_050_000.0
    assert metrics['max_drawdown'] == pytest.approx(-0.10, abs=1e-12)
    assert metrics['daily'][0] == pytest.approx(-0.10, abs=1e-12)
    assert metrics['daily'][1] == pytest.approx(950_000.0 / 900_000.0 - 1.0, abs=1e-12)
    assert metrics['daily'][2] == pytest.approx(1_050_000.0 / 950_000.0 - 1.0, abs=1e-12)
    assert metrics['monthly']['2021-01'] == pytest.approx(0.05, abs=1e-12)   # compounding, not summing


def test_paired_arms_with_different_first_session_pnl_do_not_cancel():
    """Two arms that differ only in session one are 2% apart, not identical."""
    winner = [dict(date='2021-01-04', nav=1_010_000.0), dict(date='2021-01-05', nav=1_010_000.0)]
    loser = [dict(date='2021-01-04', nav=990_000.0), dict(date='2021-01-05', nav=990_000.0)]
    up = metrics_from(winner, initial_capital=1_000_000.0)
    down = metrics_from(loser, initial_capital=1_000_000.0)
    assert up['monthly']['2021-01'] == pytest.approx(0.01, abs=1e-12)
    assert down['monthly']['2021-01'] == pytest.approx(-0.01, abs=1e-12)
    assert up['monthly']['2021-01'] - down['monthly']['2021-01'] == pytest.approx(0.02, abs=1e-12)
    assert up['total_return'] == pytest.approx(0.01, abs=1e-12)
    assert down['total_return'] == pytest.approx(-0.01, abs=1e-12)
    # the defective anchor dropped both first sessions, so the paired difference cancelled to zero
    broken = (metrics_from(winner, initial_capital=1_010_000.0)['monthly']['2021-01']
              - metrics_from(loser, initial_capital=990_000.0)['monthly']['2021-01'])
    assert broken == pytest.approx(0.0, abs=1e-12)


def test_the_funding_anchor_cannot_be_omitted_or_zero():
    nav = [dict(date='2021-01-04', nav=900_000.0)]
    with pytest.raises(ValueError, match='funding anchor'):
        metrics_from(nav, initial_capital=None)
    with pytest.raises(ValueError, match='at least one'):
        metrics_from([], initial_capital=1_000_000.0)
    with pytest.raises(ValueError, match='positive'):
        metrics_from(nav, initial_capital=0.0)


# --- every caller passes the study's own declaration --------------------------

@pytest.mark.parametrize('analysis, module', [
    (daily_analysis, daily_study), (exit_analysis, exit_study), (surface_analysis, surface_study)])
def test_each_analysis_module_reads_its_own_study_funding(analysis, module):
    declared = module.protocol()['initial_cash_usd']
    assert declared == 1_000_000
    assert analysis.INITIAL_CAPITAL == float(declared)
    assert declared_funding(module) == float(declared)


def test_the_replay_analysis_module_uses_the_tilt_study_funding():
    assert INITIAL_CAPITAL == float(study.protocol()['initial_cash_usd']) == 1_000_000.0
    assert declared_funding() == INITIAL_CAPITAL


def test_every_metrics_from_call_site_passes_the_funding_anchor():
    """A grep that cannot rot: every call in the four analysis modules names its funding."""
    for module in (replay_analysis, daily_analysis, exit_analysis, surface_analysis):
        tree = ast.parse(Path(module.__file__).read_text(encoding='utf8'))
        calls = [node for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                 and node.func.id == 'metrics_from']
        assert len(calls) == 1, module.__name__                      # one load_all call site each
        assert any(keyword.arg == 'initial_capital' for keyword in calls[0].keywords), module.__name__


# --- the frozen replay --------------------------------------------------------

@BUILT
@requires_artifact(ROOT / 'python')
def test_the_published_metrics_are_measured_from_the_declared_funding():
    name = study.job_name(('SOTA', 5, 0, 'evaluation'))
    row = load_all(ROOT)[name]
    funding = float(study.protocol()['initial_cash_usd'])
    assert row['initial_capital'] == funding
    assert row['total_return'] == pytest.approx(row['final_nav'] / funding - 1.0, abs=1e-12)
    payload = json.loads((ROOT / 'analysis.json').read_text(encoding='utf8'))
    published = payload['metrics']['SOTA']
    assert published['initial_capital'] == funding
    assert published['total_return'] == pytest.approx(row['total_return'], abs=1e-12)
    assert published['final_nav'] == pytest.approx(row['final_nav'], abs=1e-9)


@LEDGER
def test_the_first_funded_session_reconciles_against_the_fill_ledger():
    """Funding + the first session's marks and fees is exactly the first end-of-day NAV."""
    name = study.job_name(('SOTA', 5, 0, 'evaluation'))
    payload = json.loads((ROOT / 'python' / (name + '.json')).read_text(encoding='utf8'))
    funding = float(study.protocol()['initial_cash_usd'])
    first = payload['nav'][0]
    quotes = {}
    for path in (ROOT / 'bundles' / name / 'quotes').glob('*.csv'):
        for line in path.read_text(encoding='utf8').splitlines():
            stamp, price, kind = line.split(',')
            if stamp.startswith(first['date']):
                quotes.setdefault(path.stem, {})[kind] = float(price)
    fills = [row for row in payload['fills'] if row['date'] == first['date']]
    assert fills, 'the first session must have funded its positions'
    marked = sum(row['quantity'] * (quotes[row['symbol']]['close'] - float(row['price'])) for row in fills)
    fees = sum(float(row['fee']) for row in fills)
    assert float(first['nav']) - funding == pytest.approx(marked - fees, abs=0.01)
    metrics = metrics_from([dict(date=first['date'], nav=float(first['nav']))], initial_capital=funding)
    assert metrics['total_return'] == pytest.approx(float(first['nav']) / funding - 1.0, abs=1e-12)
    assert metrics['total_return'] < 0.0
    assert metrics['max_drawdown'] == pytest.approx(metrics['total_return'], abs=1e-12)
