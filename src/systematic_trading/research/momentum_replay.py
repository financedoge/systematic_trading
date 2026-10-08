"""USD research replay with a separate contract; production CNH replay is untouched.

The shared proposal/accounting library names its valuation unit CNH. Here its
internal converter is a unit adapter (USD=1), never an observed FX rate. All
cash, securities, fills and reported values are USD. Native LEAN independently
uses an actual USD account and must reproduce this oracle to the cent.
"""
from datetime import date
from decimal import Decimal as D
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace
from uuid import uuid4

from systematic_trading.backtest.accounting import quantize_money
from systematic_trading.backtest.engine import DailyBacktestEngine
from systematic_trading.domain.enums import Currency
from systematic_trading.domain.portfolio import AllocationTarget, CashBalance
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.lean.runner import compare_outputs, docker_command, lean_config
from systematic_trading.research import current_sota_definition, instruments_for_definition, BENCHMARK_INSTRUMENTS


def read_json(path):
    return json.loads(path.read_text(encoding='utf8'))


def checked_files(root, name):
    files = read_json(root/name)
    for relative, expected in files.items():
        p = (root/relative).resolve()
        if not p.is_relative_to(root.resolve()) or not p.is_file() or sha256(p)!=expected:
            raise ValueError('Research input missing/changed: '+relative)
    return files


def verify_usd_bundle(root):
    files = checked_files(root, 'manifest.json')
    if {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p!=root/'manifest.json'} != set(files):
        raise ValueError('Research bundle inventory changed')
    s = read_json(root/'spec.json')
    if s['contract']!='momentum-usd-adjusted-units-v1' or s['accounting_currency']!='USD' or s['promotion_eligible'] is not False:
        raise ValueError('Unsupported research currency/contract')
    if not 0<=D(s['transaction_cost_bps'])<10000 or D(s['initial_cash_usd'])<=0:
        raise ValueError('Invalid replay economics')
    return dict(spec=SimpleNamespace(**s))


def usd_instruments():
    from systematic_trading.research.parking_fallback import BILL
    return {**instruments_for_definition(current_sota_definition()), **BENCHMARK_INSTRUMENTS, BILL.symbol: BILL}


def freeze_usd_bundle(root, study, recipe, decisions, quotes, sessions, cost):
    from systematic_trading.live.trading_calendar import us_equity_market_close
    if root.exists():
        verify_usd_bundle(root)
        return root
    root.mkdir(parents=True)
    shutil.copytree(study/'source', root/'source')
    protocol = read_json(study/'protocol.json')
    spec = dict(contract='momentum-usd-adjusted-units-v1', accounting_currency='USD', initial_cash_usd=protocol['initial_cash_usd'],
                transaction_cost_bps=str(cost), slippage_bps='0', start_date=sessions[0], end_date=sessions[-1],
                recipe=recipe, protocol_sha256=sha256(study/'protocol.json'), input_manifest_sha256=sha256(study/'input_manifest.json'),
                target_tolerance='0.00000001', money_tolerance_cnh='0.01',
                tolerance_unit='USD (legacy comparison helper field name)', promotion_eligible=False, limitations=protocol['limitations'])
    for name,obj in [('spec.json',spec),('decisions.json',decisions),('quotes.json',quotes),('sessions.json',sessions)]:
        write_json(root/name,obj)
    (root/'quotes').mkdir()
    for s,by_date in quotes.items():
        records=[]
        for day in sessions:
            q=by_date[day]
            records += [f'{day}T09:30:00,{q["open"]},open', f'{day}T{us_equity_market_close(date.fromisoformat(day))},{q["close"]},close']
        (root/'quotes'/f'{s}.csv').write_text('\n'.join(records)+'\n',encoding='utf8')
    write_json(root/'manifest.json', {p.relative_to(root).as_posix():sha256(p) for p in sorted(root.rglob('*')) if p.is_file()})
    verify_usd_bundle(root)
    return root


