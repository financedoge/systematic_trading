"""Prepare, fit (strict pre-2023), seal, and evaluate individual breakout rules."""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal as D
import json
from pathlib import Path
import shutil
import time

import numpy as np
import pandas as pd

from run_range_breakout import read, write, digest, verify, manifest, Replay
from systematic_trading.research.range_breakout import BreakoutSpec, lifecycle, metrics
from systematic_trading.research.range_calibration import (
    candidate_grid, signal_grid, fractional_screen, panel_metrics, robust_score,
    transitions, select_fitted,
)

ROOT = Path('var/research/range-breakout-20261018-v2')
PUBLIC = Path('research/range-breakout-20261018-v2')
FRICTIONS = ((5, 0), (10, 0), (5, 1))


class SingleReplay(Replay):
    """Single-ETF adapter to the identical shared application engine."""
    def __init__(self, a, symbol, start):
        from systematic_trading.domain.market import Instrument
        from systematic_trading.backtest.accounting import quantize_money
        self.a, self.start, self.symbols = a, start, [symbol]
        self.indices = np.flatnonzero(a['days'] >= start)
        self.days = [date.fromisoformat(str(a['days'][i])) for i in self.indices]
        self.day_strings = np.array([str(d) for d in self.days])
        self.members = {symbol: Instrument(symbol=symbol, name=symbol, asset_class='etf',
            exchange='NYSE', quote_currency='USD', country='US', sector='research')}
        self.close, self.open, self.reference = {}, {}, {}
        for i, day in zip(self.indices, self.days, strict=True):
            for target, value in ((self.close, a['close'][i]), (self.open, a['open'][i]), (self.reference, a['close'][i-1])):
                target[day] = {symbol: quantize_money(D(str(float(value))))}
        self.fx = {day: {'USD': D(1)} for day in self.days}


def legacy(a):
    return lifecycle(a['close'], a['open'], a['high'], a['low'], a['volume'], BreakoutSpec())


def calibrated(a, ids, *, details=False):
    grid = candidate_grid()
    return signal_grid(a['close'], a['open'], a['high'], a['low'], a['volume'],
                       [grid[i] for i in ids], details=details)


def load_asset(root, symbol, *, fit=False):
    a = dict(np.load(root/'assets'/f'{symbol}.npz', allow_pickle=False))
    if fit:
        mask = a['days'] < '2023-01-01'
        a = {k: v[mask] for k, v in a.items()}
    return a


