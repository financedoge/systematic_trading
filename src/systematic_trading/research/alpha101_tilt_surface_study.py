"""P4.17d — the tilt budget surface on FR25 and the SOTA.

Operator request, 2026-10-11: *also add it to the FR25 strategy and see how much further we can push
the envelope. Raise the budget much higher. Don't worry about the cost first — let's find the optimal
X% tilt.*

**Frozen design, declared before any outcome.**

* **Base books, both over the same 70 evaluation decisions (2021-01-04 to 2026-10-01)** so the two
  surfaces are comparable: **FR25** (``research_fr25_14_v1``, 75% M1 / 25% financial ridge) from the
  frozen P4.14 Part B root, whose FR25 arm reproduces the published forecasts exactly, and the
  **current SOTA** (``research_fallback_f3_v1``) from the frozen P4.17c root. The base books are read,
  never recomputed: the tilt is the only thing this study changes.
* **Tilt.** The P4.17b/P4.17c rule, unchanged and already tested: rank only the names the base book
  holds, linear rank scores in [-1, +1] with zero mean, total overweight equals total underweight
  equals X/2 of NAV, one shrink factor for the 45% cap and the zero floor.
* **Family tilt** — the equal-weight mean of all sixteen registered alphas' rank scores — because
  P4.17c measured it to beat the single best-information alpha at lower cost.
* **Budget surface.** X in {10%, 20%, 30%, 50%, 75%, 100%, 150%}, declared up front. The **effective**
  tilt is reported beside the declared one, because the shrink factor saturates: a six-name book
  cannot move more than its smallest weight out of a name.
* **Cost, measured and reported but not binding.** The operator asked to search the performance
  surface irrespective of cost, so every arm is replayed; the P4.15 gate verdict and the incremental
  cost are still recorded for every arm, and any arm above the 44.0bp ceiling is flagged. This is a
  documented deviation from gate-before-replay, taken on the operator's instruction, and it promotes
  nothing.
* **No optimal X is declared.** The best X by any metric is reported as an in-sample maximum, and the
  family-adjusted interval decides. Choosing X from this surface would be tuning on the inspected
  window.

No promotion, no monitoring change, no allocation change.
"""
from decimal import Decimal as D
from pathlib import Path

import numpy as np

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research import alpha101 as lib
from systematic_trading.research import alpha101_tilt_study as rule
from systematic_trading.research.expanded_economics import job_name
from systematic_trading.research.momentum_replay import freeze_usd_bundle, read_json, run_usd_reference
from systematic_trading.research.turnover_gate import implied_turnover, screen

STUDY = 'alpha101-tilt-surface-v1'
DEFAULT_ROOT = Path('var/research/alpha101-tilt-surface-20261011-v2')
FR25_ROOT = Path('var/research/fr25-placebo-20261010-v1')
SOTA_ROOT = Path('var/research/alpha101-tilt-replay-20261011-v2')
BASES = {
    'FR25': dict(root=FR25_ROOT, bars_root=FR25_ROOT, arm='FR25',
                 label='FR25 · 75% M1 / 25% financial ridge', source='research_fr25_14_v1'),
    'SOTA': dict(root=SOTA_ROOT, bars_root=Path('var/research/sleeve-construction-20261010-v1'), arm='SOTA',
                 label='Current SOTA · qualifying defensive ETFs + cash', source='research_fallback_f3_v1'),
}
BUDGETS = (0.10, 0.20, 0.30, 0.50, 0.75, 1.00, 1.50)
ALPHAS = lib.REGISTERED
COSTS = (5, 10, 20)
DELAYS = (0, 1)
WINDOWS = ('evaluation',)
START = '2021-01-04'
EVALUATION_START = '2021-01-04'
COST_BPS = 5
DELAY = 0
WINDOW = 'evaluation'

_VALUES = {}


def tilt_arm(base, budget):
    return f'{base}-TILT-{int(round(100 * budget))}'


def arms():
    out = []
    for base in BASES:
        out.append(base)
        out.extend(tilt_arm(base, budget) for budget in BUDGETS)
    return tuple(out)


def plan(arm):
    if arm in BASES:
        return dict(arm=arm, base=arm, budget=None, label=BASES[arm]['label'], alphas=[])
    for base in BASES:
        for budget in BUDGETS:
            if arm == tilt_arm(base, budget):
                return dict(arm=arm, base=base, budget=budget,
                            label=f"{BASES[base]['label']} + {100 * budget:.0f}% family tilt",
                            alphas=list(ALPHAS))
    raise ValueError('Unregistered surface arm: ' + str(arm))


