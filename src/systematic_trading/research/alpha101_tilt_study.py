"""P4.17c — the Alpha101 tilt replayed on the current SOTA.

Operator request, 2026-10-11: *bake the tested alpha into the current SOTA with a 10% tilt and see
the final return, Sharpe, Calmar and max drawdown.*

**Frozen design, declared before any outcome.**

* **Base strategy.** ``research_fallback_f3_v1`` — the strategy the platform currently selects as
  SOTA, built from its own registered definition and its own overlay stack (asset pool filter,
  rolling model, relative momentum, adaptive trend, audited activity, USD ridge). Nothing in that
  chain is modified.
* **Tilt.** The P4.17b rule, unchanged: the names the SOTA actually holds are ranked by the alpha,
  each gets a linear rank score in ``[-1, +1]`` with zero mean, total overweight equals total
  underweight equals X/2 of NAV, and one per-decision shrink factor keeps every name inside the 45%
  cap and above zero. The tilt is appended **last** in the chain, so it acts on the finished book
  and still respects the defensive fallback's protected cash budget: the symbol set is unchanged,
  no name is added or removed, and the gross is untouched.
* **Arms.** ``SOTA`` (the strategy untouched, the only valid control), ``SOTA-TILT-53`` (the single
  alpha with the strongest measured information, **declared as selected on the inspected screen**,
  so its replay number is not an unbiased estimate), and ``SOTA-TILT-FAMILY`` (the equal-weight mean
  of all sixteen registered alphas' rank tilts — no selection at all, and therefore the honest
  companion to the single-alpha arm).
* **Budget.** ``X = 10%``, the operator's declared choice. It is not re-tuned here.
* **Measurement order.** Every arm is gated on its own implied turnover by the P4.15 gate before any
  replay, and the incremental cost against the untouched SOTA is reported beside it.
* **Replay.** The parent study's conventions, unchanged: 5/10/20bp costs, zero and one-session
  delay, full and evaluation windows, fresh cash, the same quotes and sessions.

No promotion, no monitoring change, no allocation change. A passing arm is a candidate.
"""
from decimal import Decimal as D
from pathlib import Path

import numpy as np

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research import alpha101 as lib
from systematic_trading.research import sleeve_construction_study as base
from systematic_trading.research.expanded_economics import job_name
from systematic_trading.research.momentum_replay import freeze_usd_bundle, read_json, run_usd_reference
from systematic_trading.research.turnover_gate import implied_turnover, screen

STUDY = 'alpha101-tilt-replay-v1'
PARENT = base.DEFAULT_ROOT
DEFAULT_ROOT = Path('var/research/alpha101-tilt-replay-20261011-v2')
SOTA_KEY = 'research_fallback_f3_v1'
BUDGET = D('0.10')
MAX_WEIGHT = D('0.45')
MIN_NAMES = 2
ARMS = ('SOTA', 'SOTA-TILT-53', 'SOTA-TILT-FAMILY')
LABELS = {'SOTA': 'Current SOTA · qualifying defensive ETFs + cash, untouched',
          'SOTA-TILT-53': 'SOTA + 10% tilt of alpha 53 (selected on the inspected screen)',
          'SOTA-TILT-FAMILY': 'SOTA + 10% tilt of the equal-weight mean of all sixteen alphas'}
ARM_ALPHAS = {'SOTA': (), 'SOTA-TILT-53': ('53',), 'SOTA-TILT-FAMILY': lib.REGISTERED}
COSTS = base.COSTS
DELAYS = base.DELAYS
WINDOWS = base.WINDOWS
BOOTSTRAP_BLOCKS = (3, 6, 12)
BOOTSTRAP_REPLICATIONS = 10000
SEED = 2026101106
COST_BPS = 5
DELAY = 0

_VALUES = {}


def plan(arm):
    if arm not in ARMS:
        raise ValueError('Unregistered tilt arm: ' + str(arm))
    return dict(arm=arm, label=LABELS[arm], base=SOTA_KEY, budget=str(BUDGET) if ARM_ALPHAS[arm] else None,
                alphas=list(ARM_ALPHAS[arm]))


def initialize(root=PARENT):
    base.initialize(Path(root))
    global _VALUES
    _VALUES = {}
    return base._DATA


def decision_days():
    return base.decision_days()


def evaluation_days():
    return base.evaluation_days()


def histories(day):
    """Typed audited bars up to the session before the decision, as the engine sees them."""
    return base._day(day)['histories']


