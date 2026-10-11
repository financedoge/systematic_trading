"""P4.14 Part B — FR25 placebo, refit and sensitivity study."""
from decimal import Decimal
import json
from pathlib import Path

import numpy as np
import pytest

from systematic_trading.research import fr25_placebo_study as study
from systematic_trading.research import fr25_placebo_analysis as analysis
from systematic_trading.research.selection_blend import BLENDS

ROOT = Path('var/research/fr25-placebo-20261010-v1')
PARENT = Path('var/research/selection-blend-20261010-v1')
EVIDENCE = ROOT / 'placebo.json'
BUILT = pytest.mark.skipif(not EVIDENCE.exists() or not (ROOT / 'decisions/FR25.json').exists(),
                           reason='frozen placebo evidence not built in this workspace')
DAYS = ['2020-12-31', '2021-01-04', '2021-02-01', '2021-03-01']
SYMBOLS = ['AAA', 'BBB', 'CCC', 'DDD']


def _label(i):
    """One monthly training row; 60 rows run from 2018-01 past the 2022 refit cutoff."""
    year, month = 2018 + i // 12, i % 12 + 1
    end_year, end_month = (year, month + 1) if month < 12 else (year + 1, 1)
    return dict(start=f'{year:04d}-{month:02d}-01', end=f'{end_year:04d}-{end_month:02d}-01',
                vintage=f'{year:04d}-01-01', x=[0.1 * (i % 5), -0.2, 0.3],
                y={s: 0.001 * (i + j) for j, s in enumerate(SYMBOLS)})


def _macro(day, values=None, rows=60):
    values = values or [0.01, -0.02, 0.03, -0.04]
    labels = [_label(i) for i in range(rows)]
    return dict(financial=dict(ready=True, group='financial', decision=day, known_through=day,
                               training_labels=labels, training_rows=len(labels), query=[0.05, -0.1, 0.2],
                               models={s: dict(linear_forecast=v, mean_return=0.0)
                                       for s, v in zip(SYMBOLS, values)}))


def _rank_table(values=None):
    values = values or ['-1', '-0.333333333333333333333333333', '0.333333333333333333333333333', '1']
    return {s: dict(momentum='0', xgb='0', ridge=v, combined='0') for s, v in zip(SYMBOLS, values)}


@pytest.fixture
def frozen(monkeypatch):
    selection = {day: {'FR25': dict(rank_table=_rank_table())} for day in DAYS[1:]}
    macro = {day: _macro(day) for day in DAYS[1:]}
    data = dict(selection=selection, macro=macro, days=DAYS, protocol=dict(evaluation_start='2021-01-04'))
    monkeypatch.setattr(study, '_DATA', data)
    return data


def _evidence(day, draws=(1, 2), abstain=False):
    source = {s: v['linear_forecast'] for s, v in study._DATA['macro'][day]['financial']['models'].items()}
    rows = {}
    for draw in draws:
        if abstain:
            rows[str(draw)] = dict(permutation=None, injected=None, injected_sha256=None,
                                   realised_ranks=None, changes=0, abstained=True, gross='0')
            continue
        permutation = [int(p) for p in study.draw_permutation(draw, study.decision_ordinal(day), len(SYMBOLS))]
        injection = study.expected_injection(day, permutation)
        rows[str(draw)] = dict(permutation=permutation, injected=injection,
                               injected_sha256=study.digest(injection),
                               realised_ranks=study.expected_ranks(day, permutation),
                               changes=0, abstained=False, gross='1')
    return dict(seed=study.SEED, draws=study.DRAWS,
                days={day: dict(source=None if abstain else source, draws=rows)})


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf8')


# --- registry -----------------------------------------------------------------

def test_study_blends_never_change_the_frozen_registry():
    assert BLENDS['R25'] == (3, 0, 1)
    assert BLENDS['X25'] == (3, 1, 0) and BLENDS['EQ'] == (1, 1, 1)
    study.register_blends()
    assert BLENDS['R25'] == (3, 0, 1)


