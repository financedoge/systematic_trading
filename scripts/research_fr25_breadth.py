"""Finite FR25 breadth study. Search only the calibration slice before later replay."""
from concurrent.futures import ProcessPoolExecutor
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import argparse
import hashlib
import shutil

import numpy as np

import research_expanded_fr25_net as parent
from research_cash_relative_retest import digest, gzread, gzwrite, metric, read, write
from run_range_breakout import Replay
from systematic_trading.backtest.stored import _target_schedule
from systematic_trading.research import instruments_for_definition, instantiate_overlays
from systematic_trading.research.rolling_tracking import select_rolling_model
from systematic_trading.research.target_change_rebalance import adoption_schedule

REPO = parent.REPO
OUT = REPO / 'research/fr25-breadth-20261103-v1'
WORK = REPO / 'var/research/fr25-breadth-20261103-v1'
CUTOFF = '2024-12-31'
SIZE = 52


def required_count(numerator, denominator, pool_size):
    if not (0 < numerator <= denominator and pool_size > 0):
        raise ValueError('Breadth requires a positive pool and fraction in (0,1]')
    return (numerator * pool_size + denominator - 1) // denominator


def prepare():
    if (OUT / 'protocol.json').exists():
        raise FileExistsError('Protocol already frozen')
    p = parent.validate()
    parent.check_manifest(parent.OUT / 'model-manifest.json')
    parent.check_manifest(parent.OUT / 'signal-manifest.json')
    assert p['supported_count'] == SIZE and p['windows']['calibration'][1] == CUTOFF
    verification = read(parent.OUT / 'input-verification.json')
    root = Path(verification['price_pin']['root'])
    for relative, expected in verification['verified_files'].items():
        if digest(root / relative) != expected:
            raise ValueError('Changed publication file ' + relative)
    protocol = dict(study=OUT.name, frozen_at=datetime.now(timezone.utc).isoformat(),
        parent_protocol_sha256=digest(parent.OUT / 'protocol.json'), price_pin=p['price_pin'],
        parent=parent.OUT.relative_to(REPO).as_posix(), parent_work=parent.WORK.relative_to(REPO).as_posix(),
        code_sha256=digest(Path(__file__)), free_disk_bytes=shutil.disk_usage(REPO).free,
        windows=p['windows'], frictions=p['frictions'], supported=SIZE, limitations=p['limitations'],
        hypothesis='Scaling the four-qualifier threshold by pool size restores defensive behavior and improves net portfolio outcomes. This follows inspection of both historical eras.',
        formula='Q is the count of admitted ETFs with positive 126-session momentum BEFORE selection. Fall back when Q < ceil(X * U). Otherwise select up to M ranked qualifiers. Preserve all downstream FR25 sizing, final cap and the original IEF/TLT/GLD defensive branch. Equality passes. BIL counts identically to the expanded parent. URTH is a benchmark.',
        denominator='Primary U is the frozen supported cohort (14 or 52). Exact X=4/14 gives N=4 or 15. Sensitivity uses contemporaneously admitted count before momentum. Effective N may exceed M.',
        selection='Monthly, 5 bp, next open, every integer M,N from 1 to 52 inclusive, N expressed equivalently as X=N/52. Maximize 2021-2024 annualized net Sharpe. Round Sharpe to 12 decimals for ties, then prefer N closest to scaled 15, M closest to incumbent 6, smaller M then smaller N. Identical IS weight paths may share one exact app replay. Report tie count, near-optima, yearly prefix winners, return and drawdown guards. No return floor or cost veto.',
        evaluation='Seal selection and training grid hashes before computing later targets for that choice. Carry continuous cash/positions into January 2025. Report Jan 2025-Oct 2026 chronological OOS, previously inspected development data. No later rerank.',
        cases='Selected pair, 6/15 proportional, 6/4 legacy, admitted-denominator 4/14, separate width/breadth ablations. Monthly primary plus monthly-anchored L1>0.40 dynamic control for selected and 6/15. All selected/control scenarios at 5/10/20 bp and 0/1 extra session. Include parent original14, M1, simple momentum, cash/BIL/URTH/risky-pool buyhold benchmarks.',
        uncertainty='Paired circular 21-session block bootstrap 4000 draws for selected-minus-legacy and proportional-minus-legacy by era, conditional on selection. These intervals do not correct the 2704-trial search. Display IS surface and chronological prefix selection stability.',
        weakest='Lowest net dollar contribution / beginning portfolio NAV among risky ETFs, excluding BIL/URTH, 5 bp next-open selected monthly book in each era. Inspect prices, raw volume, eligibility, fallback, targets, holdings, fills and FIFO outcomes.',
        next='Stop for discussion after this item. Finite research only.')
    write(OUT/'protocol.json', protocol)
    write(WORK/'protocol.json', protocol)
    print('Protocol frozen', digest(OUT/'protocol.json'), flush=True)


