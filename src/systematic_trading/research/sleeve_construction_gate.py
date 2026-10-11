"""P4.16 gate stage: screen every construction arm with the P4.15 turnover gate first.

Runs before any replay exists. Candidate arms that fail the gate are recorded as
gate-rejected and are not replayed; controls are always replayed, because without the
pooled control there is no comparison to make.

The dispersion is recomputed here with the app's own measurement code on this study's
frozen histories, and cross-checked against the published P4.15 calibration so the two
items provably share one input definition.
"""
from pathlib import Path

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json
from systematic_trading.research.turnover_gate import (FROZEN_COST_BPS, PROGRAMME_REFERENCE_IC, THRESHOLDS,
    VERSION, implied_turnover, screen, weights_from_targets)

GATE_ROOT = Path('var/research/turnover-gate-20261010-v1')


def _decisions(root, arm, start):
    path = Path(root) / 'decisions' / (arm + '.json')
    return {day: weights_from_targets(row['targets']) for day, row in sorted(read_json(path).items())
            if day >= start}


def _dispersion(root, days):
    from systematic_trading.research.signal_decay_job import turnover_and_sigma
    bars = read_json(Path(root) / 'bars.json')
    selection_turnover, sigma = turnover_and_sigma(bars, list(days), signal_name='m1_total', slots=6, horizon=21)
    return dict(selection_change_turnover=selection_turnover, sigma=sigma, decisions=len(days))


def _published_check(sigma):
    if not (GATE_ROOT / 'calibration.json').exists():
        return dict(available=False)
    published = read_json(GATE_ROOT / 'calibration.json')
    return dict(available=True, published_sigma=published['sigma'],
                matches_published=bool(abs(published['sigma'] - sigma) < 1e-9),
                calibration_sha256=sha256(GATE_ROOT / 'calibration.json'))


def screen_arms(root, arms=None, controls=None, always=None, version_label='p4.16'):
    """Screen every arm on its evaluation-window mapping and write the frozen gate record.

    Reads only the frozen decisions and histories: the gate is a pre-replay screen, so
    it must not need the models or the replays to exist. ``arms`` and ``always`` let a
    follow-up study reuse this stage for its own candidate and control arms.
    """
    from systematic_trading.research.sleeve_construction_study import ARMS as DEFAULT_ARMS
    from systematic_trading.research.sleeve_construction_study import CONTROLS as DEFAULT_CONTROLS
    arms = tuple(DEFAULT_ARMS if arms is None else arms)
    controls = tuple(DEFAULT_CONTROLS if controls is None else controls)
    always = tuple(DEFAULT_ARMS[:1] if always is None else always)
    root = Path(root)
    protocol = read_json(root / 'protocol.json')
    start = protocol['evaluation_start']
    calendar = sorted(read_json(root / 'decisions' / (controls[0] + '.json')))
    days = [d for d in calendar if d >= start]
    dispersion = _dispersion(root, calendar)
    published = _published_check(dispersion['sigma'])
    sigma = dispersion['sigma']
    rows, rejected, boundary = {}, [], []
    for arm in (*arms, *controls):
        evaluation = _decisions(root, arm, start)
        if sorted(evaluation) != sorted(days):
            raise ValueError('Decision calendar differs from the study calendar for ' + arm)
        implied = implied_turnover(evaluation)
        verdict = screen(implied['annual_turnover'], sigma=sigma, candidate_ic=PROGRAMME_REFERENCE_IC)
        control = arm in controls or arm in always
        # P4.15's published boundary rule: a candidate within the disclosed cost tolerance
        # of the ceiling must be replayed before a decision is taken, because the gate
        # cannot discriminate there. That rule was written before this study ran.
        ceiling = verdict['cost_ceiling_bps']
        within_boundary = bool(verdict['annual_cost_bps'] <= ceiling * (1.0 + float(THRESHOLDS['cost_tolerance'])))
        may_replay = bool(control or verdict['status'] == 'pass' or within_boundary)
        rows[arm] = dict(arm=arm, control=control, decisions=implied['decisions'],
                         first=implied['first'], last=implied['last'],
                         annual_turnover=implied['annual_turnover'],
                         annual_cost_bps=verdict['annual_cost_bps'], cost_ceiling_bps=ceiling,
                         breakeven_ic=verdict['breakeven_ic'], ic_margin=verdict['ic_margin'],
                         status=verdict['status'], cost_test=verdict['cost_test'],
                         margin_test=verdict['margin_test'], boundary_case=bool(within_boundary
                             and verdict['status'] != 'pass' and not control),
                         may_replay=may_replay, reasons=verdict['reasons'],
                         replay_reason=('control: the comparison itself' if control else
                                        'gate passed' if verdict['status'] == 'pass' else
                                        'P4.15 boundary rule: this candidate sits within the disclosed cost tolerance '
                                        'of the ceiling, where the gate cannot discriminate and its published '
                                        'contract requires a replay' if within_boundary else
                                        'gate rejected beyond the boundary band: not replayed'))
        if not may_replay:
            rejected.append(arm)
        if rows[arm]['boundary_case']:
            boundary.append(arm)
    payload = dict(version=VERSION + '-' + version_label + '-gate', cost_bps=FROZEN_COST_BPS, sigma=sigma,
                   dispersion=dispersion, published=published, thresholds=dict(THRESHOLDS),
                   window=start, decision_days=len(days), arms=rows, gate_rejected=rejected,
                   boundary_cases=boundary, candidate_ic=PROGRAMME_REFERENCE_IC,
                   boundary_rule='Cost at or below ceiling x (1 + cost_tolerance) = '
                                 f"{rows[arms[0]]['cost_ceiling_bps'] * (1.0 + float(THRESHOLDS['cost_tolerance'])):.1f}bp "
                                 'is a boundary case: the frozen gate verdict still stands and is reported, but '
                                 'P4.15\'s published contract requires a replay before a decision is taken there.',
                   note='Controls are replayed regardless, because the pooled control is the comparison itself. A '
                        'candidate rejected beyond the boundary band is not replayed.')
    write_json(root / 'gate.json', payload)
    write_json(root / 'gate_receipt.json', dict(sha256=sha256(root / 'gate.json'),
        inputs={str(path): sha256(path) for path in (root / 'protocol.json', root / 'bars.json')}))
    return dict(arms={arm: row['status'] for arm, row in rows.items()}, rejected=rejected,
                boundary=boundary, sigma=round(sigma, 6), matches_published=published.get('matches_published'),
                may_replay={arm: row['may_replay'] for arm, row in rows.items()},
                costs={arm: round(row['annual_cost_bps'], 2) for arm, row in rows.items()},
                margins={arm: None if row['ic_margin'] is None else round(row['ic_margin'], 2)
                         for arm, row in rows.items()})
