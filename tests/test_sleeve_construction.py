"""P4.16 — sleeve-aware construction."""
import json
from decimal import Decimal
from pathlib import Path

import pytest
from retained_artifacts import requires_artifact

from systematic_trading.research import sleeve_construction_study as study
from systematic_trading.research import sleeve_construction_analysis as analysis
from systematic_trading.research import sleeve_construction_gate as gate

ROOT = Path('var/research/sleeve-construction-20261010-v1')
RECORD = ROOT / 'analysis.json'
BUILT = pytest.mark.skipif(not RECORD.exists(), reason='frozen sleeve study not built in this workspace')

# The corrected root published after the peer-review gate repair (defect 7).
ROOT_V2 = study.CURRENT_ROOT
RECORD_V2 = ROOT_V2 / 'analysis.json'
BUILT_V2 = pytest.mark.skipif(not RECORD_V2.exists(),
                              reason='corrected sleeve-construction study not built in this workspace')


# --- the frozen plan ----------------------------------------------------------

def test_the_sleeves_partition_the_universe_exactly_once():
    covered = [symbol for symbols in study.SLEEVES.values() for symbol in symbols]
    assert len(covered) == len(set(covered)) == 14
    assert set(covered) == {'SPY', 'VGK', 'EWJ', 'EWH', 'EWY', 'MCHI', 'XLE', 'XLB',
                            'IEF', 'TLT', 'LQD', 'HYG', 'DBC', 'GLD'}
    assert study.SLEEVE_OF['XLE'] == 'equity' and study.SLEEVE_OF['DBC'] == 'commodity'
    assert study.SLEEVE_OF['GLD'] == 'gold'


def test_composition_budgets_are_the_universe_shares():
    budget = study.budgets('SLV-COMP')
    assert sum(budget.values()) == pytest.approx(1.0)
    assert budget['equity'] == pytest.approx(8 / 14)
    assert budget['fixed_income'] == pytest.approx(4 / 14)
    assert budget['commodity'] == pytest.approx(1 / 14)
    assert budget['gold'] == pytest.approx(1 / 14)


def test_equal_budgets_are_equal_and_pooled_is_one_sleeve():
    assert set(study.budgets('SLV-EQ').values()) == {0.25}
    assert study.budgets('POOL') == {'pooled': 1.0}
    with pytest.raises(ValueError, match='Unregistered construction arm'):
        study.budgets('SLV-TUNED')


def test_slots_follow_the_declared_rule_and_stay_inside_each_sleeve():
    pooled = study.plan('POOL')
    assert pooled['slot_total'] == 6 and pooled['slots_per_sleeve'] == 6
    for arm in ('SLV-COMP', 'SLV-EQ'):
        plans = study.plan(arm)
        assert plans['slots_per_sleeve'] == 2
        for sleeve, count in plans['slots'].items():
            assert count == min(2, len(study.SLEEVES[sleeve]))
        # two slots for each of the two single-instrument sleeves is still one name each,
        # so both sleeve arms top out at six slots: the pooled control's own breadth
        assert plans['slot_total'] == 6


def test_the_overlay_is_the_existing_primitive_with_the_pooled_parameters():
    overlay = study.sleeve_overlay('SLV-COMP')
    assert overlay.top_n_per_sleeve == 2
    assert overlay.fallback_to_top_ranked is False
    assert (overlay.short_momentum_bars, overlay.medium_momentum_bars, overlay.long_momentum_bars) == (21, 63, 126)
    assert overlay.trend_weight == Decimal('0.75') and overlay.volume_weight == Decimal('0.25')
    assert overlay.min_long_momentum == Decimal('0')
    assert overlay.sleeve_by_symbol == study.SLEEVE_OF
    assert study.sleeve_overlay('POOL').top_n_per_sleeve == 6


# --- the registered family ----------------------------------------------------

def test_the_comparison_family_is_the_registered_six():
    assert len(study.COMPARISONS) == 6 and len(set(study.COMPARISONS)) == 6
    assert ('SLV-COMP', 'POOL') in study.COMPARISONS
    assert ('SLV-EQ', 'POOL') in study.COMPARISONS
    assert ('POOL', 'CP') in study.COMPARISONS


def test_jobs_cover_every_cost_delay_and_window():
    jobs = study.jobs(study.ARMS)
    assert len(jobs) == len(study.ARMS) * len(study.COSTS) * len(study.DELAYS) * len(study.WINDOWS)
    assert all(j[0] in study.ARMS for j in jobs)
    assert ('SLV-COMP', 5, 0, 'evaluation') in jobs and ('SLV-COMP', 20, 1, 'full') in jobs