def values_for_day(alpha, day):
    """One alpha's point-in-time cross-section on a decision day."""
    key = (alpha, day)
    if key in _VALUES:
        return _VALUES[key]
    out = {}
    for symbol, rows in histories(day).items():
        if len(rows) < 2:
            continue
        history = lib.History(symbol=symbol, date=day,
                              open=np.array([float(r.open) for r in rows]),
                              high=np.array([float(r.high) for r in rows]),
                              low=np.array([float(r.low) for r in rows]),
                              close=np.array([float(r.close) for r in rows]),
                              volume=np.array([float(r.volume) for r in rows]))
        value = lib.value(alpha, history)
        if value is not None:
            out[symbol] = value
    _VALUES[key] = out
    return out


def scores_by_alpha(day, alphas):
    return {alpha: values_for_day(alpha, day) for alpha in alphas}


def rank_scores(held, values):
    """Linear rank scores in [-1, +1] with zero mean, or None when nothing can be ranked."""
    ranked = [symbol for symbol in held if symbol in values]
    if len(ranked) < MIN_NAMES:
        return None
    if len({round(values[symbol], 12) for symbol in ranked}) < 2:
        return None
    order = sorted(ranked, key=lambda symbol: (-values[symbol], symbol))
    size = len(order)
    if size == 2:
        return {order[0]: 1.0, order[1]: -1.0}
    return {symbol: (size - 1 - 2 * index) / (size - 1) for index, symbol in enumerate(order)}


def composite_scores(held, per_alpha):
    """The equal-weight mean of each alpha's rank scores: scale-free, so averaging is meaningful."""
    contributions = [rank_scores(held, values) for values in per_alpha.values()]
    contributions = [item for item in contributions if item]
    if not contributions:
        return None, 0
    symbols = sorted(set().union(*contributions))
    averaged = {symbol: sum(item.get(symbol, 0.0) for item in contributions) / len(contributions)
                for symbol in symbols}
    if len({round(value, 12) for value in averaged.values()}) < 2:
        return None, len(contributions)
    return averaged, len(contributions)


def tilt_vector(weights, scores, budget):
    """The declared tilt as a per-symbol vector, with one shrink factor for the cap and the floor.

    ``weights`` and ``scores`` are keyed by symbol; the result is the *change* to apply, and the
    diagnostics describe the shrink. A cross-section with no spread returns an empty tilt (untiltable),
    and a book arriving already above the cap shrinks the tilt to a no-op rather than pushing an
    over-cap name further up -- the final clamp runs after this overlay.
    """
    budget = float(budget)
    # Callers hand in Decimal weights (the engine) or floats (the daily study); coerce once so every
    # cap and floor test below is exact rather than a floating-point approximation.
    weights = {symbol: D(str(value)) for symbol, value in weights.items()}
    held = [symbol for symbol, weight in weights.items() if weight > 0 and symbol in scores]
    if len(held) < MIN_NAMES:
        return {}, dict(applied=False, scale=1.0, names=len(held),
                        reason='fewer than two held names carry a value')
    positive = sum(scores[symbol] for symbol in held if scores[symbol] > 0)
    negative = -sum(scores[symbol] for symbol in held if scores[symbol] < 0)
    if positive <= 0 or negative <= 0:
        return {}, dict(applied=False, scale=1.0, names=len(held), reason='the ranks carry no spread')
    tilts = {symbol: D(str((budget / 2) * (scores[symbol] / positive if scores[symbol] > 0
                                           else scores[symbol] / negative))) for symbol in held}
    over_cap = [symbol for symbol in held if weights[symbol] > MAX_WEIGHT]
    scale = D('1')
    for symbol, tilt in tilts.items():
        if tilt == 0:
            continue                     # the median name of an odd-sized book is not moved at all
        weight = weights[symbol]
        if tilt > 0:
            headroom = MAX_WEIGHT - weight
            scale = D('0') if headroom <= 0 else min(scale, headroom / tilt)
        else:
            scale = min(scale, weight / -tilt)
    scale = max(D('0'), scale)
    applied = {symbol: scale * tilt for symbol, tilt in tilts.items()}
    return applied, dict(applied=scale > 0, scale=float(scale), names=len(held),
                         cap_binding=scale < D('1'), over_cap_names=len(over_cap))


