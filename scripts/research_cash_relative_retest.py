"""Finite net replay of the frozen October 17 cash-relative experiment.

No acquisition, publication, monitoring, allocation or broker mutation. Run
prepare before evaluate. Original screens remain immutable historical evidence.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import json
import os
from pathlib import Path

for _variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_variable] = '1'

import numpy as np

from run_class_volatility_screen import read, write, digest, verify
from run_range_breakout import Replay
from systematic_trading.research.target_change_rebalance import adoption_schedule

REPO = Path(__file__).resolve().parents[1]
PARENT = REPO / 'var/research/cash-relative-momentum-20261017-v1'
EXPANSION = REPO / 'var/research/etf-expansion-20261014-v1'
OUT = REPO / 'research/cash-relative-net-20261031-v1'
WORK = REPO / 'var/research/cash-relative-net-20261031-v1'
START, END = '2021-01-04', '2026-10-12'
WINDOWS = {'calibration': (START, '2024-12-31'), 'later': ('2025-01-01', END),
           'full': (START, END),
           **{str(y): (f'{y}-01-01', min(END, f'{y}-12-31')) for y in range(2021, 2027)}}


def clean(value):
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [clean(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def gzwrite(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, 'wt', encoding='utf8') as stream:
        json.dump(clean(value), stream, allow_nan=False, separators=(',', ':'))


def gzread(path):
    with gzip.open(path, 'rt', encoding='utf8') as stream:
        return json.load(stream)


def source_files():
    # Hash the shared implementation without duplicating its source tree.
    return [Path(__file__), REPO/'scripts/run_range_breakout.py',
            REPO/'scripts/run_class_volatility_screen.py',
            *sorted((REPO/'src/systematic_trading/backtest').glob('*.py')),
            REPO/'src/systematic_trading/research/target_change_rebalance.py']


def metric(days, nav, start, end, *, initial=1_000_000, fees=None, turnover=None,
           exposure=None):
    days, nav = np.asarray(days), np.asarray(nav, float)
    ix = np.flatnonzero((days >= start) & (days <= end))
    if len(ix) < 2 or np.any(np.diff(ix) != 1):
        raise ValueError('Incomplete metric window')
    a, b = ix[0], ix[-1]
    base = nav[a-1] if a else initial
    path = np.r_[base, nav[a:b+1]]
    returns = path[1:]/path[:-1]-1
    if not np.isfinite(path).all() or np.any(path <= 0):
        raise ValueError('Invalid NAV')
    years = len(returns)/252
    cagr = (path[-1]/base)**(1/years)-1
    dd = -float(np.min(path/np.maximum.accumulate(path)-1))
    std = returns.std(ddof=1)
    return dict(start=str(days[a]), end=str(days[b]), sessions=len(ix),
        cumulative=float(path[-1]/base-1), cagr=float(cagr),
        sharpe=float(returns.mean()/std*np.sqrt(252)) if std > 1e-12 else 0.,
        max_drawdown=dd, calmar=float(cagr/dd) if dd > 1e-12 else None,
        volatility=float(std*np.sqrt(252)),
        fees_usd=float(np.asarray(fees)[a:b+1].sum()) if fees is not None else None,
        annual_turnover=float(np.asarray(turnover)[a:b+1].sum()/years) if turnover is not None else None,
        mean_exposure=float(np.asarray(exposure)[a:b+1].mean()) if exposure is not None else None)


def passes(candidate, control):
    return (candidate['sharpe'] > control['sharpe']
            and candidate['cagr'] >= control['cagr']-.005
            and candidate['max_drawdown'] <= control['max_drawdown']+.02)


def adoption_equal(actual, expected):
    """Decimal set iteration can change only the last summed-distance digit."""
    if len(actual) != len(expected):
        return False
    for left, right in zip(actual, expected, strict=True):
        if {k: v for k, v in left.items() if k != 'distance'} != {k: v for k, v in right.items() if k != 'distance'}:
            return False
        a, b = left['distance'], right['distance']
        if (a is None) != (b is None):
            return False
        if a is not None and abs(Decimal(a)-Decimal(b)) > Decimal('1e-24'):
            return False
    return True


def select(rows, window='calibration'):
    """Select only on the supplied training window; stable fixed-name tie break."""
    primary = {r['arm']: r['windows'][window] for r in rows
               if r['cost_bp'] == 5 and r['delay'] == 0}
    eligible = [key for key in primary if '_cash_relative_' in key
                and passes(primary[key], primary[key.replace('_cash_relative_', '_remove_bill_')])]
    selected = sorted(eligible, key=lambda k: (-primary[k]['sharpe'], k))[0] if eligible else 'class_cash_relative_risk-monthly'
    return dict(selected=selected, eligible=sorted(eligible),
                fallback=not bool(eligible), window=window,
                reason='Highest training net Sharpe among candidates passing matched removal-only return/drawdown guards; otherwise predeclared class/monthly diagnostic fallback, not acceptance.')


def prepare():
    if (OUT/'protocol.json').exists():
        raise FileExistsError('Protocol already frozen; preserve it')
    for filename in ('input_manifest.json', 'result_manifest.json', 'diagnostic_manifest.json'):
        verify(PARENT, filename)
    verify(EXPANSION, 'input_manifest.json')
    verify(EXPANSION, 'result_manifest.json')
    from systematic_trading.research.governed_inputs import GovernedInputs
    from systematic_trading.research.etf_expansion import load_published_pool
    from systematic_trading.research.momentum_signals import decision_sessions
    from systematic_trading.domain.market import Instrument
    pin, candidates, protocol = (read(PARENT/name) for name in ('price_pin.json', 'candidates.json', 'protocol.json'))
    reader = GovernedInputs(Path(pin['root']), pin['batch'])
    pool = load_published_pool(reader, candidates, through=END)
    if pool != read(PARENT/'pool.json'):
        raise ValueError('Published pool no longer reproduces retained original inputs')
    benchmark = load_published_pool(reader, [dict(symbol='URTH', requires_recorder=False)],
                                    through=END, start=pool['common_start'])
    if benchmark != read(EXPANSION/'benchmark.json'):
        # Provenance includes the reader's cumulative used-file inventory.
        old = read(EXPANSION/'benchmark.json')
        if benchmark['bars'] != old['bars'] or benchmark['calendar'] != old['calendar']:
            raise ValueError('Published benchmark prices changed')
    symbols, days = sorted(pool['bars']), pool['calendar']
    if len(symbols) != 50 or len(candidates) != 52:
        raise ValueError('Frozen universe changed')
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    arrays = {field: np.array([[float(pool['bars'][s][i][field]) for s in symbols]
                              for i in range(len(days))]) for field in ('open', 'high', 'low', 'close')}
    for field in ('open', 'high', 'low', 'close', 'volume'):
        arrays['raw_'+field] = np.array([[float(pool['raw_bars'][s][i][field]) for s in symbols]
                                       for i in range(len(days))])
    arrays.update(symbols=np.array(symbols), days=np.array(days),
        urth_open=np.array([float(r['open']) for r in benchmark['bars']['URTH']]),
        urth_close=np.array([float(r['close']) for r in benchmark['bars']['URTH']]))
    np.savez_compressed(WORK/'inputs.npz', **arrays)
    monthly = decision_sessions(days, START, 'monthly')
    locations = {day: i for i, day in enumerate(days)}
    schedules, checks = {}, {}
    for arm in protocol['arms']:
        tape = read(PARENT/'targets'/f'{arm}.json')
        weights = np.zeros((len(days), len(symbols)+1))
        for day, row in tape.items():
            i = locations[day]-1
            if days[i] != row['known_through']:
                raise ValueError('Signal availability mismatch')
            target = {t['symbol']: float(t['target_weight']) for t in row['targets']}
            weights[i, :-1] = [target[s] for s in symbols]
        for policy in protocol['policies']:
            key = arm+'-'+policy
            decisions, ledger = adoption_schedule(tape, monthly, policy)
            if not adoption_equal(ledger, read(PARENT/'adoptions'/f'{key}.json')):
                raise ValueError('Adoption reproduction failed: '+key)
            schedules[key+'_weights'] = weights
            schedules[key+'_indices'] = np.array([locations[d]-1 for d in decisions], int)
            checks[key] = len(decisions)
    sota = read(EXPANSION/'decisions/original14.json')
    weights = np.zeros((len(days), len(symbols)+1))
    for day, row in sota.items():
        i = locations[day]-1
        if row['known_through'] != days[i]:
            raise ValueError('FR25 target availability mismatch')
        target = {t['symbol']: float(t['target_weight']) for t in row['targets']}
        weights[i, :-1] = [target.get(s, 0.) for s in symbols]
    schedules['FR25_frozen_weights'] = weights
    schedules['FR25_frozen_indices'] = np.array([locations[d]-1 for d in sota], int)
    first = locations[START]-1
    for arm in ('cash', 'BIL_buyhold', 'URTH_buyhold', 'pool_buyhold'):
        weights = np.zeros((len(days), len(symbols)+1))
        if arm == 'BIL_buyhold':
            weights[first, symbols.index('BIL')] = .98
        elif arm == 'URTH_buyhold':
            weights[first, -1] = .98
        elif arm == 'pool_buyhold':
            weights[first, :-1] = [.98/49 if s != 'BIL' else 0 for s in symbols]
        schedules[arm+'_weights'] = weights
        schedules[arm+'_indices'] = np.array([first], int)
    np.savez_compressed(WORK/'schedules.npz', **schedules)
    recipe = dict(id='cash_relative_net_retest_v1', universeKey='frozen_cash_relative_50',
        universeMembers=[Instrument(symbol=s, name=s, asset_class='etf', exchange='NYSE',
                                   quote_currency='USD', country='US', sector='research').model_dump(mode='json')
                         for s in symbols+['URTH']])
    write(WORK/'recipe.json', recipe)
    # Snapshot only completed app-owned USD results; never use online prices.
    import requests
    response = requests.get('http://127.0.0.1:8000/api/v1/strategies', timeout=30)
    response.raise_for_status()
    catalog = response.json()
    monitors = []
    for item in catalog['strategies']:
        if item.get('lifecycle') != 'monitored':
            continue
        response = requests.get('http://127.0.0.1:8000/api/v1/strategies/'+item['strategy_id'], timeout=30)
        response.raise_for_status()
        doc = response.json()
        if doc.get('accounting_currency') != 'USD':
            raise ValueError('Monitored reference currency unavailable')
        monitors.append({k: doc.get(k) for k in ('strategy_id', 'name', 'nav_series', 'input_provenance',
            'strategy_definition', 'monitoring_generation', 'accounting_currency', 'artifact_path', 'warnings')})
        monitors[-1]['serving_version'] = doc.get('analytics', {}).get('version')
    gzwrite(WORK/'monitored.json.gz', monitors)
    p = dict(version='cash-relative-net-retest-v1', registered_at=datetime.now(timezone.utc).isoformat(),
        parent_protocol_sha256=digest(PARENT/'protocol.json'), price_pin=pin, input_files=reader.used,
        candidates=52, supported=50, exclusions=pool['exclusions'], windows=WINDOWS,
        arms=protocol['arms'], policies=protocol['policies'], frictions=[[c,d] for c in (5,10,20) for d in (0,1)],
        inherited=protocol['construction'], score=protocol['score'],
        scope='Close the previously withheld fixed-family experiment on its original complete supported pinned pool. No newly admitted ETF added to this historical retest; future pool enlargement is separate evidence.',
        execution='Shared app whole adjusted-unit USD engine; USD1m; size frozen target weights at the close immediately before execution; next-open fills plus0/1session delay. Delay retains the target and resizes at execution-prior-close,not original fixed quantities. 5/10/20bp on actual traded notional. All unfilled budgets remain zero-interest cash. No terminal liquidation. Logical adoption independent of fills.',
        selection='Use2021-2024only. Highest5bp/delay0netSharpe among8cash-relative arms beating matching removal-only Sharpe with CAGR loss<=0.5pp and drawdown worsening<=2pp. Deterministic name tie. If none,class/monthly diagnostic fallback,not accepted. No test-period selection.',
        uncertainty='Eight paired cash-relative-minus-removal contrasts; circular21-session paired blocks,2000draws,seed20261031; Bonferroni95% intervals across8contrasts. Already inspected development evidence,not formal discovery.',
        weakest='Lowest actual net ETF contribution divided by opening portfolio NAV under training-selected policy,5bp/delay0,excluding BIL/cash/URTH; show calibration and later. This explicit portfolio criterion avoids inventing standalone sleeve returns when capital changes. No stop/protection exists in this fixed recipe; show that absence.',
        monitored_references='All currently monitored app-owned USD NAV snapshots at their published5bp/no-extra-delay settings,rebased over exact common dates. Different model warmups/price vintages and inherited positions: descriptive context,not matched causal ablation. Only frozen common-input FR25 and removal-only controls carry matched replay comparisons.',
        limitations=['Current surviving cohort and dated taxonomy applied retrospectively; no historical membership or publication-vintage certification.',
            'Adjusted synthetic whole units are not broker raw-share execution. No spreads,impact,taxes or cash interest; no FX used.',
            'Training and later histories have been repeatedly inspected. The reserved prospective window was never activated; no prospective evidence is claimed.',
            'Frozen FR25 benchmark uses the original study common-window model refit,not the current app full-history fit.',
            'No absolute cost or IC proxy veto; no promotion,monitoring,funding or broker change.'],
        code={str(p.relative_to(REPO)).replace(chr(92),'/'): digest(p) for p in source_files()},
        artifacts={str(p.relative_to(REPO)).replace(chr(92),'/'): digest(p) for p in
                   (WORK/'inputs.npz', WORK/'schedules.npz', WORK/'recipe.json', WORK/'monitored.json.gz')})
    write(OUT/'input-validation.json', dict(reconstructed_pool_exact=True, frozen_adoptions=checks,
          adoption_comparison='Exact states,targets,anchors,reasons and decisions; Decimal summed-distance rounding tolerance1e-24',
          parent_inputs=digest(PARENT/'input_manifest.json'), parent_results=digest(PARENT/'result_manifest.json')))
    write(OUT/'protocol.json', p)
    print('Frozen protocol', digest(OUT/'protocol.json'), flush=True)


def validate():
    p = read(OUT/'protocol.json')
    for relative, expected in {**p['code'], **p['artifacts']}.items():
        if digest(REPO/relative) != expected:
            raise ValueError('Frozen study input/source changed: '+relative)
    return p


def init_worker():
    global ENGINE, ARRAYS, SCHEDULES
    with np.load(WORK/'inputs.npz', allow_pickle=False) as z:
        ARRAYS = dict(z)
    with np.load(WORK/'schedules.npz', allow_pickle=False) as z:
        SCHEDULES = dict(z)
    ENGINE = Replay(ARRAYS, read(WORK/'recipe.json'), START)


def job(payload):
    arm, cost, delay = payload
    key = f'{arm}_c{cost}d{delay}'
    compact, economic, count = ENGINE.run(SCHEDULES[arm+'_weights'], SCHEDULES[arm+'_indices'], cost, delay, detailed=True)
    stats = {name: metric(ENGINE.day_strings, compact['nav'], a, b, fees=compact['fees'],
             turnover=compact['turnover'], exposure=compact['exposure']) for name, (a,b) in WINDOWS.items()}
    np.savez_compressed(WORK/'paths'/f'{key}.npz', **compact)
    if cost == 5 and delay == 0:
        gzwrite(WORK/'detail'/f'{key}.json.gz', economic)
    return dict(key=key, arm=arm, cost_bp=cost, delay=delay, fills=count, windows=stats)


def evaluate(workers=4):
    p = validate()
    if (OUT/'results.json').exists():
        raise FileExistsError('Completed results already exist')
    for folder in ('paths', 'detail'):
        (WORK/folder).mkdir(exist_ok=True)
    arms = [a+'-'+t for a in p['arms'] for t in p['policies']]
    arms += ['FR25_frozen', 'cash', 'BIL_buyhold', 'URTH_buyhold', 'pool_buyhold']
    jobs = [(a,c,d) for a in arms for c,d in p['frictions']]
    rows = []
    with ProcessPoolExecutor(max_workers=workers, initializer=init_worker) as pool:
        for row in pool.map(job, jobs):
            rows.append(row)
            print(row['key'], 'later Sharpe', round(row['windows']['later']['sharpe'], 3), flush=True)
    validate()
    write(OUT/'results.json', clean(rows))
    write(OUT/'selection.json', select(rows))
    write(OUT/'result-manifest.json', {str(f.relative_to(REPO)).replace(chr(92),'/'): digest(f)
                                      for f in sorted((WORK/'paths').glob('*'))+sorted((WORK/'detail').glob('*'))})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'evaluate', 'verify'])
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if args.stage == 'prepare':
        prepare()
    elif args.stage == 'evaluate':
        evaluate(args.workers)
    else:
        validate()
        for relative, expected in read(OUT/'result-manifest.json').items():
            if digest(REPO/relative) != expected:
                raise ValueError('Result changed: '+relative)
        print('All study source/input/result hashes verified')
