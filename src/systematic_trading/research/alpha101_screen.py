"""P4.17 — Alpha101 restricted time-series subset: the per-alpha screen.

Registered 2026-10-11 in ``docs/signal-decay-and-alpha-plan.md``. The acceptance for the
item puts the cost test **before** any portfolio work: every alpha must have a measured
turnover and breakeven ratio, and the report must state which alphas are rejected and why.
This module is that screen. It produces no economics, no replay and no promotion.

**Frozen design, declared before any outcome.**

* **Family.** The sixteen registered pure time-series alphas — 6, 7, 9, 12, 21, 23, 24, 26,
  35, 43, 46, 49, 51, 53, 54, 101 — implemented verbatim in
  :mod:`systematic_trading.research.alpha101`. The family is fixed at sixteen: no alpha is
  dropped after seeing its result, and none is added.
* **Mapping.** Each decision day, the alpha's values across the pinned fourteen-instrument
  universe rank the instruments; the top six take the engine's own incoming
  inverse-volatility weights (the same base book the pooled control starts from,
  ``lookback_bars=63``, ``max_weight=0.45``, ``cash_reserve_weight=0.02``), renormalised to
  the incoming gross; every other instrument is cash. This is the pooled control's
  construction with the alpha replacing its selection score, so the screen measures the
  alpha's own turnover rather than the strategy's.
* **Point-in-time.** An alpha's value on a decision day uses audited bars up to the prior
  session only. Forward returns for scoring start at that same session.
* **Cost test.** The P4.15 gate: 40bp annual ceiling at the frozen 5bp, with the published
  10% tolerance, and a 3x IC margin over the breakeven IC at the published dispersion.
* **Information.** Rank IC of the alpha's cross-section against forward returns at 1, 5, 10,
  21 and 63 sessions, with a circular block bootstrap interval on the 21-session series.
  At least six instruments must be available, matching the mapping's slot count.

Nothing here is a strategy result. An alpha that fails the gate is closed for this
programme; an alpha that passes is a candidate for the modelling stage, not a promotion.
"""
from decimal import Decimal as D
from pathlib import Path
import re

import numpy as np

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json
from systematic_trading.research import alpha101 as lib
from systematic_trading.research.turnover_gate import implied_turnover, screen

STUDY = 'alpha101-screen-v1'
PARENT = Path('var/research/sleeve-construction-20261010-v1')
DEFAULT_ROOT = Path('var/research/alpha101-screen-20261011-v1')
PAPER = Path('research_tmp/101_formulaic_alphas.pdf')
PAPER_SHA256 = '1f9c21afe32dcb3ee77b31548acdaea00451fbfa1c0ee10c907867bcc736fce9'
GATE_ROOT = Path('var/research/turnover-gate-20261010-v1')

TOP_N = 6
LOOKBACK_BARS = 63
MAX_WEIGHT = D('0.45')
CASH_RESERVE = D('0.02')
HORIZONS = (1, 5, 10, 21, 63)
PRIMARY_HORIZON = 21
MIN_INSTRUMENTS = 6
BLOCK = 6
REPLICATIONS = 2000
SEED = 2026101105

_DATA = None


def initialize(root=PARENT):
    """Load the pinned parent evidence (this study adds no new input)."""
    from systematic_trading.research import sleeve_construction_study as parent
    parent.initialize(Path(root))
    global _DATA
    data = parent._DATA
    closes = {symbol: {row['trade_date']: float(row['close']) for row in rows}
              for symbol, rows in data['bars'].items()}
    _DATA = dict(parent=parent, root=Path(root), bars=data['bars'], days=data['days'],
                 selection=data['selection'], instruments=data['instruments'],
                 typed=data['typed'], closes=closes, day_cache={})
    return _DATA


def decision_days():
    return sorted(_DATA['selection'])


def known_through(day):
    """The last session whose data a decision on ``day`` may use."""
    index = _DATA['days'].index(day)
    if index == 0:
        raise ValueError('No prior session for ' + day)
    return _DATA['days'][index - 1]


def price_bars_for(day):
    """Audited typed bars up to the prior session, as the engine's sizing consumes them."""
    end = known_through(day)
    index = _DATA['days'].index(end) + 1
    return {symbol: rows[max(0, index - 300):index] for symbol, rows in _DATA['typed'].items()}


def histories_for(day):
    """Point-in-time histories: audited bars up to the prior session, per instrument."""
    if day in _DATA['day_cache']:
        return _DATA['day_cache'][day]
    end = known_through(day)
    index = _DATA['days'].index(end) + 1
    out = {}
    for symbol, rows in _DATA['bars'].items():
        window = rows[max(0, index - 300):index]
        if len(window) < 2:
            continue
        out[symbol] = lib.History(
            symbol=symbol, date=end,
            open=np.array([float(r['open']) for r in window]),
            high=np.array([float(r['high']) for r in window]),
            low=np.array([float(r['low']) for r in window]),
            close=np.array([float(r['close']) for r in window]),
            volume=np.array([float(r['volume']) for r in window]))
    _DATA['day_cache'] = {day: out}
    return out