def tilt_targets(targets, scores, budget):
    """Apply the declared NAV-neutral tilt to allocation targets, keeping every engine contract."""
    weights = {t.symbol: t.target_weight for t in targets}
    tilts, diagnostic = tilt_vector(weights, scores, budget)
    if not tilts:
        return list(targets), diagnostic
    adjusted = []
    for target in targets:
        tilt = tilts.get(target.symbol)
        if tilt is None or tilt == 0:
            adjusted.append(target)
            continue
        weight = target.target_weight
        moved = weight + tilt
        # The shrink factor is a rounded division, so a name tilted to exactly zero (or exactly to
        # the cap) can land a hair outside it. Clamp within a tolerance far below any real weight;
        # a genuine breach still raises.
        if moved < 0 <= moved + D('1e-24'):
            moved = D('0')
        ceiling = max(weight, MAX_WEIGHT)
        if moved > ceiling and moved < ceiling + D('1e-24'):
            moved = ceiling
        if moved < 0 or moved > ceiling:
            raise ValueError('Tilt breached the zero floor or increased an over-cap weight on ' + target.symbol)
        adjusted.append(target.model_copy(update={
            'target_weight': moved,
            'rationale': target.rationale + f' Alpha101 tilt {target.symbol}.'}))
    gross_before = sum((t.target_weight for t in targets), D(0))
    gross_after = sum((t.target_weight for t in adjusted), D(0))
    if abs(gross_after - gross_before) > D('1e-12'):
        raise ValueError('Tilt changed the gross book, which the fallback budget protects')
    return adjusted, diagnostic


class AlphaTiltOverlay:
    """The tilt as the engine's own overlay contract: same symbol set, same gross, no removals.

    The ranking happens inside ``apply``, on the targets actually received, so the tilt always ranks
    the book the strategy really holds and the shrink factor is computed against those same weights.
    """

    cash_budget_active = False

    def __init__(self, *, alphas, budget, values_by_alpha, name='alpha101-tilt'):
        self.alphas = tuple(alphas)
        self.budget = D(budget)
        self.values_by_alpha = values_by_alpha
        self.name = name
        self.diagnostics = {}

    def apply(self, targets, context):
        held = [t.symbol for t in targets if t.target_weight > 0]
        if len(self.alphas) == 1:
            scores = rank_scores(held, self.values_by_alpha[self.alphas[0]]) or {}
        else:
            composite, _ = composite_scores(held, {alpha: self.values_by_alpha[alpha]
                                                   for alpha in self.alphas})
            scores = composite or {}
        adjusted, diagnostic = tilt_targets(list(targets), scores, self.budget)
        self.diagnostics = dict(diagnostic, alphas=len(self.alphas), ranked=len(scores))
        return adjusted


def run_arm(day, arm):
    """One decision for one arm, through the SOTA's own chain and the study's validations."""
    from systematic_trading.backtest.stored import _target_schedule
    from systematic_trading.research.construction_controls import FinalWeightCapOverlay
    from systematic_trading.research.flow_concentration import ActivityConcentrationOverlay
    from systematic_trading.research.rolling_tracking import RollingModelOverlay
    from systematic_trading.research.strategy_catalog import (defensive_cash_definition,
                                                              instantiate_overlays)
    from systematic_trading.research.usd_tracking import UsdRidgeOverlay
    from systematic_trading.research.candidate_pool import AuditedActivity
    data, current = base._DATA, base._day(day)
    definition = defensive_cash_definition()
    if definition.key != SOTA_KEY:
        raise ValueError('The registered SOTA definition changed: ' + str(definition.key))
    overlays = instantiate_overlays(definition)
    bound = []
    for item in overlays:
        if isinstance(item, RollingModelOverlay):
            item.model = current['model']
        elif isinstance(item, UsdRidgeOverlay):
            item.schedule = data['models']['usd']
        elif isinstance(item, ActivityConcentrationOverlay):
            item = AuditedActivity(item.spec, current['raw'])
        bound.append(item)
    tilt = None
    alphas = ARM_ALPHAS[arm]
    if alphas:
        tilt = AlphaTiltOverlay(alphas=alphas, budget=BUDGET, values_by_alpha=scores_by_alpha(day, alphas),
                                name='alpha101-tilt-' + arm.lower())
        bound = [*bound, tilt]
    targets = _target_schedule(instruments=data['instruments'], bars_by_symbol=current['histories'],
        trade_dates=[current['asof']], rebalance_frequency='daily', lookback_bars=63, max_weight=MAX_WEIGHT,
        cash_reserve_weight=D('.02'), sleeve_name='alpha101-tilt-v1',
        target_overlays=bound)[current['asof']]
    targets = FinalWeightCapOverlay().apply(targets, None)
    held = {t.symbol for t in targets if t.target_weight > 0}
    if any(t.target_weight > MAX_WEIGHT or t.target_weight < 0 for t in targets):
        raise ValueError('Cap/long-only violation on ' + day)
    if held and not held.issubset(set(data['bars'])):
        raise ValueError('Selection left the pinned universe on ' + day)
    parent = {t['symbol']: D(t['target_weight']) for t in data['controls']['CP'][day]['targets']}
    row = dict(signal_session=day, known_through=data['days'][current['i'] - 1],
               targets=[t.model_dump(mode="json") for t in targets])
    diagnostics = dict(arm=arm, signal_session=day, selected=sorted(held),
                       parent_selected=sorted(s for s, w in parent.items() if w > 0),
                       held_count=len(held), gross=str(sum((t.target_weight for t in targets), D(0))),
                       tilt=(tilt.diagnostics if tilt is not None else dict(applied=False, reason='control arm')))
    return row, diagnostics


