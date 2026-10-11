"""P4.16 — sleeve-aware construction: does within-sleeve selection beat the pooled top six?

Registered 2026-10-10 in ``docs/signal-decay-and-alpha-plan.md``. The question is
whether the pooled cross-section is doing real work on fourteen heterogeneous
instruments, which is the premise P4.17 depends on.

**Frozen design, declared before any outcome.**

* Sleeves are the plan's own four: equity {SPY, VGK, EWJ, EWH, EWY, MCHI, XLE, XLB},
  fixed income {IEF, TLT, LQD, HYG}, commodity {DBC}, gold {GLD}.
* The construction primitive is the existing :class:`BalancedAssetGroupOverlay`. Its
  scoring is structurally identical to the pooled filter's, so with the pooled
  control's parameters (21/63/126 momentum, 0.75/0.25 trend/volume, positive
  126-session gate) the arms differ from the pooled control in **construction only**.
* ``fallback_to_top_ranked`` is off, so an unfilled sleeve budget stays in cash. That
  matches the pooled control's contract of never forcing an ineligible asset into a
  slot, and it keeps the fallback from being a second, silent difference.
* Slots per sleeve are a single declared count, ``SLOTS_PER_SLEEVE = 2``: the existing
  balanced-group overlay takes one count for every sleeve, and two is the smallest count
  that keeps the equity budget from concentrating into one capped name. With the
  composition budgets the two single-instrument sleeves can supply only one name each,
  so that arm tops out at six slots — the pooled control's own breadth; the equal-budget
  arm tops out at eight, and that breadth difference is reported rather than hidden.

Arms:

* ``POOL`` — one sleeve over all fourteen, budget 1, six slots. The construction-matched
  pooled control, and a parity check on the scoring equivalence.
* ``SLV-COMP`` — four sleeves with **budgets proportional to the universe's own
  composition** (8/4/1/1 instruments). The only information-free budget derivation
  available: it uses no return data and no inspected sample.
* ``SLV-EQ`` — four sleeves with **equal budgets**. The alternative prior.

Published references (``CP``, ``M1``) are read from the frozen parent evidence, not
recomputed. Every arm is screened by the P4.15 turnover gate **before** any replay.
"""
from decimal import Decimal as D
from pathlib import Path
import shutil

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json, checked_files, freeze_usd_bundle, run_usd_reference
from systematic_trading.research.expanded_economics import job_name

PARENT = Path('var/research/fr25-placebo-20261010-v1')
DEFAULT_ROOT = Path('var/research/sleeve-construction-20261010-v1')
PARENT_INPUTS = ('bars.json', 'raw.json', 'urth.json', 'xgb_usd.json', 'macro.json', 'selection.json',
                 'forecasts.json')
PARENT_CONTROLS = ('CP', 'M1')

SLEEVES = dict(
    equity=('SPY', 'VGK', 'EWJ', 'EWH', 'EWY', 'MCHI', 'XLE', 'XLB'),
    fixed_income=('IEF', 'TLT', 'LQD', 'HYG'),
    commodity=('DBC',),
    gold=('GLD',))
SLEEVE_OF = {symbol: sleeve for sleeve, symbols in SLEEVES.items() for symbol in symbols}
POOLED_SLOTS = 6
SLOTS_PER_SLEEVE = 2
ARMS = ('POOL', 'SLV-COMP', 'SLV-EQ')
LABELS = {'POOL': 'Pooled top six, sleeve-overlay scoring',
          'SLV-COMP': 'Within-sleeve, budgets proportional to universe composition',
          'SLV-EQ': 'Within-sleeve, equal sleeve budgets'}
CONTROLS = ('CP', 'M1')
CONTROL_LABELS = {'CP': 'Capped M1 pooled control', 'M1': 'M1/14 pooled, no final cap'}
COSTS = (5, 10, 20)
DELAYS = (0, 1)
WINDOWS = ('full', 'evaluation')