def base_book(day):
    """The engine's own incoming inverse-volatility book, before selection.

    Mirrors ``backtest.stored._target_schedule``'s sizing exactly: 63-session realized
    volatility per instrument, the risk-parity sleeve at a 45% cap, scaled by the
    investable weight ``1 - cash_reserve``.
    """
    cache = _DATA.setdefault('book_cache', {})
    if day in cache:
        return cache[day]
    from systematic_trading.data.analytics import realized_volatility_from_bars
    from systematic_trading.portfolio.beta import BetaInstrumentState, RiskParityBetaSleeve
    histories = price_bars_for(day)
    states = []
    for symbol, instrument in _DATA['instruments'].items():
        window = histories.get(symbol)
        if window is None or len(window) < LOOKBACK_BARS + 1:
            continue
        volatility = realized_volatility_from_bars(window[-LOOKBACK_BARS:])
        if volatility <= 0:
            continue
        states.append(BetaInstrumentState(instrument=instrument, realized_volatility=volatility))
    sleeve = RiskParityBetaSleeve(name='alpha101-screen-v1', max_weight=MAX_WEIGHT)
    investable = D('1') - CASH_RESERVE
    book = {target.symbol: float(target.target_weight * investable) for target in sleeve.generate_targets(states)}
    cache[day] = book
    return book


def alpha_values(alpha, day):
    """The alpha's available cross-section, point-in-time."""
    return lib.values_for_day(alpha, histories_for(day))


def mapping(alpha, days=None):
    """The alpha's declared signal-to-position mapping, and why decisions were skipped.

    A decision is mapped only when the cross-section contains at least two distinct values:
    a constant cross-section cannot rank anything, so it forms no mapping. That keeps a
    degenerate alpha — one whose formula reduces to a constant — from producing a
    mechanically ordered book and a spurious cost profile.
    """
    days = decision_days() if days is None else list(days)
    weights, skipped = {}, {}
    for day in days:
        values = alpha_values(alpha, day)
        base = base_book(day)
        eligible = {symbol: base[symbol] for symbol in values if base.get(symbol, 0.0) > 0.0}
        if len(eligible) < TOP_N:
            skipped[day] = f'only {len(eligible)} instruments with a value and an incoming weight'
            continue
        if len({round(values[symbol], 12) for symbol in eligible}) < 2:
            skipped[day] = 'the cross-section is constant, so the alpha cannot rank'
            continue
        ranked = sorted(eligible, key=lambda symbol: (-values[symbol], symbol))[:TOP_N]
        chosen_total = sum(eligible[symbol] for symbol in ranked)
        gross = sum(base.values())
        if chosen_total <= 0 or gross <= 0:
            skipped[day] = 'incoming weights do not sum to a positive gross'
            continue
        weights[day] = {symbol: eligible[symbol] / chosen_total * gross for symbol in ranked}
    return weights, skipped


def forward_returns(day, horizon):
    """Forward total return per instrument from the decision's known session."""
    end = known_through(day)
    index = _DATA['days'].index(end)
    if index + horizon >= len(_DATA['days']):
        return {}
    target = _DATA['days'][index + horizon]
    out = {}
    for symbol, series in _DATA['closes'].items():
        start, finish = series.get(end), series.get(target)
        if start and finish and start > 0:
            out[symbol] = finish / start - 1.0
    return out


def rank_ic(values, returns):
    """Spearman rank correlation of the alpha's cross-section against forward returns."""
    symbols = sorted(set(values) & set(returns))
    if len(symbols) < MIN_INSTRUMENTS:
        return None
    left = np.array([values[s] for s in symbols])
    right = np.array([returns[s] for s in symbols])
    if np.std(left) == 0 or np.std(right) == 0:
        return None
    ranked_left = np.argsort(np.argsort(left)).astype(float)
    ranked_right = np.argsort(np.argsort(right)).astype(float)
    return float(np.corrcoef(ranked_left, ranked_right)[0, 1])


def ic_series(alpha, horizon, days=None):
    days = decision_days() if days is None else list(days)
    out = {}
    for day in days:
        values = alpha_values(alpha, day)
        if not values:
            continue
        value = rank_ic(values, forward_returns(day, horizon))
        if value is not None:
            out[day] = value
    return out


