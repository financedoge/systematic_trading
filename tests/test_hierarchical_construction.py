"""P4.16b — hierarchical construction: qualify asset classes, then pick inside them."""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from systematic_trading.research import hierarchical_construction_study as study
from systematic_trading.research import hierarchical_construction_analysis as analysis
from systematic_trading.research.hierarchical_selection import HierarchicalSelection
from systematic_trading.research.sleeve_construction_study import SLEEVES

ROOT = Path('var/research/hierarchical-construction-20261011-v1')
RECORD = ROOT / 'analysis.json'
BUILT = pytest.mark.skipif(not RECORD.exists(), reason='frozen hierarchical study not built in this workspace')

# The corrected root published after the peer-review repair (singleton gate + class-score population).
ROOT_V2 = study.DEFAULT_ROOT
RECORD_V2 = ROOT_V2 / 'analysis.json'
BUILT_V2 = pytest.mark.skipif(not RECORD_V2.exists(),
                              reason='corrected hierarchical study not built in this workspace')


def _rows(arm):
    return json.loads((ROOT / 'decisions' / f'{arm}.json').read_text(encoding='utf8'))


def _held(row):
    return {t['symbol'] for t in row['targets'] if float(t['target_weight']) > 0}


def _classes(held):
    return {sleeve for sleeve, symbols in SLEEVES.items() if held & set(symbols)}


# --- the frozen rule ----------------------------------------------------------

def test_the_declared_family_is_two_k_values_with_two_slots_each():
    assert study.ARMS == ('HIER-K2', 'HIER-K3')
    assert study.CLASS_CHOICES == {'HIER-K2': 2, 'HIER-K3': 3}
    assert study.SLOTS_PER_CLASS == 2
    assert study.plan('HIER-K2')['top_classes'] == 2 and study.plan('HIER-K3')['top_classes'] == 3
    with pytest.raises(ValueError, match='Unregistered hierarchical arm'):
        study.plan('HIER-K4')


def test_the_class_score_is_the_mean_of_the_members_the_class_holds():
    """v2 rule: the population is the held members, not the globally top-ranked ones."""
    assert study.class_score([Decimal('0.9'), Decimal('0.5'), Decimal('0.1')]) == Decimal('0.5')
    assert study.class_score([Decimal('0.4')]) == Decimal('0.4')
    with pytest.raises(ValueError):
        study.class_score([])


def test_the_registered_comparisons_name_the_control_and_the_k_contrast():
    assert ('HIER-K2', 'POOL') in study.COMPARISONS
    assert ('HIER-K3', 'POOL') in study.COMPARISONS
    assert ('HIER-K3', 'HIER-K2') in study.COMPARISONS
    assert len(study.COMPARISONS) == len(set(study.COMPARISONS)) == 5


def test_the_protocol_records_that_the_rule_is_post_hoc():
    protocol = json.loads((ROOT / 'protocol.json').read_text(encoding='utf8')) if RECORD.exists() else None
    if protocol is None:
        pytest.skip('frozen study not built')
    assert 'post-hoc' in protocol['post_hoc'].lower()
    assert 'not out-of-sample' in protocol['post_hoc']
    assert 'downtrend' in protocol['rule']['qualification']


def test_the_overlay_qualifies_before_it_ranks():
    overlay = study.hierarchical_overlay('HIER-K2')
    assert isinstance(overlay, HierarchicalSelection)
    assert overlay.top_classes == 2
    assert overlay.top_n_per_sleeve == study.SLOTS_PER_CLASS
    assert overlay.fallback_to_top_ranked is False
    assert (overlay.short_momentum_bars, overlay.medium_momentum_bars, overlay.long_momentum_bars) == (21, 63, 126)
    assert overlay.trend_weight == Decimal('0.75') and overlay.volume_weight == Decimal('0.25')


# --- verdict logic ------------------------------------------------------------

def _metrics(sharpe, calmar):
    return {arm: dict(sharpe_zero_cash=sharpe if arm == 'HIER-K2' else 1.0,
                      calmar=calmar if arm == 'HIER-K2' else 1.0)
            for arm in ('HIER-K2', 'HIER-K3', 'POOL', 'CP')}


def _uncertainty(rows):
    return {str(block): rows for block in study.BOOTSTRAP_BLOCKS}


def test_supported_needs_both_better_risk_ratios_and_a_family_adjusted_interval():
    strong = _uncertainty([dict(comparison='HIER-K2-POOL', mean_annual=0.05, ci95=[0.01, 0.10], holm_p=0.02)])
    assert analysis.supported(_metrics(1.2, 1.2), strong, ('HIER-K2', 'POOL'))['supported'] is True
    # a raw interval excluding zero is not enough while the family adjustment fails
    raw_only = _uncertainty([dict(comparison='HIER-K2-POOL', mean_annual=0.05, ci95=[0.01, 0.10], holm_p=0.16)])
    verdict = analysis.supported(_metrics(1.2, 1.2), raw_only, ('HIER-K2', 'POOL'))
    assert verdict['supported'] is False and verdict['positive_blocks'] == []
    assert analysis.supported(_metrics(0.9, 1.2), strong, ('HIER-K2', 'POOL'))['supported'] is False