def test_registered_study_weights_are_the_declared_ones():
    assert BLENDS['W10'] == (9, 0, 1) and BLENDS['W40'] == (3, 0, 2)
    assert study.BLEND_KEY[10] == 'W10' and study.BLEND_KEY[25] == 'R25' and study.BLEND_KEY[40] == 'W40'


# --- declared arms ------------------------------------------------------------

def test_sensitivity_arms_exclude_the_frozen_baseline():
    arms = study.sensitivity_arms()
    assert len(arms) == 11
    assert (6, 25) not in arms
    assert sorted(arms) == sorted([(n, w) for n in (4, 5, 6, 7) for w in (10, 25, 40) if (n, w) != (6, 25)])


def test_jobs_cover_every_declared_draw_exactly_once():
    jobs = study.jobs()
    placebo = [j for j in jobs if study.draw_of(j[0])]
    assert len(placebo) == study.DRAWS
    assert sorted(study.draw_of(j[0]) for j in placebo) == list(range(1, study.DRAWS + 1))
    assert all(j[1:] == (study.COST_BPS, study.DELAY, 'evaluation') for j in placebo)
    refit = [j for j in jobs if j[0] == study.REFIT_ARM]
    assert refit == [(study.REFIT_ARM, study.COST_BPS, study.DELAY, 'sub2023')]
    assert (study.CANDIDATE, study.COST_BPS, study.DELAY, 'sub2023') in jobs
    assert (study.CONTROL, study.COST_BPS, study.DELAY, 'sub2023') in jobs


def test_window_start_rejects_an_unregistered_window():
    with pytest.raises(ValueError, match='window'):
        study.window_start(dict(start='a', evaluation_start='b'), 'extended')


# --- calendar -----------------------------------------------------------------

def test_evaluation_days_use_the_decision_calendar_not_the_session_calendar(frozen):
    assert study.evaluation_days() == DAYS[1:]
    assert study.sub_days() == [d for d in DAYS[1:] if d >= study.SUB_START]


def test_decision_ordinal_is_the_position_in_the_frozen_calendar(frozen):
    assert sorted(frozen['selection']) == DAYS[1:]
    assert study.decision_ordinal('2021-01-04') == 0
    assert study.decision_ordinal('2021-03-01') == 2


# --- randomisation ------------------------------------------------------------

def test_draw_permutation_is_declared_and_order_independent():
    first = [study.draw_permutation(draw, 7, 14).tolist() for draw in range(1, 21)]
    again = [study.draw_permutation(draw, 7, 14).tolist() for draw in reversed(range(1, 21))][::-1]
    assert first == again
    assert all(sorted(p) == list(range(14)) for p in first)
    assert len({tuple(p) for p in first}) > 1


def test_draw_permutation_separates_draws_and_decisions():
    assert study.draw_permutation(1, 3, 14).tolist() != study.draw_permutation(2, 3, 14).tolist()
    assert study.draw_permutation(1, 3, 14).tolist() != study.draw_permutation(1, 4, 14).tolist()


def test_seed_is_the_declared_protocol_date():
    assert study.SEED == 20261010 and study.DRAWS == 200 and study.PLACEBO_PERCENTILE == 0.90


# --- injection ----------------------------------------------------------------

def test_injection_permutes_the_frozen_assignment_and_keeps_the_marginal(frozen):
    day = DAYS[1]
    source = study.frozen_ridge(day)
    ridge, assigned, permutation = study.injected_ridge(day, 5)
    assert sorted(assigned.values()) == sorted(source.values())
    assert set(assigned) == set(source)
    assert assigned != source or permutation == list(range(len(SYMBOLS)))
    assert sorted(permutation) == list(range(len(SYMBOLS)))
    assert {s: str(Decimal(v)) for s, v in assigned.items()} == {
        s: v['linear_forecast'] for s, v in ridge['models'].items()}
    assert ridge['ready'] is True and ridge['group'] == 'financial'


