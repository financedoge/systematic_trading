"""Post-evaluation description only; never feeds model selection."""
from collections import Counter
import gzip
import json
from pathlib import Path
import numpy as np
import research_entry_value as study
import build_entry_value_report as report


def main():
    study.verified()
    rows=json.loads((study.OUT/'asset-results.json').read_text());fits=json.loads((study.OUT/'fits.json').read_text())
    charts=json.loads(gzip.decompress((study.OUT/'chart-data.json.gz').read_bytes()))
    primary=[r for r in rows if r['cost_bp']==5 and r['delay']==0 and r['symbol']!='BIL']
    sums=report.template.summary(rows);study.write(study.OUT/'summary.json',sums)
    result=dict(eras={},cases={},semantics={})
    for era,*_ in study.ERAS:
        r=[x for x in primary if x['era']==era and x['arm']=='value'];full=[x for x in r if fits[x['symbol']][era]['forecast']['kind']=='full']
        result['eras'][era]=dict(weakest=min(r,key=lambda x:x['cumulative'])['symbol'],
            forecast_selection=dict(Counter(f"{fits[x['symbol']][era]['forecast']['kind']}_{fits[x['symbol']][era]['forecast']['memory']}" for x in r)),
            horizon=dict(Counter(str(x['horizon']) for x in r)),zero_closed=[x['symbol'] for x in r if x['closed_trades']==0],
            median_forecast_ic=float(np.median([x['forecast']['ic'] for x in r if x['forecast']['ic'] is not None])),
            full_count=len(full),full_beats_intercept_return_mse=sum(x['forecast']['return_mse']<x['forecast_null']['return_mse'] for x in full),
            full_median_return_mse_ratio=float(np.median([x['forecast']['return_mse']/x['forecast_null']['return_mse'] for x in full])) if full else None,
            median_forecast_return=float(np.median([x['forecast']['mean_predicted_return'] for x in r])),
            median_actual_return=float(np.median([x['forecast']['mean_return'] for x in r])),
            median_downside_bias=float(np.median([x['forecast']['mean_predicted_downside']-x['forecast']['mean_downside'] for x in r])),
            passed={a:sum(x['passed'] for x in sums if x['arm']==a and x['era']==era) for a in ('hmm','value')})
    for key,c in charts.items():
        q=c['selection'];h=q['hmm']['model'];mean=np.asarray(h['means']);var=np.asarray(h['variance'])
        points=np.array([-10.,-1.,0,1,10])[:,None];ll=study.model.parent.trend_hmm.emissions(points,mean,var)
        residual=float(np.max(np.abs((ll[:,2]-ll[:,0])-2*mean[2,0]*points[:,0]/var[0,0])))
        assert residual<1e-9 and var[0,0]==var[2,0] and mean[0,0]==-mean[2,0]
        result['semantics'][key]=dict(max_log_odds_identity_error=residual,directional_variance=float(var[0,0]),amplitude=float(mean[2,0]))
        opportunities=[];days=c['days'];value=c['arms']['value']
        for t in c['arms']['hmm']['trades']:
            idx=days.index(t['entry_date'])-1
            at=lambda field:value[field][idx] if idx>=0 else None
            opportunities.append(dict(entry=t['entry_date'],exit=t['exit_date'],baseline_trade_return=t.get('net_return'),
                gate_would_allow=at('gate'),predicted_return=at('predicted_return'),predicted_downside=at('predicted_downside'),utility=at('utility')))
        result['cases'][key]=dict(rows=[x for x in primary if f"{x['symbol']}_{x['era']}"==key],forecast=q['forecast'],
            baseline_entry_checks=opportunities,worst_value_trades=sorted([t for t in value['trades'] if t.get('net_return') is not None],key=lambda t:t['net_return'])[:5])
    result['provenance']=dict(protocol=study.prior.study.digest(study.OUT/'protocol.json'),results=study.prior.study.digest(study.OUT/'asset-results.json'),script=study.prior.study.digest(Path(__file__)))
    study.write(study.OUT/'failure-audit.json',result)
    print(json.dumps(result['eras'],indent=2))
    for era in ('late','early'):
        for arm in study.model.ARMS:
            x=next(x for x in sums if x['era']==era and x['arm']==arm and x['cost_bp']==5 and x['delay']==0)
            print(era,arm,json.dumps(x))
    for s in ('GLD','WEAT','TLT','INDA','MCHI','ITA'):
        for era in ('late','early'):
            print(s,era,[(x['arm'],round(x['cumulative']*100,2),round(x['sharpe'],3),x['closed_trades']) for x in primary if x['symbol']==s and x['era']==era])


if __name__=='__main__':main()
