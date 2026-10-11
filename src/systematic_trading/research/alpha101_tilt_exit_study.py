"""P4.17f — exit rules: close the tilt when the signal stops, instead of holding to the next rebalance.

Operator direction, 2026-10-11: *holding until the next monthly rebalance is of course not optimal.
Test rebalancing (removing the tilt) whenever the signal disappears or stops.* And on cost: *nobody
said the strategy cannot spend more — the key is optimal.*

**What this study changes, and what it deliberately does not.**

* **Cost is not a filter here.** Every arm is replayed whatever it costs, and the arms are ranked on
  *net* outcomes — the replays charge 5/10/20bp, so every return below is already after cost. The
  44.0bp ceiling from P4.15 is reported as a column, never as a gate, because the operator's
  objective is the optimum rather than a budget.
* **Entry is unchanged**: the tilt is opened (or refreshed) at the strategy's own monthly decision,
  using the tested NAV-neutral family-tilt rule at budget X.
* **Exit is new**: between decisions the arm re-reads the signal every session and may *close* the
  tilt. Rules, all declared up front:

  | Rule | Closes the tilt when |
  | --- | --- |
  | ``HOLD`` | never — the incumbent behaviour, held to the next monthly decision |
  | ``EXIT-FLIP`` | the desired tilt has turned against the held one (their inner product is negative) |
  | ``EXIT-FADE`` | the desired tilt's L1 magnitude falls below half its magnitude at entry |
  | ``EXIT-NOSIG`` | the signal stops ranking the book at all (no spread, or too few names) |
  | ``EXIT-PNL`` | the tilt's own weighted return since entry reaches −2% |
  | ``EXIT-FLIP-REENTER`` | as EXIT-FLIP, and re-enters inside the month when the signal re-aligns with the entry direction at entry magnitude or more |

* **Grid.** X in {5%, 10%, 20%} x those six rules, on FR25 and the current SOTA over the same 70
  months / 1,448 sessions, plus each book's untouched control. 38 arms.

No promotion, no monitoring change, no allocation change. The best arm by any metric is reported as
an in-sample optimum with its family-adjusted interval beside it.
"""
from pathlib import Path

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research import alpha101_tilt_daily_study as daily
from systematic_trading.research.momentum_replay import read_json

STUDY = 'alpha101-tilt-exit-v1'
DEFAULT_ROOT = Path('var/research/alpha101-tilt-exit-20261011-v2')
BASES = daily.BASES
BUDGETS = (0.05, 0.10, 0.20)
# Primary family: the signal-based exits the operator asked for.
RULES = ('HOLD', 'EXIT-FLIP', 'EXIT-FADE', 'EXIT-NOSIG', 'EXIT-PNL', 'EXIT-FLIP-REENTER')
# Secondary family: the profit- and loss-based exits, at the reference budget only. The primary family
# answers "does the signal stopping end the tilt"; this one answers "does the tilt's own P&L end it".
SECONDARY_RULES = ('EXIT-SL-05', 'EXIT-TP-1')
SECONDARY_BUDGET = 0.10
PNL_STOP = -0.02
PNL_STOP_TIGHT = -0.005
TAKE_PROFIT = 0.01
FADE_FRACTION = 0.5
COSTS = (5, 10, 20)
DELAYS = (0, 1)
WINDOWS = ('evaluation',)
COST_BPS = 5
DELAY = 0
WINDOW = 'evaluation'


def arm_name(base, budget, rule_name):
    return f'{base}-X{int(round(100 * budget))}-{rule_name}'


def arms():
    out = []
    for base in BASES:
        out.append(base)
        out.extend(arm_name(base, budget, rule_name) for budget in BUDGETS for rule_name in RULES)
        out.extend(arm_name(base, SECONDARY_BUDGET, rule_name) for rule_name in SECONDARY_RULES)
    return tuple(out)


def plan(arm):
    if arm in BASES:
        return dict(arm=arm, base=arm, budget=None, rule='CONTROL', family='control',
                    label=BASES[arm]['label'])
    for base in BASES:
        for budget in BUDGETS:
            for rule_name in RULES:
                if arm == arm_name(base, budget, rule_name):
                    return dict(arm=arm, base=base, budget=budget, rule=rule_name, family='signal',
                                label=f"{BASES[base]['label']} + {100 * budget:.0f}% tilt, {rule_name}")
        for rule_name in SECONDARY_RULES:
            if arm == arm_name(base, SECONDARY_BUDGET, rule_name):
                return dict(arm=arm, base=base, budget=SECONDARY_BUDGET, rule=rule_name, family='pnl',
                            label=f"{BASES[base]['label']} + {100 * SECONDARY_BUDGET:.0f}% tilt, {rule_name}")
    raise ValueError('Unregistered exit-rule arm: ' + str(arm))


