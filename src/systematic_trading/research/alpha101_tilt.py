"""P4.17b — Alpha101 as a tactical tilt on the existing book.

Operator proposal, 2026-10-11: if the Alpha101 family died on turnover, do not use it to choose
the book — use it to overweight and underweight the holdings that are already there, set aside
some X% for that, and find the balance between cost and alpha.

**Frozen design, declared before any outcome.**

* **Base book.** The pinned capped pooled control's own decisions from the frozen P4.16 evidence
  root. Real membership, real weights, unchanged: the tilt never adds or removes an instrument.
* **Tilt shape.** The held names carrying an alpha value are ranked; each gets a linear rank score
  in ``[-1, +1]`` with zero mean; total overweight equals total underweight equals ``X / 2`` of NAV,
  so the tilt is NAV-neutral and gross exposure and cash are unchanged.
* **Bounds.** One per-decision shrink factor scales the whole tilt so no name breaches the 45% cap
  or goes negative. The shrink factor is reported: a book sitting at the cap cannot be overweighted
  into, and that interaction is a measured result rather than an assumption.
* **Budget family.** ``X in {5%, 10%, 20%}``, reported as a surface and never chosen from the
  outcome.
* **Cost test.** Incremental traded notional and cost against the untilted book, judged against the
  published headroom between the monitored book's measured drag and the P4.15 ceiling; the breakeven
  IC is taken at the incremental turnover, and the observed IC comes from the frozen P4.17 screen.
  Nothing is replayed until a candidate clears.

No economics, no replay, no promotion, and no change to membership, the 45% cap or the cash reserve.
"""
from decimal import Decimal as D
from pathlib import Path

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json
from systematic_trading.research import alpha101_screen as screening
from systematic_trading.research import turnover_gate as gate
from systematic_trading.research.turnover_gate import implied_turnover, screen

STUDY = 'alpha101-tilt-v1'
PARENT = Path('var/research/sleeve-construction-20261010-v1')
SCREEN_ROOT = Path('var/research/alpha101-screen-20261011-v1')
CALIBRATION = Path('var/research/turnover-gate-20261010-v1/calibration.json')
DEFAULT_ROOT = Path('var/research/alpha101-tilt-20261011-v1')

BUDGETS = (0.05, 0.10, 0.20)
MAX_WEIGHT = 0.45
MIN_NAMES = 2
PRIMARY_HORIZON = 21

_DATA = None


def calibration():
    """The published dispersion, the ceiling, and the headroom a new overlay may use."""
    payload = read_json(CALIBRATION)
    sigma = float(payload['sigma'])
    thresholds = payload['thresholds']
    ceiling = float(thresholds['max_annual_cost_bps']) * (1.0 + float(thresholds['cost_tolerance']))
    measured = payload['verdicts']['measured']['FR25']
    drag = float(measured['annual_cost_bps'])
    if abs(drag - 40.4) > 0.1:
        raise ValueError(f'The monitored drag is not the published 40.4bp: {drag}. Wrong arm or artifact.')
    return dict(sigma=sigma, ceiling_bps=ceiling, monitored_drag_bps=drag,
                headroom_bps=ceiling - drag, cost_bps=gate.FROZEN_COST_BPS,
                implied_turnover=float(payload['verdicts']['implied']['FR25']['annual_turnover']),
                measured_turnover=float(measured['annual_turnover']))


def headroom_thresholds(headroom_bps):
    """The gate's own thresholds with the ceiling replaced by the remaining headroom."""
    return dict(gate.THRESHOLDS, max_annual_cost_bps=float(headroom_bps), cost_tolerance=0.0)


def initialize():
    global _DATA
    screening.initialize()
    controls = read_json(PARENT / 'controls' / 'CP.json')
    observed = {row['alpha']: row['information'][str(PRIMARY_HORIZON)]['mean']
                for row in read_json(SCREEN_ROOT / 'screen.json')['rows']}
    _DATA = dict(days=sorted(controls), controls=controls, observed_ic=observed,
                 book_cache={})
    return _DATA


def decision_days():
    return _DATA['days']


def base_weights(day):
    """The pinned control's own target weights, unchanged, cash reserve included as weights sum."""
    cache = _DATA['book_cache']
    if day not in cache:
        rows = _DATA['controls'][day]['targets']
        cache[day] = {t['symbol']: float(t['target_weight']) for t in rows if float(t['target_weight']) > 0}
    return dict(cache[day])


def rank_scores(order):
    """Linear rank scores in [-1, +1] with zero mean."""
    size = len(order)
    if size < 2:
        return {}
    if size == 2:
        return {order[0]: 1.0, order[1]: -1.0}
    return {symbol: (size - 1 - 2 * index) / (size - 1) for index, symbol in enumerate(order)}


