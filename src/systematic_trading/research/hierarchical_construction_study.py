"""P4.16b — hierarchical construction: qualify asset classes, then pick inside them.

Proposed by the operator on 2026-10-11 after reviewing P4.16, which measured that
fixed sleeve budgets force `DBC` and `GLD` into all 70 evaluation decisions and that the
composition-budget arm paid 6% over the P4.15 cost ceiling for that representation. The
operator's objection: *if an asset class is in a downtrend — bonds into a rising-rate
environment — forcing an allocation to that bucket is wrong; pick the top two or three
classes, then the top two or three inside them.*

**This rule was proposed after seeing P4.16's outcome, so it is post-hoc on the
inspected sample and cannot be out-of-sample evidence.** It is registered as its own
frozen study for that reason, with its own evidence root, and it is screened by the
P4.15 turnover gate before any replay.

**Frozen rule, declared before any outcome.**

1. **Qualification.** A sleeve qualifies only if at least one of its instruments passes
   the same positive 126-session momentum gate the pooled control uses. A sleeve whose
   every instrument is in a downtrend is dropped outright — that is the operator's
   point, and it is a gate rather than a ranking so it needs no threshold.
2. **Class score.** A qualifying sleeve is scored by the mean of the members it will
   **actually hold**, as scored in the global cross-section rank table. The held members
   come from the parent overlay's own within-sleeve reranking (eligibility is the absolute
   126-session gate per member; among the members that pass, the top two of the
   *within-sleeve* rank table), and their numbers come from the *global* table — the only
   population in which a one-instrument sleeve can be scored at all, and the population
   that keeps every class on one comparable scale. This keeps one signal end to end
   instead of introducing a second class-index momentum with its own lookback. The class
   score is **not** the mean of the globally top-ranked members: that was v1's rule, and it
   could score names the rule did not hold.
3. **Choice.** The top K qualifying sleeves by class score receive equal budgets
   (`1/K` of the incoming gross each). K is 2 or 3, both declared as a family; fewer
   qualify means fewer are chosen, never a forced fill.
4. **Within.** Inside each chosen sleeve the top two eligible instruments are selected
   (one for a single-instrument sleeve) and the sleeve's budget is split across them in
   proportion to their incoming inverse-volatility weights. The absolute-momentum gate is
   decided for every member from its own price history, before any ranking or fallback and
   independently of sleeve size.
5. **No fill.** An unfilled slot leaves cash; a day with no qualifying class is
   entirely cash. Nothing is ever forced into the book.

Reused unchanged from the pooled control: the same scoring parameters, the same
downstream chain (XGBoost tilt, relative momentum, adaptive trend, audited raw activity,
USD ridge), the same final 45% cap, the same execution and the same 5bp cost.

**v2 repair, 2026-10-11 (peer review).** Two defects are repaired here, both inherited
from the shared overlay rather than from the rule above: the singleton gate hole (a
sleeve too small to form a rank table bypassed the positive-momentum gate) and the class
score's population (v1 averaged the globally top-ranked members, which could differ from
the members the within-sleeve reranking held). The rule, the arms, K, the slots, the
costs, the windows, the family and the assessment are unchanged; the parent for v2 is the
corrected P4.16 root ``sleeve-construction-20261010-v2``.
"""
from decimal import Decimal as D
from pathlib import Path

from systematic_trading.research.sleeve_construction_study import (CONTROLS, CONTROL_LABELS, COSTS, DELAYS,
    PARENT_CONTROLS, SLEEVES, WINDOWS)

VERSION = 'hierarchical-construction-v2'
PARENT = Path('var/research/sleeve-construction-20261010-v2')
DEFAULT_ROOT = Path('var/research/hierarchical-construction-20261011-v2')
SUPERSEDES = Path('var/research/hierarchical-construction-20261011-v1')
PARENT_INPUTS = ('bars.json', 'raw.json', 'urth.json', 'xgb_usd.json', 'macro.json', 'selection.json',
                 'forecasts.json')