def test_assess_reports_each_registered_status():
    gate = dict(arms={'HIER-K2': dict(status='reject', annual_cost_bps=45.5)}, boundary_cases=['HIER-K2'])
    positive = _uncertainty([dict(comparison=f'{a}-{b}', mean_annual=0.01, ci95=[-0.01, 0.03], holm_p=0.9)
                             for a, b in study.COMPARISONS])
    verdict = analysis.assess(_metrics(1.2, 1.2), positive, gate)
    assert verdict['status'] == 'inconclusive' and verdict['gate']['boundary'] == ['HIER-K2']
    negative = _uncertainty([dict(comparison=f'{a}-{b}', mean_annual=-0.01, ci95=[-0.03, 0.01], holm_p=0.9)
                             for a, b in study.COMPARISONS])
    assert analysis.assess(_metrics(1.2, 1.2), negative, gate)['status'] == 'rejected'


# --- the frozen study ---------------------------------------------------------

@BUILT
def test_the_frozen_report_and_receipts_reverify():
    from systematic_trading.lean.contracts import sha256
    report = json.loads(RECORD.read_text(encoding='utf8'))
    receipt = json.loads((ROOT / 'report_receipt.json').read_text(encoding='utf8'))
    assert sha256(ROOT / 'analysis.json') == receipt['sha256']
    assert sha256(ROOT / 'gate.json') == receipt['gate_sha256']
    assert set(report['metrics']) == {'HIER-K2', 'HIER-K3', 'POOL', 'CP', 'M1'}
    assert report['verdict']['status'] in {'hierarchical_supported', 'three_class_supported', 'inconclusive',
                                          'rejected'}


@BUILT
def test_every_reference_replay_reproduces_the_parent_statistics():
    report = json.loads(RECORD.read_text(encoding='utf8'))
    assert set(report['reference_parity']) == {'CP', 'M1', 'POOL'}
    assert all(report['reference_parity'].values())


@BUILT
def test_the_gate_record_screened_both_arms_before_the_replays():
    record = json.loads((ROOT / 'gate.json').read_text(encoding='utf8'))
    assert set(record['arms']) == {'HIER-K2', 'HIER-K3', 'CP', 'M1'}
    assert record['arms']['HIER-K3']['status'] == 'pass'
    assert record['arms']['HIER-K2']['boundary_case'] is True
    assert record['boundary_cases'] == ['HIER-K2']
    assert record['gate_rejected'] == []


@BUILT
def test_no_arm_ever_forces_more_classes_or_names_than_the_rule_allows():
    for arm in study.ARMS:
        limit = study.CLASS_CHOICES[arm]
        for day, row in _rows(arm).items():
            held = _held(row)
            assert len(_classes(held)) <= limit, (arm, day, held)
            for sleeve in _classes(held):
                assert len(held & set(SLEEVES[sleeve])) <= study.SLOTS_PER_CLASS, (arm, day, sleeve)
            weights = {t['symbol']: Decimal(t['target_weight']) for t in row['targets']}
            assert all(w >= 0 for w in weights.values()), (arm, day)
            assert all(w <= Decimal('0.45') for w in weights.values()), (arm, day)
            assert sum(weights.values()) <= Decimal('0.98') + Decimal('1e-12'), (arm, day)


@BUILT
def test_the_rule_dropped_a_downtrending_class_exactly_as_intended():
    """The operator's example: bonds into a rising-rate year must not be forced in."""
    for arm in study.ARMS:
        rows = _rows(arm)
        year = [d for d in sorted(rows) if d.startswith('2022')]
        assert year
        for day in year:
            held = _held(rows[day])
            assert not (held & set(SLEEVES['fixed_income'])), (arm, day, held)


@BUILT
def test_a_day_with_no_qualifying_class_is_cash_rather_than_a_forced_allocation():
    report = json.loads(RECORD.read_text(encoding='utf8'))
    for arm in study.ARMS:
        admission = report['admission'][arm]
        assert admission['cash_only_days'] >= 1
        assert admission['decisions'] == 70
    assert report['admission']['HIER-K2']['chosen_share']['fixed_income'] < \
        report['admission']['POOL']['chosen_share']['fixed_income']


@BUILT
def test_the_pinned_parent_study_is_unchanged():
    from systematic_trading.lean.contracts import sha256
    receipt = json.loads((ROOT / 'data_receipt.json').read_text(encoding='utf8'))
    # the root's own receipt records the parent it was frozen against, so the check does not
    # follow the module's current default root
    for name, digest in receipt['parent_hashes'].items():
        assert sha256(Path(receipt['parent']) / name) == digest
    for name, digest in receipt['parent_replay_hashes'].items():
        assert sha256(Path(receipt['parent']) / 'decisions' / f'{name}.json') == digest


# --- the corrected v2 root (peer-review repair) -------------------------------

def _v2_rows(arm):
    return json.loads((ROOT_V2 / 'decisions' / f'{arm}.json').read_text(encoding='utf8'))


_BARS_CACHE = {}