def protocol():
    return dict(
        peer_review_20261011=('Corrected after peer review found four implementation defects: (1) the hold/exit arms re-submitted an unchanged target vector every session, which rebalances on price drift instead of holding shares, so rows are now emitted only when the target changes; (2) the exit-and-re-enter branch sat behind a guard an exit had already emptied and could never re-enter; (3) the profit/loss exits read the close of the session they traded, which is look-ahead, and now read only closes strictly before it; (4) alpha 43 divided every historical volume by the latest rolling average dollar volume instead of each date\'s own, and rank IC ranked tied values in ticker order instead of averaging them. The v1 root is superseded and kept as the historical record.'),
        study=STUDY, version=STUDY + '-v1',
        bases={k: dict(v, root=str(v['root']), bars_root=str(v['bars_root'])) for k, v in BASES.items()},
        budgets=list(BUDGETS), rules=list(RULES), arms=list(arms()), pnl_stop=PNL_STOP,
        secondary=dict(budget=SECONDARY_BUDGET, rules=list(SECONDARY_RULES), stop=PNL_STOP_TIGHT,
                       take_profit=TAKE_PROFIT,
                       note='profit- and loss-based exits, reported as a second declared family'),
        fade_fraction=FADE_FRACTION, costs=list(COSTS), delays=list(DELAYS), windows=list(WINDOWS),
        initial_cash_usd=1_000_000,
        objective='Rank the arms on net outcomes after 5/10/20bp costs. The P4.15 ceiling is reported as a '
                  'column and never gates a replay here, per the operator: the objective is the optimum, not a '
                  'cost budget.',
        exit_rules={
            'HOLD': 'never closes between decisions',
            'EXIT-FLIP': 'closes when the desired tilt has turned against the held one',
            'EXIT-FADE': f'closes when the desired tilt L1 magnitude falls below {FADE_FRACTION:.0%} of entry',
            'EXIT-NOSIG': 'closes when the signal stops ranking the book at all',
            'EXIT-PNL': f'closes when the tilt weighted return since entry reaches {PNL_STOP:.0%}',
            'EXIT-SL-05': f'closes when the tilt weighted return since entry reaches {PNL_STOP_TIGHT:.1%}',
            'EXIT-TP-1': f'closes when the tilt weighted return since entry reaches +{TAKE_PROFIT:.0%}',
            'EXIT-FLIP-REENTER': 'as EXIT-FLIP, and re-enters inside the month when the signal re-aligns with '
                                 'the entry direction at entry magnitude or more',
        },
        limitations=[
            'One inspected window, 2021-01-04 to 2026-10-01; the best arm is an in-sample optimum.',
            'The tilt is opened at the strategy\'s monthly decision; only the exit is intra-month.',
            'The P&L stop is measured on the tilt\'s weighted return, a declared proxy for its own contribution, '
            'not on the book\'s NAV.',
            'Costs are the parents\' 5/10/20bp with zero and one-session delay; none is re-optimised.',
        ])


# --- the exit simulation ------------------------------------------------------

def l1(vector):
    return sum(abs(value) for value in vector.values())


def alignment(held, wanted):
    return sum(held.get(symbol, 0.0) * wanted.get(symbol, 0.0) for symbol in set(held) | set(wanted))


def direction(held):
    return {symbol: (1.0 if value > 0 else -1.0) for symbol, value in held.items() if value != 0}


def closes_by_day(base):
    """Audited closes per session, for the P&L stop."""
    bars = read_json(BASES[base]['bars_root'] / 'bars.json')
    return {symbol: {str(row['trade_date']): float(row['close']) for row in rows}
            for symbol, rows in bars.items()}


def tilt_return(held, state, known):
    """The tilt's own weighted return since entry, using only closes known before the decision session.

    ``known`` is the last close **strictly before** the session being decided. Reading the same
    session's close (as this did until 2026-10-11) decides a trade at today's open with information
    from today's close — look-ahead bias that peer review reproduced and that
    ``test_alpha101_tilt_exit`` now covers.
    """
    contribution = 0.0
    for symbol, tilt in held.items():
        entry_price = state['entry_prices'].get(symbol)
        now = known.get(symbol)
        if entry_price and now:
            contribution += tilt * (now / entry_price - 1.0)
    return contribution