def test_primary_conditions_are_the_frozen_ones():
    assert study.COST_BPS == 5 and study.DELAY == 0
    assert study.SEED == 2026101003
    assert study.BOOTSTRAP_BLOCKS == (3, 6, 12)


# --- verdict logic ------------------------------------------------------------

def _metrics(sharpe, calmar):
    arms = ('SLV-COMP', 'SLV-EQ', 'POOL', 'CP')
    return {arm: dict(sharpe_zero_cash=sharpe if arm == 'SLV-COMP' else 1.0,
                      calmar=calmar if arm == 'SLV-COMP' else 1.0) for arm in arms}


def _uncertainty(rows):
    return {str(block): rows for block in study.BOOTSTRAP_BLOCKS}


def test_supported_requires_both_better_risk_ratios_and_a_family_adjusted_interval():
    strong = _uncertainty([dict(comparison='SLV-COMP-POOL', mean_annual=0.03, ci95=[0.01, 0.05], holm_p=0.02)])
    assert analysis.supported(_metrics(1.2, 1.2), strong, ('SLV-COMP', 'POOL'))['supported'] is True
    # a positive interval without better risk ratios is not support
    assert analysis.supported(_metrics(0.9, 1.2), strong, ('SLV-COMP', 'POOL'))['supported'] is False
    # better risk ratios without a family-adjusted interval is not support
    weak = _uncertainty([dict(comparison='SLV-COMP-POOL', mean_annual=0.03, ci95=[-0.01, 0.05], holm_p=0.40)])
    assert analysis.supported(_metrics(1.2, 1.2), weak, ('SLV-COMP', 'POOL'))['supported'] is False


def test_supported_rejects_an_interval_whose_lower_bound_touches_zero():
    row = _uncertainty([dict(comparison='SLV-COMP-POOL', mean_annual=0.03, ci95=[0.0, 0.05], holm_p=0.01)])
    assert analysis.supported(_metrics(1.2, 1.2), row, ('SLV-COMP', 'POOL'))['positive_blocks'] == []


def test_contrast_lookup_is_by_registered_pair():
    rows = _uncertainty([dict(comparison='SLV-EQ-POOL', mean_annual=0.02, ci95=[0.0, 0.04], holm_p=0.5)])
    assert analysis.contrast(rows, ('SLV-EQ', 'POOL'), 6)['mean_annual'] == pytest.approx(0.02)
    with pytest.raises(StopIteration):
        analysis.contrast(rows, ('SLV-COMP', 'POOL'), 6)


def test_assess_returns_each_registered_status_branch():
    gate_record = dict(arms={'SLV-COMP': dict(status='reject', annual_cost_bps=46.8)},
                       boundary_cases=['SLV-COMP'])
    positive = _uncertainty([dict(comparison=f'{a}-{b}', mean_annual=0.01, ci95=[-0.01, 0.03], holm_p=0.9)
                             for a, b in study.COMPARISONS])
    verdict = analysis.assess(_metrics(1.2, 1.2), positive, gate_record)
    assert verdict['status'] == 'inconclusive' and verdict['gate']['boundary'] == ['SLV-COMP']
    negative = _uncertainty([dict(comparison=f'{a}-{b}', mean_annual=-0.01, ci95=[-0.03, 0.01], holm_p=0.9)
                             for a, b in study.COMPARISONS])
    assert analysis.assess(_metrics(1.2, 1.2), negative, gate_record)['status'] == 'rejected'


def test_assess_supports_the_primary_arm_only_when_the_rule_is_met():
    rows = _uncertainty([dict(comparison=f'{a}-{b}',
                              mean_annual=0.02 if (a, b) == ('SLV-COMP', 'POOL') else 0.0,
                              ci95=[0.01, 0.03] if (a, b) == ('SLV-COMP', 'POOL') else [-0.01, 0.01],
                              holm_p=0.01 if (a, b) == ('SLV-COMP', 'POOL') else 0.9)
                         for a, b in study.COMPARISONS])
    verdict = analysis.assess(_metrics(1.2, 1.2), rows, dict(arms={}, boundary_cases=[]))
    assert verdict['status'] == 'sleeve_supported' and verdict['primary']['supported'] is True


# --- the frozen study ---------------------------------------------------------

