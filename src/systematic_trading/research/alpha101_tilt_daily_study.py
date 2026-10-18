"""P4.17e 鈥?the daily, threshold-triggered Alpha101 tilt.

Operator clarification, 2026-10-11: *not the monthly rebalance 鈥?monitor daily, and whenever the alpha
signal gives a buy/sell, rebalance X% of the portfolio. High rebalancing frequency to enhance the
return. If cost becomes an issue, control the threshold at which the signal trades, to reduce its
trading frequency.*

**Frozen design, declared before any outcome.**

* **Bases, over the 70-decision evaluation window (2021-01-04 to 2026-10-01)**: **FR25**
  (``research_fr25_14_v1``) from the frozen P4.14 Part B root and the **current SOTA**
  (``research_fallback_f3_v1``) from the frozen P4.17c root. The strategy's own target book is
  piecewise constant between its monthly decisions; only the tilt varies daily.
* **Daily signal.** Every session, the names the base book holds are ranked by the equal-weight mean of
  all sixteen registered alphas' rank scores, computed from audited bars strictly before that session.
* **Tilt.** The tested rule: linear rank scores in [-1, +1] with zero mean, total overweight equals
  total underweight equals X/2 of NAV, one shrink factor for the 45% cap and the zero floor.
* **Trigger.** The desired tilt is compared with the tilt currently held. The arm trades, moving the
  whole tilt to the newly desired one, when the L1 distance between them reaches ``theta * X``:
  ``theta = 0`` re-tilts every session (maximum frequency), ``theta = 0.5`` needs half the budget to
  change, ``theta = 1.0`` needs a full budget's worth. A strategy rebalance date always re-derives the
  tilt unconditionally, because the book it was ranked against has changed.
* **Grid.** ``X in {5%, 10%, 20%}`` x ``theta in {0, 0.5, 1.0}``, plus the monthly 10% arm from P4.17d
  as a like-for-like frequency reference, plus the untouched base book as the control. Declared up
  front; no arm is chosen from the outcome.
* **Cost.** Measured and gated for every arm at 5/10/20bp. The operator asked for high frequency and
  for the threshold to be the cost control, so the gate verdict is reported as the *frontier*: the
  threshold is the knob that decides how much of the frequency survives the 44.0bp ceiling.

No promotion, no monitoring change, no allocation change.
"""
from decimal import Decimal as D
from pathlib import Path

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research import alpha101 as lib
from systematic_trading.research import alpha101_tilt_study as rule
from systematic_trading.research.alpha101_tilt_surface_study import BASES, EVALUATION_START
from systematic_trading.research.expanded_economics import job_name
from systematic_trading.research.momentum_replay import freeze_usd_bundle, read_json, run_usd_reference
from systematic_trading.research.turnover_gate import implied_turnover, legacy_screen as screen

STUDY = 'alpha101-tilt-daily-v1'
DEFAULT_ROOT = Path('var/research/alpha101-tilt-daily-20261011-v3')
MONTHLY_REFERENCE = Path('var/research/alpha101-tilt-surface-20261011-v2')
BUDGETS = (0.05, 0.10, 0.20)
# theta is the deadband as a multiple of the budget. 0 re-tilts every session; 1.0 needs a whole
# budget's worth of movement; 2.0 and 3.0 are declared to locate where the cost ceiling starts to
# bind, which is the frontier the operator asked the threshold to control.
THRESHOLDS = (0.0, 0.5, 1.0, 2.0, 3.0)
REFERENCE_BUDGET = 0.10
ALPHAS = lib.REGISTERED
LOOKBACK = 260                      # every registered alpha is window-bounded by 200 sessions
COSTS = (5, 10, 20)
DELAYS = (0, 1)
WINDOWS = ('evaluation',)
COST_BPS = 5
DELAY = 0
WINDOW = 'evaluation'
WORKERS = 16


def daily_arm(base, budget, threshold):
    return f'{base}-D{int(round(100 * budget))}-T{int(round(100 * threshold))}'


def monthly_arm(base):
    return f'{base}-M{int(round(100 * REFERENCE_BUDGET))}'


def arms():
    out = []
    for base in BASES:
        out.append(base)
        out.extend(daily_arm(base, budget, threshold) for budget in BUDGETS for threshold in THRESHOLDS)
        out.append(monthly_arm(base))
    return tuple(out)


