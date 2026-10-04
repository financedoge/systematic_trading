"""Post-selection descriptive transfer of the two already fitted USD recipes."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json, freeze_usd_bundle, run_usd_reference
from systematic_trading.research.momentum_calculation import quotes_for_data
from systematic_trading.research.usd_momentum_model import apply_usd_predictions


def calculate(args):
    root,job=args
    parent='parent-'+job['parent']+'-M'
    decisions=read_json(root/'decisions'/(parent+'.json'))
    models=read_json(root/(job['selected_from']+'-models.json'))
    for day,model in models.items():
        row=decisions[day]
        targets=apply_usd_predictions([AllocationTarget.model_validate(t) for t in row['targets']],model['predictions'])
        row['targets']=[t.model_dump(mode='json') for t in targets]
        row['diagnostic']['usd_model_available']=True
    path=root/'decisions'/(job['id']+'.json')
    if path.exists():raise FileExistsError('Immutable transfer decisions exist')
    write_json(path,decisions)
    bars=read_json(root/'bars.json');p=read_json(root/'protocol.json');days=[r['trade_date'] for r in bars['SPY']]
    quotes,sessions=quotes_for_data(bars,days,p['start'])
    for cost in p['cost_bps']:
        name=job['id']+'-cost'+str(cost);bundle=root/'bundles'/name
        spec=dict(job,models_sha256=sha256(root/(job['selected_from']+'-models.json')),
            transfer_registration_sha256=sha256(root/'transfer_registration.json'),post_selection=True)
        freeze_usd_bundle(bundle,root,spec,decisions,quotes,sessions,cost)
        output=root/'python'/(name+'.json')
        write_json(output,run_usd_reference(bundle))
        write_json(output.with_suffix('.receipt.json'),dict(status='succeeded',sha256=sha256(output),manifest_sha256=sha256(bundle/'manifest.json'),
            evaluation_start=min(models),evaluation_months=[d[:7] for d in models],matched_parent=parent,post_selection=True))
    return job['id']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);args=p.parse_args()
    jobs=[j for j in read_json(args.root/'transfer_registration.json')['jobs'] if j['recipe'].startswith('U')]
    with ProcessPoolExecutor(min(16,len(jobs))) as pool:
        for result in pool.map(calculate,[(args.root,j) for j in jobs]):print(result,flush=True)