def protocol():
    return dict(
        peer_review_20261011=('Corrected after peer review found four implementation defects: (1) the hold/exit arms re-submitted an unchanged target vector every session, which rebalances on price drift instead of holding shares, so rows are now emitted only when the target changes; (2) the exit-and-re-enter branch sat behind a guard an exit had already emptied and could never re-enter; (3) the profit/loss exits read the close of the session they traded, which is look-ahead, and now read only closes strictly before it; (4) alpha 43 divided every historical volume by the latest rolling average dollar volume instead of each date\'s own, and rank IC ranked tied values in ticker order instead of averaging them. The v1 root is superseded and kept as the historical record.'),
        study=STUDY, version=STUDY + '-v1', bases={k: dict(v, root=str(v['root'])) for k, v in BASES.items()},
        budgets=list(BUDGETS), alphas=list(ALPHAS), arms=list(arms()),
        window=dict(start=START, evaluation_start=EVALUATION_START, windows=list(WINDOWS)),
        costs=list(COSTS), delays=list(DELAYS), initial_cash_usd=1_000_000,
        deviations=['Every arm is replayed regardless of its gate verdict, on the operator\'s instruction '
                    'to search the performance surface irrespective of cost; the gate verdict and '
                    'incremental cost are still recorded and any arm above the 44.0bp ceiling is flagged.',
                    'No optimal X is declared: the best X by any metric is an in-sample maximum and the '
                    'family-adjusted interval decides.'],
        limitations=[
            'Both base books cover the same 70 evaluation decisions, 2021-01-04 to 2026-10-01, which '
            'P4.13-P4.17 have already inspected; nothing here is out-of-sample evidence.',
            'The tilt is applied at the base book\'s own monthly decisions only.',
            'The effective tilt can be smaller than the declared budget because one shrink factor keeps '
            'every name inside the 45% cap and above zero; both are reported.',
            'FR25\'s base decisions come from the frozen P4.14 Part B root, whose FR25 arm reproduces the '
            'published forecasts exactly; the SOTA\'s come from the frozen P4.17c root.',
            'Cost, delay, currency and cash treatment are inherited from the parent studies; none is '
            're-optimised.',
        ])


def initialize():
    global _VALUES
    _VALUES = {}
    bases = {}
    for name, spec in BASES.items():
        rows = read_json(spec['root'] / 'decisions' / (spec['arm'] + '.json'))
        days = sorted(day for day in rows if day >= EVALUATION_START)
        bases[name] = dict(rows=rows, days=days)
    return bases


def base_weights(base):
    rows, days = _DATA[base]['rows'], _DATA[base]['days']
    return {day: {t['symbol']: float(t['target_weight']) for t in rows[day]['targets']
                  if float(t['target_weight']) > 0} for day in days}


def bar_rows(base):
    """Audited bars the base book's own decisions were made from, for point-in-time alpha values."""
    return read_json(BASES[base]['bars_root'] / 'bars.json')


def values_for_day(base, alpha, day):
    """The alpha's cross-section using only bars strictly before the decision."""
    key = (base, alpha, day)
    if key in _VALUES:
        return _VALUES[key]
    rows = _BARS[base]
    out = {}
    for symbol, series in rows.items():
        window = [row for row in series if str(row['trade_date']) < day]
        if len(window) < 2:
            continue
        history = lib.History(symbol=symbol, date=day,
                              open=np.array([float(r['open']) for r in window]),
                              high=np.array([float(r['high']) for r in window]),
                              low=np.array([float(r['low']) for r in window]),
                              close=np.array([float(r['close']) for r in window]),
                              volume=np.array([float(r['volume']) for r in window]))
        value = lib.value(alpha, history)
        if value is not None:
            out[symbol] = value
    _VALUES[key] = out
    return out


def composite_for_day(base, day):
    return {alpha: values_for_day(base, alpha, day) for alpha in ALPHAS}


def tilted_rows(base, budget):
    """The base book with the family tilt applied, plus per-decision diagnostics."""
    from systematic_trading.domain.portfolio import AllocationTarget
    rows = _DATA[base]['rows']
    out, diagnostics = {}, []
    for day in _DATA[base]['days']:
        row = rows[day]
        targets = [AllocationTarget.model_validate(t) for t in row['targets']]
        overlay = rule.AlphaTiltOverlay(alphas=ALPHAS, budget=D(str(budget)),
                                        values_by_alpha=composite_for_day(base, day),
                                        name=f'tilt-{base.lower()}')
        adjusted = overlay.apply(targets, None)
        weight = {t.symbol: t.target_weight for t in adjusted}
        if any(value < 0 or value > rule.MAX_WEIGHT for value in weight.values()):
            raise ValueError('Tilt produced an out-of-contract weight on ' + day)
        out[day] = dict(row, targets=[t.model_dump(mode='json') for t in adjusted])
        diagnostics.append(dict(day=day, **overlay.diagnostics))
    return out, diagnostics


_DATA = None
_BARS = None