def validate():
    p = read(OUT/'protocol.json')
    if p['code_sha256'] != digest(Path(__file__)) or p['parent_protocol_sha256'] != digest(parent.OUT/'protocol.json'):
        raise ValueError('Study code or parent protocol changed')
    return p


def monthly_indices(days):
    return np.array([i-1 for i in range(1,len(days)) if days[i] >= parent.START
                     and (days[i] == parent.START or days[i][:7] != days[i-1][:7])], dtype=int)


def input_arrays(train=False):
    with np.load(parent.WORK/'inputs.npz') as values:
        a = dict(values)
    if train:
        end = np.searchsorted(a['days'], CUTOFF, side='right')
        a = {k:v[:end] if k!='symbols' else v for k,v in a.items()}
    return a


def init_targets():
    global TAPE, SYMBOLS
    parent.target_init('expanded')
    TAPE = gzread(parent.WORK/'targets/expanded.json.gz')
    SYMBOLS = sorted(parent.TYPED)


def weights(day, width, minimum):
    i = parent.DAYS.index(day)
    as_of = date.fromisoformat(day)
    history = {s:bars[max(0,i-500):i] for s,bars in parent.TYPED.items()}
    overlays = instantiate_overlays(parent.DEFINITION)
    selector = overlays[0]
    selector.top_n = width
    selector.min_selected = minimum
    selector.admitted_symbols = parent.ADMISSION[day]
    selector.schedule = parent.MODEL['financial']
    selector.rolling_schedule = parent.MODEL['rolling']
    selector.allow_monthly_fallback = True
    for spec, overlay in zip(parent.DEFINITION.overlays,overlays,strict=True):
        if spec.kind == 'rolling_model':
            overlay.model = select_rolling_model(parent.MODEL['rolling'], history, as_of)
        elif spec.kind == 'usd_ridge':
            overlay.schedule = parent.MODEL['usd']
            overlay.allow_monthly_fallback = True
        elif spec.kind == 'audited_etf_activity':
            overlay.raw = {s:bars[max(0,i-500):i] for s,bars in parent.RAW.items()}
    targets = _target_schedule(instruments=instruments_for_definition(parent.DEFINITION),
        bars_by_symbol=history,trade_dates=[as_of],rebalance_frequency='daily',lookback_bars=63,
        max_weight=Decimal('.45'),cash_reserve_weight=Decimal('.02'),
        sleeve_name=parent.DEFINITION.sleeve_name,target_overlays=overlays)[as_of]
    qualified = TAPE[day]['selection']['eligible']
    if list(selector.observation['eligible']) != qualified or bool(selector.cash_budget_active) != (len(qualified)<minimum):
        raise ValueError('Breadth or rank mismatch on '+day)
    vector = {r.symbol:float(r.target_weight) for r in targets}
    return np.array([vector.get(s,0.) for s in SYMBOLS]+[0.])


def prior_weights(day):
    targets = {t['symbol']:float(t['target_weight']) for t in TAPE[day]['targets']}
    return np.array([targets.get(s,0.) for s in SYMBOLS]+[0.])


def training_day(day):
    if day>CUTOFF:
        raise ValueError('Training date outside calibration')
    q = len(TAPE[day]['selection']['eligible'])
    table = np.zeros((SIZE+1, SIZE+1))
    # Row zero is the common defensive branch. All breadth thresholds on the
    # same side of Q produce identical targets for a given width.
    if q < SIZE:
        table[0] = weights(day,6,q+1)
    for width in range(1,min(q,SIZE)+1):
        table[width] = weights(day,width,1)
    if q < SIZE:
        table[max(1,q+1):] = table[q] if q else table[0]
    control = table[0 if q<4 else 6]
    if not np.allclose(control, prior_weights(day),rtol=0,atol=1e-13):
        raise ValueError('Training legacy control differs on '+day)
    return q,table


