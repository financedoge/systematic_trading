"""Operator-nominated incidents; observations only, not parameter selection."""
import json
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import research_entry_value as parent
OUT=ROOT/'research/stop-review-20261027-v1'
WORK=ROOT/'var/research/stop-review-20261027-v1'


def main():
    market,*_,selected=parent.verified();OUT.mkdir(exist_ok=True);WORK.mkdir(parents=True,exist_ok=True)
    coverage={};cases={}
    for symbol in sorted(market):
        data=parent.prior.study.load_asset(symbol)
        for k in ('open','high','low','close','volume'):
            if not np.isfinite(data[k]).all() or np.any(data[k]<=0):raise ValueError((symbol,k))
        tol=1e-7*np.maximum(1,data['close'])
        bad=(data['low']>np.minimum(data['open'],data['close'])+tol)|(data['high']<np.maximum(data['open'],data['close'])-tol)|(data['high']<data['low'])
        if bad.any():raise ValueError((symbol,'OHLC geometry',int(bad.sum())))
        coverage[symbol]=dict(rows=len(data['days']),first=str(data['days'][0]),last=str(data['days'][-1]))
    for symbol,lo,hi in [('CPER','2025-03-04','2025-09-04'),('IWM','2024-07-01','2024-12-01')]:
        f,c,sim,start=parent.replay(symbol,'late',market,selected,arm='hmm');raw=parent.prior.study.load_asset(symbol)
        trades=[t for t in sim['episodes'] if str(f.days[t['entry_index']])<=hi and (t['exit_index'] is None or str(f.days[t['exit_index']])>=lo)]
        timeline=[]
        for i in np.flatnonzero((f.days>=np.datetime64(lo))&(f.days<=np.datetime64(hi))):
            timeline.append(dict(day=str(f.days[i]),open=f.open[i],high=raw['high'][i],low=raw['low'][i],close=f.close[i],volume=f.volume[i],
                up=c['fast_probability'][i,2],down=c['fast_probability'][i,0],slow_up=c['slow_probability'][i,2],stop=sim['stop'][i],
                thesis_failed=c['thesis_exit'][i],eligible=c['eligible'][i],desired=sim['desired'][i],nav=sim['nav'][i]))
        cases[symbol]=dict(interval=[lo,hi],trades=[dict(t,entry_date=str(f.days[t['entry_index']]),exit_date=str(f.days[t['exit_index']]) if t['exit_index'] is not None else None) for t in trades],timeline=timeline)
        print(symbol,json.dumps(parent.clean(cases[symbol]['trades'])),flush=True)
    parent.write(OUT/'baseline-inspection.json',dict(parent_protocol=parent.prior.study.digest(parent.OUT/'protocol.json'),coverage=coverage,cases=cases,
        script_sha256=parent.prior.study.digest(Path(__file__)),source='Same hash-verified adjusted OHLC and raw volume as parent, no online prices'))
    print('OHLC coverage verified',len(coverage),flush=True)


if __name__=='__main__':main()