def run_usd_reference(root):
    started=time.perf_counter()
    spec=verify_usd_bundle(root)['spec']
    decisions,quotes,sessions=[read_json(root/name) for name in ('decisions.json','quotes.json','sessions.json')]
    instruments={s:usd_instruments()[s] for s in quotes}
    fills=[]
    decision_days=iter(sorted(decisions))
    cost=D(spec.transaction_cost_bps)/10000
    class Engine(DailyBacktestEngine):
        def _apply_orders(self, **kw):
            day=next(decision_days)
            before={s:p.quantity for s,p in kw['positions'].items()}
            super()._apply_orders(**kw)
            after={s:p.quantity for s,p in kw['positions'].items()}
            for s in sorted(set(before)|set(after)):
                quantity=after.get(s,0)-before.get(s,0)
                if quantity:
                    price=kw['execution_prices'][s]
                    notional=quantize_money(abs(quantity)*price)
                    fills.append(dict(date=day,symbol=s,quantity=quantity,price=str(price),fee=str(quantize_money(notional*cost))))
    days=[date.fromisoformat(d) for d in sessions]
    result=Engine().run(trade_dates=days,instruments=instruments,
        initial_cash=[CashBalance(currency=Currency.USD,amount=D(spec.initial_cash_usd))],
        daily_prices={d:{s:D(q[str(d)]['close']) for s,q in quotes.items()} for d in days},
        daily_rebalance_prices={d:{s:D(q[str(d)]['reference']) for s,q in quotes.items()} for d in days},
        daily_execution_prices={d:{s:D(q[str(d)]['open']) for s,q in quotes.items()} for d in days},
        daily_fx_to_cnh={d:{Currency.USD:D(1)} for d in days},
        target_schedule={date.fromisoformat(d):[AllocationTarget.model_validate(t) for t in r['targets']] for d,r in decisions.items()},
        transaction_cost_bps=spec.transaction_cost_bps)
    return dict(schema_version=1,engine='python',accounting_currency='USD',complete=True,decisions=decisions,fills=fills,
        nav=[dict(date=str(r.trade_date),nav=str(r.nav_cnh),cash=str(r.cash_cnh)) for r in result.nav_series],
        final_positions={p.symbol:p.quantity for p in result.final_snapshot.positions},elapsed_seconds=time.perf_counter()-started)


def native_parity(bundle, output, image, cpus='5'):
    spec=verify_usd_bundle(bundle)['spec']
    if output.exists():
        receipt=read_json(output/'run.json')
        if receipt['status']!='succeeded' or receipt['manifest_sha256']!=sha256(bundle/'manifest.json'):
            raise ValueError('Failed/changed native run; retain and use a distinct attempt path')
        checked_files(output,'artifact_manifest.json')
        return receipt
    output.mkdir(parents=True)
    name='st-momentum-'+uuid4().hex[:12]
    receipt=dict(status='running',manifest_sha256=sha256(bundle/'manifest.json'),image=image,promotion_eligible=False,
                 resources=dict(cpus=cpus,memory='4g'),started=time.time())
    config=lean_config()
    config['algorithm-location']='/input/source/systematic_trading/research/momentum_lean.py'
    write_json(output/'config.json',config)
    try:
        reference=run_usd_reference(bundle)
        write_json(output/'reference.json',reference)
        command=docker_command(image=image,bundle=bundle,output=output,name=name,cpus=cpus,memory='4g')
        with (output/'lean.log').open('w',encoding='utf8') as log:
            subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
        actual=read_json(output/'economic.json')
        parity=compare_outputs(reference,actual,spec)
        write_json(output/'parity.json',parity)
        if not parity['passed']:
            raise ValueError('USD native parity failed: '+str(parity['differences'][:5]))
        verify_usd_bundle(bundle)
        receipt.update(status='succeeded',economic_sha256=parity['economic_sha256'])
    except BaseException as exc:
        receipt.update(status='failed',error=repr(exc))
        subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=30)
        raise
    finally:
        receipt['elapsed_seconds']=time.time()-receipt['started']
        write_json(output/'artifact_manifest.json',{p.relative_to(output).as_posix():sha256(p) for p in output.rglob('*') if p.is_file() and p.name not in ('run.json','artifact_manifest.json')})
        write_json(output/'run.json',receipt)
    return receipt


if __name__=='__main__':
    write_json(Path(sys.argv[2]),run_usd_reference(Path(sys.argv[1])))