def _gate_momentum(symbol, day, lookback=126):
    if 'data' not in _BARS_CACHE:
        bars = json.loads((ROOT_V2 / 'bars.json').read_text(encoding='utf8'))
        _BARS_CACHE['data'] = (bars, {row['trade_date']: index for index, row in enumerate(bars['SPY'])})
    bars, session_index = _BARS_CACHE['data']
    history = bars[symbol][max(0, session_index[day] - 500):session_index[day]]
    if len(history) < lookback + 1:
        return None
    return (Decimal(str(history[-1]['close'])) / Decimal(str(history[-(lookback + 1)]['close']))) - Decimal('1')


@BUILT_V2
def test_the_corrected_root_reverifies_its_receipts_and_registers_both_populations():
    from systematic_trading.lean.contracts import sha256
    report = json.loads(RECORD_V2.read_text(encoding='utf8'))
    receipt = json.loads((ROOT_V2 / 'report_receipt.json').read_text(encoding='utf8'))
    protocol = json.loads((ROOT_V2 / 'protocol.json').read_text(encoding='utf8'))
    assert sha256(ROOT_V2 / 'analysis.json') == receipt['sha256']
    assert sha256(ROOT_V2 / 'gate.json') == receipt['gate_sha256']
    assert protocol['version'] == study.VERSION == 'hierarchical-construction-v2'
    assert protocol['parent']['root'].endswith('sleeve-construction-20261010-v2')
    assert protocol['supersedes']['root'] == str(study.SUPERSEDES)
    assert 'within-sleeve reranking' in protocol['rule']['class_score']
    assert 'global cross-section rank table' in protocol['rule']['class_score']
    assert 'never scored from a member it does not hold' in protocol['rule']['member_scores']
    assert 'before any ranking or fallback' in protocol['rule']['qualification']
    assert set(report['metrics']) == {'HIER-K2', 'HIER-K3', 'POOL', 'CP', 'M1'}
    assert report['reference_parity'] == {'CP': True, 'M1': True, 'POOL': True}


@BUILT_V2
def test_no_corrected_hierarchical_decision_holds_a_name_that_failed_the_gate():
    for arm in study.ARMS:
        for day, row in _v2_rows(arm).items():
            for target in row['targets']:
                if Decimal(target['target_weight']) <= 0:
                    continue
                momentum = _gate_momentum(target['symbol'], day)
                assert momentum is not None and momentum > 0, (arm, day, target['symbol'], momentum)


@BUILT_V2
def test_the_corrected_arms_hold_exactly_what_the_published_arms_held():
    """The class-score population repair changes no choice on the pinned decisions."""
    for arm in study.ARMS:
        before, after = _rows(arm), _v2_rows(arm)
        assert set(before) == set(after)
        for day in before:
            assert {t['symbol']: Decimal(t['target_weight']) for t in before[day]['targets']} == \
                {t['symbol']: Decimal(t['target_weight']) for t in after[day]['targets']}, (arm, day)


@BUILT_V2
def test_the_class_score_audit_records_how_often_the_populations_disagreed():
    """The audit re-derives the superseded population on the corrected decisions."""
    from systematic_trading.lean.contracts import sha256
    audit_path = ROOT_V2 / 'audit' / 'class-score-population.json'
    assert audit_path.exists()
    audit = json.loads(audit_path.read_text(encoding='utf8'))
    assert audit['days'] == 130
    for path, digest in audit['source_sha256'].items():
        assert sha256(Path(path)) == digest
    frozen_overlay = ROOT_V2 / 'source/systematic_trading/research/hierarchical_selection.py'
    assert audit['source_sha256'][str(frozen_overlay.resolve())] == sha256(frozen_overlay)
    assert 'mean of the global member scores of exactly the members' in \
        frozen_overlay.read_text(encoding='utf8')
    for arm in study.ARMS:
        row = audit['arms'][arm]
        assert row['decisions'] == 130
        assert row['mismatched_days'] == 35 and row['chosen_mismatch_days'] == 0
        assert row['member_mismatch_pairs'] == 38 and row['score_mismatch_pairs'] == 36
        assert row['member_mismatch_by_sleeve'] == {'fixed_income': 19, 'equity': 19}
        # the review's case is present in the published evidence, not only in a synthetic fixture
        assert any(pair['sleeve'] == 'fixed_income' and pair['v1_members'] == ['HYG', 'TLT']
                   and pair['held'] == ['LQD', 'TLT'] for pair in row['member_mismatch'])


@BUILT_V2
def test_the_corrected_arms_still_drop_the_downtrending_class():
    for arm in study.ARMS:
        rows = _v2_rows(arm)
        year = [day for day in sorted(rows) if day.startswith('2022')]
        assert year
        for day in year:
            assert not (_held(rows[day]) & set(SLEEVES['fixed_income'])), (arm, day)
    report = json.loads(RECORD_V2.read_text(encoding='utf8'))
    assert report['admission']['HIER-K2']['chosen_share']['fixed_income'] < \
        report['admission']['POOL']['chosen_share']['fixed_income']
    assert report['admission']['HIER-K2']['cash_only_days'] == 1