def plan(arm):
    if arm in BASES:
        return dict(arm=arm, base=arm, mode='control', budget=None, threshold=None, label=BASES[arm]['label'])
    for base in BASES:
        for budget in BUDGETS:
            for threshold in THRESHOLDS:
                if arm == daily_arm(base, budget, threshold):
                    return dict(arm=arm, base=base, mode='daily', budget=budget, threshold=threshold,
                                label=f"{BASES[base]['label']} + daily {100 * budget:.0f}% tilt, "
                                      f"threshold {100 * threshold:.0f}% of budget")
        if arm == monthly_arm(base):
            return dict(arm=arm, base=base, mode='monthly', budget=REFERENCE_BUDGET, threshold=None,
                        label=f"{BASES[base]['label']} + monthly {100 * REFERENCE_BUDGET:.0f}% tilt")
    raise ValueError('Unregistered daily-tilt arm: ' + str(arm))


def protocol():
    return dict(
        peer_review_20261011=('Revision 3 supersedes earlier timing, raw-activity and funding results. '
            'Monthly schedules retain unchanged rebalances; daily events have strictly prior cutoffs; '
            'exits use a declared prior-close contribution proxy; re-entry is reachable; raw activity '
            'is date-aligned. Legacy roots are retained and not reused as repaired evidence.'),
        study=STUDY, version=STUDY + '-review3',
        bases={k: dict(v, root=str(v['root']), bars_root=str(v['bars_root'])) for k, v in BASES.items()},
        budgets=list(BUDGETS), thresholds=list(THRESHOLDS), reference_budget=REFERENCE_BUDGET,
        reference_root='recomputed from this study inputs', alphas=list(ALPHAS), arms=list(arms()),
        window=dict(start=EVALUATION_START, evaluation_start=EVALUATION_START, windows=list(WINDOWS)),
        costs=list(COSTS), delays=list(DELAYS), initial_cash_usd=1_000_000, lookback=LOOKBACK,
        trigger=dict(distance='L1 distance between the desired and the currently held tilt vector',
                     rule='trade when distance >= theta * X, moving the whole tilt to the desired one',
                     establishment='the tilt is established on the first session it is computable; from '
                                   'then on the deadband governs, because the distance from a zero tilt '
                                   'is only about X and a band of X or more could otherwise never open',
                     rebalance_dates='a strategy rebalance always re-derives the tilt unconditionally'),
        limitations=[
            'One inspected window, 2021-01-04 to 2026-10-01; nothing here is out-of-sample evidence.',
            'Shares are held between events. Every monthly or alpha event rebalances the complete '
            'book to base targets plus tilt; event costs include resetting base-weight drift. This is '
            'not an overlay-only quantity trade.',
            'The threshold is the declared cost control, and the gate verdict is reported as the frontier '
            'rather than used to stop a replay, because the operator asked for the high-frequency surface.',
            'Costs are the parent studies\' 5/10/20bp with zero and one-session delay; none is re-optimised.',
        ])


# --- daily signal ------------------------------------------------------------

def _alpha_worker(payload):
    """One alpha's daily cross-section, computed from a rolling window of audited bars."""
    import bisect
    bars_path, days, alpha = payload
    bars = read_json(Path(bars_path))
    raw = read_json(Path(bars_path).with_name('raw.json'))
    series = {symbol: list(rows) for symbol, rows in bars.items()}
    dates = {symbol: [str(row['trade_date']) for row in rows] for symbol, rows in series.items()}
    out = {}
    for day in days:
        values = {}
        for symbol, rows in series.items():
            cut = bisect.bisect_left(dates[symbol], day) - 1
            if cut < 1:
                continue
            window = rows[max(0, cut - LOOKBACK + 1):cut + 1]
            history = lib.history_from_rows(symbol, window, str(window[-1]['trade_date']),
                raw_rows=raw.get(symbol, ()), lookback=LOOKBACK)
            value = lib.value(alpha, history)
            if value is not None:
                values[symbol] = value
        out[day] = values
    return alpha, out


def values_path(root, base):
    return Path(root) / 'scores' / (base + '.values.json')