def block_interval(series, *, block=BLOCK, replications=REPLICATIONS, seed=SEED):
    """Circular block bootstrap interval for the mean of a decision-level series."""
    values = np.array(list(series), dtype=float)
    size = len(values)
    if size < block + 1:
        return None
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, size, size=(replications, max(1, size // block)))
    offsets = np.arange(block)
    means = np.empty(replications)
    for index in range(replications):
        picks = (starts[index][:, None] + offsets[None, :]).ravel() % size
        means[index] = float(np.mean(values[picks[:size]]))
    return dict(mean=float(np.mean(values)), low=float(np.percentile(means, 2.5)),
                high=float(np.percentile(means, 97.5)), block=block, replications=replications,
                seed=seed, observations=size)


def sigma_from_calibration():
    """The published forward-return dispersion, read from the frozen P4.15 calibration."""
    calibration = read_json(GATE_ROOT / 'calibration.json')
    record = calibration.get('dispersion') or calibration
    for key in ('sigma', 'dispersion', 'daily_sigma'):
        value = record.get(key) if isinstance(record, dict) else None
        if isinstance(value, (int, float)):
            return float(value), calibration
    raise ValueError('No dispersion recorded in the frozen calibration')


def extract_formulas(path=PAPER):
    """The registered alphas' formulas, read from the pinned paper copy."""
    from pypdf import PdfReader
    text = '\n'.join(page.extract_text() or '' for page in PdfReader(str(path)).pages)
    text = text.replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"')
    lines = [line.rstrip() for line in text.split('\n')]
    found = {}
    for index, line in enumerate(lines):
        match = re.match(r'^Alpha#(\d{1,3})\s*[:.]?\s*(.*)$', line.strip())
        if not match:
            continue
        number = match.group(1)
        if number not in lib.REGISTERED or number in found:
            continue
        body = [match.group(2).strip()]
        for extra in lines[index + 1:index + 4]:
            if not extra.strip() or re.match(r'^Alpha#\d', extra.strip()):
                break
            body.append(extra.strip())
        found[number] = ' '.join(part for part in body if part)
    missing = [name for name in lib.REGISTERED if name not in found]
    if missing:
        raise ValueError('Formulas not found in the paper copy: ' + ', '.join(missing))
    return found


def clean_formula(text):
    """Strip page furniture and normalise whitespace for the transcription check."""
    text = re.sub(r'\s+\d{1,2}\s*$', '', text.strip())
    text = re.sub(r'\s*A\.1\..*$', '', text)
    return ' '.join(text.split())


def protocol():
    return dict(
        study=STUDY, version=STUDY + '-v1', parent=str(PARENT),
        paper=dict(path=str(PAPER), sha256=PAPER_SHA256),
        registered=list(lib.REGISTERED), family_size=len(lib.REGISTERED),
        family_declared='all sixteen registered alphas, no additions and no removals after outcomes',
        mapping=dict(
            top_n=TOP_N, lookback_bars=LOOKBACK_BARS, max_weight=str(MAX_WEIGHT),
            cash_reserve=str(CASH_RESERVE), tie_break='descending alpha value, then symbol name',
            minimum_distinct_values=2,
            description='top six by alpha value take the engine\'s incoming inverse-volatility weights, '
                        'renormalised to the incoming gross; everything else is cash. A decision whose '
                        'cross-section is constant is skipped rather than mapped, because a constant '
                        'cannot rank.',
            no_ic_rule='a candidate with no measurable rank IC is reported insufficient and is never '
                       'judged against the programme reference IC'),
        information=dict(horizons=list(HORIZONS), primary_horizon=PRIMARY_HORIZON,
                         min_instruments=MIN_INSTRUMENTS, blocks=BLOCK, replications=REPLICATIONS,
                         seed=SEED,
                         statistic='Spearman rank correlation of the cross-section against forward returns'),
        cost_test=dict(source='P4.15 turnover gate', ceiling_bps=40.0, tolerance=0.10, min_ic_margin=3.0,
                       cost_bps=5.0),
        declares=['no portfolio result is produced here',
                  'an alpha passing the gate is a modelling candidate, not a promotion',
                  'the published adv definition is dollar volume while volume is shares, so the alphas '
                  'that compare them are reported rather than repaired'])


def prepare(root=DEFAULT_ROOT):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / 'protocol.json', protocol())
    formulas = extract_formulas()
    declared = {name: lib.FORMULAS[name] for name in lib.REGISTERED}
    mismatched = [name for name in lib.REGISTERED
                  if clean_formula(formulas[name]) != clean_formula(declared[name])]
    write_json(root / 'formulas.json', dict(
        paper=str(PAPER), paper_sha256=sha256(PAPER), extracted=formulas, declared=declared,
        mismatched=mismatched))
    if mismatched:
        raise ValueError('Transcribed formulas do not match the paper: ' + ', '.join(mismatched))
    from systematic_trading.research.sleeve_construction_study import PARENT_INPUTS
    manifest = {name: sha256(PARENT / name) for name in PARENT_INPUTS if (PARENT / name).exists()}
    write_json(root / 'input_manifest.json', dict(
        parent=str(PARENT), files=manifest, parent_report_sha256=sha256(PARENT / 'report.json'),
        note='P4.17 adds no new data source: every input is the pinned P4.16 evidence root'))
    write_json(root / 'data_receipt.json', dict(
        parent_report_sha256=sha256(PARENT / 'report.json'),
        parent_hashes={name: digest for name, digest in manifest.items()},
        paper_sha256=sha256(PAPER)))
    return dict(root=str(root), protocol_sha256=sha256(root / 'protocol.json'),
                family=len(lib.REGISTERED), mismatched=mismatched)


def screen_alpha(alpha, sigma):
    """Turnover, cost, breakeven, information and the gate verdict for one alpha."""
    weights, skipped = mapping(alpha)
    days = decision_days()
    implied = implied_turnover(weights) if len(weights) >= 2 else None
    ics = {str(horizon): ic_series(alpha, horizon) for horizon in HORIZONS}
    primary = ics[str(PRIMARY_HORIZON)]
    interval = block_interval(primary.values()) if primary else None
    values = alpha_values(alpha, days[-1])
    verdict = None
    if implied is not None:
        verdict = screen(implied['annual_turnover'], sigma=sigma,
                         candidate_ic=float(np.mean(list(primary.values()))) if primary else None)
        if not primary:
            # The gate judges a candidate that declares no IC of its own against the programme
            # reference IC. That is right for a stated candidate and wrong for one whose IC
            # cannot be measured at all, so the screen never passes it.
            verdict = dict(verdict, status='insufficient', margin_test=None,
                           reasons=['no measurable rank IC: the cross-section carries no information, so '
                                    'the candidate is not judged against the programme reference IC'])
    return dict(
        alpha=alpha, formula=lib.FORMULAS[alpha],
        coverage=dict(decisions=len(days), mapped=len(weights), skipped=len(skipped),
                      share=len(weights) / len(days), first_skip=(sorted(skipped)[0] if skipped else None),
                      skip_reason=(skipped[sorted(skipped)[0]] if skipped else None)),
        dispersion=dict(last_day_values=len(values),
                        distinct=len({round(value, 10) for value in values.values()}),
                        constant=(len({round(value, 10) for value in values.values()}) == 1 if values else None)),
        turnover=None if implied is None else dict(annual=implied['annual_turnover'],
                                                   decisions=implied['decisions'],
                                                   mean_per_decision=implied['mean_traded_per_decision']),
        gate=verdict,
        information={horizon: dict(observations=len(ics[str(horizon)]),
                                   mean=(float(np.mean(list(ics[str(horizon)].values())))
                                         if ics[str(horizon)] else None))
                     for horizon in HORIZONS},
        primary_interval=interval,
        ic_series=primary)


def run_screen(root=DEFAULT_ROOT):
    root = Path(root)
    sigma, calibration = sigma_from_calibration()
    initialize()
    rows = [screen_alpha(alpha, sigma) for alpha in lib.REGISTERED]
    payload = dict(study=STUDY, sigma=sigma, calibration_source=str(GATE_ROOT / 'calibration.json'),
                   decisions=len(decision_days()), evaluation_start=_DATA['selection'][decision_days()[0]].get(
                       'known_through'),
                   rows=rows)
    write_json(root / 'screen.json', payload)
    return dict(screen_sha256=sha256(root / 'screen.json'), passed=sum(
        1 for row in rows if row['gate'] and row['gate']['status'] == 'pass'),
        rejected=sum(1 for row in rows if row['gate'] and row['gate']['status'] == 'reject'),
        insufficient=sum(1 for row in rows if not row['gate'] or row['gate']['status'] == 'insufficient'))


def verify(root=DEFAULT_ROOT):
    """Re-run the screen and compare with the frozen artifact, and re-check the inputs."""
    root = Path(root)
    checks = dict(parent_unchanged=True, paper_unchanged=sha256(PAPER) == PAPER_SHA256)
    manifest = read_json(root / 'input_manifest.json')
    for name, digest in manifest['files'].items():
        if sha256(PARENT / name) != digest:
            checks['parent_unchanged'] = False
    formulas = read_json(root / 'formulas.json')
    checks['formulas_match_paper'] = not formulas['mismatched']
    before = read_json(root / 'screen.json')
    run_screen(root)
    after = read_json(root / 'screen.json')
    checks['screen_reproduced'] = before == after
    return checks