# Registered comparison family. C4 is a parity control, not a claim.
COMPARISONS = (('SLV-COMP', 'POOL'), ('SLV-EQ', 'POOL'), ('SLV-COMP', 'SLV-EQ'),
               ('POOL', 'CP'), ('SLV-COMP', 'CP'), ('SLV-EQ', 'CP'))
BOOTSTRAP_BLOCKS = (3, 6, 12)
BOOTSTRAP_REPLICATIONS = 10000
SEED = 2026101003
COST_BPS = 5
DELAY = 0


def slots_for(budget):
    """The declared per-sleeve slot count, bounded by the instruments a sleeve holds."""
    return SLOTS_PER_SLEEVE if budget < 1 else POOLED_SLOTS


def budgets(arm):
    if arm == 'POOL':
        return {'pooled': 1.0}
    if arm == 'SLV-COMP':
        total = sum(len(v) for v in SLEEVES.values())
        return {sleeve: len(symbols) / total for sleeve, symbols in SLEEVES.items()}
    if arm == 'SLV-EQ':
        return {sleeve: 1.0 / len(SLEEVES) for sleeve in SLEEVES}
    raise ValueError('Unregistered construction arm: ' + str(arm))


def sleeve_map(arm):
    return {'POOL': {symbol: 'pooled' for symbols in SLEEVES.values() for symbol in symbols}}.get(
        arm) or dict(SLEEVE_OF)


def plan(arm):
    budget = budgets(arm)
    slots = {sleeve: min(slots_for(weight), len(SLEEVES.get(sleeve, ()))) if sleeve in SLEEVES
             else slots_for(weight) for sleeve, weight in budget.items()}
    return dict(arm=arm, label=LABELS[arm], sleeve_by_symbol=sleeve_map(arm), budgets=budget, slots=slots,
                slot_total=sum(slots.values()), slots_per_sleeve=(POOLED_SLOTS if arm == 'POOL'
                                                                  else SLOTS_PER_SLEEVE),
                budget_basis=('pooled: one sleeve over the whole universe' if arm == 'POOL' else
                              'universe composition 8/4/1/1' if arm == 'SLV-COMP' else 'equal sleeve budgets 1/1/1/1'))