@BUILT
def test_the_frozen_report_and_its_receipts_reverify():
    from systematic_trading.lean.contracts import sha256
    report = json.loads(RECORD.read_text(encoding='utf8'))
    receipt = json.loads((ROOT / 'report_receipt.json').read_text(encoding='utf8'))
    assert sha256(ROOT / 'analysis.json') == receipt['sha256']
    assert sha256(ROOT / 'gate.json') == receipt['gate_sha256']
    assert set(report['metrics']) == {'POOL', 'SLV-COMP', 'SLV-EQ', 'CP', 'M1'}
    assert report['verdict']['status'] in {'sleeve_supported', 'equal_budget_supported', 'inconclusive', 'rejected'}


@BUILT
def test_the_gate_record_screened_every_arm_before_the_replays():
    record = json.loads((ROOT / 'gate.json').read_text(encoding='utf8'))
    assert set(record['arms']) == {'POOL', 'SLV-COMP', 'SLV-EQ', 'CP', 'M1'}
    assert record['arms']['SLV-EQ']['status'] == 'pass'
    assert record['arms']['SLV-COMP']['boundary_case'] is True
    assert record['boundary_cases'] == ['SLV-COMP']
    assert record['published']['matches_published'] is True
    assert record['gate_rejected'] == []


@BUILT
@requires_artifact(ROOT / 'controls')
def test_the_construction_matched_arm_reproduces_the_pooled_control_except_on_fallbacks():
    study.initialize(ROOT)
    parity = analysis.pool_vs_control(ROOT)
    assert parity['decisions'] == 130
    assert parity['differing'] == 11
    assert parity['membership_differences'] == 11 and parity['weight_only_differences'] == 0
    assert parity['defensive_fallback_differences'] == 11


@BUILT
@requires_artifact(ROOT / 'controls')
def test_every_frozen_decision_respects_the_cap_and_the_sleeve_slot_contract():
    study.initialize(ROOT)
    protocol = json.loads((ROOT / 'protocol.json').read_text(encoding='utf8'))
    for arm in study.ARMS:
        plans = protocol['arms'][arm]
        slots = plans['slots']
        for day, row in analysis.decision_rows(ROOT, arm).items():
            weights = {t['symbol']: Decimal(t['target_weight']) for t in row['targets']}
            held = {s for s, w in weights.items() if w > 0}
            assert all(w >= 0 for w in weights.values()), (arm, day)
            assert all(w <= Decimal('0.45') for w in weights.values()), (arm, day)
            assert sum(weights.values()) <= Decimal('0.98') + Decimal('1e-12'), (arm, day)
            # the sleeve contract is a selection-layer constraint: the budgets and per-sleeve
            # slots decide which names enter, while downstream overlays and adaptive-trend
            # exposure may move realised weights and gross afterwards
            if arm == 'POOL':
                assert len(held) <= slots['pooled'], (arm, day)
                continue
            for sleeve, symbols in study.SLEEVES.items():
                assert len(held & set(symbols)) <= slots[sleeve], (arm, day, sleeve)


# --- the corrected v2 root (peer-review gate repair) --------------------------

_BARS_CACHE = {}


def _bars_and_session_index(root):
    key = str(root)
    if key not in _BARS_CACHE:
        bars = json.loads((root / 'bars.json').read_text(encoding='utf8'))
        _BARS_CACHE[key] = (bars, {row['trade_date']: index for index, row in enumerate(bars['SPY'])})
    return _BARS_CACHE[key]


def _gate_momentum(root, symbol, day, lookback=126):
    """The absolute 126-session momentum the construction overlay itself sees on ``day``."""
    bars, session_index = _bars_and_session_index(root)
    index = session_index[day]
    history = bars[symbol][max(0, index - 500):index]
    if len(history) < lookback + 1:
        return None
    return (Decimal(str(history[-1]['close'])) / Decimal(str(history[-(lookback + 1)]['close']))) - Decimal('1')


@BUILT_V2
def test_the_corrected_root_reverifies_its_own_receipts_and_records_the_repair():
    from systematic_trading.lean.contracts import sha256
    report = json.loads(RECORD_V2.read_text(encoding='utf8'))
    receipt = json.loads((ROOT_V2 / 'report_receipt.json').read_text(encoding='utf8'))
    protocol = json.loads((ROOT_V2 / 'protocol.json').read_text(encoding='utf8'))
    assert sha256(ROOT_V2 / 'analysis.json') == receipt['sha256']
    assert sha256(ROOT_V2 / 'gate.json') == receipt['gate_sha256']
    assert protocol['version'] == study.VERSION == 'sleeve-construction-v2'
    assert protocol['supersedes']['root'] == str(study.SUPERSEDES)
    assert 'sleeve-construction-20261010-v1' in protocol['supersedes']['evidence']
    assert 'before any ranking or rank fallback' in protocol['momentum_gate']
    assert 'independently of' in protocol['momentum_gate']
    assert set(report['metrics']) == {'POOL', 'SLV-COMP', 'SLV-EQ', 'CP', 'M1'}
    assert report['verdict']['status'] in {'sleeve_supported', 'equal_budget_supported', 'inconclusive', 'rejected'}


