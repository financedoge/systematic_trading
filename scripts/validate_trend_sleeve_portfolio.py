"""Native Windows multiasset accounting fixtures for exported portfolio paths.

Targets are reconstructed at the execution open from the fractional ledger.
This is an accounting oracle, not independent causal policy/optimizer inference.
Native whole-unit sizing and cent prices differ from fractional research units.
"""
from decimal import Decimal
import gzip
import json
import shutil
import numpy as np
import research_trend_sleeve_portfolio as study
from systematic_trading.backtest.accounting import quantize_money
from systematic_trading.config import AppSettings
from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.research.momentum_replay import freeze_usd_bundle,native_parity


def main(width=False):
    arrays,v=study.load()
    output,work=study.OUT,study.WORK
    cases=('early_equal_c5d0','late_risk_c5d0','late_equal_c5d1')
    if width:
        import research_trend_sleeve_width as extension
        if study.study.clean(extension.protocol())!=study.read(extension.OUT/'protocol.json'):
            raise ValueError('Width protocol changed')
        output,work=extension.OUT,extension.WORK
        cases=('early_equal_n20_c5d0','late_risk_n30_c5d0')
    if AppSettings().lean_runtime_backend!='native':raise ValueError('Native Windows required')
    detail=json.loads(gzip.decompress((output/'detail.json.gz').read_bytes()))
    limitation=('Accounting-only execution-open target oracle reconstructed from frozen fractional portfolio fills. '
        'Native checks whole-share/cent-price cash, fills and NAV against independent app reference. '
        'Execution-open reference prices are not a tradable prior-close strategy. Does not independently validate ranks, HMMs, ERC, causality or fractional research sizing.')
    contract=work/'native-contract'
    if not contract.exists():
        shutil.copytree(study.ROOT/'src/systematic_trading',contract/'source/systematic_trading',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        study.write(contract/'protocol.json',dict(initial_cash_usd='1000000',limitations=[limitation]))
        study.write(contract/'input_manifest.json',dict(protocol=study.digest(output/'protocol.json'),detail=study.digest(output/'detail.json.gz')))
    recipe=study.read(study.frozen.RECIPE_PATH)
    image=study.read(study.ROOT/'config/strategy-monitoring.json')['calculation']['image'];receipts=[]
    for key in cases:
        era=key.split('_')[0];z=detail[key];symbols=z['symbols'];all_symbols=arrays[era+'_symbols'].tolist()
        ix=[all_symbols.index(s) for s in symbols];start=v['eras'][era]['start'];days=arrays[era+'_days'];sessions=list(map(str,days[start+1:]))
        op=arrays[era+'_open'][:,ix];cl=arrays[era+'_close'][:,ix]
        fills={}
        for f in z['fills']:fills.setdefault(f['date'],[]).append(f)
        quotes={s:{} for s in symbols};decisions={};units=np.zeros(len(symbols));cash=1
        for t in range(start+1,len(days)):
            day=str(days[t])
            for s,j in zip(symbols,range(len(symbols))):
                quotes[s][day]={k:str(quantize_money(Decimal(str(value)))) for k,value in dict(open=op[t,j],close=cl[t,j],reference=op[t,j]).items()}
            trades=fills.get(day,[])
            for f in trades:
                j=symbols.index(f['symbol']);q=f['units']*(1 if f['side']=='buy' else -1)
                units[j]+=q;cash-=q*f['price']+f['fee']
            if trades:
                capital=cash+units@op[t];weights=units*op[t]/capital
                targets=[AllocationTarget(symbol=s,target_weight=Decimal(str(float(w))),sleeve='portfolio-accounting',rationale='Frozen execution-open accounting oracle').model_dump(mode='json') for s,w in zip(symbols,weights) if w>1e-10]
                decisions[day]=dict(signal_session=str(days[t-1]),known_through=str(days[t-1]),targets=targets)
        bundle=work/'native-bundles'/key;target=work/'native'/key
        freeze_usd_bundle(bundle,contract,recipe,decisions,quotes,sessions,5)
        receipt=native_parity(bundle,target,image,cpus='2')
        actual=study.read(target/'economic.json');reference=study.read(target/'reference.json')
        a=np.array([float(r['nav']) for r in actual['nav']]);b=np.array([float(r['nav']) for r in reference['nav']]);error=float(np.max(abs(a-b)))
        if error>.011:raise ValueError('Native/reference discrepancy')
        receipts.append(dict(case=key,status=receipt['status'],sessions=len(sessions),symbols=len(symbols),
            max_native_reference_usd=error,native_return=float(a[-1]/1e6-1),fractional_return=float(z['nav'][-1]-1),
            max_native_fractional_nav_difference=float(np.max(abs(a/1e6-np.array(z['nav'][1:])))),limitation=limitation,
            receipt_sha256=study.digest(target/'run.json'),bundle_sha256=study.digest(bundle/'manifest.json')))
        study.write(output/'native-checks.json',receipts);print('Native verified',key,error,flush=True)


if __name__=='__main__':
    import sys
    main(width='--width' in sys.argv)
