"""GLD daily-trading diagnostic. Preserve v3 numeric parameters; execute daily."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import numpy as np
from run_joint_breakout import ROOT as PARENT,asset,check,read,write,digest,verify,manifest,SingleReplay,transitions,summary_path
from systematic_trading.research.range_joint import History,describe,PARAMETERS,WINDOWS
from systematic_trading.research.range_trace import trace

ROOT=Path('var/research/gld-breakout-drilldown-20261018-v1')
PUBLIC=Path('research/gld-breakout-drilldown-20261018-v1')


def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
    if isinstance(x,(np.bool_,bool)):return bool(x)
    if isinstance(x,(np.integer,int)):return int(x)
    if isinstance(x,(np.floating,float)):return round(float(x),10) if np.isfinite(x) else None
    return x


def build():
    check(PARENT);verify(PARENT,'variants_manifest.json');verify(PARENT,'selection_manifest.json')
    choice=read(PARENT/'selection.json')['choices']['GLD'];p=np.array(choice['parameters']);a=asset('GLD');h=History.build(a)
    rows,episodes=trace(h,p);n=len(rows);days=a['days'];sig=np.array([r['active'] for r in rows],bool)
    frozen=dict(np.load(PARENT/'evaluation/GLD/signal.npz'))
    for k in ('active','stop','upper','duration','exit_reason'):
        np.testing.assert_allclose(np.array([r[k] for r in rows]),frozen[k],equal_nan=True,atol=1e-12,rtol=1e-12)
    modes={};fills=[];metrics={}
    spans=[('IS',str(days[252]),'2022-12-31'),('validation','2023-01-01','2023-12-31'),('OOS','2024-01-01',str(days[-1]))]
    for policy in ('event',):
        fields={k:np.full(n,np.nan) for k in ('nav','cash','quantity','fill_quantity','fill_price','fee','decision','target')}
        for period,start,end in spans:
            mask=days<=end;prefix={k:v[mask] for k,v in a.items()};ss=sig[mask];runner=SingleReplay(prefix,'GLD',start)
            idx=transitions(ss,prefix['days'],start,policy);path,economic,_=runner.run(.98*ss[:,None],idx,5,0,detailed=True)
            met=summary_path(path,runner);metrics[period+'_'+policy]=met;offset=int(np.flatnonzero(days>=start)[0])
            if period=='OOS':
                expected=np.load(PARENT/'evaluation/GLD'/f"local_stability_{policy}.npz")
                for k in ('nav','fees','turnover','exposure'):np.testing.assert_allclose(path[k],expected[k],atol=1e-10,rtol=0)
            if period=='IS' and policy=='event':
                expected=read(PARENT/'fits/GLD.json')['variants']['local_stability']['exact']['scenarios']['5:0']['metrics']
                for k,v in met.items():
                    if v is not None:assert abs(v-expected[k])<1e-10
            if period=='validation':
                expected=read(PARENT/'validation/GLD.json')['rows']['local_stability_'+policy]['scenarios']['5:0']['metrics']
                for k,v in met.items():
                    if v is not None:assert abs(v-expected[k])<1e-10
            bydate={f['date']:f for f in economic['fills']};quantity=0;signal_map={i+1:i for i in idx}
            for j,e in enumerate(economic['nav']):
                t=offset+j;day=str(days[t]);f=bydate.get(day);oldq=quantity;dq=int(f['quantity']) if f else 0;quantity+=dq
                for k,val in dict(nav=float(e['nav']),cash=float(e['cash']),quantity=quantity,fill_quantity=dq,
                    fill_price=float(f['price']) if f else np.nan,fee=float(f['fee']) if f else 0.,
                    decision=t in signal_map,target=.98*ss[t-1] if t in signal_map else np.nan).items():fields[k][t]=val
                if f:
                    sd=signal_map[t];reason='first account adoption' if sd==idx[0] else 'daily signal changed'
                    action='entry' if oldq==0 and quantity>0 else 'exit_all' if quantity==0 else 'add' if dq>0 else 'trim'
                    entrydate=rows[sd]['virtual_entry'];source_episode=rows[sd]['episode']
                    if rows[sd]['action']=='entry_confirmed':entrydate=t
                    fills.append(dict(period=period,policy=policy,index=t,date=day,signal_date=str(days[sd]),action=action,quantity=dq,
                        before=oldq,after=quantity,price=float(f['price']),fee=float(f['fee']),reason=reason,
                        model_action=rows[sd]['action'],model_episode=source_episode,
                        model_entry=str(days[entrydate]) if entrydate>=0 else None))
        modes[policy]={k:clean(v) for k,v in fields.items()}
    # The daily entry date matches execution; stops remain close conditions, not intraday orders.
    for t,r in enumerate(rows):
        r['low_below_stop']=bool(np.isfinite(r['stop']) and a['low'][t]<r['stop'])
    columns={k:clean([r[k] for r in rows]) for k in rows[0]}
    windows=[]
    tail,block,short,ref=map(int,(p[5],p[7],p[8],p[10]))
    for j in range(int(p[3]),int(p[4])+1):
        windows.append(dict(index=j,sessions=int(WINDOWS[j]),lower=clean(h.arrays[5][tail,j]),
            upper=clean(h.arrays[4][tail,j]),width=clean(h.arrays[6][tail,j]),drift=clean(h.arrays[7][block,j]),
            short_vol=clean(h.arrays[8][short,j]),long_vol=clean(h.arrays[9][j]),rank=clean(h.arrays[10][tail,ref,j])))
    fitting=dict(fit=read(PARENT/'fits/GLD.json'),validation=read(PARENT/'validation/GLD.json'),
        variants=read(PARENT/'variants.json')['variants']['GLD'],bounds=[dict(name=x[0],low=x[1],high=x[2],integer=x[3],selected=float(y)) for x,y in zip(PARAMETERS,p,strict=True)])
    data=clean(dict(symbol='GLD',through=str(days[-1]),days=days,price={k:a[k] for k in ('close','open','high','low','raw_close','volume')},
        parameters=p,decoded=describe(p),choice=choice,trace=columns,windows=windows,episodes=episodes,modes=modes,fills=fills,
        metrics=metrics,spans=spans,parent_selection_sha256=digest(PARENT/'selection.json'),fitting=fitting,
        native=read(ROOT/'native_verification.json') if (ROOT/'native_verification.json').exists() else None,
        limitations=['USD adjusted price units; engine fills rounded to cents; 5bp per side; idle cash yield zero; 98% target at entry, held unchanged until exit.',
            'Three independent accounts: pre2023 IS, calendar2023 validation,2024+ OOS; parameters are the final2023-selected rule.',
            'Chart ranges use central 60% of prior log closes, not the full min/max envelope. Audited adjusted OHLC and raw volume reuse the pinned v2 publication; audited price consistency does not establish point-in-time historical publication availability.',
            'Operator-directed daily trading: every completed close evaluates entry/exit, with target changes executed at the next session open. No calendar rebalance and no intraday stop order. On an entry session the model uses the open and then observes that session close; fill prices are rounded to cents.',
            'The parameter vector is inherited from v3 to isolate the execution change. It has not been reselected or refitted in this diagnostic. Future fitting and 2023 model selection are daily-only.',
            'No strategy promotion, monitoring or broker action.',
            'The original 2024+ evaluation is now inspected. Subsequent GLD changes informed by this audit are development retests of these dates, not fresh untouched OOS evidence.']))
    PUBLIC.mkdir(parents=True,exist_ok=True);ROOT.mkdir(parents=True,exist_ok=True)
    encoded=json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    (PUBLIC/'data.js').write_text('window.GLD_DIAGNOSTIC='+encoded+';\n',encoding='utf-8')
    # One portable data artifact; the HTML offers a local JSON export without a second stored copy.
    shutil.copyfile('scripts/gld_drilldown.html',PUBLIC/'index.html')
    shutil.copyfile(__file__,ROOT/'runner.py');shutil.copyfile('src/systematic_trading/research/range_trace.py',ROOT/'range_trace.py')
    write(ROOT/'receipt.json',dict(parent_input_sha256=digest(PARENT/'input_manifest.json'),selection_sha256=digest(PARENT/'selection.json'),
        GLD_asset_sha256=digest(Path('var/research/range-breakout-20261018-v2/assets/GLD.npz')),
        trace_days=n,signal_episodes=len(episodes),OOS_confirmations=sum(e['confirmation']>=int(np.flatnonzero(days>='2024-01-01')[0]) for e in episodes),
        execution='Daily close decisions, next session open execution; no calendar rebalancing. Numeric parameters unchanged to isolate execution.',
        OOS_daily_fills=[f for f in fills if f['period']=='OOS'],
        checks='Every signal/stop/risk value matches frozen v3. Daily OOS NAV,fees,turnover,exposure match saved event path;2023 daily metrics match saved evaluation;IS daily metrics match retained fit.',
        metrics=metrics,source_files={s:digest(Path(s)) for s in ['scripts/gld_drilldown.html','scripts/build_gld_drilldown.py','src/systematic_trading/research/range_trace.py','scripts/verify_gld_drilldown.cjs','scripts/verify_gld_daily_native.py','tests/test_range_trace.py']}))
    manifest(PUBLIC,'manifest.json',[PUBLIC/'index.html',PUBLIC/'data.js'])
    retained=[ROOT/'receipt.json',ROOT/'runner.py',ROOT/'range_trace.py']
    if (ROOT/'native_verification.json').exists():retained.append(ROOT/'native_verification.json')
    manifest(ROOT,'manifest.json',retained)
    print(json.dumps(dict(days=n,episodes=len(episodes),data_mib=round(len(encoded.encode())/2**20,2),metrics=metrics),indent=2))


if __name__=='__main__':
    argparse.ArgumentParser(description=__doc__).parse_args();build()