def should_exit(rule_name, held, wanted, state, known):
    if rule_name == 'HOLD':
        return False
    if rule_name == 'EXIT-NOSIG':
        return not wanted
    if rule_name in ('EXIT-FLIP', 'EXIT-FLIP-REENTER'):
        return alignment(held, wanted) < 0
    if rule_name == 'EXIT-FADE':
        return l1(wanted) < FADE_FRACTION * state['entry_magnitude']
    if rule_name == 'EXIT-PNL':
        return tilt_return(held, state, known) <= PNL_STOP
    if rule_name == 'EXIT-SL-05':
        return tilt_return(held, state, known) <= PNL_STOP_TIGHT
    if rule_name == 'EXIT-TP-1':
        return tilt_return(held, state, known) >= TAKE_PROFIT
    raise ValueError('Unregistered exit rule: ' + str(rule_name))


def should_reenter(held_direction, wanted, state):
    if not wanted or not held_direction:
        return False
    aligns = sum(held_direction.get(symbol, 0.0) * wanted.get(symbol, 0.0) for symbol in wanted) > 0
    return aligns and l1(wanted) >= state['entry_magnitude']


def simulate(books, rebals, budget, rule_name, desired, closes):
    """Daily targets for one arm: monthly entry, declared intra-month exits, same book and gross.

    Two rules matter and are both pinning tests:

    * A row is emitted **only when the target vector changes**, so between events the engine holds
      shares and price drift generates no trade. Re-submitting the same targets every session (as this
      did until 2026-10-11) is a daily-rebalanced process, not the monthly strategy being compared.
    * The exit test may only read closes **strictly before** the session it trades. ``known`` carries
      the previous close, never today's.

    Re-entry is evaluated when no tilt is held, so an exited arm can genuinely re-enter; before the
    fix the branch sat behind a ``held`` guard that an exit had already emptied, which made it
    unreachable and made its diagnostic count re-tilts of a position that was still on.
    """
    held, rows, events = {}, {}, {'entries': 0, 'exits': 0, 'reentries': 0, 'exit_days': [],
                                  'submitted': 0}
    state = {'entry_magnitude': 0.0, 'entry_prices': {}, 'entry_direction': {}}
    known, last_submitted = {}, None
    pending_entry = False
    for day in sorted(books):
        weights = books[day]
        wanted = desired.get(day) or {}
        changed = False
        if day in rebals:
            held = dict(wanted)
            events['entries'] += 1
            # The entry base is the entry session's own close, which is known before every later
            # decision. Only the *exit* rules must avoid the session they trade.
            state = {'entry_magnitude': l1(held), 'entry_prices': {}, 'entry_direction': direction(held)}
            pending_entry = True
            changed = True
        else:
            if pending_entry and held:
                state['entry_prices'] = {symbol: known.get(symbol) for symbol in held}
                pending_entry = False
            if held:
                if should_exit(rule_name, held, wanted, state, known):
                    held = {}
                    events['exits'] += 1
                    events['exit_days'].append(day)
                    changed = True
            elif rule_name == 'EXIT-FLIP-REENTER' and should_reenter(state['entry_direction'], wanted, state):
                held = dict(wanted)
                events['reentries'] += 1
                state = {'entry_magnitude': l1(held), 'entry_prices': {},
                         'entry_direction': direction(held)}
                pending_entry = True
                changed = True
        combined = {symbol: weights.get(symbol, 0.0) + held.get(symbol, 0.0)
                    for symbol in set(weights) | set(held)}
        combined = {symbol: weight for symbol, weight in combined.items() if abs(weight) > 1e-12}
        if changed or combined != last_submitted:
            rows[day] = combined
            last_submitted = dict(combined)
            events['submitted'] += 1
        for symbol, series in closes.items():
            value = series.get(day)
            if value is not None:
                known[symbol] = value
    events['days'] = len(books)
    return rows, events