def bank():
    validate()
    a=input_arrays(True)
    indices=monthly_indices(a['days'])
    dates=a['days'][indices+1]
    with ProcessPoolExecutor(max_workers=4,initializer=init_targets) as pool:
        rows=list(pool.map(training_day,dates.tolist(),chunksize=1))
    dest=WORK/'training-bank.npz'
    np.savez_compressed(dest,indices=indices,qualifiers=np.array([r[0] for r in rows]),
                        targets=np.stack([r[1] for r in rows]))
    write(WORK/'bank-receipt.json',dict(sha256=digest(dest),monthly_decisions=len(dates),
          legacy_target_parity='All training monthly dates',last_date=str(dates[-1])))


def training_path(table,q,m,n):
    return table[np.arange(len(q)),np.where(q<n,0,m)]


def init_search():
    global ENGINE,BANK,INDICES
    a=input_arrays(True)
    ENGINE=Replay(a,read(parent.WORK/'recipe.json'),parent.START)
    BANK=dict(np.load(WORK/'training-bank.npz'))
    INDICES=BANK['indices']


def search_job(pair):
    m,n=pair
    selected=training_path(BANK['targets'],BANK['qualifiers'],m,n)
    full=np.zeros((len(ENGINE.a['days']), SIZE+1))
    full[INDICES]=selected
    result,_,_=ENGINE.run(full,INDICES,5,0)
    metrics={}
    for year in range(2021,2025):
        metrics[str(year)]=metric(ENGINE.day_strings,result['nav'],parent.START,f'{year}-12-31',
            turnover=result['turnover'],fees=result['fees'],exposure=result['exposure'])
    return metrics


def best(grid,year):
    return min(grid,key=lambda row:(-round(row['prefix'][year]['sharpe'],12),abs(row['n']-15),
                                    abs(row['m']-6),row['m'],row['n']))


def search():
    validate()
    if (OUT/'selection.json').exists():
        raise FileExistsError('Preserve sealed selection')
    assert digest(WORK/'training-bank.npz')==read(WORK/'bank-receipt.json')['sha256']
    bank_data=dict(np.load(WORK/'training-bank.npz'))
    groups={}
    for m in range(1,SIZE+1):
        for n in range(1,SIZE+1):
            targets=training_path(bank_data['targets'],bank_data['qualifiers'],m,n)
            fingerprint=hashlib.sha256(targets.tobytes()).hexdigest()
            groups.setdefault(fingerprint,[]).append((m,n))
    grid=[]
    with ProcessPoolExecutor(max_workers=4,initializer=init_search) as pool:
        for (fingerprint,pairs),metrics in zip(groups.items(),pool.map(search_job,[g[0] for g in groups.values()],chunksize=4),strict=True):
            grid.extend(dict(m=m,n=n,is_path=fingerprint,prefix=metrics) for m,n in pairs)
    chosen=best(grid,'2024')
    dest=OUT/'training-grid.json.gz'
    gzwrite(dest,grid)
    winners={year:[best(grid,year)['m'],best(grid,year)['n']] for year in ('2021','2022','2023','2024')}
    value=chosen['prefix']['2024']['sharpe']
    selection=dict(frozen_at=datetime.now(timezone.utc).isoformat(),m=chosen['m'],n=chosen['n'],
        trials=len(grid),distinct_paths=len(groups),prefix_winners=winners,net_is=chosen['prefix']['2024'],
        largest_input_session=CUTOFF,grid_sha256=digest(dest),protocol_sha256=digest(OUT/'protocol.json'),
        tied_pairs=[[r['m'],r['n']] for r in grid if round(r['prefix']['2024']['sharpe'],12)==round(value,12)],
        within_005_sharpe=sum(r['prefix']['2024']['sharpe']>=value-.05 for r in grid),
        best_other_paths=[dict(m=r['m'],n=r['n'],sharpe=r['prefix']['2024']['sharpe']) for r in
            sorted((next(x for x in grid if (x['m'],x['n'])==g[0]) for g in groups.values()),
                   key=lambda v:-v['prefix']['2024']['sharpe'])[:10]])
    write(OUT/'selection.json',selection)
    print('Locked',chosen['m'],chosen['n'],value,len(groups),flush=True)


