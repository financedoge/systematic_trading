"""Inspect frozen mode fits; future exit returns are diagnostics, never inputs."""
import json

import numpy as np

import research_trend_modes as study
import research_multiscale_modes as next_study


def main():
    fits=study.verified();rows=json.loads((study.OUT/'asset-results.json').read_text());details=json.loads((study.OUT/'diagnostics.json').read_text())
    results={}
    for symbol in ('GLD','CORN','EWA','TLT','MCHI'):
        f=study.model.Features.build(study.study.load_asset(symbol))
        for domain in ('short','long'):
            p=fits[symbol][domain+'_late']['selected']['selected']['parameters'];cl=study.model.classify(f,p)
            q=p['down'];feature=f.cache[q['length']];z=feature[p['method']]
            period=f.days>=np.datetime64('2026-01-01')
            conditions={'down_strength':z['down']>=q['strength'],'fit_quality':z['quality']>=q['quality'],
                'selling_pressure':-feature['pressure']>=q['pressure'],'activity':feature['activity']>=q['activity']}
            combined=conditions['down_strength']&conditions['fit_quality']
            if p['volume']:combined&=conditions['selling_pressure']&conditions['activity']
            conditions['joint_daily_conditions']=combined;conditions['confirmed_down']=cl['masks']['down']
            counts={}
            for k,mask in conditions.items():
                ix=np.flatnonzero(mask&period);counts[k]=dict(sessions=len(ix),first=str(f.days[ix[0]]) if len(ix) else None)
            if p['volume']:
                price=study.model.confirmed(conditions['down_strength']&conditions['fit_quality'],q['confirm'])
                ix=np.flatnonzero(price&period)
                counts['price_conditions_without_volume']=dict(sessions=len(ix),first=str(f.days[ix[0]]) if len(ix) else None)
            snapshots=[]
            for date in ('2026-03-31','2026-06-30','2026-10-16'):
                t=int(np.searchsorted(f.days,np.datetime64(date),side='right'))-1
                snapshots.append(dict(date=str(f.days[t]),close=f.close[t],down_strength=z['down'][t],quality=z['quality'][t],
                    selling_pressure=-feature['pressure'][t],activity=feature['activity'][t],state=int(cl['state'][t])))
            trades=[]
            for ep in details[symbol+'_'+domain]['trades']:
                e=dict(ep);x=e['exit_index']
                if x is not None:
                    for horizon in (5,21):
                        e['post_exit_'+str(horizon)+'_return']=f.close[x+horizon]/f.open[x]-1 if x+horizon<len(f.days) else None
                    a,b=max(0,x-10),min(len(f.days),x+11)
                    low,high=f.close[a:b].min(),f.close[a:b].max()
                    e['retrospective_local_price_percentile']=(f.open[x]-low)/(high-low) if high>low else None
                trades.append(e)
            metric=next(r for r in rows if r['symbol']==symbol and r['domain']==domain and r['era']=='late' and r['variant']=='selected' and r['cost_bp']==5 and r['delay']==0)
            results[symbol+'_'+domain]=dict(parameters=p,metrics=metric,down_conditions_2026=counts,snapshots=snapshots,trades=trades,
                warning='Post-exit returns/local ranges use future prices solely for diagnosis. They are not entry/exit inputs. Previous strategy has no protective stop.')
    next_study.write(next_study.OUT/'parent-case-audit.json',results)
    for key,r in results.items():
        closed=[e for e in r['trades'] if e['exit']]
        rebound=[e for e in closed if e.get('post_exit_21_return') is not None]
        print(key,'return',round(100*r['metrics']['cumulative'],2),'closed',len(closed),'positive21afterexit',sum(e['post_exit_21_return']>0 for e in rebound),'/',len(rebound))


if __name__=='__main__':main()