def freeze(root=DEFAULT_ROOT):
    import shutil
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    source = root / 'source' / 'systematic_trading'
    if not source.exists():
        shutil.copytree(Path('src/systematic_trading'), source,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (root / 'decisions').mkdir(exist_ok=True)
    write_json(root / 'protocol.json', protocol())
    diagnostics = {}
    for base in BASES:
        values = daily.build_values(root, base)
        books = daily.base_books(base)
        rebals = daily.rebalance_days(base)
        closes = closes_by_day(base)
        source_rows = read_json(BASES[base]['root'] / 'decisions' / (BASES[base]['arm'] + '.json'))
        templates = {}
        for key, row in sorted(source_rows.items()):
            if key >= daily.EVALUATION_START:
                templates.setdefault(key[:7], row)
        control = {}
        for day, weights in books.items():
            row = daily.tilt_row(templates[day[:7]], weights)
            if control.get('last') != weights:
                control[day] = row
                control['last'] = dict(weights)
        control.pop('last', None)
        write_json(root / 'decisions' / (base + '.json'), control)
        diagnostics[base] = dict(entries=0, exits=0, reentries=0, days=len(books))
        for budget in BUDGETS:
            desired = daily.desired_tilt(base, budget, values, books)
            for rule_name in RULES:
                tilted, events = simulate(books, rebals, budget, rule_name, desired, closes)
                arm = arm_name(base, budget, rule_name)
                write_json(root / 'decisions' / (arm + '.json'),
                           {day: daily.tilt_row(templates[day[:7]], weights) for day, weights in tilted.items()})
                diagnostics[arm] = events
        desired_secondary = daily.desired_tilt(base, SECONDARY_BUDGET, values, books)
        for rule_name in SECONDARY_RULES:
            tilted, events = simulate(books, rebals, SECONDARY_BUDGET, rule_name, desired_secondary, closes)
            arm = arm_name(base, SECONDARY_BUDGET, rule_name)
            write_json(root / 'decisions' / (arm + '.json'),
                       {day: daily.tilt_row(templates[day[:7]], weights) for day, weights in tilted.items()})
            diagnostics[arm] = events
    write_json(root / 'decision_diagnostics.json', diagnostics)
    write_json(root / 'decision_manifest.json',
               {f.relative_to(root).as_posix(): sha256(f) for f in sorted((root / 'decisions').glob('*.json'))})
    write_json(root / 'input_manifest.json', dict(
        bases={name: dict(arm=spec['arm'],
                          decisions=sha256(spec['root'] / 'decisions' / (spec['arm'] + '.json')),
                          bars=sha256(spec['bars_root'] / 'bars.json')) for name, spec in BASES.items()},
        note='P4.17f adds no new data source: the same two frozen base books and their audited bars'))
    write_json(root / 'data_receipt.json', dict(
        protocol_sha256=sha256(root / 'protocol.json'),
        decision_manifest_sha256=sha256(root / 'decision_manifest.json')))
    return dict(root=str(root), protocol_sha256=sha256(root / 'protocol.json'), arms=len(arms()),
                diagnostics={arm: {k: v for k, v in diagnostics[arm].items() if k != 'exit_days'}
                             for arm in diagnostics})


def jobs():
    return [(arm, cost, delay, window) for arm in arms() for cost in COSTS for delay in DELAYS
            for window in WINDOWS]


def window_start(window):
    return daily.EVALUATION_START


def economics(root, job):
    """The parent replay path with this study's own arm registry in the bundle spec."""
    from systematic_trading.research.momentum_calculation import quotes_for_data
    from systematic_trading.research.momentum_replay import freeze_usd_bundle, run_usd_reference
    root = Path(root)
    arm, cost, delay, window = job
    name = daily.job_name(job)
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
    name = daily.job_name(job)
    output = Path(root) / 'python' / (name + '.json')
    if output.exists():
        bundle = Path(root) / 'bundles' / name
        if read_json(output.with_suffix('.receipt.json')) != dict(
                sha256=sha256(output), manifest_sha256=sha256(bundle / 'manifest.json')):
            raise ValueError('Completed economics changed: ' + name)
        return name
    return economics(root, job)


def costs(root):
    """Cost and the P4.15 verdict for every arm — reported, never used as a filter here."""
    from systematic_trading.research.alpha101_tilt import calibration
    configured = calibration()
    from systematic_trading.research.turnover_gate import implied_turnover, screen
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
        rows[arm] = dict(base=base, implied=measured,
                         incremental_turnover=measured['annual_turnover'] - reference[base]['annual_turnover'],
                         incremental_cost_bps=(measured['annual_turnover']
                                               - reference[base]['annual_turnover']) * configured['cost_bps'],
                         verdict=screen(measured['annual_turnover'], sigma=configured['sigma']))
    write_json(root / 'gate.json', dict(study=STUDY, sigma=configured['sigma'],
                                        ceiling_bps=configured['ceiling_bps'], arms=rows,
                                        note='Reported for information; no arm was filtered by it.'))
    passing = [arm for arm in arms() if rows[arm]['verdict']['status'] == 'pass']
    return dict(passing=len(passing), arms=len(arms()),
                cost={arm: round(rows[arm]['verdict']['annual_cost_bps'], 1) for arm in arms()})


def verify(root=DEFAULT_ROOT):
    root = Path(root)
    manifest = read_json(root / 'input_manifest.json')
    checks = {'base_inputs_unchanged': all(
        sha256(BASES[name]['root'] / 'decisions' / (spec['arm'] + '.json')) == spec['decisions']
        and sha256(BASES[name]['bars_root'] / 'bars.json') == spec['bars']
        for name, spec in manifest['bases'].items())}
    checks['decisions_present'] = all((root / 'decisions' / (arm + '.json')).exists() for arm in arms())
    checks['economics_complete'] = all((root / 'python' / (daily.job_name(job) + '.json')).exists()
                                       for job in jobs())
    return checks