def test_identity_assignment_reproduces_the_frozen_ridge(frozen):
    ridge, assigned, permutation = study.injected_ridge(DAYS[2], 1, identity=True)
    assert permutation == list(range(len(SYMBOLS)))
    assert assigned == study.frozen_ridge(DAYS[2])


def test_permuted_ranks_are_the_permuted_frozen_ranks(frozen):
    day = DAYS[3]
    ranks = study.frozen_ranks(day)
    permutation = [int(p) for p in study.draw_permutation(9, study.decision_ordinal(day), len(SYMBOLS))]
    expected = study.expected_ranks(day, permutation)
    symbols = sorted(ranks)
    assert expected == {s: ranks[symbols[p]] for s, p in zip(symbols, permutation)}
    assert sorted(expected.values()) == sorted(ranks.values())


def test_abstained_day_has_no_frozen_ridge(monkeypatch, frozen):
    frozen['macro'][DAYS[1]]['financial']['ready'] = False
    frozen['selection'][DAYS[1]]['FR25']['rank_table'] = None
    assert study.frozen_ridge(DAYS[1]) is None
    ridge, assigned, permutation = study.injected_ridge(DAYS[1], 1)
    assert ridge is None and assigned is None and permutation is None


def test_a_ready_model_with_missing_ranks_is_rejected(monkeypatch, frozen):
    table = frozen['selection'][DAYS[1]]['FR25']['rank_table']
    table['AAA']['ridge'] = None
    with pytest.raises(ValueError, match='Partially populated'):
        study.frozen_ridge(DAYS[1])


def test_ranks_without_a_ready_model_are_rejected(frozen):
    frozen['macro'][DAYS[1]]['financial']['ready'] = False
    with pytest.raises(ValueError, match='without a ready'):
        study.frozen_ranks(DAYS[1])


# --- refit --------------------------------------------------------------------

def test_refit_sample_stops_at_the_declared_cutoff(frozen):
    rows = study.refit_rows(frozen['macro'][DAYS[1]]['financial'])
    assert rows and all(row['end'] <= study.REFIT_LABEL_CUTOFF for row in rows)
    assert len(rows) < len(frozen['macro'][DAYS[1]]['financial']['training_labels'])


def test_refit_requires_the_frozen_minimum_rows(frozen):
    financial = frozen['macro'][DAYS[1]]['financial']
    financial['training_labels'] = financial['training_labels'][:10]
    with pytest.raises(ValueError, match='minimum'):
        study.refit_rows(financial)
    with pytest.raises(ValueError, match='minimum'):
        study.fit_forecasts(financial['training_labels'], financial['query'], SYMBOLS)


def test_refit_is_reproducible_and_moves_the_forecasts(frozen):
    financial = frozen['macro'][DAYS[1]]['financial']
    rows = study.refit_rows(financial)
    first = study.fit_forecasts(rows, financial['query'], SYMBOLS)
    second = study.fit_forecasts(rows, financial['query'], SYMBOLS)
    assert first == second
    full = study.fit_forecasts(financial['training_labels'], financial['query'], SYMBOLS)
    assert any(abs(first[s] - full[s]) > 1e-15 for s in SYMBOLS)


def test_refit_ridge_carries_its_sample_provenance(frozen):
    ridge = study.refit_ridge(DAYS[1])
    assert ridge['ready'] is True
    assert ridge['refit']['cutoff'] == study.REFIT_LABEL_CUTOFF
    assert ridge['refit']['rows'] >= study.REFIT_MIN_ROWS
    assert set(ridge['models']) == set(SYMBOLS)


# --- evidence verification ----------------------------------------------------

def test_verify_placebo_accepts_the_declared_draws(monkeypatch, tmp_path, frozen):
    _write_json(tmp_path / 'placebo.json', _evidence(DAYS[1], draws=(1, 2, 3)))
    report = study.verify_placebo(tmp_path)
    assert report['draws_checked'] == 3 and report['abstained_days'] == 0