def tilt_weights(base, values, budget):
    """One decision's tilted book, NAV-neutral and bounded by the cap and by zero.

    A held cross-section with no spread cannot rank anything, so it is left untilted rather
    than tilted on the symbol tie-break: that is the same rule the P4.17 screen applies to a
    constant cross-section across the universe.
    """
    held = sorted(symbol for symbol, weight in base.items() if weight > 0 and symbol in values)
    if len(held) < MIN_NAMES:
        return dict(base), dict(applied=False, scale=1.0, names=len(held),
                                reason='fewer than two held names carry an alpha value')
    if len({round(values[symbol], 12) for symbol in held}) < 2:
        return dict(base), dict(applied=False, scale=1.0, names=len(held),
                                reason='the held cross-section is constant, so the alpha cannot rank inside '
                                       'the book')
    scores = rank_scores(sorted(held, key=lambda symbol: (-values[symbol], symbol)))
    positive = sum(value for value in scores.values() if value > 0)
    negative = -sum(value for value in scores.values() if value < 0)
    if positive <= 0 or negative <= 0:
        return dict(base), dict(applied=False, scale=1.0, names=len(held), reason='ranks carry no spread')
    raw = {symbol: (budget / 2) * (value / positive if value > 0 else value / negative)
           for symbol, value in scores.items()}
    scale = 1.0
    for symbol, tilt in raw.items():
        weight = base[symbol]
        if tilt > 0 and weight + tilt > MAX_WEIGHT:
            scale = min(scale, (MAX_WEIGHT - weight) / tilt)
        elif tilt < 0:
            scale = min(scale, weight / -tilt)
    scale = max(0.0, scale)
    tilted = dict(base)
    for symbol, tilt in raw.items():
        tilted[symbol] = base[symbol] + scale * tilt
    gross = sum(abs(scale * tilt) for tilt in raw.values())
    return tilted, dict(applied=True, scale=scale, names=len(held), gross_tilt=gross,
                        cap_binding=scale < 1.0 - 1e-12)


def tilted_map(alpha, budget, values_by_day=None):
    """The tilted book across every decision, with per-decision diagnostics."""
    books, diagnostics = {}, []
    for day in decision_days():
        values = values_by_day[day] if values_by_day is not None else screening.alpha_values(alpha, day)
        tilted, diagnostic = tilt_weights(base_weights(day), values, budget)
        books[day] = tilted
        diagnostics.append(dict(day=day, **diagnostic))
    return books, diagnostics


def values_across_days(alpha):
    """The alpha's cross-section on every decision, computed once per alpha."""
    return {day: screening.alpha_values(alpha, day) for day in decision_days()}


def observed_ic(alpha):
    value = _DATA['observed_ic'].get(alpha)
    return None if value is None else float(value)


def measure(alpha, budget, *, sigma, thresholds, values_by_day=None):
    """The declared cost and information measurement for one (alpha, budget) candidate."""
    configured = calibration()
    books, diagnostics = tilted_map(alpha, budget, values_by_day)
    base_map = {day: base_weights(day) for day in decision_days()}
    implied_base = implied_turnover(base_map)
    implied_tilted = implied_turnover(books)
    incremental = implied_tilted['annual_turnover'] - implied_base['annual_turnover']
    cost = incremental * configured['cost_bps']
    ic = observed_ic(alpha)
    applied = [row for row in diagnostics if row['applied']]
    if incremental <= 0.0:
        verdict = dict(version=gate.VERSION, status='pass', cost_test=True, margin_test=None,
                       annual_turnover=incremental, annual_cost_bps=cost,
                       cost_ceiling_bps=float(thresholds['max_annual_cost_bps']), reasons=[
                           f'the tilt costs nothing at this budget: it offsets {abs(cost):.1f}bp of the '
                           'book\'s own turnover rather than adding to it'])
    elif ic is None:
        verdict = dict(version=gate.VERSION, status='insufficient', cost_test=cost <= float(
            thresholds['max_annual_cost_bps']), margin_test=None, annual_turnover=incremental,
            annual_cost_bps=cost, cost_ceiling_bps=float(thresholds['max_annual_cost_bps']),
            reasons=['the alpha has no measurable rank IC, so the requirement cannot be judged'])
    else:
        verdict = screen(incremental, sigma=sigma, candidate_ic=ic, thresholds=thresholds)
    if not applied and verdict['status'] == 'pass':
        # A zero-incremental-cost pass would be a false pass: the alpha never ranked anything, so
        # there is nothing to be cheap about. Same rule as the P4.17 screen's no-measurable-IC case.
        verdict = dict(verdict, status='insufficient', margin_test=None, reasons=[
            diagnostics[0]['reason'] if diagnostics else 'the alpha never ranked the book, so nothing was tilted'])
    binding = sum(1 for row in applied if row['cap_binding'])
    return dict(
        alpha=alpha, budget=budget, formula=None,
        books=dict(decisions=len(books), names_mean=(sum(row['names'] for row in applied) / len(applied)
                                                     if applied else None),
                   applied_decisions=len(applied),
                   cap_binding_decisions=binding,
                   cap_binding_share=(binding / len(applied) if applied else None),
                   scale_mean=(sum(row['scale'] for row in applied) / len(applied) if applied else None),
                   scale_min=min((row['scale'] for row in applied), default=None),
                   gross_tilt_mean=(sum(row['gross_tilt'] for row in applied) / len(applied) if applied else None)),
        turnover=dict(base_annual=implied_base['annual_turnover'],
                      tilted_annual=implied_tilted['annual_turnover'], incremental_annual=incremental),
        gate=verdict, observed_ic=ic)