def arm_days(arm):
    return {day: run_arm(day, arm) for day in decision_days()}


def freeze(root, rows):
    base.freeze_decisions(Path(root), rows)
    write_json(Path(root) / 'arm_plans.json', {arm: plan(arm) for arm in rows})


def jobs(arms=ARMS):
    return base.jobs(arms)


def window_start(window):
    return base.window_start(base._DATA['protocol'], window)


def arm_turnover(root, arm):
    decisions = read_json(Path(root) / 'decisions' / (arm + '.json'))
    weights = {day: {t['symbol']: float(t['target_weight']) for t in row['targets']} for day, row in decisions.items()}
    return implied_turnover(weights)


def gate(root, *, sigma=None):
    """P4.15 gate for every arm, plus the incremental cost against the untouched SOTA."""
    from systematic_trading.research.alpha101_tilt import calibration
    configured = calibration()
    sigma = configured['sigma'] if sigma is None else sigma
    reference = arm_turnover(root, 'SOTA')
    rows = {}
    for arm in ARMS:
        measured = arm_turnover(root, arm)
        incremental = measured['annual_turnover'] - reference['annual_turnover']
        rows[arm] = dict(
            implied=measured,
            incremental_turnover=incremental,
            incremental_cost_bps=incremental * configured['cost_bps'],
            verdict=screen(measured['annual_turnover'], sigma=sigma))
    payload = dict(study=STUDY, sigma=sigma, reference='SOTA', arms=rows,
                   ceiling_bps=configured['ceiling_bps'], monitored_drag_bps=configured['monitored_drag_bps'])
    write_json(Path(root) / 'gate.json', payload)
    return dict(arms={arm: rows[arm]['verdict']['status'] for arm in ARMS},
                costs={arm: round(rows[arm]['verdict']['annual_cost_bps'], 2) for arm in ARMS},
                incremental={arm: round(rows[arm]['incremental_cost_bps'], 2) for arm in ARMS})


def economics(root, job):
    from systematic_trading.research.momentum_calculation import quotes_for_data
    root = Path(root)
    data = base._DATA
    arm, cost, delay, window = job
    name = job_name(job)
    start = window_start(window)
    quotes, sessions = quotes_for_data(data['bars'], data['days'], start)
    decisions = {s: v for s, v in read_json(root / 'decisions' / (arm + '.json')).items() if s >= start}
    if not decisions:
        raise ValueError('No decisions inside the replay window for ' + name)
    if delay:
        decisions = {sessions[sessions.index(s) + delay]: v for s, v in decisions.items()
                     if sessions.index(s) + delay < len(sessions)}
    bundle = root / 'bundles' / name
    freeze_usd_bundle(bundle, root, dict(id=arm, window=window, delay_sessions=delay, tilt=plan(arm)),
                      decisions, quotes, sessions, cost)
    output = root / 'python' / (name + '.json')
    if output.exists():
        raise FileExistsError('Preserve completed economics')
    write_json(output, run_usd_reference(bundle))
    write_json(output.with_suffix('.receipt.json'),
               dict(sha256=sha256(output), manifest_sha256=sha256(bundle / 'manifest.json')))
    return name


def economics_resumable(root, job):
    name = job_name(job)
    output = Path(root) / 'python' / (name + '.json')
    if output.exists():
        bundle = Path(root) / 'bundles' / name
        if read_json(output.with_suffix('.receipt.json')) != dict(
                sha256=sha256(output), manifest_sha256=sha256(bundle / 'manifest.json')):
            raise ValueError('Completed economics changed: ' + name)
        return name
    return economics(root, job)


