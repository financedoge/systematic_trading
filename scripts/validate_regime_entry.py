"""Native Windows checks of single-ETF signals under app whole-unit sizing."""
from decimal import Decimal
import json
import shutil

import numpy as np

import research_regime_entry as study
from systematic_trading.backtest.accounting import quantize_money
from systematic_trading.config import AppSettings
from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.research.momentum_replay import freeze_usd_bundle, native_parity


def main():
    fits,calibration,initial,exits,selected=study.verified()
    if AppSettings().lean_runtime_backend!='native':raise ValueError('Native Windows required')
    contract=study.WORK/'native-contract'
    if not contract.exists():
        shutil.copytree(study.ROOT/'src/systematic_trading',contract/'source/systematic_trading',
                        ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        study.write(contract/'protocol.json',dict(initial_cash_usd='1000000',limitations=[
            'Single ETF only; no portfolio strategy. Frozen causal signals. Whole-unit app sizing/cent prices differ from fractional research accounting. No broker authority.']))
        study.write(contract/'input_manifest.json',dict(protocol_sha256=study.prior.study.digest(study.OUT/'protocol.json'),
            result_sha256=study.prior.study.digest(study.OUT/'asset-results.json')))
    rows=json.loads((study.OUT/'asset-results.json').read_text())
    weakest=min((r for r in rows if r['era']=='late' and r['arm']=='guarded' and r['cost_bp']==5 and r['delay']==0 and r['symbol']!='BIL'),key=lambda r:r['cumulative'])['symbol']
    recipe=json.loads(study.prior.study.frozen.RECIPE_PATH.read_text())
    image=json.loads((study.ROOT/'config/strategy-monitoring.json').read_text())['calculation']['image']
    receipts=[]
    for symbol,delay in dict.fromkeys([('INDA',0),('GLD',1),(weakest,0)]):
        era,_,first,last=study.ERAS[0]
        if era!='late':raise ValueError('Explicit late chronology expected')
        f,cl,sim,start=study.replay(symbol,era,fits,selected,delay=delay)
        lo=start+1
        decisions={};quotes={symbol:{}};sessions=list(map(str,f.days[lo:]))
        fills={z['session']:z for z in sim['fills']}
        for t in range(lo,len(f.days)):
            day=str(f.days[t]);signal=t-1-delay if t in fills else t-1
            quotes[symbol][day]={k:str(quantize_money(Decimal(str(v)))) for k,v in
                dict(open=f.open[t],close=f.close[t],reference=f.close[signal]).items()}
            if t in fills:
                targets=[] if fills[t]['side']=='sell' else [AllocationTarget(symbol=symbol,target_weight=Decimal(1),
                    sleeve='single-etf-regime',rationale='Frozen causal single-ETF policy signal').model_dump(mode='json')]
                decisions[day]=dict(signal_session=str(f.days[signal]),known_through=str(f.days[signal]),targets=targets)
        key=f'{symbol}_guarded_c5d{delay}'
        bundle,target=study.WORK/'native-bundles'/key,study.WORK/'native'/key
        freeze_usd_bundle(bundle,contract,recipe,decisions,quotes,sessions,5)
        receipt=native_parity(bundle,target,image,cpus='2')
        actual=json.loads((target/'economic.json').read_text());reference=json.loads((target/'reference.json').read_text())
        native_nav=np.array([float(r['nav']) for r in actual['nav']]);reference_nav=np.array([float(r['nav']) for r in reference['nav']])
        diff=float(np.max(np.abs(native_nav-reference_nav)))
        if diff>.011:raise ValueError('Native/reference discrepancy')
        receipts.append(dict(symbol=symbol,delay=delay,status=receipt['status'],max_native_reference_dollars=diff,
            fractional_return=float(sim['nav'][-1]-1),app_whole_unit_return=float(native_nav[-1]/1e6-1),
            max_fractional_nav_difference=float(np.max(np.abs(native_nav/1e6-sim['nav'][lo:]))),
            limitation='Native validates whole-unit application accounting of frozen single-ETF signals, not independent fitting or inference of the HMM.',
            receipt_sha256=study.prior.study.digest(target/'run.json'),bundle_sha256=study.prior.study.digest(bundle/'manifest.json')))
        study.write(study.OUT/'native-checks.json',receipts)
        print('Verified single ETF',symbol,delay,diff,flush=True)


if __name__=='__main__':main()