def daily_job(args):
    day,m,n=args
    row=TAPE[day]
    q=len(row['selection']['eligible'])
    admitted=len(parent.ADMISSION[day])
    rules={'legacy':(6,4),'scaled':(6,15),'admitted':(6,required_count(4,14,admitted)),
           'winner':(m,n),'width_only':(m,4),'breadth_only':(6,n)}
    vectors={}
    cache={('defensive' if q<4 else min(q,6)):prior_weights(day)}
    for name,(width,threshold) in rules.items():
        branch='defensive' if q<threshold else min(q,width)
        if branch not in cache:
            cache[branch]=weights(day,width,threshold)
        vectors[name]=cache[branch]
    return day,q,admitted,vectors


def selected_runs():
    validate()
    selected=read(OUT/'selection.json')
    assert selected['grid_sha256']==digest(OUT/'training-grid.json.gz')
    a=input_arrays()
    indices=monthly_indices(a['days'])
    begin=indices[0]+1
    dates=a['days'][begin:]
    with ProcessPoolExecutor(max_workers=4,initializer=init_targets) as pool:
        rows=list(pool.map(daily_job,[(d,selected['m'],selected['n']) for d in dates.tolist()],chunksize=5))
    assert [r[0] for r in rows]==dates.tolist()
    schedules={}
    for name in rows[0][3]:
        full=np.zeros((len(a['days']),SIZE+1))
        full[begin-1:-1]=np.stack([r[3][name] for r in rows])
        schedules[name+'_weights']=full
        schedules[name+'_indices']=indices
        if name in ('winner','scaled'):
            tape={r[0]:dict(signal_session=r[0],known_through=str(a['days'][begin+i-1]),
                targets=[dict(symbol=str(symbol),target_weight=str(w)) for symbol,w in zip(a['symbols'],r[3][name][:-1],strict=True) if w>0])
                for i,r in enumerate(rows)}
            adopted,_=adoption_schedule(tape,a['days'][indices+1].tolist(),'0.40')
            schedules[name+'_event_weights']=full
            schedules[name+'_event_indices']=np.array([np.searchsorted(a['days'],d)-1 for d in adopted])
    np.savez_compressed(WORK/'schedules.npz',**schedules)
    write(OUT/'breadth-observations.json',[dict(session=r[0],known_through=str(a['days'][begin+i-1]),qualified=r[1],admitted=r[2]) for i,r in enumerate(rows)])
    engine=Replay(a,read(parent.WORK/'recipe.json'),parent.START)
    results=[]
    for arm in sorted(k.removesuffix('_indices') for k in schedules if k.endswith('_indices')):
        for cost,delay in read(OUT/'protocol.json')['frictions']:
            values,econ,_=engine.run(schedules[arm+'_weights'],schedules[arm+'_indices'],cost,delay,detailed=(cost,delay)==(5,0))
            key=f'{arm}_c{cost}d{delay}'
            if (cost,delay)==(5,0) or arm=='winner_event' and (cost,delay)==(20,1):
                (WORK/'paths').mkdir(exist_ok=True)
                np.savez_compressed(WORK/'paths'/(key+'.npz'),**values)
                if econ:gzwrite(WORK/'detail'/(key+'.json.gz'),econ)
            windows={w:metric(engine.day_strings,values['nav'],start,end,fees=values['fees'],
                turnover=values['turnover'],exposure=values['exposure']) for w,(start,end) in parent.WINDOWS.items()}
            results.append(dict(arm=arm,cost_bp=cost,delay=delay,windows=windows))
            if arm=='legacy':
                with np.load(parent.WORK/'paths'/f'expanded-monthly_c{cost}d{delay}.npz') as old:
                    if not np.array_equal(old['nav'],values['nav']):raise ValueError('Legacy NAV failed parity')
            if arm=='winner' and (cost,delay)==(5,0):
                if abs(windows['calibration']['sharpe']-selected['net_is']['sharpe'])>1e-12:
                    raise ValueError('Training-only optimum failed full-period parity')
    write(OUT/'results.json',results)
    print('Completed',len(results),'cases using selection',digest(OUT/'selection.json'),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['prepare','bank','search','selected_runs'])
    globals()[parser.parse_args().stage]()
