"""Audit recovery gates on completed primary paths, without changing thresholds."""
import gzip
import json
from collections import Counter
import numpy as np
import research_decision_review as s


def main():
    charts=json.loads(gzip.decompress((s.OUT/'chart-data.json.gz').read_bytes()));out=[]
    for key,c in charts.items():
        for arm in ('stop','review'):
            a=c['arms'][arm];watch=None;counts=Counter();dates=[];fills={}
            for e in a['fills']:fills.setdefault(e['day'],[]).append(e)
            for i,day in enumerate(c['days']):
                sold=False
                for e in fills.get(day,[]):
                    if e['side']=='buy':watch=None
                    else:watch=dict(i=i,price=e['price'],atr=c['atr'][i-1]);sold=True
                if not watch or sold or a['held'][i] or not 1<=i-watch['i']<=20:continue
                counts['flat_watch_days']+=1
                conditions=dict(evidence=a['up_evidence'][i]>=np.log(4),positive_probability=a['probability'][i]>.5,
                    net_value=a['forecast'][i]>.0015,price_band=watch['price']*1.001<=c['close'][i]<=watch['price']+1.5*watch['atr'],
                    bullish_close=c['close'][i]>max(c['open'][i],c['close'][i-1]),
                    close_location=(c['close'][i]-c['low'][i])/(c['high'][i]-c['low'][i])>=.6 if c['high'][i]>c['low'][i] else False,
                    volume=c['pressure'][i]>=0)
                passed=True
                for name,ok in conditions.items():
                    counts['alone_'+name]+=int(ok);passed=passed and ok;counts['through_'+name]+=int(passed)
                if all(conditions.values()):dates.append(day)
            actual=[c['days'][i] for i,v in enumerate(a['review_signal']) if v==1]
            assert dates==actual,(key,arm,dates,actual)
            out.append(dict(case=key,arm=arm,counts=dict(counts),signals=dates))
    s.write(s.OUT/'recovery-gate-audit.json',out)
    selected={'TLT_late':['2023-11-03','2024-08-02','2024-08-16','2025-01-23'],
        'IWM_early':['2020-05-12','2020-02-14','2022-05-31'],
        'PPLT_late':['2025-04-21','2025-07-18'],'IAT_early':['2020-10-06','2021-02-08']}
    s.write(s.OUT/'failure-trade-audit.json',{key:{arm:[{k:t.get(k) for k in
        ('entry_date','exit_date','entry','exit_price','net_return','exit_reason','initial_risk_fraction')}
        for t in a['trades'] if t['entry_date'] in dates] for arm,a in charts[key]['arms'].items()}
        for key,dates in selected.items()})
    for era in ('late','early'):
        for arm in ('stop','review'):
            counts=Counter()
            for r in out:
                if r['case'].endswith('_'+era) and r['arm']==arm and not r['case'].startswith('BIL_'):counts.update(r['counts'])
            print(era,arm,dict(counts))


if __name__=='__main__':main()