def protocol():
    return dict(study=STUDY, version=STUDY + '-v1', parent=str(PARENT), base_strategy=SOTA_KEY,
                peer_review_20261011=('Re-run after peer review corrected alpha 43 (each date now divides by '
                                      'its own rolling average dollar volume), the hold semantics (targets are '
                                      'submitted only when they change, so a held position is not rebalanced '
                                      'daily), the exit-and-re-enter branch and the look-ahead in the '
                                      'profit/loss exits. The v1 root is superseded and kept as the historical '
                                      'record.'),
                base_strategy_label=base.CONTROL_LABELS.get('CP', 'capped pooled control'),
                initial_cash_usd=1_000_000,
                limitations=[
                    'The evaluation window was already inspected by P4.13-P4.17, so nothing here is '
                    'out-of-sample evidence.',
                    'SOTA-TILT-53 uses the alpha with the strongest measured information, chosen after '
                    'inspecting the P4.17 screen, so its replay number is not an unbiased estimate; '
                    'SOTA-TILT-FAMILY selects nothing and dilutes by averaging in three negative-information '
                    'alphas and one degenerate one.',
                    'X is the operator-declared 10%; the P4.17b measurement covered 5%, 10% and 20% and this '
                    'replay does not re-tune it.',
                    'The tilt is applied monthly at the SOTA\'s own decision dates, appended last in its '
                    'overlay chain, so it inherits the model tilt, relative momentum, adaptive trend, activity '
                    'and USD layers rather than replacing any of them.',
                    'Cost, delay, currency and cash treatment are inherited from the parent study so the '
                    'comparison is like-for-like; none is re-optimised.',
                ],
                arms={arm: plan(arm) for arm in ARMS},
                tilt=dict(budget=str(BUDGET), max_weight=str(MAX_WEIGHT), min_names=MIN_NAMES,
                          position='appended last in the SOTA overlay chain, so it acts on the finished book and '
                                   'still respects the defensive fallback\'s protected cash budget',
                          membership='unchanged: the same symbol set, no additions or removals, gross untouched',
                          shape='NAV-neutral linear rank tilt; total overweight = total underweight = X/2; one '
                                'shrink factor for the 45% cap and the zero floor',
                          composite='the equal-weight mean of each alpha\'s rank scores, which is scale-free'),
                costs=list(COSTS), delays=list(DELAYS), windows=list(WINDOWS),
                bootstrap=dict(blocks=list(BOOTSTRAP_BLOCKS), replications=BOOTSTRAP_REPLICATIONS, seed=SEED),
                selection_disclosure='SOTA-TILT-53 uses the alpha with the strongest measured information, which '
                                     'was chosen after inspecting the P4.17 screen, so its result is not an '
                                     'unbiased estimate; SOTA-TILT-FAMILY selects nothing',
                declares=['the untouched SOTA is the only valid control',
                          'every arm is gated on its own implied turnover before any replay',
                          'no promotion, no monitoring change, no allocation change'])


def prepare(root=DEFAULT_ROOT):
    import shutil
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    existing = sorted(p.name for p in (root / 'python').glob('*.json')) if (root / 'python').exists() else []
    if existing:
        raise ValueError('Preserve completed economics: this root already holds ' + ', '.join(existing[:3]))
    source = root / 'source' / 'systematic_trading'
    if not source.exists():
        shutil.copytree(Path('src/systematic_trading'), source,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    write_json(root / 'protocol.json', protocol())
    manifest = {name: sha256(PARENT / name) for name in base.PARENT_INPUTS if (PARENT / name).exists()}
    write_json(root / 'input_manifest.json', dict(
        parent=str(PARENT), files=manifest, protocol_sha256=sha256(root / 'protocol.json'),
        note='P4.17c adds no new data source: the pinned P4.16 evidence root, replayed on the registered SOTA'))
    write_json(root / 'data_receipt.json', dict(
        parent_report_sha256=sha256(PARENT / 'report.json'), inputs=manifest))
    return dict(root=str(root), protocol_sha256=sha256(root / 'protocol.json'), arms=len(ARMS),
                jobs=len(jobs()))


def verify(root=DEFAULT_ROOT):
    root = Path(root)
    checks = dict(parent_unchanged=True)
    for name, digest in read_json(root / 'input_manifest.json')['files'].items():
        if sha256(PARENT / name) != digest:
            checks['parent_unchanged'] = False
    checks['decisions_present'] = all((root / 'decisions' / (arm + '.json')).exists() for arm in ARMS)
    checks['economics_complete'] = all((root / 'python' / (job_name(job) + '.json')).exists() for job in jobs())
    return checks