PARENT_REPLAYS = ('POOL', 'CP', 'M1')
ARMS = ('HIER-K2', 'HIER-K3')
CLASS_CHOICES = {'HIER-K2': 2, 'HIER-K3': 3}
LABELS = {'HIER-K2': 'Top 2 qualifying classes, equal budgets, top 2 inside each',
          'HIER-K3': 'Top 3 qualifying classes, equal budgets, top 2 inside each'}
SLOTS_PER_CLASS = 2
COST_BPS = 5
DELAY = 0
COMPARISONS = (('HIER-K2', 'POOL'), ('HIER-K3', 'POOL'), ('HIER-K3', 'HIER-K2'),
               ('HIER-K2', 'CP'), ('HIER-K3', 'CP'))
BOOTSTRAP_BLOCKS = (3, 6, 12)
BOOTSTRAP_REPLICATIONS = 10000
SEED = 2026101104


def plan(arm):
    if arm not in ARMS:
        raise ValueError('Unregistered hierarchical arm: ' + str(arm))
    return dict(arm=arm, label=LABELS[arm], top_classes=CLASS_CHOICES[arm], slots_per_class=SLOTS_PER_CLASS,
                sleeves={sleeve: list(symbols) for sleeve, symbols in SLEEVES.items()},
                budget_basis=f'equal budgets over the top {CLASS_CHOICES[arm]} qualifying classes')


def class_score(values):
    """Mean of the member scores of the members the class will actually hold.

    ``values`` is the global cross-section score of each held member, one entry per
    member the parent overlay's within-sleeve reranking selected. The population is
    therefore the held set, not the globally top-ranked members (v1's rule).
    """
    members = list(values)
    if not members:
        raise ValueError('A class with no held member has no class score.')
    return sum(members) / len(members)


def hierarchical_overlay(arm):
    """The qualified-class selection stage, built on the existing group overlay."""
    from systematic_trading.research.hierarchical_selection import HierarchicalSelection
    selected = plan(arm)
    return HierarchicalSelection(top_classes=selected['top_classes'],
        sleeve_by_symbol={symbol: sleeve for sleeve, symbols in SLEEVES.items() for symbol in symbols},
        sleeve_budgets={sleeve: 0 for sleeve in SLEEVES}, top_n_per_sleeve=SLOTS_PER_CLASS,
        min_selected_per_sleeve=1, short_momentum_bars=21, medium_momentum_bars=63, long_momentum_bars=126,
        volume_bars=21, slow_volume_bars=126, trend_weight=D('0.75'), volume_weight=D('0.25'),
        require_positive_long_momentum=True, min_long_momentum=D('0'), fallback_to_top_ranked=False,
        name=f'hierarchical-construction-{arm.lower()}')


def run_arm(day, arm):
    from systematic_trading.research.sleeve_construction_study import run_arm as base_run
    return base_run(day, arm, overlay_factory=hierarchical_overlay)


def arm_days(arm):
    from systematic_trading.research.sleeve_construction_study import decision_days
    return {day: run_arm(day, arm) for day in decision_days()}


def jobs(arms=ARMS):
    return [(arm, cost, delay, window) for arm in arms for cost in COSTS for delay in DELAYS for window in WINDOWS]


def window_start(protocol, window):
    return protocol['start'] if window == 'full' else protocol['evaluation_start']


def economics(job):
    """One replay. Mirrors the P4.16 contract with this study's own construction record."""
    from systematic_trading.lean.contracts import sha256, write_json
    from systematic_trading.research import sleeve_construction_study as base
    from systematic_trading.research.expanded_economics import job_name
    from systematic_trading.research.momentum_calculation import quotes_for_data
    from systematic_trading.research.momentum_replay import freeze_usd_bundle, read_json, run_usd_reference
    data = base._DATA
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
    from systematic_trading.lean.contracts import sha256
    from systematic_trading.research.expanded_economics import job_name
    from systematic_trading.research.momentum_replay import read_json
    name = job_name(job)
    output = Path(root) / 'python' / (name + '.json')
    if output.exists():
        bundle = Path(root) / 'bundles' / name
        if read_json(output.with_suffix('.receipt.json')) != dict(
                sha256=sha256(output), manifest_sha256=sha256(bundle / 'manifest.json')):
            raise ValueError('Completed economics changed: ' + name)
        return name
    return economics(job)