def protocol():
    configured = calibration()
    return dict(
        study=STUDY, version=STUDY + '-v1', parent=str(PARENT), screen_root=str(SCREEN_ROOT),
        registration='P4.17b in docs/signal-decay-and-alpha-plan.md, operator-proposed 2026-10-11',
        family=dict(alphas=list(screening.lib.REGISTERED), budgets=list(BUDGETS),
                    grid_size=len(screening.lib.REGISTERED) * len(BUDGETS),
                    declared='the whole alphas-by-budget grid is reported; X is never chosen from the outcome'),
        tilt=dict(max_weight=str(D('0.45')), min_names=MIN_NAMES,
                  shape='linear rank scores in [-1, +1] with zero mean over the held names that carry a value; '
                        'total overweight = total underweight = X/2 of NAV; one per-decision shrink factor so no '
                        'name breaches the cap or goes negative',
                  membership='unchanged: the tilt never adds or removes an instrument',
                  no_spread_rule='a held cross-section with fewer than two distinct values cannot rank, so it is '
                                 'left untilted instead of being tilted on the symbol tie-break',
                  no_tilt_rule='a candidate that never ranked the book, or whose IC cannot be measured, is '
                               'reported insufficient and is never passed on a zero incremental cost'),
        cost_test=dict(headroom_bps=configured['headroom_bps'], ceiling_bps=configured['ceiling_bps'],
                       monitored_drag_bps=configured['monitored_drag_bps'], cost_bps=configured['cost_bps'],
                       rule='the incremental traded notional is judged against the headroom between the '
                            'monitored book\'s measured drag and the P4.15 ceiling; the breakeven IC is taken '
                            'at the incremental turnover and the observed IC from the frozen P4.17 screen',
                       margin='the frozen 3x IC margin is unchanged'),
        calibration=configured,
        declares=['no economics and no replay: nothing is replayed until a candidate clears the gate',
                  'a passing tilt would still need a replay, family adjustment across the grid, and decay '
                  'monitoring before any promotion',
                  'the monitored book, its membership, the 45% cap and the cash reserve are unchanged'])


def prepare(root=DEFAULT_ROOT):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / 'protocol.json', protocol())
    write_json(root / 'input_manifest.json', dict(
        parent=str(PARENT),
        files={str(path): sha256(path) for path in (
            PARENT / 'controls' / 'CP.json', SCREEN_ROOT / 'screen.json', SCREEN_ROOT / 'formulas.json',
            CALIBRATION)},
        note='P4.17b adds no new data source: the pinned control decisions, the frozen P4.17 screen and the '
             'published P4.15 calibration'))
    write_json(root / 'data_receipt.json', dict(
        screen_sha256=sha256(SCREEN_ROOT / 'screen.json'),
        calibration_sha256=sha256(CALIBRATION),
        controls_sha256=sha256(PARENT / 'controls' / 'CP.json')))
    return dict(root=str(root), protocol_sha256=sha256(root / 'protocol.json'),
                calibration=calibration())


def run(root=DEFAULT_ROOT):
    root = Path(root)
    configured = calibration()
    thresholds = headroom_thresholds(configured['headroom_bps'])
    rows = []
    for alpha in screening.lib.REGISTERED:
        values_by_day = values_across_days(alpha)
        for budget in BUDGETS:
            rows.append(measure(alpha, budget, sigma=configured['sigma'], thresholds=thresholds,
                                values_by_day=values_by_day))
    for row in rows:
        row['formula'] = screening.lib.FORMULAS[row['alpha']]
    payload = dict(study=STUDY, calibration=configured, thresholds=thresholds,
                   decisions=len(decision_days()), rows=rows)
    write_json(root / 'tilt.json', payload)
    passing = [row for row in rows if row['gate']['status'] == 'pass']
    return dict(tilt_sha256=sha256(root / 'tilt.json'), candidates=len(rows),
                passed=len(passing), rejected=sum(1 for row in rows if row['gate']['status'] == 'reject'),
                insufficient=sum(1 for row in rows if row['gate']['status'] == 'insufficient'),
                best=[(row['alpha'], row['budget']) for row in sorted(
                    passing, key=lambda row: -(row['gate'].get('ic_margin') or 0))[:5]])


def verify(root=DEFAULT_ROOT):
    root = Path(root)
    if _DATA is None:
        initialize()
    manifest = read_json(root / 'input_manifest.json')
    checks = {str(path): sha256(Path(path)) == digest for path, digest in manifest['files'].items()}
    before = read_json(root / 'tilt.json')
    run(root)
    checks['reproduced'] = before == read_json(root / 'tilt.json')
    return checks