def _tampered(day, draw):
    declared = [int(p) for p in study.draw_permutation(draw, study.decision_ordinal(day), len(SYMBOLS))]
    return declared[1:] + declared[:1] if len(declared) > 1 else declared


def test_verify_placebo_rejects_a_tampered_permutation(tmp_path, frozen):
    evidence = _evidence(DAYS[1], draws=(1, 2))
    evidence['days'][DAYS[1]]['draws']['2']['permutation'] = _tampered(DAYS[1], 2)
    _write_json(tmp_path / 'placebo.json', evidence)
    with pytest.raises(ValueError, match='not the declared draw'):
        study.verify_placebo(tmp_path)


def test_verify_placebo_rejects_a_tampered_injection(tmp_path, frozen):
    evidence = _evidence(DAYS[1], draws=(1,))
    row = evidence['days'][DAYS[1]]['draws']['1']
    row['injected']['AAA'] = '999'
    _write_json(tmp_path / 'placebo.json', evidence)
    with pytest.raises(ValueError, match='injection'):
        study.verify_placebo(tmp_path)


def test_verify_placebo_rejects_injection_on_an_abstained_day(tmp_path, frozen):
    evidence = _evidence(DAYS[1], draws=(1,), abstain=True)
    evidence['days'][DAYS[1]]['draws']['1']['permutation'] = _tampered(DAYS[1], 1)
    _write_json(tmp_path / 'placebo.json', evidence)
    with pytest.raises(ValueError, match='abstained day'):
        study.verify_placebo(tmp_path)


def test_verify_placebo_rejects_a_changed_seed(tmp_path, frozen):
    evidence = _evidence(DAYS[1], draws=(1,))
    evidence['seed'] = study.SEED + 1
    _write_json(tmp_path / 'placebo.json', evidence)
    with pytest.raises(ValueError, match='randomisation'):
        study.verify_placebo(tmp_path)


def test_verify_decisions_flags_a_changed_parent_decision(tmp_path, monkeypatch):
    parent = tmp_path / 'parent'
    root = tmp_path / 'study'
    row = dict(signal_session='2021-01-04', targets=[dict(symbol='AAA', target_weight='1')])
    _write_json(parent / 'decisions/FR25.json', {'2021-01-04': row})
    for arm in (study.CANDIDATE, study.SENTINEL, study.BASELINE_ARM):
        _write_json(root / 'decisions' / (arm + '.json'), {'2021-01-04': row})
    assert study.verify_decisions(root, parent)[study.CANDIDATE]['matches_frozen_parent'] is True
    _write_json(root / 'decisions' / (study.SENTINEL + '.json'),
                {'2021-01-04': dict(row, targets=[dict(symbol='BBB', target_weight='1')])})
    with pytest.raises(ValueError, match='does not reproduce'):
        study.verify_decisions(root, parent)


# --- resumable economics ------------------------------------------------------

def test_economics_resumable_refuses_a_changed_completed_replay(tmp_path):
    from systematic_trading.lean.contracts import sha256
    job = (study.CONTROL, study.COST_BPS, study.DELAY, 'evaluation')
    name = study.job_name(job)
    bundle = tmp_path / 'bundles' / name
    bundle.mkdir(parents=True)
    _write_json(bundle / 'manifest.json', {'a': 'b'})
    output = tmp_path / 'python' / (name + '.json')
    _write_json(output, {'complete': True})
    _write_json(output.with_suffix('.receipt.json'), dict(sha256='0' * 64, manifest_sha256='0' * 64))
    with pytest.raises(ValueError, match='Completed economics changed'):
        study.economics_resumable(tmp_path, job)
    _write_json(output.with_suffix('.receipt.json'),
                dict(sha256=sha256(output), manifest_sha256=sha256(bundle / 'manifest.json')))
    assert study.economics_resumable(tmp_path, job) == name


