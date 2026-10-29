"""Native Windows accounting fixtures; scope explicitly excludes inference."""
from decimal import Decimal
import gzip,json,shutil
from pathlib import Path
import numpy as np
import research_broadtrend_blend as study
from systematic_trading.backtest.accounting import quantize_money
from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.research.momentum_replay import freeze_usd_bundle,native_parity
from systematic_trading.config import AppSettings


def main():
    if AppSettings().lean_runtime_backend!='native':raise ValueError('Native Windows required')
    work=study.ROOT/'var/research/broadtrend-fr25-20261029-v1';contract=work/'native-contract'
    detail=json.loads(gzip.decompress((study.OUT/'detail.json.gz').read_bytes()))
    panel=study.parent.frozen._load_panel();all_days=panel['days'].astype(str);symbols=panel['symbols'].tolist()
    limitation='Accounting-only execution-open oracle. Independent native LEAN and app whole-share/cent-price accounting; not independent causal HMM inference or validation of fractional strategy execution.'
    if not contract.exists():
        shutil.copytree(study.ROOT/'src/systematic_trading',contract/'source/systematic_trading',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        study.write(contract/'protocol.json',dict(initial_cash_usd='1000000',limitations=[limitation]))
        study.write(contract/'input_manifest.json',dict(protocol=study.digest(study.OUT/'protocol.json'),detail=study.digest(study.OUT/'detail.json.gz')))
    recipe=study.read(study.parent.frozen.RECIPE_PATH);image=study.read(study.ROOT/'config/strategy-monitoring.json')['calculation']['image'];receipts=[]
    for key in ['broadtrend_c5d0','blend_c5d0']:
        z=detail[key];ix=np.searchsorted(all_days,z['days']);op=panel['open'][ix];cl=panel['close'][ix]
        units=np.zeros(len(symbols));cash=1.;by={};quotes={s:{} for s in symbols};decisions={}
        for f in z['fills']:by.setdefault(f['date'],[]).append(f)
        for t,day in enumerate(z['days'][1:],1):
            for j,s in enumerate(symbols):quotes[s][day]={k:str(quantize_money(Decimal(str(v)))) for k,v in dict(open=op[t,j],close=cl[t,j],reference=op[t,j]).items()}
            trades=by.get(day,[])
            for f in trades:
                j=symbols.index(f['symbol']);q=f['units']*(1 if f['side']=='buy' else -1);units[j]+=q;cash-=q*f['price']+f['fee']
            if trades:
                w=units*op[t]/(cash+units@op[t]);targets=[AllocationTarget(symbol=s,target_weight=Decimal(str(float(v))),sleeve='accounting-fixture',rationale=limitation).model_dump(mode='json') for s,v in zip(symbols,w) if v>1e-10]
                decisions[day]=dict(signal_session=z['days'][t-1],known_through=z['days'][t-1],targets=targets)
        bundle=work/'native-bundles'/key;output=work/'native'/key
        freeze_usd_bundle(bundle,contract,recipe,decisions,quotes,z['days'][1:],5)
        receipt=native_parity(bundle,output,image,cpus='2')
        a=study.read(output/'economic.json');ref=study.read(output/'reference.json')
        error=float(np.max(np.abs(np.array([float(x['nav']) for x in a['nav']])-np.array([float(x['nav']) for x in ref['nav']]))))
        if error>.011:raise ValueError('Native/reference NAV difference')
        receipts.append(dict(case=key,status=receipt['status'],max_native_reference_usd=error,limitation=limitation,
            receipt_sha256=study.digest(output/'run.json'),bundle_sha256=study.digest(bundle/'manifest.json')))
        study.write(study.OUT/'native-checks.json',receipts);print('Native verified',key,error,flush=True)


if __name__=='__main__':main()
