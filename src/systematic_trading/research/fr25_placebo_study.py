"""P4.14 Part B — FR25 matched-availability placebo, data-through-2022 refit and sensitivity.

Frozen 2026-10-10 in ``docs/signal-decay-and-alpha-plan.md`` **before any Part B
outcome**. Part A (``fr25_robustness``) analysed the published selection-blend
evidence and returned *inconclusive*; Part B cannot be evaluated from published
artifacts because each perturbation changes which assets were selected and
therefore the realised path, so it needs its own frozen study and its own
evidence root. This module never extends or overwrites the parent root, and never
changes the monitored strategy registry, an allocation, an approval or a broker
record.

Three perturbations, all selection-layer operations:

* **Placebo rank.** At each decision the frozen FR25 financial-ridge *forecast
  values* are permuted across the available symbols and injected through the
  engine's own ``SelectionBlend`` path, so eligibility, abstention and every
  downstream sizing overlay are preserved by construction. Re-implementing the
  downstream sizing outside the engine is explicitly forbidden: a placebo must
  differ from FR25 in exactly one respect, the assignment of ridge information.
* **Data-through-2022 refit.** The financial ridge is refitted on labels completed
  by ``REFIT_LABEL_CUTOFF`` and replayed from ``SUB_START``. It is reproducible
  from frozen evidence because the parent protocol preserved every training row
  and every decision-time query vector inside ``macro.json``.
* **Top-N and financial-weight sensitivity.** The same axes the parent study
  already varied, reported as a surface. Not a search, and not out-of-sample
  evidence.
"""
from decimal import Decimal as D
from pathlib import Path
import hashlib
import json
import shutil

import numpy as np

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.candidate_pool import AuditedActivity
from systematic_trading.research.expanded_economics import job_name
from systematic_trading.research.momentum_replay import (checked_files, freeze_usd_bundle,
    read_json, run_usd_reference, usd_instruments)
from systematic_trading.research.selection_blend import BLENDS, SelectionBlend

PARENT = Path('var/research/selection-blend-20261010-v1')
DEFAULT_ROOT = Path('var/research/fr25-placebo-20261010-v1')
# Reused frozen inputs, copied under their own names into this study's root.
PARENT_INPUTS = ('bars.json', 'raw.json', 'urth.json', 'xgb_usd.json', 'macro.json', 'selection.json',
                 'forecasts.json')
# Pinned lineage copies. They keep their parent names, so they live in their own folder rather than
# colliding with this study's own protocol and manifests.
PARENT_PINS = ('protocol.json', 'input_manifest.json', 'decision_manifest.json')
PARENT_CONTROLS = ('M1', 'CP')
CANDIDATE = 'FR25'
CONTROL = 'CP'
SENTINEL = 'SENTINEL'
REFIT_ARM = 'REFIT22'
COST_BPS = 5
DELAY = 0

# Declared before any Part B outcome.
SEED = 20261010
DRAWS = 200
PLACEBO_PERCENTILE = 0.90
REFIT_LABEL_CUTOFF = '2022-12-31'
REFIT_MIN_ROWS = 36
SUB_START = '2023-01-03'
SLOTS = (4, 5, 6, 7)
RIDGE_WEIGHTS_PCT = (10, 25, 40)
SENSITIVITY_BASELINE = (6, 25)
BASELINE_ARM = 'N6W25'
STUDY_BLENDS = {'W10': (9, 0, 1), 'W40': (3, 0, 2)}
BLEND_KEY = {10: 'W10', 25: 'R25', 40: 'W40'}
RECIPE = dict(blend='R25', group='financial')

TOLERANCE = dict(positive_year_share=2 / 3, block_for_lower_bound=6,
                 placebo_percentile=PLACEBO_PERCENTILE, selection_tolerance='1e-12')

