"""Descriptive results and incident evidence; no parameter changes."""
import gzip
import json
import numpy as np
import research_coherent_review as study
from analyze_stop_review import summary


def main():
    rows=json.loads((study.OUT/'asset-results.json').read_text());diags=json.loads((study.OUT/'diagnostics.json').read_text())
    charts=json.loads(gzip.decompress((study.OUT/'chart-data.json.gz').read_bytes()))
    sums=summary(rows+diags);study.write(study.OUT/'summary.json',sums)
    primary=[r for r in rows if r['cost_bp']==5 and r['delay']==0]
    weakest={era:min((r for r in primary if r['era']==era and r['arm']=='review' and r['symbol']!='BIL'),key=lambda r:(r['cumulative'],r['symbol'])) for era,*_ in study.ERAS}
    study.write(study.OUT/'weakest-cases.json',weakest)
    incidents={}
    for symbol,first,last in [('CPER','2025-03-04','2025-09-04'),('IWM','2024-07-01','2024-12-01')]:
        c=charts[symbol+'_late'];days=np.array(c['days']);ix=np.flatnonzero((days>=first)&(days<=last));a,b=int(ix[0]),int(ix[-1]);out={}
        for arm,v in c['arms'].items():
            out[arm]=dict(window_return=v['nav'][b]/v['nav'][a-1]-1,
                trades=[t for t in v['trades'] if t['entry_date']<=last and (t['exit_date'] is None or t['exit_date']>=first)],
                events=[e for e in v['events'] if first<=e['day']<=last],
                daily=[dict(day=c['days'][i],close=c['close'][i],fast_up=c['fast_up'][i],
                    **{k:v[k][i] for k in ('hold_value','recover_value','reviewer_owned','review_signal','stop','shared_score','decision_anchor')}) for i in ix])
        incidents[symbol]=dict(first=first,last=last,actual_last=c['days'][b],arms=out)
    study.write(study.OUT/'incident-audit.json',incidents)
    lookup={(r['symbol'],r['era'],r['arm']):r for r in primary}
    attribution=[]
    for r in primary:
        if r['arm']=='baseline' or r['symbol']=='BIL':continue
        a=lookup[r['symbol'],r['era'],'baseline']
        attribution.append(dict(symbol=r['symbol'],era=r['era'],arm=r['arm'],gain=r['cumulative']-a['cumulative'],
            control=a['cumulative'],candidate=r['cumulative'],entry_invalidations=r['entry_invalidations'],
            recoveries=r['recovery_closed'],recovery_wins=r['recovery_wins'],cancelled=r['cancelled_recoveries']))
    study.write(study.OUT/'attribution.json',sorted(attribution,key=lambda r:r['gain']))
    anchor=study.previous.OUT/'historical-close-stop-anchor.json'
    study.write(study.OUT/'historical-close-stop-anchor.json',json.loads(anchor.read_text()))
    print(json.dumps(study.clean(dict(primary=[s for s in sums if s['cost_bp']==5 and s['delay']==0],weakest=weakest,
        incidents={s:{a:r['window_return'] for a,r in v['arms'].items()} for s,v in incidents.items()},
        passes={a:sum(s['passed'] for s in sums if s['arm']==a) for a in study.model.ARMS})),indent=2))


if __name__=='__main__':main()