def build_values(root, base):
    """Every alpha's daily cross-section, computed once and cached in the root."""
    from systematic_trading.research.alpha101_tilt_surface_study import verify_base_inputs
    verify_base_inputs(base)
    path = values_path(root, base)
    if path.exists():
        receipt = read_json(path.with_suffix('.receipt.json'))
        if receipt != value_receipt(path, base):
            raise ValueError('Daily alpha cache or its audited inputs changed')
        return read_json(path)
    from concurrent.futures import ProcessPoolExecutor
    bars_path = str(BASES[base]['bars_root'] / 'bars.json')
    bars = read_json(Path(bars_path))
    sessions = [str(row['trade_date']) for row in bars['SPY']]
    days = [day for day in sessions if day >= EVALUATION_START]
    payloads = [(bars_path, days, alpha) for alpha in ALPHAS]
    with ProcessPoolExecutor(max_workers=min(WORKERS, len(payloads))) as pool:
        results = list(pool.map(_alpha_worker, payloads))
    out = {day: {} for day in days}
    for alpha, per_day in results:
        for day, values in per_day.items():
            for symbol, value in values.items():
                out[day].setdefault(symbol, {})[alpha] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, out)
    write_json(path.with_suffix('.receipt.json'), value_receipt(path, base))
    return out


def value_receipt(path, base):
    source = BASES[base]['bars_root']
    return dict(values=sha256(path), bars=sha256(source / 'bars.json'), raw=sha256(source / 'raw.json'),
                alpha_source=sha256(Path(lib.__file__)), version='raw-activity-v2')


def event_context(base, source_rows, days):
    """Latest actual monthly decision and prior session for every daily event."""
    sessions = [str(row['trade_date']) for row in read_json(BASES[base]['bars_root'] / 'bars.json')['SPY']]
    prior = {day: sessions[i - 1] for i, day in enumerate(sessions) if i}
    decisions = iter(sorted(source_rows))
    following, current = next(decisions, None), None
    templates = {}
    for day in sorted(days):
        while following is not None and following <= day:
            current = source_rows[following]
            following = next(decisions, None)
        if current is None or day not in prior:
            raise ValueError('Missing prior decision or session for ' + day)
        templates[day] = current
    return templates, prior


def composite_scores(held, per_symbol_values):
    """The mean of each alpha's rank scores over the held names, via the tested rule.

    The cached daily values are keyed symbol -> {alpha: value}; the rule wants alpha -> {symbol: value},
    so the cross-section is transposed here and nothing else is re-derived.
    """
    per_alpha = {}
    for symbol, values in per_symbol_values.items():
        for alpha, value in values.items():
            per_alpha.setdefault(alpha, {})[symbol] = value
    scores, _ = rule.composite_scores(sorted(held), per_alpha)
    return scores or {}


def desired_tilt(base, budget, values, books):
    """Each session's desired tilt, computed once per (base, budget) and kept as floats."""
    out = {}
    for day, weights in books.items():
        held = [symbol for symbol, weight in weights.items() if weight > 0]
        scores = composite_scores(held, values.get(day, {}))
        vector, _ = rule.tilt_vector(weights, scores, D(str(budget))) if scores else ({}, None)
        out[day] = {symbol: float(tilt) for symbol, tilt in vector.items()}
    return out


def base_books(base):
    """The strategy's own book per session: its monthly decision, held until the next one."""
    spec = BASES[base]
    decisions = read_json(spec['root'] / 'decisions' / (spec['arm'] + '.json'))
    values = read_json(spec['bars_root'] / 'bars.json')
    sessions = [str(row['trade_date']) for row in values['SPY']]
    days = [day for day in sessions if day >= EVALUATION_START]
    out, current = {}, None
    for day in days:
        if day in decisions:
            current = {t['symbol']: float(t['target_weight']) for t in decisions[day]['targets']
                       if float(t['target_weight']) > 0}
        if current is not None:
            out[day] = dict(current)
    return out


def rebalance_days(base):
    spec = BASES[base]
    decisions = read_json(spec['root'] / 'decisions' / (spec['arm'] + '.json'))
    return {day for day in decisions if day >= EVALUATION_START}


