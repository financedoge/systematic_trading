"""Run the two reserved USD recipes only after governed vintage publication."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
import os
from pathlib import Path

import numpy as np

from systematic_trading.config import AppSettings
from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.market_data.analytics_store import AnalyticsStore
from systematic_trading.research.momentum_replay import read_json, checked_files, freeze_usd_bundle, run_usd_reference
from systematic_trading.research.momentum_calculation import quotes_for_data
from systematic_trading.research.usd_momentum_model import ridge_predict, apply_usd_predictions


def calculate(args):
    root,key=args
    registration=read_json(root/'usd_registration.json')
    inputs=read_json(root/'usd_inputs.json')
    if sha256(root/'usd_inputs.json')!=registration['inputs_sha256']:raise ValueError('Changed USD inputs')
    records=inputs['training_records'];current=inputs['current_features']
    decisions=read_json(root/'decisions/parent-M.json');models={};available=[]
    for day,row in decisions.items():
        fitted=ridge_predict(records,current[day],row['known_through'],key=='U1-M') if day in current else None
        row['diagnostic']['usd_model_available']=fitted is not None
        if fitted is None:continue
        models[day]=fitted;available.append(day)
        targets=apply_usd_predictions([AllocationTarget.model_validate(t) for t in row['targets']],fitted['predictions'])
        row['targets']=[t.model_dump(mode='json') for t in targets]
        row['diagnostic']['usd_vintage']=inputs['vintages'][day]
    if not available:raise ValueError('No USD fit has 60 admissible training months')
    write_json(root/'decisions'/(key+'.json'),decisions)
    write_json(root/(key+'-models.json'),models)
    bars=read_json(root/'bars.json');days=[r['trade_date'] for r in bars['SPY']]
    protocol=read_json(root/'protocol.json');quotes,sessions=quotes_for_data(bars,days,protocol['start'])
    for cost in protocol['cost_bps']:
        name=key+'-cost'+str(cost)
        bundle=root/'bundles'/name
        freeze_usd_bundle(bundle,root,dict(id=key,recipe=key[:2],cadence='monthly',
            usd_registration_sha256=sha256(root/'usd_registration.json'),evaluation_start=available[0],
            earlier_behavior='unchanged parent until sufficient matched USD training history'),decisions,quotes,sessions,cost)
        path=root/'python'/(name+'.json')
        if path.exists():raise FileExistsError('Immutable USD economic output exists')
        write_json(path,run_usd_reference(bundle))
        write_json(path.with_suffix('.receipt.json'),dict(sha256=sha256(path),manifest_sha256=sha256(bundle/'manifest.json'),
            status='succeeded',evaluation_start=available[0],evaluation_months=[d[:7] for d in available]))
    return dict(id=key,first_fit=available[0],last_fit=available[-1],fit_count=len(available),available_months=[d[:7] for d in available])


def run(root):
    checked_files(root,'input_manifest.json');checked_files(root,'feature_manifest.json')
    publication=AnalyticsStore.from_settings(AppSettings()).latest('governance/usd-broad-index')
    if publication is None:raise ValueError('USD input is not published')
    import json
    governed=Path(json.loads(publication['provenance'])['root'])
    if sha256(governed/'manifest.json')!=publication['version']:raise ValueError('USD batch hash mismatch')
    checked_files(governed,'manifest.json')
    snapshots=read_json(governed/'snapshots.json')
    protocol=read_json(root/'protocol.json');bars=read_json(root/'bars.json');frames=read_json(root/'features.json')
    decisions=read_json(root/'decisions/parent-M.json');days=[r['trade_date'] for r in bars['SPY']]
    current={};vintages={}
    for snapshot in snapshots:
        day=snapshot['decision_date']
        if day not in decisions:continue
        known=decisions[day]['known_through']
        if snapshot['known_through']!=known or snapshot['vintage_date']>=known:
            raise ValueError('USD signal availability differs from decision cutoff')
        frame=frames[day];i=days.index(day)
        current[day]={}
        for s,rows in bars.items():
            prices=np.array([float(r['close']) for r in rows[i-64:i]])
            vol=float(np.std(prices[1:]/prices[:-1]-1,ddof=1)*np.sqrt(252))
            current[day][s]=dict(S=float(frame['horizons']['A6'][s]),L=float(frame['horizons']['A7'][s]),vol63=vol,**snapshot['features'])
        vintages[day]=dict(vintage=snapshot['vintage_date'],last_observation=snapshot['observation_date'],
                            available_at=snapshot['available_at'],source_sha256=snapshot['source_sha256'])
    training=[]
    ordered=list(decisions)
    price={s:{r['trade_date']:float(r['close']) for r in rows} for s,rows in bars.items()}
    for day,next_day in zip(ordered,ordered[1:]):
        if day not in current:continue
        known=decisions[day]['known_through'];end=decisions[next_day]['known_through']
        returns={s:price[s][end]/price[s][known]-1 for s in bars};mean=sum(returns.values())/len(returns)
        training.extend(dict(symbol=s,known_through=known,label_end=end,label=returns[s]-mean,features=current[day][s]) for s in bars)
    inputs=dict(training_records=training,current_features=current,vintages=vintages)
    if (root/'usd_registration.json').exists():
        if any(p.name.startswith(('U0-', 'U1-')) for p in (root/'python').glob('*-cost*.json')):
            raise FileExistsError('USD results already exist; do not overwrite registration')
        archive=root/'usd_preparation_attempts';archive.mkdir(exist_ok=True)
        import shutil
        shutil.copyfile(root/'usd_registration.json',archive/(sha256(root/'usd_registration.json')+'.json'))
    write_json(root/'usd_inputs.json',inputs)
    write_json(root/'usd_registration.json',dict(registered_at=datetime.now(UTC).isoformat(),status='prerequisite now published; reserved U0/U1 activated',
        protocol_sha256=sha256(root/'protocol.json'),usd_batch=publication['version'],publication=publication,
        inputs_sha256=sha256(root/'usd_inputs.json'),model=protocol['usd_model'],
        code={str(f):sha256(f) for f in [Path(__file__),Path('src/systematic_trading/research/usd_momentum_model.py'),Path('src/systematic_trading/research/usd_index_governance.py')]},
        evidence='Prior-day ALFRED snapshots of post-February-2019 DTWEXBGS; each USD horizon uses a single vintage; no goods-only index splice.',
        evaluation='Both complete portfolios follow the same parent before models become available. Paired inference only uses months where BOTH models have >=60 completed monthly labels. Other recipes retain their full registered sample.',
        bootstrap='Joint calendar blocks over the full calendar; unavailable USD months masked, never treated as extra zero-return evidence.',
        usd_unavailable_at_initial_registration=True,performance_reviewed_before_activation=False))
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
    with ProcessPoolExecutor(2) as pool:results=list(pool.map(calculate,[(root,'U0-M'),(root,'U1-M')]))
    if results[0]['available_months']!=results[1]['available_months']:raise ValueError('USD samples differ')
    write_json(root/'usd_calculation_receipt.json',dict(results=results,registration_sha256=sha256(root/'usd_registration.json')))
    print(results)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);run(p.parse_args().root)