def initialize(root):
    from systematic_trading.research.sleeve_construction_study import initialize as base_initialize
    base_initialize(root)


def prepare(root, runner, parent=PARENT):
    """Freeze a new root that pins the P4.16 evidence it reads decisions and inputs from."""
    import shutil
    from systematic_trading.lean.contracts import sha256, write_json
    from systematic_trading.research.momentum_replay import checked_files, read_json
    root, parent = Path(root).resolve(), Path(parent).resolve()
    if root.exists():
        raise FileExistsError('Preserve the frozen hierarchical-construction study')
    checked_files(parent, 'input_manifest.json')
    checked_files(parent, 'decision_manifest.json')
    pp = read_json(parent / 'protocol.json')
    p = dict(version=VERSION, client_date='2026-10-11',
             revision='v2 — peer-review repair of the shared overlay (singleton momentum gate and class-score '
                      'population). The rule, the arms, K, the slots, the costs, the windows, the family and the '
                      'assessment are unchanged from v1; the parent is the corrected P4.16 root '
                      '"sleeve-construction-20261010-v2" so the pooled control carries the same gate repair.',
             supersedes=dict(root=str(SUPERSEDES),
                             defects=['A sleeve too small to form a rank table returned its whole target list '
                                      'unchanged, so the single-instrument commodity and gold sleeves bypassed the '
                                      'positive 126-session momentum gate, and the top-ranked fallback could select '
                                      'a member that failed the gate.',
                                      'The class score averaged the globally top-ranked members, which could differ '
                                      'from the members the parent overlay\'s within-sleeve reranking held.'],
                             fix=['Absolute-momentum eligibility is now evaluated for every member from its own '
                                  'price history before any ranking or fallback, independently of sleeve size.',
                                  'The class score is now the mean of the global member scores of exactly the '
                                  'members the within-sleeve reranking holds.'],
                             evidence='var/research/hierarchical-construction-20261011-v1 remains the published v1 '
                                      'run; this root is the corrected run.'),
             question='Does qualifying asset classes and picking inside them beat the pooled top-six, and beat '
                      'fixed sleeve budgets that force representation?',
             origin='Operator proposal 2026-10-11, after P4.16 measured that fixed budgets force DBC and GLD into '
                    'all 70 evaluation decisions and that the composition-budget arm paid 6% over the P4.15 cost '
                    'ceiling for it.',
             post_hoc='This rule was proposed after P4.16 outcomes were known, so it is post-hoc on the inspected '
                      'sample and is not out-of-sample evidence.',
             parent=dict(root=str(parent), protocol_sha256=sha256(parent / 'protocol.json'),
                         input_manifest_sha256=sha256(parent / 'input_manifest.json'),
                         decision_manifest_sha256=sha256(parent / 'decision_manifest.json')),
             start=pp['start'], evaluation_start=pp['evaluation_start'], end=pp['end'],
             initial_cash_usd=pp['initial_cash_usd'], currency=pp['currency'], risk_free=pp['risk_free'],
             sleeves={k: list(v) for k, v in SLEEVES.items()},
             arms={arm: plan(arm) for arm in ARMS},
             controls={name: CONTROL_LABELS[name] for name in CONTROLS},
             comparisons=[dict(candidate=a, control=b) for a, b in COMPARISONS],
             family_size=len(COMPARISONS), cost_bps=list(COSTS), delayed_sessions=list(DELAYS),
             bootstrap_blocks=list(BOOTSTRAP_BLOCKS), bootstrap_replications=BOOTSTRAP_REPLICATIONS, seed=SEED,
             primary=dict(cost_bps=COST_BPS, delay=0, window='evaluation'),
             rule=dict(qualification='a sleeve qualifies only if at least one member passes the positive '
                                     '126-session momentum gate; a sleeve in a downtrend is dropped, not '
                                     'underweighted. The gate is an absolute per-member test, evaluated before any '
                                     'ranking or fallback and independently of sleeve size, so a one-instrument '
                                     'sleeve is gated exactly like a many-instrument sleeve and a member with no '
                                     '126-session history does not pass',
                       class_score='mean of the member scores of exactly the members the sleeve will hold; the held '
                                   'members come from the parent overlay\'s within-sleeve reranking and their '
                                   'numbers from the global cross-section rank table, the only population in which '
                                   'a one-instrument sleeve is scoreable',
                       member_scores='global cross-section rank table over all incoming targets; a class is never '
                                     'scored from a member it does not hold',
                       choice='top K qualifying sleeves by class score, equal budgets of 1/K of incoming gross',
                       within='top two eligible instruments per chosen sleeve, split by incoming inverse-volatility '
                              'weight',
                       no_fill='an unfilled slot leaves cash; no qualifying class leaves the day entirely in cash',
                       k_family='K=2 and K=3 are both declared; neither is selected on outcomes'),
             downstream='Identical to the pooled control and to P4.16: the same scoring parameters, XGBoost tilt, '
                        'relative momentum, adaptive trend, audited raw activity, USD ridge and final 45% cap.',
             gate='Every arm is screened by the P4.15 turnover gate before any replay.',
             assessment='Shared-report comparison against the construction-matched pooled control with '
                         'family-adjusted uncertainty over the registered contrasts at 3/6/12-month blocks.',
             promotion_eligible=False,
             limitations=[
                 'Post-hoc: proposed after P4.16 outcomes were known. Nothing here is out-of-sample evidence.',
                 'The 2021 onward evaluation window was already inspected in the parent studies.',
                 'Sleeve membership is the plan\'s own four-way split, not an observed taxonomy.',
                 'The class score is member-derived, not a class index; a class-index momentum variant with its own '
                 'lookback is a different, untested rule. The class score averages the members the rule holds, as '
                 'scored in the global cross-section table, so it is a class-ranking statistic rather than a promise '
                 'about portfolio weights.',
                 'K=2 and K=3 are both reported; choosing between them on these outcomes would be tuning on the '
                 'inspected sample.',
                 'The rule can only reduce representation relative to fixed budgets, so it trades forced exposure '
                 'for concentration; the comparison measures that trade rather than assuming it is favourable.'],
             budget=dict(arms=len(ARMS), replays=len(ARMS) * len(COSTS) * len(DELAYS) * len(WINDOWS)))
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
    for name in PARENT_REPLAYS:
        shutil.copyfile(parent / 'decisions' / (name + '.json'), root / 'decisions' / (name + '.json'))
    write_json(root / 'protocol.json', p)
    write_json(root / 'data_receipt.json', dict(parent=str(parent),
        parent_hashes={name: sha256(parent / name) for name in PARENT_INPUTS},
        parent_protocol_sha256=sha256(parent / 'protocol.json'),
        parent_control_hashes={name: sha256(parent / 'controls' / (name + '.json')) for name in PARENT_CONTROLS},
        parent_replay_hashes={name: sha256(parent / 'decisions' / (name + '.json')) for name in PARENT_REPLAYS},
        price_batch=read_json(parent / 'data_receipt.json')['price_batch'],
        economic_pin=read_json(parent / 'data_receipt.json')['economic_pin'],
        image=read_json(parent / 'data_receipt.json')['image']))
    write_json(root / 'input_manifest.json',
               {f.relative_to(root).as_posix(): sha256(f) for f in root.rglob('*')
                if f.is_file() and f != root / 'input_manifest.json'})
    return dict(root=str(root), protocol_sha256=sha256(root / 'protocol.json'), budget=p['budget'])