@BUILT_V2
def test_the_gate_record_screened_every_corrected_arm_before_the_replays():
    record = json.loads((ROOT_V2 / 'gate.json').read_text(encoding='utf8'))
    assert set(record['arms']) == {'POOL', 'SLV-COMP', 'SLV-EQ', 'CP', 'M1'}
    assert record['arms']['SLV-EQ']['status'] == 'pass'
    assert record['arms']['SLV-COMP']['boundary_case'] is True
    assert record['boundary_cases'] == ['SLV-COMP']
    assert record['published']['matches_published'] is True
    assert record['gate_rejected'] == []


@BUILT_V2
@requires_artifact(ROOT_V2 / 'decisions')
def test_no_corrected_decision_holds_a_name_whose_momentum_gate_failed():
    """The regression the review asked for: the gate holds for one-name sleeves too."""
    protocol = json.loads((ROOT_V2 / 'protocol.json').read_text(encoding='utf8'))
    for arm in study.ARMS:
        for day, row in analysis.decision_rows(ROOT_V2, arm).items():
            for target in row['targets']:
                if Decimal(target['target_weight']) <= 0:
                    continue
                momentum = _gate_momentum(ROOT_V2, target['symbol'], day)
                assert momentum is not None and momentum > 0, (arm, day, target['symbol'], momentum)
    assert protocol['evaluation_start']


@BUILT_V2
@requires_artifact(ROOT_V2 / 'decisions')
def test_the_single_instrument_sleeves_are_held_exactly_on_their_gate_positive_days():
    """The published 'permanent DBC/GLD exposure' reading, re-derived under the repair."""
    evaluation_start = json.loads((ROOT_V2 / 'protocol.json').read_text(encoding='utf8'))['evaluation_start']
    for arm in ('SLV-COMP', 'SLV-EQ'):
        rows = analysis.decision_rows(ROOT_V2, arm)
        evaluation_days = sorted(day for day in rows if day >= evaluation_start)
        admission = analysis.admission(ROOT_V2, arms=(arm,), window_days=evaluation_days)[arm]
        assert len(evaluation_days) == 70 and len(rows) == 130
        for symbol in ('DBC', 'GLD'):
            held_days = {day for day, row in rows.items()
                         if symbol in {t['symbol'] for t in row['targets'] if Decimal(t['target_weight']) > 0}}
            gate_days = {day for day in rows
                         if (_gate_momentum(ROOT_V2, symbol, day) or Decimal(0)) > Decimal('0')}
            assert held_days == gate_days, (arm, symbol)
            assert admission['held_counts'][symbol] == len(held_days & set(evaluation_days)) == 49
            assert len(gate_days & set(evaluation_days)) < len(evaluation_days)  # not "throughout"
            assert len(gate_days) == (80 if symbol == 'DBC' else 94)


@BUILT_V2
@requires_artifact(ROOT / 'decisions')
def test_the_repair_moves_only_the_single_instrument_sleeves():
    """Every other admission count, and the pooled arm's decisions, are unchanged."""
    v1 = analysis.admission(ROOT)
    v2 = analysis.admission(ROOT_V2)
    for arm in ('SLV-COMP', 'SLV-EQ', 'POOL'):
        changed = {symbol for symbol in v1[arm]['held_counts']
                   if v1[arm]['held_counts'][symbol] != v2[arm]['held_counts'][symbol]}
        assert changed == ({'DBC', 'GLD'} if arm != 'POOL' else set()), (arm, changed)
    assert analysis.pool_vs_control(ROOT_V2)['differing'] == 11
    old = analysis.decision_rows(ROOT, 'POOL')
    new = analysis.decision_rows(ROOT_V2, 'POOL')
    for day in old:
        before = {t['symbol']: Decimal(t['target_weight']) for t in old[day]['targets']}
        after = {t['symbol']: Decimal(t['target_weight']) for t in new[day]['targets']}
        assert before == after, ('POOL', day)
