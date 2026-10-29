"""Descriptive attribution; no post-evaluation strategy selection."""
import gzip
import json
import numpy as np
import research_stop_review as study


def summary(rows,reference='baseline'):
    lookup={(r['symbol'],r['era'],r['arm'],r['cost_bp'],r['delay']):r for r in rows};out=[]
    for era,*_ in study.ERAS:
        for cost,delay in study.FRICTIONS:
            for arm in sorted(set(r['arm'] for r in rows)):
                a=[r for r in rows if r['era']==era and r['arm']==arm and r['cost_bp']==cost and r['delay']==delay and r['symbol']!='BIL']
                if not a:continue
                b=[lookup[r['symbol'],era,reference,cost,delay] for r in a]
                sg=float(np.median([x['sharpe'] for x in a])-np.median([x['sharpe'] for x in b]));qg=float(np.quantile([x['cagr'] for x in a],.25)-np.quantile([x['cagr'] for x in b],.25))
                guard=float(np.mean([x['cagr']>=y['cagr']-.01 and x['maxdd']>=y['maxdd']-.02 for x,y in zip(a,b)]))
                out.append(dict(era=era,cost_bp=cost,delay=delay,arm=arm,reference=reference,cases=len(a),
                    median_sharpe=float(np.median([x['sharpe'] for x in a])),median_cagr=float(np.median([x['cagr'] for x in a])),
                    lower_quartile_cagr_gain=qg,median_sharpe_gain=sg,guard_fraction=guard,passed=sg>0 and qg>0 and guard>=.9,
                    improved=sum(x['cumulative']>y['cumulative']+1e-10 for x,y in zip(a,b)),worse=sum(x['cumulative']<y['cumulative']-1e-10 for x,y in zip(a,b)),
                    median_annual_cost_bp=float(np.median([x['cost_bp_annual']+x['stop_slippage_bp_annual'] for x in a])),median_turnover=float(np.median([x['turnover_annual'] for x in a])),
                    **{'median_'+k:float(np.median([x[k] for x in a if x[k] is not None])) for k in ('correlation','beta','alpha_annual','ic5','exposure')},
                    yearly={year:float(np.median([x['yearly'][year] for x in a])) for year in a[0]['yearly']}))
    return out


def main():
    rows=json.loads((study.OUT/'asset-results.json').read_text());diags=json.loads((study.OUT/'diagnostics.json').read_text())
    charts=json.loads(gzip.decompress((study.OUT/'chart-data.json.gz').read_bytes()))
    sums=summary(rows+diags);study.write(study.OUT/'summary.json',sums);study.write(study.OUT/'review-vs-stop.json',summary(rows,'stop'))
    primary=[r for r in rows if r['cost_bp']==5 and r['delay']==0];weakest={era:min((r for r in primary if r['era']==era and r['arm']=='review' and r['symbol']!='BIL'),key=lambda r:(r['cumulative'],r['symbol'])) for era,*_ in study.ERAS}
    study.write(study.OUT/'weakest-cases.json',weakest)
    incidents={}
    for symbol,first,last in [('CPER','2025-03-04','2025-09-04'),('IWM','2024-07-01','2024-12-01')]:
        c=charts[symbol+'_late'];days=np.array(c['days']);ix=np.flatnonzero((days>=first)&(days<=last));start,end=int(ix[0]),int(ix[-1]);out={}
        for arm,a in {**c['arms'],**c['diagnostics']}.items():
            nav=np.asarray(a['nav'],float);trades=[t for t in a['trades'] if t['entry_date']<=last and (t['exit_date'] is None or t['exit_date']>=first)]
            out[arm]=dict(window_return=float(nav[end]/nav[start-1]-1),trades=trades)
        counterfactual=[];a=c['arms']['baseline']
        for t in out['baseline']['trades']:
            if t['exit_date'] is None:continue
            begin=int(np.flatnonzero(days==t['entry_date'])[0]);finish=int(np.flatnonzero(days==t['exit_date'])[0]);stop=np.asarray(a['stop'],float)
            hits=[i for i in range(begin,finish) if np.isfinite(stop[i]) and c['low'][i]<=stop[i]]
            if not hits:continue
            i=hits[0];fill=min(c['open'][i],stop[i])*.9995
            counterfactual.append(dict(entry=t['entry_date'],baseline_exit=t['exit_date'],baseline_return=t['net_return'],first_touch=c['days'][i],
                open=c['open'][i],high=c['high'][i],low=c['low'][i],close=c['close'][i],stop=stop[i],standing_fill=fill,
                standing_return=fill/t['entry']*.9995/1.0005-1,conditional_close_return=c['close'][i]*.9995/t['entry']*.9995/1.0005-1))
        review_windows=[]
        for trade in out['stop']['trades']:
            if trade['exit_date'] is None:continue
            x=int(np.flatnonzero(days==trade['exit_date'])[0]);atr=c['atr'][x-(trade['exit_index']-trade['exit_signal'])];price=trade['exit_price'];observations=[]
            for i in range(x+1,min(x+11,len(days))):
                loc=(c['close'][i]-c['low'][i])/(c['high'][i]-c['low'][i]) if c['high'][i]>c['low'][i] else .5
                conditions=dict(near_exit=price*1.001<=c['close'][i]<=price+atr,up=c['fast_up'][i]>=.55,down=c['fast_down'][i]<=.35,
                    slope=c['normalized_slope'][i]>0 or c['normalized_slope'][i]>c['normalized_slope'][i-1],
                    bullish_close=c['close'][i]>max(c['close'][i-1],c['open'][i]),location=loc>=.6,volume=c['pressure'][i]>=0)
                observations.append(dict(day=c['days'][i],close=c['close'][i],up=c['fast_up'][i],down=c['fast_down'][i],conditions=conditions,qualifies=all(conditions.values())))
            review_windows.append(dict(exit_date=trade['exit_date'],exit_fill=price,upper=price+atr,observations=observations))
        incidents[symbol]=dict(first=first,last=last,actual_last_session=c['days'][end],arms=out,fixed_entry_first_stop=counterfactual,stop_review_windows=review_windows,
            counterfactual_limit='Fixed baseline entry/stop path until first touch, holding one trade constant. Not compounded portfolio performance; same-close hypothetical execution unverified.')
    study.write(study.OUT/'incident-audit.json',incidents)
    lookup={(r['symbol'],r['era'],r['arm']):r for r in primary};changes=[]
    for r in primary:
        if r['arm']!='review' or r['symbol']=='BIL':continue
        b=lookup[r['symbol'],r['era'],'baseline'];s=lookup[r['symbol'],r['era'],'stop']
        changes.append(dict(symbol=r['symbol'],era=r['era'],baseline=b['cumulative'],stop=s['cumulative'],review=r['cumulative'],
            gain=r['cumulative']-b['cumulative'],review_gain=r['cumulative']-s['cumulative'],sharpe_change=r['sharpe']-b['sharpe'],
            recovery_closed=r['recovery_closed'],recovery_wins=r['recovery_wins'],warnings=r['warnings'],resets=r['resets'],changes=r['changes']))
    study.write(study.OUT/'attribution.json',sorted(changes,key=lambda r:r['gain']))
    print(json.dumps(study.clean(dict(primary_summary=[s for s in sums if s['cost_bp']==5 and s['delay']==0],
        weakest=weakest,incidents={s:{a:q['window_return'] for a,q in v['arms'].items()} for s,v in incidents.items()},
        passes={a:sum(s['passed'] for s in sums if s['arm']==a) for a in study.model.ARMS})),indent=2))


if __name__=='__main__':main()