def freeze(root=DEFAULT_ROOT):
    """Write every arm's decisions, the diagnostics, and the manifest."""
    import shutil
    global _DATA, _BARS
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    source = root / 'source' / 'systematic_trading'
    if not source.exists():
        shutil.copytree(Path('src/systematic_trading'), source,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    _DATA = initialize()
    _BARS = {base: bar_rows(base) for base in BASES}
    (root / 'decisions').mkdir(exist_ok=True)
    diagnostics = {}
    for base in BASES:
        rows = {day: _DATA[base]['rows'][day] for day in _DATA[base]['days']}
        write_json(root / 'decisions' / (base + '.json'), rows)
        diagnostics[base] = [dict(day=day, applied=False, reason='control arm') for day in _DATA[base]['days']]
        for budget in BUDGETS:
            arm = tilt_arm(base, budget)
            tilted, diag = tilted_rows(base, budget)
            write_json(root / 'decisions' / (arm + '.json'), tilted)
            diagnostics[arm] = diag
    write_json(root / 'decision_diagnostics.json', diagnostics)
    write_json(root / 'decision_manifest.json',
               {f.relative_to(root).as_posix(): sha256(f) for f in sorted((root / 'decisions').glob('*.json'))})
    write_json(root / 'protocol.json', protocol())
    write_json(root / 'input_manifest.json', dict(
        bases={name: dict(arm=spec['arm'],
                          decisions=sha256(spec['root'] / 'decisions' / (spec['arm'] + '.json')),
                          bars=sha256(spec['bars_root'] / 'bars.json')) for name, spec in BASES.items()},
        note='P4.17d adds no new data source: two frozen base books and their own audited bars'))
    write_json(root / 'data_receipt.json', dict(
        protocol_sha256=sha256(root / 'protocol.json'),
        decision_manifest_sha256=sha256(root / 'decision_manifest.json')))
    return dict(root=str(root), protocol_sha256=sha256(root / 'protocol.json'), arms=len(arms()),
                decisions={base: len(_DATA[base]['days']) for base in BASES})


def jobs():
    return [(arm, cost, delay, window) for arm in arms() for cost in COSTS for delay in DELAYS
            for window in WINDOWS]


def window_start(window):
    return START if window == 'full' else EVALUATION_START


def economics(root, job):
    from systematic_trading.research.momentum_calculation import quotes_for_data
    root = Path(root)
    arm, cost, delay, window = job
    name = job_name(job)
    base = plan(arm)['base']
    bars = read_json(BASES[base]['bars_root'] / 'bars.json')
    days = [row['trade_date'] for row in bars['SPY']]
    start = window_start(window)
    quotes, sessions = quotes_for_data(bars, days, start)
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


def gate(root):
    """Cost and gate verdict for every arm, including arms the operator asked to replay anyway."""
    from systematic_trading.research.alpha101_tilt import calibration
    configured = calibration()
    root = Path(root)
    rows, reference = {}, {}
    for base in BASES:
        decisions = read_json(root / 'decisions' / (base + '.json'))
        reference[base] = implied_turnover({day: {t['symbol']: float(t['target_weight'])
                                                  for t in row['targets']} for day, row in decisions.items()})
    for arm in arms():
        base = plan(arm)['base']
        decisions = read_json(root / 'decisions' / (arm + '.json'))
        measured = implied_turnover({day: {t['symbol']: float(t['target_weight'])
                                           for t in row['targets']} for day, row in decisions.items()})
        incremental = measured['annual_turnover'] - reference[base]['annual_turnover']
        rows[arm] = dict(base=base, implied=measured, incremental_turnover=incremental,
                         incremental_cost_bps=incremental * configured['cost_bps'],
                         verdict=screen(measured['annual_turnover'], sigma=configured['sigma']))
    payload = dict(study=STUDY, sigma=configured['sigma'], ceiling_bps=configured['ceiling_bps'],
                   monitored_drag_bps=configured['monitored_drag_bps'], arms=rows)
    write_json(root / 'gate.json', payload)
    return dict(status={arm: rows[arm]['verdict']['status'] for arm in arms()},
                cost={arm: round(rows[arm]['verdict']['annual_cost_bps'], 1) for arm in arms()})


def verify(root=DEFAULT_ROOT):
    root = Path(root)
    manifest = read_json(root / 'input_manifest.json')
    checks = {'base_inputs_unchanged': all(
        sha256(BASES[name]['root'] / 'decisions' / (spec['arm'] + '.json')) == spec['decisions']
        and sha256(BASES[name]['bars_root'] / 'bars.json') == spec['bars']
        for name, spec in manifest['bases'].items())}
    checks['decisions_present'] = all((root / 'decisions' / (arm + '.json')).exists() for arm in arms())
    checks['economics_complete'] = all((root / 'python' / (job_name(job) + '.json')).exists() for job in jobs())
    return checks
