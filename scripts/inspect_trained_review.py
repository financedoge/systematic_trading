"""Post-evaluation diagnosis only. Does not change fitted models or trades."""
from collections import Counter
import gzip
import json
import numpy as np
import research_trained_review as study


def main():
    charts = json.loads(gzip.decompress((study.OUT/'chart-data.json.gz').read_bytes()))
    rows = json.loads((study.OUT/'asset-results.json').read_text())
    fits = json.loads((study.OUT/'fits.json').read_text())
    forecasts = json.loads((study.OUT/'forecast-diagnostics.json').read_text())
    selected = [r for r in rows if r['cost_bp'] == 5 and r['delay'] == 0 and r['symbol'] != 'BIL']
    lookup = {(r['symbol'], r['era'], r['arm']): r for r in selected}
    pool = []
    prediction = []
    for era, *_ in study.ERAS:
        for arm, kind in [('stop', 'price'), ('review', 'volume')]:
            rr = [r for r in selected if r['era'] == era and r['arm'] == arm]
            active = [r for r in rr if r['enabled']]
            alltrades = [e for r in rr for e in charts[r['symbol']+'_'+era]['arms'][arm]['trades'] if e['exit_index'] is not None]
            pool.append(dict(era=era, arm=arm, enabled=len(active), cases=len(rr),
                **{k:sum(r[k] for r in rr) for k in ('recovery_closed','recovery_wins','entry_invalidations','cancelled_recoveries','handoffs')},
                one_session_trades=sum(e['exit_index']-e['entry_index']==1 for e in alltrades), closed_trades=len(alltrades),
                active_constant_hold=sum(fits[r['symbol']][era]['models'][kind]['models']['hold']['ridge'] is None for r in active),
                median_return=float(np.median([r['cumulative'] for r in rr])),
                median_paired_return_gain=float(np.median([r['cumulative']-lookup[r['symbol'],era,'baseline']['cumulative'] for r in rr]))))
            for task in ('hold','recover'):
                ff=[r[task] for r in forecasts if r['era']==era and r['arm']==arm and r['symbol']!='BIL' and r[task]['count']]
                ic = lambda key: [r[key]['ic'] for r in ff if r[key]['ic'] is not None]
                prediction.append(dict(era=era,arm=arm,task=task,etfs=len(ff),observations=sum(r['count'] for r in ff),
                    loss_median={k:float(np.median([r[k]['loss'] for r in ff])) for k in ('constant','fixed','shadow')},
                    fixed_beats_constant=sum(r['fixed']['loss']<r['constant']['loss']-1e-12 for r in ff),
                    shadow_beats_fixed=sum(r['shadow']['loss']<r['fixed']['loss'] for r in ff),
                    ic_median={k:float(np.median(ic(k))) if ic(k) else None for k in ('fixed','shadow')},
                    ic_defined={k:len(ic(k)) for k in ('fixed','shadow')}))
    cases={}
    for symbol,era in [('WEAT','late'),('MCHI','early'),('GLD','late'),('IWM','late'),('CPER','late'),('SLV','late'),('DBA','late'),('SOXX','late'),('DBB','early')]:
        c=charts[symbol+'_'+era];f=fits[symbol][era]['models']['volume'];a=c['arms']['review'];closed=[e for e in a['trades'] if e['exit_index'] is not None]
        models={t:{k:f['models'][t][k] for k in ('ridge','groups','rows')} | {'intercept':f['models'][t]['beta'][0]} for t in ('hold','recover')}
        hold=np.array([v for v in a['hold_value'] if v is not None]);recover=np.array([v for v in a['recover_value'] if v is not None])
        cases[symbol+'_'+era]=dict(margin=f['margin'],models=models,metrics={arm:lookup[symbol,era,arm] for arm in study.model.ARMS},
            hold_range=[float(hold.min()),float(hold.max())] if len(hold) else None,recover_range=[float(recover.min()),float(recover.max())] if len(recover) else None,
            one_session_trades=sum(e['exit_index']-e['entry_index']==1 for e in closed),
            exit_reasons=dict(Counter(e['exit_reason'] for e in closed)),
            initial_trades=closed[:6],largest_losses=sorted(closed,key=lambda e:e['net_return'])[:5],
            largest_winners=sorted(closed,key=lambda e:e['net_return'],reverse=True)[:5])
    study.write(study.OUT/'inspection.json',dict(pool=pool,prediction=prediction,cases=cases,
        limitation='Descriptive audit of already inspected evaluation. No additional fit, parameter change or post-hoc variant selection.'))
    print(json.dumps(study.clean(dict(pool=pool,prediction=prediction,
        cases={k:{q:v[q] for q in ('margin','models','hold_range','recover_range','one_session_trades','exit_reasons')} for k,v in cases.items()})),indent=2))


if __name__=='__main__':main()
