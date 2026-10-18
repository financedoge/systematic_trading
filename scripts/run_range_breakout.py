"""Finite, audited range-breakout study. One worker; compact scenario artifacts."""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal as D
import hashlib
import itertools
import json
from pathlib import Path
import shutil
import time

import numpy as np
import pandas as pd

from systematic_trading.research.range_breakout import (
    BreakoutSpec, adaptive_features, features, lifecycle, portfolio_tapes,
    adopted_indices, metrics,
)

ROOT = Path('var/research/range-breakout-20261018-v1')
PROTOCOL = Path('research/range-breakout-20261018-v1/protocol.json')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify(root, manifest):
    for relative, expected in read(root/manifest).items():
        path = (root/relative).resolve()
        if not path.is_relative_to(root.resolve()) or digest(path) != expected:
            raise ValueError('Input changed: '+relative)


def manifest(root, name, files):
    write(root/name, {p.relative_to(root).as_posix(): digest(p) for p in files})


def specs():
    return [BreakoutSpec(*x) for x in itertools.product(('adaptive', 252, 504), (False, True), (False, True))]


def prepare(root):
    if root.exists():
        verify(root, 'input_manifest.json')
        return
    from systematic_trading.research.governed_inputs import GovernedInputs
    from systematic_trading.research.etf_expansion import load_published_pool, admission_for_day
    from systematic_trading.research.fr25_tracking import fr25_definition
    from systematic_trading.research import instruments_for_definition
    p = read(PROTOCOL)
    parent = Path(p['price_pin_source']).parent
    parent_manifest = read(parent/'input_manifest.json')
    for relative in ('price_pin.json', 'candidates.json', 'protocol.json'):
        if digest(parent/relative) != parent_manifest[relative]:
            raise ValueError('Changed parent input: '+relative)
    sota_path = Path(p['sota_decisions_source'])
    if digest(sota_path) != read(parent/'result_manifest.json')['decisions/original14.json']:
        raise ValueError('Changed FR25 decision evidence')
    candidates = read(Path(p['candidate_source']))
    inventory = read('research/etf-universe-inventory-2026-10-13/inventory.json')
    xop = next(f for f in read('config/research-etf-recorders.json')['funds'] if f['symbol'] == 'XOP')
    candidates.append(dict(next(f for f in inventory['candidates'] if f['symbol'] == 'XOP'), **xop))
    pin = read(Path(p['price_pin_source']))
    reader = GovernedInputs(Path(pin['root']), pin['batch'])
    pool = load_published_pool(reader, candidates, through=p['through'])
    bench = load_published_pool(reader, [dict(symbol='URTH', requires_recorder=False)],
                                through=p['through'], start=pool['common_start'])
    if 'URTH' not in bench['bars']:
        raise ValueError('Audited benchmark missing')
    symbols, days = sorted(pool['bars']), pool['calendar']
    arrays = {field: np.array([[float(pool['bars'][s][i][field]) for s in symbols]
                              for i in range(len(days))]) for field in ('open', 'high', 'low', 'close')}
    arrays['volume'] = np.array([[float(pool['raw_bars'][s][i]['volume']) for s in symbols]
                                for i in range(len(days))])
    arrays['raw_close'] = np.array([[float(pool['raw_bars'][s][i]['close']) for s in symbols]
                                   for i in range(len(days))])
    dollars = pd.DataFrame(arrays['raw_close']*arrays['volume'])
    med, minimum = dollars.rolling(63).median().to_numpy(), dollars.rolling(63).min().to_numpy()
    metadata = {f['symbol']: f for f in candidates}
    admitted = np.zeros_like(arrays['close'], dtype=bool)
    for t in range(252, len(days)):
        groups = {}
        for j, s in enumerate(symbols):
            if med[t, j] >= 5e6 and minimum[t, j] >= 5e5:
                groups.setdefault(metadata[s]['duplicate_review_group'], []).append(j)
        for group in groups.values():
            j = min(group, key=lambda k: (-med[t, k], metadata[symbols[k]]['candidate_id']))
            admitted[t, j] = True
    for t in (252, 503, 800, len(days)-2):
        expected = admission_for_day(pool['records'], candidates, days[t+1])['admitted']
        if sorted(np.array(symbols)[admitted[t]].tolist()) != expected:
            raise ValueError('Optimized causal admission differs from application contract')
    fr25 = np.zeros_like(arrays['close'])
    sota = read(sota_path)
    anchor = np.zeros(len(symbols))
    for t, day in enumerate(days[:-1]):
        next_day = days[t+1]
        if next_day in sota:
            row = sota[next_day]
            if row['known_through'] != day:
                raise ValueError('FR25 availability mismatch')
            anchor = np.array([float(next((r['target_weight'] for r in row['targets']
                                          if r['symbol'] == s), 0)) for s in symbols])
        fr25[t] = anchor
    fr25[-1] = anchor
    arrays.update(admitted=admitted, fr25=fr25, days=np.array(days), symbols=np.array(symbols),
                  urth_open=np.array([float(r['open']) for r in bench['bars']['URTH']]),
                  urth_close=np.array([float(r['close']) for r in bench['bars']['URTH']]))
    class_protocol = read('research/cash-relative-momentum-20261017-v1/protocol.json')
    members = instruments_for_definition(fr25_definition())
    recipe = dict(id='range_breakout_research_v1', universeKey='frozen_range_pool', universeMembers=[])
    from systematic_trading.domain.market import Instrument
    for s in symbols+['URTH']:
        instrument = members.get(s) or Instrument(symbol=s, name=s, asset_class='etf', exchange='NYSE',
                                                 quote_currency='USD', country='US', sector='research')
        recipe['universeMembers'].append(instrument.model_dump(mode='json'))
    root.mkdir(parents=True)
    shutil.copyfile(PROTOCOL, root/'protocol.json')
    shutil.copyfile(sota_path, root/'fr25_decisions.json')
    np.savez_compressed(root/'inputs.npz', **arrays)
    write(root/'candidates.json', candidates)
    write(root/'price_pin.json', pin)
    write(root/'construction.json', {k: class_protocol[k] for k in ('classes', 'overlap_parents')})
    write(root/'recipe.json', recipe)
    write(root/'input_receipt.json', dict(candidate_count=len(candidates), supported_count=len(symbols),
        symbols=symbols, exclusions=pool['exclusions'], common_start=pool['common_start'],
        published_batch=pin['batch'], verified_publication_files=reader.used,
        source_decisions_sha256=digest(sota_path), parent_protocol=read(parent/'protocol.json'),
        parent_manifest_sha256=digest(parent/'input_manifest.json'),
        case_studies={'GLD': 'gold ETF', 'SOXX': 'semiconductor equity ETF',
                      'XLE': 'energy equities, not crude oil', 'DBC': 'diversified commodity futures, not crude oil'},
        crude_oil_gap='USO/DBO/BNO lack a qualified complete history in this frozen supported pool. No direct oil-price conclusion.',
        versions=dict(numpy=np.__version__, pandas=pd.__version__)))
    # One source snapshot for the whole study, never one per scenario.
    shutil.copytree('src/systematic_trading', root/'source/systematic_trading',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copyfile(__file__, root/'runner.py')
    manifest(root, 'input_manifest.json', [f for f in root.rglob('*') if f.is_file()])
    print(json.dumps(dict(stage='prepared', supported=len(symbols), candidates=len(candidates),
                          exclusions=pool['exclusions'], protocol_sha256=digest(root/'protocol.json'))), flush=True)


def signals(root):
    verify(root, 'input_manifest.json')
    if (root/'signal_manifest.json').exists():
        verify(root, 'signal_manifest.json')
        return
    a = dict(np.load(root/'inputs.npz', allow_pickle=False))
    symbols, days = a['symbols'].tolist(), a['days'].tolist()
    n, m = a['close'].shape
    construction = read(root/'construction.json')
    conflicts = {frozenset((p, c)) for p, children in construction['overlap_parents'].items() for c in children}
    output, diagnostics = {}, {}
    for lookback in ('adaptive', 252, 504):
        cached = [adaptive_features(a['close'][:, j], a['high'][:, j], a['low'][:, j], a['volume'][:, j])
                  if lookback == 'adaptive' else features(a['close'][:, j], a['high'][:, j], a['low'][:, j],
                                                         a['volume'][:, j], lookback) for j in range(m)]
        for spec in [s for s in specs() if s.lookback == lookback]:
            active, score, exits, state = np.zeros((n, m), bool), np.zeros((n, m)), np.zeros((n, m), bool), np.zeros((n, m), np.int8)
            diag = {}
            for j, s in enumerate(symbols):
                result = lifecycle(a['close'][:, j], a['open'][:, j], a['high'][:, j], a['low'][:, j],
                                   a['volume'][:, j], spec, cached=cached[j])
                active[:, j], score[:, j], state[:, j] = result['active'], result['score'], result['state']
                exits[result['exits'], j] = True
                episodes = []
                for row in result['episodes']:
                    row = dict(row)
                    k = row['exit_signal']
                    row['signal_date'] = days[row['signal_index']]
                    row['entry_date'] = days[row['fill_index']] if row['fill_index'] < n else None
                    row['exit_date'] = days[k+1] if k is not None and k+1 < n else None
                    row['exit_price'] = float(a['open'][k+1, j]) if row['exit_date'] else None
                    row['gross_return'] = row['exit_price']/row['entry_price']-1 if row['exit_price'] else None
                    if row['entry_price'] is not None:
                        row['max_favorable_return'] = row['peak']/row['entry_price']-1
                    episodes.append(row)
                diag[s] = dict(episodes=episodes, failed_confirmations=result['failed_confirmations'],
                               tight_sessions=int(cached[j]['tight'].sum()), active_sessions=int(active[:, j].sum()))
            tapes = portfolio_tapes(a['close'], a['admitted'], symbols, score, active, a['fr25'], conflicts)
            for application in ('selection', 'trading', 'tilt'):
                output[spec.key+'__'+application] = tapes[application]
            output[spec.key+'__exits'] = exits
            if spec.key == 'Ladaptive-V1-H1':
                output['primary_state'], output['primary_score'] = state, score
            output['M1'], output['blend_control'] = tapes['M1'], tapes['blend_control']
            diagnostics[spec.key] = diag
            print('Signals', spec.key, sum(len(d['episodes']) for d in diag.values()), 'episodes', flush=True)
    output['FR25'] = a['fr25']
    eligible = a['admitted']
    output['equal_weight'] = .98*eligible/np.maximum(1, eligible.sum(axis=1))[:, None]
    vol = pd.DataFrame(a['close']).pct_change(fill_method=None).rolling(63).std().to_numpy()
    inverse = np.where(eligible & (vol > 0), 1/np.maximum(vol, 1e-12), 0)
    output['risk_parity'] = np.minimum(.45, .98*inverse/np.maximum(1e-12, inverse.sum(axis=1))[:, None])
    np.savez_compressed(root/'signals.npz', **output)
    write(root/'episodes.json', diagnostics)
    manifest(root, 'signal_manifest.json', [root/'signals.npz', root/'episodes.json'])


class Replay:
    """Shared application engine, preloaded once; no new approximate accountant."""
    def __init__(self, a, recipe, start):
        from systematic_trading.domain.market import Instrument
        from systematic_trading.backtest.accounting import quantize_money
        self.a, self.start = a, start
        self.symbols = a['symbols'].tolist()+['URTH']
        self.indices = np.flatnonzero(a['days'] >= start)
        self.days = [date.fromisoformat(str(a['days'][i])) for i in self.indices]
        self.day_strings = np.array([str(d) for d in self.days])
        self.members = {r['symbol']: Instrument.model_validate(r) for r in recipe['universeMembers']}
        close = np.column_stack([a['close'], a['urth_close']])
        opens = np.column_stack([a['open'], a['urth_open']])
        self.close, self.open, self.reference = {}, {}, {}
        for i, day in zip(self.indices, self.days, strict=True):
            for target, values in ((self.close, close[i]), (self.open, opens[i]), (self.reference, close[i-1])):
                target[day] = {s: quantize_money(D(str(x))) for s, x in zip(self.symbols, values, strict=True)}
        self.fx = {day: {'USD': D(1)} for day in self.days}

    def decisions(self, weights, indices, delay):
        from systematic_trading.domain.portfolio import AllocationTarget
        result = {}
        for t in indices:
            execution = t+1+delay
            if execution >= len(self.a['days']):
                continue
            day = date.fromisoformat(str(self.a['days'][execution]))
            result[day] = [AllocationTarget(symbol=s, target_weight=D(str(round(float(w), 12))),
                                           sleeve='range-breakout', rationale='Frozen causal range-breakout study')
                           for s, w in zip(self.symbols, weights[t], strict=True) if w > 0]
        return result

    def run(self, weights, indices, cost, delay, *, detailed=False):
        from systematic_trading.backtest.engine import DailyBacktestEngine
        from systematic_trading.backtest.accounting import quantize_money
        from systematic_trading.domain.portfolio import CashBalance
        from systematic_trading.domain.enums import Currency
        schedule = self.decisions(weights, indices, delay)
        order_days, fill_rows = iter(sorted(schedule)), []
        class Engine(DailyBacktestEngine):
            def _apply_orders(self, **kw):
                day = next(order_days)
                before = {s: p.quantity for s, p in kw['positions'].items()}
                super()._apply_orders(**kw)
                after = {s: p.quantity for s, p in kw['positions'].items()}
                for s in sorted(before.keys() | after.keys()):
                    quantity = after.get(s, 0)-before.get(s, 0)
                    if quantity:
                        price = kw['execution_prices'][s]
                        fee = quantize_money(quantize_money(abs(quantity)*price)*D(str(cost))/10000)
                        fill_rows.append(dict(date=str(day), symbol=s, quantity=quantity, price=str(price), fee=str(fee)))
        result = Engine().run(trade_dates=self.days, instruments=self.members,
            initial_cash=[CashBalance(currency=Currency.USD, amount=D(1_000_000))],
            daily_prices=self.close, daily_rebalance_prices=self.reference, daily_execution_prices=self.open,
            daily_fx_to_cnh=self.fx, target_schedule=schedule, transaction_cost_bps=D(str(cost)))
        nav = np.array([float(r.nav_cnh) for r in result.nav_series])
        exposure = np.array([float(r.gross_exposure_cnh/r.nav_cnh) for r in result.nav_series])
        q, cash = np.zeros(len(self.symbols)), 1_000_000.
        turnover, fees = np.zeros(len(nav)), np.zeros(len(nav))
        contribution = np.zeros((len(nav), len(self.symbols)))
        fills_by_day = {}
        for row in fill_rows:
            fills_by_day.setdefault(row['date'], []).append(row)
        previous_close = np.array(list(self.reference[self.days[0]].values()), float)
        for t, day in enumerate(self.days):
            closing = np.array(list(self.close[day].values()), float)
            opening = np.array(list(self.open[day].values()), float)
            open_nav = cash+q@opening
            contribution[t] = q*(closing-previous_close)
            for f in fills_by_day.get(str(day), []):
                j = self.symbols.index(f['symbol'])
                amount, fee = f['quantity']*float(f['price']), float(f['fee'])
                q[j] += f['quantity']
                cash -= amount+fee
                contribution[t, j] += f['quantity']*(closing[j]-float(f['price']))-fee
                turnover[t] += abs(amount)/open_nav
                fees[t] += fee
            if abs(cash+q@closing-nav[t]) > .03:
                raise ValueError('Attribution ledger failed reconciliation')
            previous_close = closing
        if abs(contribution.sum()-(nav[-1]-1_000_000)) > .05:
            raise ValueError('Contribution sum does not reconcile')
        compact = dict(nav=nav, turnover=turnover, fees=fees, exposure=exposure)
        if cost == 5 and delay == 0:
            compact['contribution'] = contribution
        economic = dict(engine='python', accounting_currency='USD', complete=True, fills=fill_rows,
                        nav=[dict(date=str(r.trade_date), nav=str(r.nav_cnh), cash=str(r.cash_cnh)) for r in result.nav_series])
        return compact, economic if detailed else None, len(fill_rows)


def mappings(root, a, sig):
    p, days = read(root/'protocol.json'), a['days'].tolist()
    outputs = {}
    for key in ('M1', 'blend_control', 'FR25', 'equal_weight', 'risk_parity'):
        for policy in (('monthly', 'event') if key in ('M1', 'blend_control') else ('monthly',)):
            w = np.column_stack([sig[key], np.zeros(len(days))])
            outputs[key+'__'+policy] = dict(weights=w, indices=adopted_indices(w, days, p['start'], policy),
                                           control=key+'__'+policy)
    for s in ('URTH', 'BIL'):
        w = np.zeros((len(days), len(a['symbols'])+1))
        j = len(a['symbols']) if s == 'URTH' else a['symbols'].tolist().index(s)
        w[:, j] = 1
        t = next(i for i, d in enumerate(days) if d >= p['start'])-1
        outputs[s] = dict(weights=w, indices=[t], control=s)
    for spec in specs():
        for app in ('selection', 'trading', 'tilt'):
            for policy in p['policies']:
                key = spec.key+'__'+app
                w = np.column_stack([sig[key], np.zeros(len(days))])
                risk = np.column_stack([sig[spec.key+'__exits'], np.zeros(len(days), bool)]) if app in ('trading', 'tilt') else None
                name = key+'__'+policy
                control = ('blend_control' if app == 'tilt' else 'M1')+'__'+policy
                outputs[name] = dict(weights=w, indices=adopted_indices(w, days, p['start'], policy, exits=risk), control=control)
    return outputs


def replay(root, limit=None):
    verify(root, 'input_manifest.json')
    verify(root, 'signal_manifest.json')
    a, sig = dict(np.load(root/'inputs.npz')), dict(np.load(root/'signals.npz'))
    p = read(root/'protocol.json')
    runner = Replay(a, read(root/'recipe.json'), p['start'])
    maps = mappings(root, a, sig)
    results = read(root/'metrics.json') if (root/'metrics.json').exists() else {}
    started, completed = time.perf_counter(), 0
    for name, mapping in maps.items():
        for cost, delay in itertools.product(p['cost_bps'], p['additional_delay_sessions']):
            key = name+f'__c{cost}d{delay}'
            if key in results:
                if digest(root/'paths'/(key+'.npz')) != results[key]['sha256']:
                    raise ValueError('Scenario artifact changed')
                continue
            compact, _, count = runner.run(mapping['weights'], mapping['indices'], cost, delay)
            path = root/'paths'/(key+'.npz')
            path.parent.mkdir(exist_ok=True)
            np.savez_compressed(path, **compact)
            windows = {'full': (p['start'], p['through']), 'calibration': (p['start'], p['calibration_end']),
                       'evaluation': (p['evaluation_start'], p['through'])}
            for year in range(2021, 2027):
                windows[str(year)] = (f'{year}-01-01', f'{year}-12-31')
            for year in (2024, 2025, 2026):
                windows[f'train{year}'] = (f'{year-3}-01-01', f'{year-1}-12-31')
            results[key] = dict(sha256=digest(path), fills=count, adoptions=len(mapping['indices']), control=mapping['control'],
                windows={k: metrics(**{x: compact[x] for x in ('nav', 'turnover', 'fees', 'exposure')},
                                   days=runner.day_strings, start=v[0], end=v[1]) for k, v in windows.items()})
            completed += 1
            write(root/'metrics.json', results)
            if completed % 6 == 0 or completed == 1:
                print(json.dumps(dict(stage='replay', completed=len(results), total=len(maps)*6,
                    elapsed=round(time.perf_counter()-started, 1), last=key,
                    evaluation=results[key]['windows']['evaluation'])), flush=True)
            if limit and completed >= limit:
                return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=('prepare', 'signals', 'replay'))
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    if args.stage == 'replay':
        replay(args.root, args.limit)
    else:
        {'prepare': prepare, 'signals': signals}[args.stage](args.root)


if __name__ == '__main__':
    main()