def test_economics_resumable_requires_a_receipt(tmp_path):
    job = (study.CONTROL, study.COST_BPS, study.DELAY, 'evaluation')
    name = study.job_name(job)
    _write_json(tmp_path / 'python' / (name + '.json'), {'complete': True})
    with pytest.raises(FileNotFoundError):
        study.economics_resumable(tmp_path, job)


# --- analysis -----------------------------------------------------------------

def _statistics(nav, first=100):
    return dict(cagr=0.1, sharpe_zero_cash=1.0, calmar=1.0, max_drawdown=-0.1, annual_turnover=8.0,
                mean_gross=0.95, terminal_nav=str(nav), total_return=nav / first - 1,
                mean_equity_weight=0.1, mean_asset_weights={}, dates=[], daily_returns=[], monthly={},
                calendar_returns={})


def _placebo_fixture(tmp_path, monkeypatch, navs, candidate_nav, draws=None):
    """Four declared draws over a shared control, and the decisions behind the changed counts."""
    monkeypatch.setattr(analysis, 'DRAWS', len(navs))
    results = {analysis.job_name((study.CONTROL, study.COST_BPS, study.DELAY, 'evaluation')):
               _statistics(100, first=100)}
    for draw, nav in enumerate(navs, start=1):
        results[analysis.job_name((study.placebo_arm(draw), study.COST_BPS, study.DELAY, 'evaluation'))] = \
            _statistics(nav, first=100)
    results[analysis.job_name((study.CANDIDATE, study.COST_BPS, study.DELAY, 'evaluation'))] = \
        _statistics(candidate_nav, first=100)
    control_decisions = {'2021-01-04': {'targets': [dict(symbol='AAA', target_weight='1')]}}
    _write_json(tmp_path / 'decisions/CP.json', control_decisions)
    _write_json(tmp_path / 'decisions/FR25.json',
                {'2021-01-04': {'targets': [dict(symbol='BBB', target_weight='1')]}})
    for draw in range(1, len(navs) + 1):
        _write_json(tmp_path / 'decisions' / (study.placebo_arm(draw) + '.json'),
                    draws.get(draw, control_decisions) if draws else control_decisions)
    _write_json(tmp_path / 'protocol.json', dict(initial_cash_usd='1000000'))
    _write_json(tmp_path / 'placebo.json', {'days': {'2021-01-04': {'draws': {
        str(k): {'changes': 0} for k in range(1, len(navs) + 1)}}}})
    return results


def test_placebo_percentile_uses_below_and_half_of_ties(monkeypatch, tmp_path):
    results = _placebo_fixture(tmp_path, monkeypatch, [90, 100, 110, 120], candidate_nav=120)
    payload = analysis.placebo_rank(tmp_path, results)
    assert payload['draws'] == 4
    assert payload['observed_log_excess'] == pytest.approx(np.log(1.2))
    # three draws below the observed value and one exactly equal: (3 + 0.5) / 4
    assert payload['percentile'] == pytest.approx(0.875)
    assert payload['draws_below'] == 3 and payload['draws_equal'] == 1
    assert payload['observed_rank'] == 5
    assert payload['draws_sorted'][0]['draw'] == 4


def test_excess_uses_the_part_a_total_return_convention(monkeypatch, tmp_path):
    results = _placebo_fixture(tmp_path, monkeypatch, [90, 100, 110, 120], candidate_nav=120)
    payload = analysis.placebo_rank(tmp_path, results)
    # every arm is valued from the same first session, so the excess is the difference
    # of total returns rather than the ratio of terminal values
    assert payload['observed_excess_pp'] == pytest.approx(0.20)
    draws = {row['draw']: row for row in payload['draws_sorted']}
    assert draws[1]['excess_pp'] == pytest.approx(-0.10)
    assert draws[4]['excess_pp'] == pytest.approx(0.20)