def simulate(books, rebals, budget, threshold, desired):
    """Daily rows for one arm: hold the tilt until the signal moves far enough to re-trade.

    A row is emitted at every scheduled monthly rebalance, including unchanged weights, and whenever
    an alpha event changes the target vector. Emitting the same targets every session
    (as this did until 2026-10-11) does not hold a position: the replay rebalances back to the target
    weights on every session, so price drift alone generates trades and the arm stops being comparable
    with the monthly strategy that holds its shares between decisions. Peer review caught that, and
    ``test_alpha101_tilt_daily`` now pins the emission rule.
    """
    held_tilt, rows, trades, distances = {}, {}, 0, []
    last_submitted = None
    for day, weights in books.items():
        wanted = desired.get(day) or {}
        distance = sum(abs(wanted.get(s, 0.0) - held_tilt.get(s, 0.0)) for s in set(wanted) | set(held_tilt))
        trigger = (not held_tilt and wanted) or day in rebals or distance >= threshold * budget - 1e-12
        if trigger and wanted != held_tilt:
            # A trade is a change to the tilt actually held, which includes the establishing one.
            # A trigger that finds the same tilt already in place trades nothing.
            trades += 1
            held_tilt = dict(wanted)
        distances.append(distance)
        combined = {}
        for symbol in set(weights) | set(held_tilt):
            combined[symbol] = weights.get(symbol, 0.0) + held_tilt.get(symbol, 0.0)
        combined = {symbol: weight for symbol, weight in combined.items() if abs(weight) > 1e-12}
        if day in rebals or combined != last_submitted:
            rows[day] = combined
            last_submitted = dict(combined)
    return rows, dict(days=len(books), trades=trades, submitted=len(rows),
                      trade_share=trades / len(books) if books else 0.0,
                      mean_distance=sum(distances) / len(distances) if distances else 0.0)


def tilt_row(template, weights, *, day=None, known_through=None):
    """The base book's monthly decision with the daily tilt applied, in the frozen row shape."""
    targets = []
    for target in template['targets']:
        weight = D(str(weights.get(target['symbol'], 0.0)))
        if weight < 0 or weight > rule.MAX_WEIGHT:
            raise ValueError('Daily tilt produced an out-of-contract weight on ' + target['symbol'])
        targets.append(target | {'target_weight': str(weight), 'rationale': 'Daily Alpha101 tilt.'})
    missing = set(weights) - {t['symbol'] for t in template['targets']}
    if missing:
        raise ValueError('Daily tilt introduced a symbol outside the base universe: ' + ', '.join(sorted(missing)))
    row = dict(template, targets=targets)
    if day is not None:
        if known_through is None or known_through >= day:
            raise ValueError('Daily event needs a strictly prior signal cutoff')
        row.update(signal_session=day, known_through=known_through)
    return row


