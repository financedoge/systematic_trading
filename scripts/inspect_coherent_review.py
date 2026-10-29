"""Describe the frozen evaluation and verify the actual review decisions."""
import gzip
import json
import numpy as np
import research_coherent_review as study


def main():
    rows=json.loads((study.OUT/'asset-results.json').read_text());fits=json.loads((study.OUT/'fits.json').read_text())
    forecast=json.loads((study.OUT/'forecast-diagnostics.json').read_text());charts=json.loads(gzip.decompress((study.OUT/'chart-data.json.gz').read_bytes()))
    primary=[r for r in rows if r['cost_bp']==5 and r['delay']==0 and r['symbol']!='BIL'];pool=[];enabled=[];cases={}
    for era,*_ in study.ERAS:
        for arm,kind in [('stop','price'),('review','volume')]:
            rr=[r for r in primary if r['era']==era and r['arm']==arm];fr=[r for r in forecast if r['era']==era and r['arm']==arm and r['symbol']!='BIL']
            ic=[r['ic'] for r in fr if r['ic'] is not None]
            pool.append(dict(era=era,arm=arm,enabled=sum(r['enabled'] for r in rr),cases=len(rr),
                **{k:sum(r[k] for r in rr) for k in ('entry_invalidations','recovery_closed','recovery_wins','one_session_trades')},
                median_cumulative=float(np.median([r['cumulative'] for r in rr])),
                constant_mse=float(np.median([r['constant_mse'] for r in fr])),fixed_mse=float(np.median([r['fixed_mse'] for r in fr])),
                ic=float(np.median(ic)) if ic else None,ic_defined=len(ic),
                fixed_beats_constant=sum(r['fixed_mse']<r['constant_mse']-1e-12 for r in fr)))
            for r in rr:
                if not r['enabled']:continue
                f=fits[r['symbol']][era]['models'][kind];fr_=next(q for q in fr if q['symbol']==r['symbol'])
                baseline=next(q for q in primary if q['symbol']==r['symbol'] and q['era']==era and q['arm']=='baseline')
                stress=[]
                for v in rows:
                    if v['symbol']==r['symbol'] and v['era']==era and v['arm']==arm:
                        b=next(q for q in rows if q['symbol']==r['symbol'] and q['era']==era and q['arm']=='baseline' and q['cost_bp']==v['cost_bp'] and q['delay']==v['delay'])
                        stress.append(dict(cost=v['cost_bp'],delay=v['delay'],return_gain=v['cumulative']-b['cumulative'],sharpe_gain=v['sharpe']-b['sharpe'],drawdown_gain=v['maxdd']-b['maxdd']))
                enabled.append(dict(symbol=r['symbol'],era=era,arm=arm,training_gain=f['selection']['relative_loss_gain'],
                    ridge=f['model']['ridge'],forecast=fr_,baseline=baseline,candidate=r,stress=stress))
    weakest=json.loads((study.OUT/'weakest-cases.json').read_text())
    focus={('CORN','late'),('MCHI','early'),('WEAT','late'),('GLD','late'),('XLU','late'),('XLU','early'),('ITA','late'),('MBB','late'),*((r['symbol'],e) for e,r in weakest.items())}
    for symbol,era in focus:
        c=charts[symbol+'_'+era];arm='stop' if symbol=='XLU' else 'review';a=c['arms'][arm]
        closed=[e for e in a['trades'] if e['exit_index'] is not None]
        pairs=[]
        for e in closed:
            old=next((o for o in c['arms']['baseline']['trades'] if o['entry_date']==e['entry_date']),None)
            if old and old.get('net_return') is not None and old['exit_date']!=e['exit_date']:
                pairs.append(dict(entry=e['entry_date'],old_exit=old['exit_date'],new_exit=e['exit_date'],old_return=old['net_return'],new_return=e['net_return'],gain=e['net_return']-old['net_return']))
        cases[symbol+'_'+era]=dict(arm=arm,models=fits[symbol][era]['models'],paired_exits=sorted(pairs,key=lambda r:r['gain']),
            metrics=[r for r in primary if r['symbol']==symbol and r['era']==era],
            largest_losses=sorted(closed,key=lambda e:e['net_return'])[:5],largest_winners=sorted(closed,key=lambda e:e['net_return'],reverse=True)[:5])
    study.write(study.OUT/'inspection.json',dict(pool=pool,enabled=enabled,cases=cases,
        limitation='Descriptive analysis of frozen results. No post-evaluation changes or additional parameter selection.'))
    print(json.dumps(study.clean(dict(pool=pool,enabled=[{k:v for k,v in r.items() if k not in ('baseline','candidate')} for r in enabled],
        losses={k:[{q:t[q] for q in ('entry_date','exit_date','net_return','exit_reason','initial_risk_fraction')} for t in v['largest_losses'][:3]] for k,v in cases.items()})),indent=2))


if __name__=='__main__':main()