def test_changed_decisions_are_measured_against_the_control(monkeypatch, tmp_path):
    draws = {2: {'2021-01-04': {'targets': [dict(symbol='AAA', target_weight='0.5'),
                                             dict(symbol='CCC', target_weight='0.5')]}}}
    results = _placebo_fixture(tmp_path, monkeypatch, [90, 100, 110, 120], candidate_nav=120, draws=draws)
    payload = analysis.placebo_rank(tmp_path, results)
    by_draw = {row['draw']: row for row in payload['draws_sorted']}
    assert by_draw[1]['changed_selections'] == 0
    assert by_draw[2]['changed_selections'] == 1
    assert payload['observed_changed_selections'] == 1


def test_placebo_check_requires_strictly_exceeding_the_ninetieth_percentile(monkeypatch, tmp_path):
    results = _placebo_fixture(tmp_path, monkeypatch, [90, 100, 110, 120], candidate_nav=115)
    payload = analysis.placebo_rank(tmp_path, results)
    assert payload['q90'] == pytest.approx(np.percentile([np.log(0.9), 0, np.log(1.1), np.log(1.2)], 90))
    assert payload['placebo_check_passes'] is (payload['observed_log_excess'] > payload['q90'])
    assert payload['placebo_check_passes'] is False


def _checks(excess=0.12, ci95=(0.001, 0.02)):
    return dict(
        attribution=dict(total_return_difference=excess, total_log_difference=np.log(1 + excess),
                         contributions=[dict(log_difference=0.01)]),
        years=[dict(complete=True, excess=1.0)],
        bootstrap={6: dict(ci95=list(ci95))})


def test_assess_rejects_when_the_placebo_check_fails():
    verdict = analysis.assess(dict(q90=0.5, placebo_check_passes=False), _checks(ci95=(-0.001, 0.02)))
    assert verdict['placebo_test'] is False
    assert verdict['declared_mapping'] == 'reject'
    assert verdict['literal_mapping'] == 'inconclusive'
    assert verdict['retention_verdict'] == 'not preserved'


def test_assess_is_inconclusive_when_only_the_interval_fails():
    verdict = analysis.assess(dict(q90=0.01, placebo_check_passes=True), _checks(ci95=(-0.001, 0.02)))
    assert verdict['placebo_test'] is True
    assert verdict['declared_mapping'] == 'inconclusive'
    assert verdict['literal_mapping'] == 'inconclusive'
    assert verdict['retention_verdict'] == 'not preserved'


def test_assess_rejects_a_negative_point_estimate_even_with_a_passing_placebo():
    verdict = analysis.assess(dict(q90=-0.5, placebo_check_passes=True), _checks(excess=-0.05))
    assert verdict['declared_mapping'] == 'reject'


def test_preserve_needs_every_check_and_is_documented_as_unreachable():
    verdict = analysis.assess(dict(q90=0.01, placebo_check_passes=True), _checks(ci95=(0.001, 0.02)))
    assert verdict['declared_mapping'] == 'preserve' and verdict['retention_verdict'] == 'preserved'
    assert 'Unreachable' in study.VERDICT_MAPPING['preserve']


def test_log_pp_converts_a_log_excess():
    assert analysis.log_pp(np.log(1.12)) == pytest.approx(0.12)


# --- frozen study, when the evidence exists -----------------------------------

@BUILT
def test_frozen_placebo_evidence_reverifies():
    study.initialize(ROOT)
    report = study.verify_placebo(ROOT)
    assert report['days'] == 70 and report['abstained_days'] == 0
    assert report['symbol_counts'] == [14]
    assert report['draws_checked'] == report['days'] * study.DRAWS
    assert report['draws'] == study.DRAWS and report['seed'] == study.SEED


@BUILT
@pytest.mark.skipif(not PARENT.exists(), reason='parent study not built in this workspace')
def test_frozen_decisions_reproduce_the_parent_candidate():
    study.initialize(ROOT)
    bridges = study.verify_decisions(ROOT)
    for arm in (study.CANDIDATE, study.SENTINEL, study.BASELINE_ARM):
        assert bridges[arm]['matches_frozen_parent'] is True
        assert bridges[arm]['shared_decisions'] == 70
