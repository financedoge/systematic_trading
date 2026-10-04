import argparse
from pathlib import Path

import numpy as np

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json
from systematic_trading.research.momentum_analysis import statistics, comparison_matrix, paired_bootstrap


def analyze(root):
    p=read_json(root/'protocol.json')
    results={}
    for path in sorted((root/'python').glob('*-cost*.json')):
        if path.name.endswith('.receipt.json'):continue
        name,cost=path.stem.rsplit('-cost',1);cost=int(cost)
        receipt=read_json(path.with_suffix('.receipt.json'))
        if receipt['sha256']!=sha256(path):raise ValueError('Changed economics')
        quotes=read_json(root/'bundles'/path.stem/'quotes.json')
        results.setdefault(name,{})[cost]=statistics(read_json(path),quotes,float(p['initial_cash_usd']))
        if receipt.get('evaluation_months'):
            result=results[name][cost]
            result['complete_strategy_monthly']=dict(result['monthly'])
            result['monthly']={m:r for m,r in result['monthly'].items() if m in receipt['evaluation_months']}
            result['evaluation_start']=receipt['evaluation_start']
    write_json(root/'statistics.json',results)
    pairs={}
    matrix=comparison_matrix(p,results)
    for block in p['inference']['blocks']:
        boot=paired_bootstrap(matrix,block,p['inference']['replications'],p['inference']['seed'])
        pairs[str(block)]={c['id']:r for c,r in zip(p['comparisons'],boot,strict=True)}
    write_json(root/'paired_results.json',pairs)
    eligible=[]
    for job in p['recipes']:
        key=job['id']
        if key.startswith('parent') or key not in results:continue
        parent='parent-'+('W' if job['cadence']=='weekly' else 'M')
        difference={cost:np.array([r-results[parent][cost]['monthly'][m] for m,r in results[key][cost].get('complete_strategy_monthly',results[key][cost]['monthly']).items()]) for cost in p['cost_bps']}
        later=np.array([r-results[parent][5]['monthly'][m] for m,r in results[key][5]['monthly'].items() if m>='2023-01'])
        dd=results[parent][5]['max_drawdown']-results[key][5]['max_drawdown']
        if difference[5].mean()>0 and later.mean()>0 and difference[20].mean()>0 and dd<=.02:
            eligible.append((float(difference[5].mean()),key,job))
    eligible.sort(key=lambda r:(-r[0],r[1]))
    jobs=[]
    if eligible:
        for parent in ('activity','rolling'):
            for cadence in sorted({j['cadence'] for _,_,j in eligible[:3]}):
                jobs.append(dict(id='parent-'+parent+('-W' if cadence=='weekly' else '-M'),recipe='parent',cadence=cadence,parent=parent))
        for slot,(_,key,job) in enumerate(eligible[:3],1):
            for parent in ('activity','rolling'):
                jobs.append(dict(id=f'transfer-{slot}-{parent}',recipe=job['recipe'],cadence=job['cadence'],parent=parent,selected_from=key))
    registration=dict(rule=p['transfer_selection'],eligible=[k for _,k,_ in eligible],selected=[k for _,k,_ in eligible[:3]],jobs=jobs)
    if (root/'transfer_registration.json').exists() and read_json(root/'transfer_registration.json')!=registration:
        raise ValueError('Transfer selection changed; retain prior registration and record the correction before retrying')
    write_json(root/'transfer_registration.json',registration)
    print('selected',registration['selected'])
    for k in ['parent-M','parent-W','A1-M','A2-M','A7-M','A8-M','B1-M','B2-M','B3-M','B4-M','C0-M','C1-M','C2-M']:
        r=results[k][5]
        print(k,'CAGR',round(r['cagr']*100,3),'DD',round(r['max_drawdown']*100,3),'annual cost bp',round(r['annual_cost_bps'],2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True,type=Path)
    analyze(parser.parse_args().root)