def prepare(root, *, amend_coverage=False):
    if (root/'input_manifest.json').exists() and not amend_coverage:
        verify(root, 'input_manifest.json')
        return
    if amend_coverage:
        verify(root, 'input_manifest.json')
        write(root/'coverage_amendment.json', dict(previous_manifest_sha256=digest(root/'input_manifest.json'),
            previously_fitted=sorted(p.stem for p in (root/'fits').glob('*.json')),
            reason='Coverage-only amendment before any OOS evaluation: retain each longest complete valid suffix, never fill unsupported early bars. No rule/search/selection changes. Existing case inputs must be identical.',
            previous_assets={p.stem:digest(p) for p in (root/'assets').glob('*.npz')}))
    from systematic_trading.config import get_settings
    from systematic_trading.market_data.analytics_store import AnalyticsStore
    from systematic_trading.research.governed_inputs import GovernedInputs
    from systematic_trading.research.candidate_pool import audited_bar
    from systematic_trading.research.etf_admission import admission_hold
    import exchange_calendars as xc
    publication = AnalyticsStore.from_settings(get_settings()).latest('governance/catalog')
    price_root = Path(json.loads(publication['provenance'])['root'])
    reader = GovernedInputs(price_root, publication['version'])
    protocol = read(PUBLIC/'protocol.json')
    if json.loads(publication['provenance'])['cutoff'] != protocol['through']:
        raise ValueError('Publication cutoff changed; explicitly register new study')
    candidates = read('var/research/range-breakout-uso-20261018-v1/candidates.json')
    cal = xc.get_calendar('XNYS', start='1990-01-01', end='2026-12-31')
    receipts, exclusions = {}, {}
    (root/'assets').mkdir(parents=True, exist_ok=True)
    for fund in candidates:
        s = fund['symbol']
        try:
            if hold := admission_hold(s, fund.get('admission_hold')):
                raise ValueError(hold)
            audit = reader.audit(s)
            if audit['status'] != 'audited_with_limitations':
                raise ValueError('Unsupported audit status')
            if fund.get('requires_recorder', True) and audit.get('research_recorder', {}).get('isin') != fund['isin']:
                raise ValueError('Recorder identity mismatch')
            rows = reader.rows(s, '1990-01-01', protocol['through'])
            if not rows or rows[-1]['trade_date'] != protocol['through']:
                raise ValueError('No complete history through cutoff')
            expected = cal.sessions_in_range(rows[0]['trade_date'], protocol['through']).strftime('%Y-%m-%d').tolist()
            actual = [r['trade_date'] for r in rows]
            if set(actual)-set(expected):
                raise ValueError('Observations outside XNYS calendar')
            unsupported = set(expected)-set(actual)
            for row in rows:
                try:
                    audited_bar(row)
                    audited_bar(row, raw=True)
                except ValueError:
                    unsupported.add(row['trade_date'])
            original_first = rows[0]['trade_date']
            if unsupported:
                last_bad = max(unsupported)
                rows = [r for r in rows if r['trade_date'] > last_bad]
                expected = [d for d in expected if d > last_bad]
            if len(rows) < 253 or [r['trade_date'] for r in rows] != expected:
                raise ValueError('Insufficient complete supported suffix')
            arrays = {k: np.array([r['adjusted_'+k] for r in rows], float) for k in ('open', 'high', 'low', 'close')}
            arrays.update(days=np.array(expected), volume=np.array([r['raw_volume'] for r in rows], float),
                          raw_close=np.array([r['raw_close'] for r in rows], float))
            np.savez_compressed(root/'assets'/f'{s}.npz', **arrays)
            fit_n = int(np.sum(arrays['days'] < '2023-01-01'))
            receipts[s] = dict(first=expected[0], original_first=original_first, unsupported_dates=sorted(unsupported),
                last=expected[-1], observations=len(rows), fit_observations=fit_n,
                fit_sessions_after_warmup=fit_n-252, fit_start=expected[min(252, len(rows)-1)],
                enough_history=fit_n-252 >= 1260, identity='recorder' if fund.get('requires_recorder',True) else 'provider retrospective')
        except (ValueError, KeyError, OSError) as exc:
            exclusions[s] = str(exc)
    if not all(s in receipts for s in ('GLD', 'USO', 'SOXX')):
        raise ValueError('Required cases unsupported: '+str(exclusions))
    write(root/'protocol.json', protocol)
    write(root/'candidates.json', candidates)
    write(root/'grid.json', [s.record() for s in candidate_grid()])
    write(root/'price_pin.json', dict(root=str(price_root), batch=reader.batch, through=protocol['through']))
    write(root/'input_receipt.json', dict(assets=receipts, exclusions=exclusions, files=reader.used,
        calendar=dict(name='XNYS', version=xc.__version__), source_provenance=json.loads(publication['provenance']),
        additional_stocks='Not needed: cases have 15-20 IS years after warmup; broad ETF controls extend to1993.'))
    shutil.copyfile(__file__, root/'runner.py')
    shutil.copyfile('scripts/run_range_breakout.py', root/'run_range_breakout.py')
    shutil.copytree('src/systematic_trading', root/'source/systematic_trading', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    if amend_coverage:
        old = read(root/'coverage_amendment.json')['previous_assets']
        for s, expected_hash in old.items():
            if digest(root/'assets'/f'{s}.npz') != expected_hash:
                raise ValueError('Coverage amendment changed existing asset '+s)
    manifest(root, 'input_manifest.json', [*sorted((root/'assets').glob('*.npz')),
        *[f for f in (root/'source').rglob('*') if f.is_file()],
        *[root/f for f in ('protocol.json','candidates.json','grid.json','price_pin.json','input_receipt.json','runner.py','run_range_breakout.py')],
        *([root/'coverage_amendment.json'] if amend_coverage else [])])
    print(json.dumps(dict(stage='prepared', supported=len(receipts), exclusions=exclusions,
                         cases={s: receipts[s] for s in ('GLD','USO','SOXX')}, candidates=len(candidate_grid()))), flush=True)


def summary_path(path, runner):
    return metrics(**{k: path[k] for k in ('nav','turnover','fees','exposure')}, days=runner.day_strings,
                   start=runner.start, end=str(runner.day_strings[-1]))


def screen_asset(root, s):
    a = load_asset(root, s, fit=True)
    if np.any(a['days'] >= '2023-01-01'):
        raise ValueError('OOS contamination')
    active = calibrated(a, list(range(len(candidate_grid()))))['active']
    nav, closed, turns = fractional_screen(a['close'], a['open'], active, 252)
    score, block_sharpes = robust_score(nav)
    pm = panel_metrics(nav)
    bh, _, _ = fractional_screen(a['close'], a['open'], np.ones((len(a['days']), 1), bool), 252)
    bm = panel_metrics(bh)
    guards = (pm['cagr'] >= max(0., bm['cagr'][0]-.02)) & (pm['max_drawdown'] >= bm['max_drawdown'][0]-.05) & (closed >= 8)
    order = sorted(range(len(score)), key=lambda i: (-score[i], i))
    shortlist = sorted(set(order[:6]+[i for i in order if guards[i]][:6]))
    (root/'screens').mkdir(exist_ok=True)
    np.savez_compressed(root/'screens'/f'{s}.npz', score=score, closed=closed, turnover=turns,
                        block_sharpes=block_sharpes, **pm)
    return a, active, shortlist


def fit_asset(root, s):
    a, active, shortlist = screen_asset(root, s)
    start = str(a['days'][252])
    runner = SingleReplay(a, s, start)
    bh_active = np.ones(len(a['days']), bool)
    benchmarks = {}
    for cost, delay in FRICTIONS:
        path, _, _ = runner.run(.98*bh_active[:,None], transitions(bh_active, a['days'], start), cost, delay)
        benchmarks[f'{cost}:{delay}'] = summary_path(path, runner)
    tape = {'v1': legacy(a)['active'], **{str(i): active[:, i] for i in shortlist}}
    records = []
    for ident, sig in tape.items():
        scenarios = {}
        indices = transitions(sig, a['days'], start)
        # Closed signal episodes are counted inside IS only; no future exit used.
        closed = int(np.sum(sig[251:-1] & ~sig[252:]))
        for cost, delay in FRICTIONS:
            path, _, count = runner.run(.98*sig[:,None], indices, cost, delay)
            met = summary_path(path, runner)
            score, blocks = robust_score(path['nav']/1e6)
            bm = benchmarks[f'{cost}:{delay}']
            scenarios[f'{cost}:{delay}'] = dict(**met, score=float(score[0]), block_sharpes=blocks[:,0].tolist(), fills=count,
                guard_pass=bool(met['cagr'] >= max(0,bm['cagr']-.02) and met['max_drawdown'] >= bm['max_drawdown']-.05))
        primary = scenarios['5:0']
        evidence = len(a['days'])-252 >= 1260 and closed >= 8 and primary['average_exposure'] >= .1
        evidence = evidence and all(sig[252:][b].any() for b in np.array_split(np.arange(len(sig)-252),3))
        records.append(dict(id=ident, score=min(r['score'] for r in scenarios.values()),
            guard_pass=all(r['guard_pass'] for r in scenarios.values()), evidence=bool(evidence), closed=closed,
            annual_turnover=primary['annual_turnover'], scenarios=scenarios))
    selected = select_fitted(records)
    write(root/'fits'/f'{s}.json', dict(symbol=s, first=str(a['days'][0]), fit_start=start,
        known_through=str(a['days'][-1]), sessions=len(runner.days), shortlist=shortlist,
        selected=selected, records=records, buyhold=benchmarks,
        screen_sha256=digest(root/'screens'/f'{s}.npz')))
    print(json.dumps(dict(stage='fit', symbol=s, sessions=len(runner.days), selected=None if selected is None else selected['id'],
                         guard_pass=None if selected is None else selected['guard_pass'], shortlist=len(records))), flush=True)


def fit(root, only=None):
    verify(root, 'input_manifest.json')
    receipts = read(root/'input_receipt.json')['assets']
    order = ['GLD','USO','SOXX'] + sorted(set(receipts)-{'GLD','USO','SOXX'})
    started = time.perf_counter()
    for s in order:
        if only and s not in only:
            continue
        if (root/'fits'/f'{s}.json').exists():
            if read(root/'fits'/f'{s}.json')['screen_sha256'] != digest(root/'screens'/f'{s}.npz'):
                raise ValueError('Fit screen changed')
            continue
        fit_asset(root, s)
        print(json.dumps(dict(elapsed_seconds=round(time.perf_counter()-started))), flush=True)


def seal(root):
    verify(root, 'input_manifest.json')
    if (root/'selection.json').exists():
        verify(root, 'selection_manifest.json')
        return
    receipts = read(root/'input_receipt.json')['assets']
    ranks = []
    from scipy.stats import rankdata
    for s, rec in receipts.items():
        fit = read(root/'fits'/f'{s}.json')
        if fit['known_through'] >= '2023-01-01':
            raise ValueError('OOS fit record')
        if rec['enough_history']:
            scores = np.load(root/'screens'/f'{s}.npz')['score']
            ranks.append(rankdata(scores, method='average')/len(scores))
    pooled = int(np.argmax(np.median(ranks, axis=0)))
    selections = {}
    for s in receipts:
        best = read(root/'fits'/f'{s}.json')['selected']
        selections[s] = dict(id=best['id'] if best else str(pooled), individually_fitted=best is not None,
            guard_pass=bool(best and best['guard_pass']), fallback_reason=None if best else 'Insufficient history/trade evidence')
    write(root/'selection.json', dict(version='sealed-pre2023', fit_end='2022-12-31',
        input_manifest_sha256=digest(root/'input_manifest.json'), shared_id=str(pooled), selections=selections,
        sealed_utc=pd.Timestamp.now(tz='UTC').isoformat(), grid_sha256=digest(root/'grid.json')))
    manifest(root, 'selection_manifest.json', [root/'selection.json', *sorted((root/'fits').glob('*.json')),
                                               *sorted((root/'screens').glob('*.npz'))])
    print(json.dumps(dict(stage='sealed', shared_id=pooled, individual=sum(r['individually_fitted'] for r in selections.values()),
                         total=len(selections), sha256=digest(root/'selection.json'))), flush=True)


def selected_signal(a, ident, *, details=False):
    if ident == 'v1':
        r = legacy(a)
        return {k: r[k] for k in ('active','stop','heat','episodes','exits')}
    r = calibrated(a, [int(ident)], details=details)
    return {k: v[:,0] for k, v in r.items()}


def evaluate(root, only=None):
    verify(root, 'input_manifest.json')
    verify(root, 'selection_manifest.json')
    selected = read(root/'selection.json')
    order = ['GLD','USO','SOXX']+sorted(set(selected['selections'])-{'GLD','USO','SOXX'})
    for s in order:
        if only and s not in only:
            continue
        dest = root/'evaluation'/s
        if (dest/'manifest.json').exists():
            verify(dest, 'manifest.json')
            continue
        a = load_asset(root, s)
        current = selected_signal(a, selected['selections'][s]['id'], details=True)
        tapes = {'selected': current['active'], 'shared': selected_signal(a, selected['shared_id'])['active'],
                 'v1': legacy(a)['active'], 'buyhold': np.ones(len(a['days']),bool),
                 'sma200': a['close'] > pd.Series(a['close']).rolling(200).mean().to_numpy()}
        runner = SingleReplay(a, s, '2023-01-01')
        dest.mkdir(parents=True, exist_ok=True)
        result = {}
        for name, sig in tapes.items():
            for policy in (('event','monthly') if name == 'selected' else ('event',)):
                for cost, delay in ((c,d) for c in (5,10,20) for d in (0,1)):
                    idx = transitions(sig, a['days'], '2023-01-01', policy)
                    path, _, count = runner.run(.98*sig[:,None], idx, cost, delay)
                    key = f'{name}_{policy}_c{cost}d{delay}'
                    windows = dict(oos=summary_path(path, runner))
                    for year in range(2023,2027):
                        windows[str(year)] = metrics(**{k: path[k] for k in ('nav','turnover','fees','exposure')},
                            days=runner.day_strings, start=f'{year}-01-01', end=f'{year}-12-31')
                    result[key] = dict(windows=windows, fills=count)
                    # Only a handful of one-dimensional paths, never the grid's daily state.
                    np.savez_compressed(dest/f'{key}.npz', **path)
        serial = {k: v for k,v in current.items() if isinstance(v,np.ndarray)}
        np.savez_compressed(dest/'signal.npz', **serial, days=a['days'])
        write(dest/'metrics.json', result)
        manifest(dest, 'manifest.json', [p for p in dest.glob('*') if p.is_file()])
        print(json.dumps(dict(stage='oos', symbol=s, selected=selected['selections'][s],
            result=result['selected_event_c5d0']['windows']['oos'], buyhold=result['buyhold_event_c5d0']['windows']['oos'])), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=('prepare','fit','seal','evaluate'))
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--only',nargs='*')
    parser.add_argument('--amend-coverage',action='store_true')
    args=parser.parse_args()
    if args.stage == 'prepare':
        prepare(args.root,amend_coverage=args.amend_coverage)
    elif args.stage == 'fit':
        fit(args.root,args.only)
    elif args.stage == 'seal':
        seal(args.root)
    else:
        evaluate(args.root,args.only)


if __name__ == '__main__':
    main()