# Frozen verdict mapping. The tolerance is unambiguous: retention needs all four
# checks. Its verdict sentence ("otherwise reject, or inconclusive when the point
# estimate is positive but the interval spans zero and the concentration tests
# pass") describes the noise-limited case, and a failed placebo is not
# noise-limited: it says the ridge assignment carries no more information than a
# random assignment with identical availability. Both readings are reported.
VERDICT_MAPPING = dict(
    preserve='every frozen check passes. Unreachable in this study because the frozen 6-month bootstrap lower '
             'bound already failed in Part A, and Part B may not rescue a failed interval test.',
    reject='any of: point estimate not positive; leave-one-out fails; placebo check fails.',
    inconclusive='point estimate positive, placebo check passes, and at least one of the year or interval checks '
                 'fails: the sample cannot distinguish the effect from noise.',
    alternative_reading='The plan also says Part B can only move the verdict between preserve and inconclusive. '
                        'Read literally that makes a failed placebo inconclusive as well, because the point '
                        'estimate is positive and the interval spans zero. Both readings are reported, and the '
                        'retention verdict "not preserved" is identical under either.')


def register_blends():
    """Add only the study's weight variants; never alter a frozen registry entry."""
    frozen = dict(BLENDS)
    for key, weights in STUDY_BLENDS.items():
        if key in frozen and frozen[key] != weights:
            raise ValueError('Study blend collides with the frozen registry: ' + key)
    BLENDS.update(STUDY_BLENDS)
    if {k: v for k, v in BLENDS.items() if k in frozen} != frozen:
        raise ValueError('Frozen blend registry changed')
    if BLENDS['R25'] != (3, 0, 1):
        raise ValueError('Frozen FR25 blend weights changed')


register_blends()

_DATA = None


def sensitivity_arms():
    return [(n, w) for n in SLOTS for w in RIDGE_WEIGHTS_PCT if (n, w) != SENSITIVITY_BASELINE]


def variant_name(slots, weight):
    return f'N{slots}W{weight}'


def placebo_arm(draw):
    return f'PLACEBO-{int(draw):03d}'


def draw_of(arm):
    return int(arm.split('-')[1]) if arm.startswith('PLACEBO-') else None


def variant_of(arm):
    for n, w in sensitivity_arms():
        if variant_name(n, w) == arm:
            return n, w
    return None


def decision_arms():
    return [CANDIDATE, CONTROL, 'M1', SENTINEL, BASELINE_ARM,
            *[variant_name(n, w) for n, w in sensitivity_arms()],
            *[placebo_arm(k) for k in range(1, DRAWS + 1)], REFIT_ARM]


def jobs():
    """Every economic replay this study runs: one arm, one cost, one window."""
    rows = [(a, COST_BPS, DELAY, 'evaluation') for a in decision_arms() if a != REFIT_ARM]
    rows += [(REFIT_ARM, COST_BPS, DELAY, 'sub2023'), (CANDIDATE, COST_BPS, DELAY, 'sub2023'),
             (CONTROL, COST_BPS, DELAY, 'sub2023')]
    return rows


def window_start(protocol, window):
    if window == 'full':
        return protocol['start']
    if window == 'evaluation':
        return protocol['evaluation_start']
    if window == 'sub2023':
        return SUB_START
    raise ValueError('Unregistered Part B window: ' + str(window))


