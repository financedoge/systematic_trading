"""Independent native accounting of frozen ordered intraday event fixtures.

The existing LEAN daily USD contract uses one decision per session. We explicitly
serialize each research fill and closing mark onto a synthetic event calendar.
These are accounting fixtures, NOT substituted research market histories and NOT
an independent native validation of OHLC stop executability or inference.
"""
from decimal import Decimal
import gzip
import json
import shutil
import numpy as np
import research_coherent_review as study
from systematic_trading.backtest.accounting import quantize_money
from systematic_trading.config import AppSettings
from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.research.momentum_replay import freeze_usd_bundle,native_parity


def main():
    study.verified()
    if AppSettings().lean_runtime_backend!='native':raise ValueError('Native Windows required')
    limitation='Synthetic accounting event clock: each frozen fill and daily close mark occupies one engine session. Prices at fill events are modeled fills, not market opens. Validates ordering, sizing, fees and NAV only; does not independently prove intraday fills or HMM/learning.'
    contract=study.WORK/'native-event-contract'
    if not contract.exists():
        shutil.copytree(study.ROOT/'src/systematic_trading',contract/'source/systematic_trading',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        study.write(contract/'protocol.json',dict(initial_cash_usd='1000000',limitations=[limitation]))
        study.write(contract/'input_manifest.json',dict(protocol=study.prior.study.digest(study.OUT/'protocol.json'),charts=study.prior.study.digest(study.OUT/'chart-data.json.gz')))
    charts=json.loads(gzip.decompress((study.OUT/'chart-data.json.gz').read_bytes()));weakest=json.loads((study.OUT/'weakest-cases.json').read_text())
    recipe=json.loads(study.prior.study.frozen.RECIPE_PATH.read_text());image=json.loads((study.ROOT/'config/strategy-monitoring.json').read_text())['calculation']['image'];receipts=[]
    for symbol,era in dict.fromkeys([('CPER','late'),('IWM','late'),(weakest['late']['symbol'],'late'),(weakest['early']['symbol'],'early')]):
        c=charts[symbol+'_'+era];a=c['arms']['review'];fills={};events=[]
        for e in a['fills']:fills.setdefault(e['day'],[]).append(e)
        for day,price,nav in zip(c['days'],c['close'],a['nav']):
            if day<c['evaluation_start']:continue
            events += [dict(real_day=day,kind=e.get('phase','open'),side=e['side'],price=e['price']) for e in fills.get(day,[])]
            events.append(dict(real_day=day,kind='close_mark',side=None,price=price,fractional_nav=nav/100))
        # Use actual exchange session labels only as a clock for ordered synthetic events.
        calendar=study.prior.study.load_asset(symbol)['days'];sessions=list(map(str,calendar[:len(events)]))
        assert len(sessions)==len(events)
        quotes={symbol:{}};decisions={};mapping=[]
        for j,(day,e) in enumerate(zip(sessions,events)):
            price=str(quantize_money(Decimal(str(e['price']))));quotes[symbol][day]=dict(open=price,close=price,reference=price)
            if e['side']:
                target=[] if e['side']=='sell' else [AllocationTarget(symbol=symbol,target_weight=Decimal(1),sleeve='accounting-fixture',rationale='Frozen ordered modeled fill, synthetic event clock').model_dump(mode='json')]
                known=sessions[max(0,j-1)];decisions[day]=dict(signal_session=known,known_through=known,targets=target)
            mapping.append(dict(event_session=day,**e))
        key=f'{symbol}_{era}_review_event_accounting';bundle=study.WORK/'native-bundles'/key;target=study.WORK/'native'/key
        freeze_usd_bundle(bundle,contract,recipe,decisions,quotes,sessions,5)
        study.write(study.WORK/(key+'-mapping.json'),mapping)
        receipt=native_parity(bundle,target,image,cpus='2')
        actual=json.loads((target/'economic.json').read_text());reference=json.loads((target/'reference.json').read_text())
        native=np.array([float(r['nav']) for r in actual['nav']]);ref=np.array([float(r['nav']) for r in reference['nav']]);diff=float(np.max(abs(native-ref)))
        assert diff<=.011
        marked=np.array([i for i,e in enumerate(events) if e['kind']=='close_mark']);frac=np.array([events[i]['fractional_nav'] for i in marked])
        receipts.append(dict(symbol=symbol,era=era,status=receipt['status'],events=len(events),fills=sum(e['side'] is not None for e in events),
            max_native_reference_dollars=diff,max_whole_unit_vs_fractional_nav=float(np.max(abs(native[marked]/1e6-frac))),
            native_return=float(native[-1]/1e6-1),fractional_return=float(frac[-1]-1),limitation=limitation,
            receipt_sha256=study.prior.study.digest(target/'run.json'),bundle_sha256=study.prior.study.digest(bundle/'manifest.json'),
            event_mapping_sha256=study.prior.study.digest(study.WORK/(key+'-mapping.json'))))
        study.write(study.OUT/'native-checks.json',receipts);print('Native event accounting',symbol,era,diff,flush=True)


if __name__=='__main__':main()