def prepare(root, runner, parent=PARENT):
    """Freeze a new study root that pins the parent inputs and the parent protocol."""
    root, parent = Path(root).resolve(), Path(parent).resolve()
    if root.exists():
        raise FileExistsError('Preserve the frozen sleeve-construction study')
    checked_files(parent, 'input_manifest.json')
    checked_files(parent, 'decision_manifest.json')
    pp = read_json(parent / 'protocol.json')
    if (parent / 'analysis.json').exists():
        parent_report = read_json(parent / 'analysis.json')
        parent_verdict = parent_report.get('verdict', {}).get('retention_verdict')
    else:
        parent_verdict = None
    p = dict(version='sleeve-construction-v1', client_date='2026-10-10',
             question='Does selecting within asset-class sleeves beat the pooled top-six over fourteen '
                      'heterogeneous instruments?',
             parent=dict(root=str(parent), protocol_sha256=sha256(parent / 'protocol.json'),
                         input_manifest_sha256=sha256(parent / 'input_manifest.json'),
                         decision_manifest_sha256=sha256(parent / 'decision_manifest.json'),
                         fr25_retention_verdict=parent_verdict),
             start=pp['start'], evaluation_start=pp['evaluation_start'], end=pp['end'],
             initial_cash_usd=pp['initial_cash_usd'], currency=pp['currency'], risk_free=pp['risk_free'],
             sleeves={k: list(v) for k, v in SLEEVES.items()},
             arms={arm: plan(arm) for arm in ARMS},
             controls={name: CONTROL_LABELS[name] for name in CONTROLS},
             comparisons=[dict(candidate=a, control=b) for a, b in COMPARISONS],
             family_size=len(COMPARISONS), cost_bps=list(COSTS), delayed_sessions=list(DELAYS),
             bootstrap_blocks=list(BOOTSTRAP_BLOCKS), bootstrap_replications=BOOTSTRAP_REPLICATIONS, seed=SEED,
             primary=dict(cost_bps=COST_BPS, delay=0, window='evaluation'),
             downstream='Identical to the pooled control: existing XGBoost weight tilt, relative momentum, adaptive '
                        'trend, audited raw activity, USD ridge and the explicit final 45% cap. Only the selection '
                        'stage changes.',
             scoring='BalancedAssetGroupOverlay parameterized to the pooled control: 21/63/126-session momentum, '
                     '0.75/0.25 trend/volume, positive 126-session gate, alphabetical ties. Its scoring code is '
                     'structurally identical to the pooled filter, so the arms differ in construction, not signal. '
                     'The POOL arm is the measured check on that equivalence.',
             fallback='fallback_to_top_ranked is off: an unfilled sleeve budget stays in cash, matching the pooled '
                      'control contract of never forcing an ineligible asset into a slot.',
             slots_rule='A single declared per-sleeve slot count of 2 (the pooled arm keeps 6 over its one sleeve), '
                        'because the balanced-group overlay takes one count for every sleeve and two is the smallest '
                        'count that keeps the equity budget out of a single capped name. The composition budgets then '
                        'top out at six slots and the equal budgets at eight; breadth is reported.',
             gate='Every arm is screened by the P4.15 turnover gate before any replay. A rejected arm is reported as '
                  'gate-rejected and is not replayed.',
             assessment='Shared-report comparison against the pooled control with family-adjusted uncertainty over '
                         'the registered six contrasts at 3/6/12-month blocks. No threshold grid, no parameter '
                         'search, no promotion.',
             promotion_eligible=False,
             limitations=[
                 'The evaluation window was already inspected when the pooled control was chosen, so nothing here is '
                 'out-of-sample evidence.',
                 'Sleeve membership is the plan\'s own four-way split of the fourteen instruments; it is a modelling '
                 'choice, not an observed asset-class taxonomy, and XLE/XLB are sector equity inside the equity '
                 'sleeve.',
                 'Sleeve budgets force representation: the commodity and gold sleeves hold one instrument each, so '
                 'those names enter whenever their gate passes. That is the mechanism under test, not a defect, but '
                 'it makes admission counts part of the result.',
                 'The POOL arm is the construction-matched control; CP is the published pooled control. Where they '
                 'differ, the difference is the fallback contract, and it is measured rather than assumed away.',
                 'Cost, delay, currency and cash treatment are inherited from the parent study so the comparison is '
                 'like-for-like; none is re-optimised.'],
             budget=dict(arms=len(ARMS), replays=len(ARMS) * len(COSTS) * len(DELAYS) * len(WINDOWS),
                         reference_replays=len(CONTROLS) * len(COSTS) * len(DELAYS) * len(WINDOWS)))
    root.mkdir(parents=True)
    shutil.copytree(Path(__file__).parents[1], root / 'source/systematic_trading',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copyfile(runner, root / 'runner.py')
    for name in PARENT_INPUTS:
        shutil.copyfile(parent / name, root / name)
    (root / 'controls').mkdir()
    (root / 'decisions').mkdir()
    for name in PARENT_CONTROLS:
        shutil.copyfile(parent / 'controls' / (name + '.json'), root / 'controls' / (name + '.json'))
        shutil.copyfile(parent / 'controls' / (name + '.json'), root / 'decisions' / (name + '.json'))
    write_json(root / 'protocol.json', p)
    write_json(root / 'data_receipt.json', dict(parent=str(parent),
        parent_hashes={name: sha256(parent / name) for name in PARENT_INPUTS},
        parent_protocol_sha256=sha256(parent / 'protocol.json'),
        parent_control_hashes={name: sha256(parent / 'controls' / (name + '.json')) for name in PARENT_CONTROLS},
        price_batch=read_json(parent / 'data_receipt.json')['price_batch'],
        economic_pin=read_json(parent / 'data_receipt.json')['economic_pin'],
        image=read_json(parent / 'data_receipt.json')['image']))
    write_json(root / 'input_manifest.json',
               {f.relative_to(root).as_posix(): sha256(f) for f in root.rglob('*')
                if f.is_file() and f != root / 'input_manifest.json'})
    return dict(root=str(root), protocol_sha256=sha256(root / 'protocol.json'), budget=p['budget'])


_DATA = None


def initialize(root):
    from systematic_trading.domain.market import PriceBar
    from systematic_trading.research.momentum_replay import usd_instruments
    global _DATA
    root = Path(root)
    bars = read_json(root / 'bars.json')
    instruments = usd_instruments()
    _DATA = dict(root=root, bars=bars,
                 typed={s: [PriceBar.model_validate(r) for r in rows] for s, rows in bars.items()},
                 raw={s: [PriceBar.model_validate(r) for r in rows] for s, rows in read_json(root / 'raw.json').items()},
                 models=read_json(root / 'xgb_usd.json'), macro=read_json(root / 'macro.json'),
                 selection=read_json(root / 'selection.json'), forecasts=read_json(root / 'forecasts.json'),
                 days=[r['trade_date'] for r in bars['SPY']], protocol=read_json(root / 'protocol.json'),
                 controls={a: read_json(root / 'controls' / (a + '.json')) for a in PARENT_CONTROLS},
                 instruments={s: instruments[s] for s in bars}, day_cache={})


def decision_days():
    return sorted(_DATA['selection'])


def evaluation_days():
    return [d for d in decision_days() if d >= _DATA['protocol']['evaluation_start']]


def _day(day):
    data = _DATA
    if day in data['day_cache']:
        return data['day_cache'][day]
    from datetime import date
    from systematic_trading.research.rolling_tracking import select_rolling_model
    i = data['days'].index(day)
    asof = date.fromisoformat(day)
    histories = {s: rows[max(0, i - 500):i] for s, rows in data['typed'].items()}
    raw = {s: rows[max(0, i - 500):i] for s, rows in data['raw'].items()}
    model = select_rolling_model(data['models']['rolling'], histories, asof)
    data['day_cache'] = {day: dict(i=i, asof=asof, histories=histories, raw=raw, model=model)}
    return data['day_cache'][day]


def sleeve_overlay(arm):
    """The existing balanced-group primitive, parameterized to the pooled control."""
    from systematic_trading.signals.balanced import BalancedAssetGroupOverlay
    selected = plan(arm)
    return BalancedAssetGroupOverlay(sleeve_by_symbol=selected['sleeve_by_symbol'],
        sleeve_budgets=selected['budgets'], top_n_per_sleeve=selected['slots_per_sleeve'],
        min_selected_per_sleeve=1, short_momentum_bars=21, medium_momentum_bars=63, long_momentum_bars=126,
        volume_bars=21, slow_volume_bars=126, trend_weight=D('0.75'), volume_weight=D('0.25'),
        require_positive_long_momentum=True, min_long_momentum=D('0'), fallback_to_top_ranked=False,
        name=f'sleeve-construction-{arm.lower()}')


def run_arm(day, arm, overlay_factory=None):
    """One construction decision through the engine's own sizing and cap contracts.

    ``overlay_factory`` lets a follow-up study substitute its own selection stage while
    reusing this chain, the validations and the economics unchanged.
    """
    from systematic_trading.backtest.stored import _target_schedule
    from systematic_trading.research.construction_controls import FinalWeightCapOverlay
    from systematic_trading.research.flow_concentration import ActivityConcentrationOverlay
    from systematic_trading.research.rolling_tracking import RollingModelOverlay
    from systematic_trading.research.strategy_catalog import defensive_cash_definition, instantiate_overlays
    from systematic_trading.research.usd_tracking import UsdRidgeOverlay
    from systematic_trading.research.candidate_pool import AuditedActivity
    data, current = _DATA, _day(day)
    overlays = instantiate_overlays(defensive_cash_definition())
    overlay = (overlay_factory or sleeve_overlay)(arm)
    overlays[0] = overlay
    bound = []
    for item in overlays:
        if isinstance(item, RollingModelOverlay):
            item.model = current['model']
        elif isinstance(item, UsdRidgeOverlay):
            item.schedule = data['models']['usd']
        elif isinstance(item, ActivityConcentrationOverlay):
            item = AuditedActivity(item.spec, current['raw'])
        bound.append(item)
    targets = _target_schedule(instruments=data['instruments'], bars_by_symbol=current['histories'],
        trade_dates=[current['asof']], rebalance_frequency='daily', lookback_bars=63, max_weight=D('.45'),
        cash_reserve_weight=D('.02'), sleeve_name='sleeve-construction-v1',
        target_overlays=bound)[current['asof']]
    targets = FinalWeightCapOverlay().apply(targets, None)
    held = {t.symbol for t in targets if t.target_weight > 0}
    if any(t.target_weight > D('.45') or t.target_weight < 0 for t in targets):
        raise ValueError('Cap/long-only violation on ' + day)
    if held and not held.issubset(set(data['bars'])):
        raise ValueError('Selection left the pinned universe on ' + day)
    original = {t['symbol']: D(t['target_weight']) for t in data['controls']['CP'][day]['targets']}
    row = dict(signal_session=day, known_through=data['days'][current['i'] - 1],
               targets=[t.model_dump(mode='json') for t in targets])
    diagnostics = dict(arm=arm, signal_session=day, selected=sorted(held),
        parent_selected=sorted(s for s, w in original.items() if w > 0), held_count=len(held),
        gross=str(sum((t.target_weight for t in targets), D(0))),
        sleeves={sleeve: sorted(held & set(symbols)) for sleeve, symbols in SLEEVES.items()})
    return row, diagnostics


def arm_days(arm):
    return {day: run_arm(day, arm) for day in decision_days()}


def freeze_decisions(root, rows):
    root = Path(root)
    (root / 'decisions').mkdir(exist_ok=True)
    for arm, day_rows in rows.items():
        write_json(root / 'decisions' / (arm + '.json'), {d: v[0] for d, v in sorted(day_rows.items())})
    write_json(root / 'decision_diagnostics.json',
               {arm: {d: v[1] for d, v in sorted(day_rows.items())} for arm, day_rows in rows.items()})
    write_json(root / 'decision_manifest.json',
               {f.relative_to(root).as_posix(): sha256(f) for f in sorted((root / 'decisions').glob('*.json'))})


def jobs(arms=ARMS):
    return [(arm, cost, delay, window) for arm in arms for cost in COSTS for delay in DELAYS for window in WINDOWS]


def window_start(protocol, window):
    return protocol['start'] if window == 'full' else protocol['evaluation_start']


def economics(job):
    from systematic_trading.research.momentum_calculation import quotes_for_data
    data = _DATA
    root, protocol = data['root'], data['protocol']
    arm, cost, delay, window = job
    name = job_name(job)
    start = window_start(protocol, window)
    quotes, sessions = quotes_for_data(data['bars'], data['days'], start)
    decisions = {s: v for s, v in read_json(root / 'decisions' / (arm + '.json')).items() if s >= start}
    if not decisions:
        raise ValueError('No decisions inside the replay window for ' + name)
    if delay:
        decisions = {sessions[sessions.index(s) + delay]: v for s, v in decisions.items()
                     if sessions.index(s) + delay < len(sessions)}
    bundle = root / 'bundles' / name
    freeze_usd_bundle(bundle, root, dict(id=arm, window=window, delay_sessions=delay,
        construction=plan(arm) if arm in ARMS else dict(reference=CONTROL_LABELS.get(arm, arm))),
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
    return economics(job)