def prepare(root, runner, parent=PARENT):
    """Freeze a new study root that pins the parent protocol and input hashes."""
    root, parent = Path(root).resolve(), Path(parent).resolve()
    if root.exists():
        raise FileExistsError('Preserve the frozen placebo study')
    checked_files(parent, 'input_manifest.json')
    checked_files(parent, 'decision_manifest.json')
    pp = read_json(parent / 'protocol.json')
    p = dict(version='fr25-placebo-partb-v1', client_date='2026-10-10', part='B — its own frozen study',
             question='Is FR25 selection advantage robust, or is it 13 selections and one year?',
             parent=dict(root=str(parent), protocol_sha256=sha256(parent / 'protocol.json'),
                         input_manifest_sha256=sha256(parent / 'input_manifest.json'),
                         decision_manifest_sha256=sha256(parent / 'decision_manifest.json')),
             candidate=CANDIDATE, control=CONTROL, cost_bps=COST_BPS, delayed_sessions=DELAY,
             start=pp['start'], evaluation_start=pp['evaluation_start'], end=pp['end'],
             initial_cash_usd=pp['initial_cash_usd'], currency=pp['currency'], risk_free=pp['risk_free'],
             placebo=dict(
                 draws=DRAWS, seed=SEED,
                 randomisation='At each decision the frozen FR25 financial-ridge forecast values are permuted '
                               'across the available symbols. A permutation preserves the marginal distribution '
                               'and destroys only the assignment, which is precisely the information the ridge '
                               'claims to supply.',
                 generator='numpy SeedSequence([seed, draw, ordinal]) with PCG64, where ordinal is the 0-based '
                           'position of the decision in the frozen monthly decision calendar. Independent per draw '
                           'and per decision, so replay order and parallelism cannot change a draw.',
                 injection="models[symbol]['linear_forecast'] plus ready on the frozen macro entry, regenerated "
                           "through SelectionBlend._selection_scores; downstream sizing is never re-implemented.",
                 availability='Where the frozen FR25 ridge is unavailable the day is abstained: no placebo point '
                              'is injected and the whole selection reverts to M1 exactly as FR25 does.',
                 sentinel='SENTINEL is a declared verification arm, not a draw: the identity assignment. It must '
                          'reproduce the parent FR25 decisions exactly and is excluded from the distribution.',
                 statistic='log(terminal NAV of the draw) - log(terminal NAV of CP) over the same fresh-cash '
                           'evaluation replay, reported with the percentage-point difference.',
                 percentile='P = (draws strictly below + 0.5 * draws equal) / DRAWS; the 90th percentile of the '
                            'draw distribution is also reported by linear interpolation. Retention requires the '
                            'observed FR25 excess to exceed it.',
                 retention_percentile=PLACEBO_PERCENTILE),
             refit=dict(cutoff=REFIT_LABEL_CUTOFF, min_rows=REFIT_MIN_ROWS, replay_from=SUB_START,
                        source='Frozen macro.json training rows and decision-time query vectors; no new data.',
                        requirement='If it cannot be run reproducibly, report it as not run rather than approximated.',
                        comparison='Fresh, identical start on the first 2023 decision for the refit arm, FR25 and CP, '
                                   'so the 2023-onward comparison is like-for-like and not a continuation of a path '
                                   'whose earlier decisions the refit could not have made.'),
             sensitivity=dict(slots=list(SLOTS), ridge_weights_pct=list(RIDGE_WEIGHTS_PCT),
                              baseline=list(SENSITIVITY_BASELINE),
                              note='The same axes the parent study already varied. Reported as a surface; not a '
                                   'search and not out-of-sample evidence.'),
             tolerance=TOLERANCE, verdict_mapping=VERDICT_MAPPING, promotion_eligible=False,
             limitations=[
                 'The evaluation window was already inspected when FR25 was chosen, so nothing in this study is '
                 'out-of-sample evidence.',
                 'A permutation destroys the assignment of ridge information but preserves its availability, its '
                 'marginal distribution and the downstream sizing chain, so this tests the ridge ranking '
                 'information rather than the ridge family as a whole.',
                 'The sensitivity surface re-uses axes the parent study already varied and cannot be presented as a '
                 'fresh result or as a search.',
                 'The data-through-2022 refit re-fits only the ridge stage; momentum and XGBoost are unchanged, and '
                 'the refit path starts from fresh cash in 2023 rather than continuing the evaluation path.',
                 'The reference pair, costs, delay, currency and cash treatment are inherited from the parent study '
                 'so the comparison is like-for-like; none of them is re-optimised here.',
                 'A reject is a research finding. It does not by itself deallocate, and switching remains an '
                 'operator decision through the existing allocation workflow.'],
             budget=dict(placebo_draws=DRAWS, sensitivity_arms=len(sensitivity_arms()), refit_arms=1,
                         control_replays=4, total_replays=len(jobs())))
    root.mkdir(parents=True)
    shutil.copytree(Path(__file__).parents[1], root / 'source/systematic_trading',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copyfile(runner, root / 'runner.py')
    for name in PARENT_INPUTS:
        shutil.copyfile(parent / name, root / name)
    (root / 'parent').mkdir()
    for name in PARENT_PINS:
        shutil.copyfile(parent / name, root / 'parent' / name)
    (root / 'controls').mkdir()
    (root / 'decisions').mkdir()
    for a in PARENT_CONTROLS:
        shutil.copyfile(parent / 'controls' / (a + '.json'), root / 'controls' / (a + '.json'))
        shutil.copyfile(parent / 'controls' / (a + '.json'), root / 'decisions' / (a + '.json'))
    write_json(root / 'protocol.json', p)
    write_json(root / 'data_receipt.json', dict(parent=str(parent),
        parent_hashes={name: sha256(parent / name) for name in (*PARENT_INPUTS, *PARENT_PINS)},
        parent_control_hashes={a: sha256(parent / 'controls' / (a + '.json')) for a in PARENT_CONTROLS},
        price_batch=read_json(parent / 'data_receipt.json')['price_batch'],
        economic_pin=read_json(parent / 'data_receipt.json')['economic_pin'],
        image=read_json(parent / 'data_receipt.json')['image']))
    write_json(root / 'input_manifest.json',
               {f.relative_to(root).as_posix(): sha256(f) for f in root.rglob('*')
                if f.is_file() and f != root / 'input_manifest.json'})
    return dict(root=str(root), protocol_sha256=sha256(root / 'protocol.json'), budget=p['budget'])


def initialize(root):
    from systematic_trading.domain.market import PriceBar
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
    """The frozen monthly decision calendar, never the underlying session calendar."""
    return sorted(_DATA['selection'])


def evaluation_days():
    return [d for d in decision_days() if d >= _DATA['protocol']['evaluation_start']]


def sub_days():
    return [d for d in evaluation_days() if d >= SUB_START]


def decision_ordinal(day):
    """0-based position in the frozen decision calendar, the declared draw entropy."""
    return decision_days().index(day)


def _day(day):
    """Per-day invariants, identical for every draw at this decision."""
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


def _frozen(day):
    """Frozen ridge forecasts and ranks for the candidate arm, or None if abstained."""
    fitted = _DATA['macro'][day]['financial']
    table = _DATA['selection'][day][CANDIDATE]['rank_table']
    if table is None:
        return fitted, None, None
    ranks = {s: v['ridge'] for s, v in table.items()}
    present = [s for s, v in ranks.items() if v is not None]
    if not fitted['ready'] and present:
        raise ValueError('Frozen ridge ranks exist without a ready frozen model: ' + day)
    if fitted['ready'] and len(present) != len(ranks):
        raise ValueError('Partially populated frozen ridge rank table: ' + day)
    if not fitted['ready']:
        return fitted, None, None
    values = {s: fitted['models'][s]['linear_forecast'] for s in ranks}
    return fitted, values, ranks


def frozen_ridge(day):
    return _frozen(day)[1]


def frozen_ranks(day):
    return _frozen(day)[2]


def draw_permutation(draw, ordinal, size):
    """Declared randomisation: an independent generator per (draw, decision)."""
    entropy = [int(SEED), int(draw), int(ordinal)]
    return np.random.default_rng(np.random.SeedSequence(entropy)).permutation(int(size))


def injected_ridge(day, draw, identity=False):
    """Permute the frozen ridge assignment; an abstained day is left untouched."""
    values = frozen_ridge(day)
    if values is None:
        return None, None, None
    symbols = sorted(values)
    permutation = list(range(len(symbols))) if identity else [int(p) for p in
                  draw_permutation(draw, decision_ordinal(day), len(symbols))]
    assigned = {s: values[symbols[p]] for s, p in zip(symbols, permutation)}
    ridge = dict(ready=True, group='financial',
                 models={s: dict(linear_forecast=str(D(assigned[s])), mean_return=0.0) for s in symbols})
    return ridge, assigned, permutation


def permuted(source, permutation):
    """Apply a position->source-index permutation to a symbol-keyed mapping."""
    symbols = sorted(source)
    return {s: str(D(source[symbols[p]])) for s, p in zip(symbols, permutation)}


def expected_ranks(day, permutation):
    return permuted(frozen_ranks(day), permutation)


def expected_injection(day, permutation):
    return permuted(frozen_ridge(day), permutation)


def fit_forecasts(rows, query, symbols, ridge_alpha=1):
    """Refit the frozen financial ridge recipe on an explicit completed-label sample."""
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    if len(rows) < REFIT_MIN_ROWS:
        raise ValueError('Refit sample has fewer than the frozen minimum completed labels')
    x = np.array([r['x'] for r in rows])
    query = np.array([query])
    scaler = StandardScaler().fit(x)
    out = {}
    for s in sorted(symbols):
        y = np.array([r['y'][s] for r in rows])
        mean = float(y.mean())
        linear = Ridge(alpha=ridge_alpha).fit(scaler.transform(x), y - mean)
        out[s] = mean + float(linear.predict(scaler.transform(query))[0])
    return out


def refit_rows(financial):
    rows = [r for r in financial['training_labels'] if r['end'] <= REFIT_LABEL_CUTOFF]
    if len(rows) < REFIT_MIN_ROWS:
        raise ValueError('Data-through-2022 sample has fewer than the frozen minimum completed labels')
    return rows


def refit_ridge(day):
    """Ridge fitted only on labels completed by the cutoff, queried at this decision."""
    fitted = _DATA['macro'][day]['financial']
    if not fitted['ready']:
        return None
    rows = refit_rows(fitted)
    symbols = sorted(fitted['models'])
    forecasts = fit_forecasts(rows, fitted['query'], symbols)
    return dict(ready=True, group='financial',
                refit=dict(cutoff=REFIT_LABEL_CUTOFF, rows=len(rows), last_label_end=max(r['end'] for r in rows)),
                models={s: dict(linear_forecast=str(D(str(v))), mean_return=0.0) for s, v in forecasts.items()})


def refit_parity(day):
    """Refit machinery check: the full frozen sample must reproduce the frozen forecasts.

    At the first 2023 decision the two samples coincide, because no label completed
    after 2022-12-31 can exist yet; that coincidence is reported rather than treated
    as a failure, and later decisions must differ.
    """
    fitted = _DATA['macro'][day]['financial']
    symbols = sorted(fitted['models'])
    full = fit_forecasts(fitted['training_labels'], fitted['query'], symbols)
    worst = max(abs(full[s] - float(fitted['models'][s]['linear_forecast'])) for s in symbols)
    subset = fit_forecasts(refit_rows(fitted), fitted['query'], symbols)
    differing = sum(1 for s in symbols
                    if abs(subset[s] - float(fitted['models'][s]['linear_forecast'])) > 1e-12)
    return dict(day=day, symbols=len(symbols), rows=len(fitted['training_labels']),
                subset_rows=len(refit_rows(fitted)), worst_absolute_difference=worst,
                full_sample_matches=bool(worst == 0.0),
                subset_sample_equals_full=len(refit_rows(fitted)) == len(fitted['training_labels']),
                symbols_differing_from_frozen=differing, subset_changes_the_forecast=bool(differing))


def run_recipe(day, recipe, ridge, top_n=None, arm=None):
    """One decision through the engine's own selection and sizing contracts."""
    from systematic_trading.backtest.stored import _target_schedule
    from systematic_trading.research.construction_controls import FinalWeightCapOverlay
    from systematic_trading.research.flow_concentration import ActivityConcentrationOverlay
    from systematic_trading.research.rolling_tracking import RollingModelOverlay
    from systematic_trading.research.strategy_catalog import defensive_cash_definition, instantiate_overlays
    from systematic_trading.research.usd_tracking import UsdRidgeOverlay
    data, current = _DATA, _day(day)
    if set(data['forecasts'][day]) != set(current['histories']):
        raise ValueError('Frozen XGBoost forecast universe differs from the decision universe')
    fitted = ridge if recipe['group'] else dict(ready=False)
    if fitted is None:
        fitted = data['macro'][day][recipe['group']]
    if fitted.get('last_label_end') and fitted['last_label_end'] > fitted['known_through']:
        raise ValueError('Future ridge label')
    overlays = instantiate_overlays(defensive_cash_definition())
    selector = SelectionBlend(overlays[0], recipe, data['forecasts'][day], fitted)
    if top_n is not None:
        if int(top_n) < 1 or int(top_n) > len(current['histories']):
            raise ValueError('Unregistered selection slot count')
        selector.top_n = int(top_n)
    overlays[0] = selector
    bound = []
    for overlay in overlays:
        if isinstance(overlay, RollingModelOverlay):
            overlay.model = current['model']
        elif isinstance(overlay, UsdRidgeOverlay):
            overlay.schedule = data['models']['usd']
        elif isinstance(overlay, ActivityConcentrationOverlay):
            overlay = AuditedActivity(overlay.spec, current['raw'])
        bound.append(overlay)
    targets = _target_schedule(instruments=data['instruments'], bars_by_symbol=current['histories'],
        trade_dates=[current['asof']], rebalance_frequency='daily', lookback_bars=63, max_weight=D('.45'),
        cash_reserve_weight=D('.02'), sleeve_name='candidate-pool-momentum-v1',
        target_overlays=bound)[current['asof']]
    targets = FinalWeightCapOverlay().apply(targets, None)
    slots = int(selector.top_n)
    held = {t.symbol for t in targets if t.target_weight > 0}
    if len(held) > slots or not held.issubset(selector.observation['selected']):
        raise ValueError('Downstream overlay changed the selection contract')
    if any(t.target_weight > D('.45') or t.target_weight < 0 for t in targets):
        raise ValueError('Cap/long-only violation')
    parent = {t['symbol']: D(t['target_weight']) for t in data['controls'][CONTROL][day]['targets']}
    if selector.abstained and {t.symbol: t.target_weight for t in targets} != parent:
        raise ValueError('Unavailable ridge did not revert exactly to the capped M1 control')
    original = {s for s, w in parent.items() if w > 0}
    row = dict(signal_session=day, known_through=data['days'][current['i'] - 1],
               targets=[t.model_dump(mode='json') for t in targets])
    diagnostics = dict(arm=arm, signal_session=day, slots=slots, selected=sorted(held),
        parent_selected=sorted(original), selected_before_downstream=selector.observation['selected'],
        eligible=selector.observation['eligible'], fallback=selector.observation['fallback'],
        abstained=bool(selector.abstained), changes=len(held - original),
        gross=str(sum((t.target_weight for t in targets), D(0))),
        rank_table=getattr(selector, 'rank_table', None))
    return row, diagnostics


def single_decision(day, arm):
    """FR25, its identity sentinel, the frozen baseline variant, or one sensitivity variant."""
    if arm == CANDIDATE:
        return run_recipe(day, RECIPE, None, top_n=6, arm=arm)
    if arm == SENTINEL:
        ridge, _, _ = injected_ridge(day, 0, identity=True)
        return run_recipe(day, RECIPE, ridge, top_n=6, arm=arm)
    if arm == BASELINE_ARM:
        return run_recipe(day, dict(blend=BLEND_KEY[25], group='financial'), None, top_n=6, arm=arm)
    variant = variant_of(arm)
    if variant is None:
        raise ValueError('Unregistered Part B arm: ' + arm)
    north, weight = variant
    return run_recipe(day, dict(blend=BLEND_KEY[weight], group='financial'), None, top_n=north, arm=arm)


def placebo_decision(day, draw):
    """One declared placebo draw at one decision, with the round-trip invariant checked.

    The engine re-ranks the injected values through its own ``_rank_metric``, so the
    realised ridge rank must equal the permuted frozen ridge rank exactly. That is
    the check that the placebo differs from FR25 in the assignment of ridge
    information and in nothing else.
    """
    ridge, assigned, permutation = injected_ridge(day, draw)
    row, diagnostics = run_recipe(day, RECIPE, ridge, top_n=6, arm=placebo_arm(draw))
    if assigned is None:
        return row, dict(diagnostics, injected=None, permutation=None, available=False,
                         rank_table=None, selected_before_downstream=None, eligible=None)
    engine = {s: str(D(diagnostics['rank_table'][s]['ridge'])) for s in assigned}
    injected = {s: str(D(v)) for s, v in assigned.items()}
    if engine != expected_ranks(day, permutation):
        raise ValueError('Placebo injection did not survive the engine ranking at ' + day)
    if injected != expected_injection(day, permutation):
        raise ValueError('Recorded injection is not the permuted frozen assignment at ' + day)
    return row, dict(diagnostics, injected=injected, permutation=permutation, available=True,
                     injected_sha256=digest(injected), realised_ranks=engine)


def placebo_day(day, draws=DRAWS):
    """All declared draws for one decision; the day's invariants are built once."""
    rows, evidence = {}, {}
    _, values, _ = _frozen(day)
    source = None if values is None else {s: str(D(v)) for s, v in values.items()}
    for draw in range(1, draws + 1):
        row, diagnostics = placebo_decision(day, draw)
        rows[placebo_arm(draw)] = row
        evidence[str(draw)] = {k: v for k, v in diagnostics.items() if k != 'rank_table'}
    return day, rows, evidence, source


def arm_days(arm):
    """Every evaluation decision for a single non-placebo arm."""
    return {day: single_decision(day, arm) for day in evaluation_days()}


def refit_days():
    """The data-through-2022 refit arm over its own replay window."""
    out = {}
    for day in sub_days():
        ridge = refit_ridge(day)
        if ridge is None:
            raise ValueError('The refit replay requires a ready financial model at ' + day)
        out[day] = run_recipe(day, RECIPE, ridge, top_n=6, arm=REFIT_ARM)
    return out


def digest(value):
    payload = json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf8')
    return hashlib.sha256(payload).hexdigest()


def freeze_decisions(root, rows, placebo_evidence):
    """Write every computed arm's decisions and diagnostics; controls stay as copied."""
    root = Path(root)
    (root / 'decisions').mkdir(exist_ok=True)
    for arm, day_rows in rows.items():
        write_json(root / 'decisions' / (arm + '.json'), {d: v[0] for d, v in sorted(day_rows.items())})
    write_json(root / 'placebo.json', dict(version='fr25-placebo-partb-v1', seed=SEED, draws=DRAWS,
        randomisation=_DATA['protocol']['placebo']['randomisation'], days=placebo_evidence))
    write_json(root / 'decision_diagnostics.json', {arm: {d: v[1] for d, v in sorted(day_rows.items())}
                                                    for arm, day_rows in rows.items()})
    write_json(root / 'decision_manifest.json',
               {f.relative_to(root).as_posix(): sha256(f) for f in sorted((root / 'decisions').glob('*.json'))})


def economics(job):
    """One frozen economic replay: bundle, quote tape, sessions and the reference engine."""
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
    freeze_usd_bundle(bundle, root, dict(id=arm, window=window, delay_sessions=delay, draws=DRAWS if draw_of(arm) else None,
        draw=draw_of(arm), selection=dict(blend=RECIPE['blend'], group=RECIPE['group'], slots=6,
        refit_cutoff=REFIT_LABEL_CUTOFF if arm == REFIT_ARM else None)), decisions, quotes, sessions, cost)
    output = root / 'python' / (name + '.json')
    if output.exists():
        raise FileExistsError('Preserve completed economics')
    write_json(output, run_usd_reference(bundle))
    write_json(output.with_suffix('.receipt.json'),
               dict(sha256=sha256(output), manifest_sha256=sha256(bundle / 'manifest.json')))
    return name


def economics_resumable(root, job):
    """Never overwrite a completed replay; verify it instead so a restart can resume."""
    name = job_name(job)
    output = Path(root) / 'python' / (name + '.json')
    if output.exists():
        bundle = Path(root) / 'bundles' / name
        receipt = read_json(output.with_suffix('.receipt.json'))
        if receipt != dict(sha256=sha256(output), manifest_sha256=sha256(bundle / 'manifest.json')):
            raise ValueError('Completed economics changed: ' + name)
        return name
    return economics(job)


def verify_decisions(root, parent=PARENT):
    """The bridges that make this study's arms trustworthy."""
    root, parent = Path(root), Path(parent)
    frozen = read_json(parent / 'decisions' / (CANDIDATE + '.json'))
    out = {}
    for arm in (CANDIDATE, SENTINEL, BASELINE_ARM):
        rows = read_json(root / 'decisions' / (arm + '.json'))
        shared = sorted(set(rows) & set(frozen))
        if not shared:
            raise ValueError('No shared decisions with the frozen candidate arm: ' + arm)
        mismatches = [d for d in shared if rows[d]['targets'] != frozen[d]['targets']]
        out[arm] = dict(shared_decisions=len(shared), mismatches=len(mismatches),
                        matches_frozen_parent=not mismatches, first=shared[0], last=shared[-1])
        if mismatches:
            raise ValueError(arm + ' does not reproduce the parent candidate decisions: ' + str(mismatches[:3]))
    return out


def verify_placebo(root):
    """Recompute the declared randomisation and every recorded injection."""
    root = Path(root)
    evidence = read_json(root / 'placebo.json')
    if evidence['seed'] != SEED or evidence['draws'] != DRAWS:
        raise ValueError('Placebo evidence does not match the frozen randomisation')
    checked, abstained, sizes = 0, 0, set()
    for day, day_rows in sorted(evidence['days'].items()):
        source = day_rows['source']
        if source is None:
            abstained += 1
            if any(v['permutation'] is not None for v in day_rows['draws'].values()):
                raise ValueError('Placebo injected on an abstained day: ' + day)
            continue
        symbols = sorted(source)
        sizes.add(len(symbols))
        ordinal = decision_ordinal(day)
        marginal = sorted(str(D(v)) for v in source.values())
        for draw, row in day_rows['draws'].items():
            permutation = [int(p) for p in draw_permutation(int(draw), ordinal, len(symbols))]
            if row['permutation'] != permutation:
                raise ValueError('Recorded permutation is not the declared draw: ' + day + ' draw ' + draw)
            injection = expected_injection(day, permutation)
            if digest(injection) != row['injected_sha256']:
                raise ValueError('Recorded injection hash differs: ' + day + ' draw ' + draw)
            if sorted(injection.values()) != marginal:
                raise ValueError('Permutation did not preserve the ridge marginal: ' + day + ' draw ' + draw)
            if row['injected'] != injection:
                raise ValueError('Recorded injection is not the permuted assignment: ' + day + ' draw ' + draw)
            if row['realised_ranks'] != expected_ranks(day, permutation):
                raise ValueError('Recorded realised rank differs: ' + day + ' draw ' + draw)
            checked += 1
    return dict(days=len(evidence['days']), abstained_days=abstained, draws_checked=checked,
                symbol_counts=sorted(sizes), seed=evidence['seed'], draws=evidence['draws'])