def freeze(root=DEFAULT_ROOT):
    import shutil
    root = Path(root)
    if (root / 'protocol.json').exists():
        raise FileExistsError('Preserve frozen study; use a new evidence root')
    root.mkdir(parents=True, exist_ok=True)
    source = root / 'source' / 'systematic_trading'
    if not source.exists():
        shutil.copytree(Path('src/systematic_trading'), source,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (root / 'decisions').mkdir(exist_ok=True)
    write_json(root / 'protocol.json', protocol())
    diagnostics = {}
    for base in BASES:
        spec = BASES[base]
        values = build_values(root, base)
        books = base_books(base)
        rebals = rebalance_days(base)
        source_rows = read_json(spec['root'] / 'decisions' / (spec['arm'] + '.json'))
        templates, prior = event_context(base, source_rows, books)
        rows = {}
        for day, weights in books.items():
            template = templates.get(day)
            if template is None:
                raise ValueError('No monthly decision template for ' + day)
            # The control submits only when its own book changes, i.e. at each monthly decision.
            # Writing one row per session rebalanced the control every day, which is not the
            # strategy being controlled for.
            if day in rebals:
                rows[day] = tilt_row(template, weights, day=day, known_through=prior[day])
        write_json(root / 'decisions' / (base + '.json'), rows)
        diagnostics[base] = dict(mode='control', days=len(books), submitted=len(rows), trades=0,
                                 trade_share=0.0, mean_distance=0.0)
        reference_tilt = desired_tilt(base, REFERENCE_BUDGET, values, books)
        monthly = {day: tilt_row(templates[day],
            {s: books[day].get(s, 0) + reference_tilt[day].get(s, 0)
             for s in set(books[day]) | set(reference_tilt[day])}, day=day, known_through=prior[day])
            for day in books if day in rebals}
        write_json(root / 'decisions' / (monthly_arm(base) + '.json'), monthly)
        diagnostics[monthly_arm(base)] = dict(mode='monthly', days=len(monthly), trades=len(monthly),
                                              trade_share=len(monthly) / len(rows), mean_distance=0.0)
        for budget in BUDGETS:
            desired = desired_tilt(base, budget, values, books)
            for threshold in THRESHOLDS:
                tilted, stats = simulate(books, rebals, budget, threshold, desired)
                arm = daily_arm(base, budget, threshold)
                write_json(root / 'decisions' / (arm + '.json'),
                           {day: tilt_row(templates[day], weights, day=day, known_through=prior[day])
                            for day, weights in tilted.items()})
                diagnostics[arm] = dict(mode='daily', **stats)
    write_json(root / 'decision_diagnostics.json', diagnostics)
    write_json(root / 'decision_manifest.json',
               {f.relative_to(root).as_posix(): sha256(f) for f in sorted((root / 'decisions').glob('*.json'))})
    write_json(root / 'input_manifest.json', dict(
        bases={name: dict(arm=spec['arm'],
                          decisions=sha256(spec['root'] / 'decisions' / (spec['arm'] + '.json')),
                          bars=sha256(spec['bars_root'] / 'bars.json'),
                          raw=sha256(spec['bars_root'] / 'raw.json')) for name, spec in BASES.items()},
        monthly_reference='recomputed from the same raw-activity values and monthly schedule',
        note='P4.17e adds no new data source: the same two frozen base books and their audited bars'))
    write_json(root / 'data_receipt.json', dict(
        protocol_sha256=sha256(root / 'protocol.json'),
        decision_manifest_sha256=sha256(root / 'decision_manifest.json')))
    return dict(root=str(root), protocol_sha256=sha256(root / 'protocol.json'), arms=len(arms()),
                diagnostics=diagnostics)


def jobs():
    return [(arm, cost, delay, window) for arm in arms() for cost in COSTS for delay in DELAYS
            for window in WINDOWS]


def window_start(window):
    return EVALUATION_START


def economics(root, job):
    from systematic_trading.research.momentum_calculation import quotes_for_data
    root = Path(root)
    arm, cost, delay, window = job
    name = job_name(job)
    base = plan(arm)['base']
    bars = read_json(BASES[base]['bars_root'] / 'bars.json')
    days = [str(row['trade_date']) for row in bars['SPY']]
    quotes, sessions = quotes_for_data(bars, days, window_start(window))
    decisions = {s: v for s, v in read_json(root / 'decisions' / (arm + '.json')).items()
                 if s >= window_start(window)}
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
    from systematic_trading.research.alpha101_tilt import calibration
    configured = calibration()
    root = Path(root)
    reference = {}
    for base in BASES:
        decisions = read_json(root / 'decisions' / (base + '.json'))
        reference[base] = implied_turnover({day: {t['symbol']: float(t['target_weight'])
                                                  for t in row['targets']} for day, row in decisions.items()})
    rows = {}
    for arm in arms():
        base = plan(arm)['base']
        decisions = read_json(root / 'decisions' / (arm + '.json'))
        measured = implied_turnover({day: {t['symbol']: float(t['target_weight'])
                                           for t in row['targets']} for day, row in decisions.items()})
        incremental = measured['annual_turnover'] - reference[base]['annual_turnover']
        rows[arm] = dict(base=base, implied=measured, incremental_turnover=incremental,
                         incremental_cost_bps=incremental * configured['cost_bps'],
                         verdict=screen(measured['annual_turnover'], sigma=configured['sigma']))
    write_json(root / 'gate.json', dict(study=STUDY, sigma=configured['sigma'],
                                        ceiling_bps=configured['ceiling_bps'],
                                        monitored_drag_bps=configured['monitored_drag_bps'], arms=rows))
    return dict(status={arm: rows[arm]['verdict']['status'] for arm in arms()},
                cost={arm: round(rows[arm]['verdict']['annual_cost_bps'], 1) for arm in arms()})


def verify(root=DEFAULT_ROOT):
    root = Path(root)
    manifest = read_json(root / 'input_manifest.json')
    checks = {'base_inputs_unchanged': all(
        sha256(BASES[name]['root'] / 'decisions' / (spec['arm'] + '.json')) == spec['decisions']
        and sha256(BASES[name]['bars_root'] / 'bars.json') == spec['bars']
        and sha256(BASES[name]['bars_root'] / 'raw.json') == spec.get('raw')
        for name, spec in manifest['bases'].items())}
    checks['decisions_present'] = all((root / 'decisions' / (arm + '.json')).exists() for arm in arms())
    checks['economics_complete'] = all((root / 'python' / (job_name(job) + '.json')).exists() for job in jobs())
    return checks
