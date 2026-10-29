"""Freeze then evaluate the operator's 70% FR25 / 30% BroadTrend hypothesis."""
import argparse
import json
import numpy as np
import research_trend_sleeve_portfolio as parent
from systematic_trading.research import broadtrend, broadtrend_blend as blend

ROOT=parent.ROOT
OUT=ROOT/'research/broadtrend-fr25-20261029-v1'
write,read,digest,gzwrite=parent.write,parent.read,parent.digest,parent.gzwrite


def protocol():
    return dict(version='broadtrend-fr25-1.0.0',parent=read(parent.OUT/'shadow-validation.json'),
        fr25=parent.frozen.verified_input_provenance(),models=broadtrend.PACK_SHA256,
        scope='Matched USD development test; 2024-01-31 cash anchor, next-open fills through frozen FR25 2026-10-12.',
        arms={'fr25':'100% FR25 monthly','blend':'70% FR25 / 30% BroadTrend monthly','broadtrend':'100% BroadTrend monthly',
            'blend_dynamic':'70/30 month-end OR cash-inclusive L1 latest theoretical target vs last adopted target >= 0.10'},
        capital='Monthly reset strategy capital70/30. Between resets preserve FR25 shares/cash and all BroadTrend per-ETF sleeve shares/cash; daily BroadTrend signals trade only their own cash. No daily strategy-capital renormalization. All shadow accounts continue.',
        execution='Fractional adjusted USD units, zero cash interest, target decisions at close and fills at open t+1+delay. Aggregate same-ETF orders net across strategy sleeves; charge fee once on external net notional. Solve post-fee NAV consistently. Internal same-ETF capital transfers have no fee. Uninvested FR25 budget remains its cash, BroadTrend cash stays in each ETF sleeve. No terminal sale.',
        dynamic='Recompute full70/30 theoretical ETF exposure plus cash daily from frozen FR25 targets and BroadTrend desired state; compare to last adopted theoretical target, never actual drift. Threshold0.10 predeclared; no threshold search. Freeze one pending decision until execution; delay applies to underlying daily signals too. Dynamic changes both capital timing and FR25 adoption timing, not a pure capital-drift control.',
        frictions=[[c,d] for c in [5,10,20] for d in [0,1]],
        assessment='Primary net Sharpe; prefer blend only with CAGR loss <=1 percentage point and max drawdown worsening <=2 points versus100%FR25, report all six frictions and annual blocks. Also show pure diversification/risk reduction even if return guard fails. No posthoc70/30 weight search.',
        diagnostics='Actual fee/turnover/exposure; annual returns; component daily correlation and covariance risk share; block-bootstrap paired Sharpe/CAGR difference (21-session common blocks,1000draws,seed2910), descriptive only. Worst ETF contribution chart and standalone strategy chart.',
        limitations=['Repeatedly inspected and selected histories; no untouched holdout or prospective evidence.',
            'Frozen FR25 panel ends2026-10-12 and has no comparable pre2023 reconstruction; blend evidence cannot establish multi-cycle stability.',
            'Cash has zero interest, Sharpe uses zero rate; synthetic adjusted units, no taxes/FX/spread/market impact.',
            'Internal netting assumes commonaccount and compatible ETF units; current broker daily-sleeve execution is not implemented. Monitoring is separately authorized, funding is not.',
            'Fullpool beating tested rank portfolios is not universal optimality. Standalone early chronology lost money.'],
        code={str(p.relative_to(ROOT)).replace(chr(92),'/'):digest(p) for p in [Path(__file__),
            ROOT/'src/systematic_trading/research/broadtrend_blend.py',ROOT/'tests/test_broadtrend.py']})


from pathlib import Path


def prepare():
    parent.load();OUT.mkdir(parents=True,exist_ok=True)
    p=parent.study.clean(protocol())
    if (OUT/'protocol.json').exists() and read(OUT/'protocol.json')!=p:raise ValueError('Frozen blend protocol changed')
    write(OUT/'protocol.json',p);print('Frozen',digest(OUT/'protocol.json'),flush=True)


def evaluate():
    if parent.study.clean(protocol())!=read(OUT/'protocol.json'):raise ValueError('Blend protocol changed')
    if (OUT/'results.json').exists():raise ValueError('Completed evidence exists')
    arrays,meta=parent.load();panel=parent.frozen._load_panel()
    all_days=arrays['late_days'];days=panel['days'].astype(str);symbols=panel['symbols'].tolist()
    common=np.intersect1d(all_days,days);ai=np.searchsorted(all_days,common);pi=np.searchsorted(days,common)
    bt_symbols=[s for s in arrays['late_symbols'].tolist() if s!='BIL'];js=[arrays['late_symbols'].tolist().index(s) for s in bt_symbols]
    op=panel['open'][pi];cl=panel['close'][pi];fr=panel['fr25'][pi]
    for j,s in enumerate(bt_symbols):
        k=symbols.index(s)
        if not np.array_equal(op[:,k],arrays['late_open'][ai,js[j]]) or not np.array_equal(cl[:,k],arrays['late_close'][ai,js[j]]):
            raise ValueError('FR25 and BroadTrend quote bases differ')
    start=int(np.searchsorted(common,'2024-01-31'));results=[];detail={};paths={};checks=[];attrs={}
    for cost,delay in [(c,d) for c in (5,10,20) for d in (0,1)]:
        desired=arrays[f'late_desired_c{cost}d{delay}'][ai][:,js];held=arrays[f'late_held_c{cost}d{delay}'][ai][:,js]
        for arm,alpha,clock in [('fr25',1.,'monthly'),('blend',.7,'monthly'),('broadtrend',0.,'monthly'),('blend_dynamic',.7,'dynamic')]:
            z=blend.run(common,symbols,op,cl,fr,desired,held,bt_symbols,start=start,alpha=alpha,cost_bp=cost,delay=delay,clock=clock)
            error=broadtrend.independent_ledger(z,cl[start:])['max_nav_error'];stats=parent.model.metrics(z)
            nn=z['nav'];dd=np.array(z['days']);yearly={}
            for yr in sorted(set(d[:4] for d in z['days'][1:])):
                ix=np.flatnonzero(np.char.startswith(dd,yr)&(np.arange(len(dd))>0));yearly[yr]=float(nn[ix[-1]]/nn[ix[0]-1]-1)
            key=f'{arm}_c{cost}d{delay}';results.append(dict(arm=arm,cost_bp=cost,delay=delay,**stats,yearly=yearly));paths[key]=nn
            checks.append(dict(case=key,ledger_error=error))
            if cost==5 and delay==0:
                detail[key]=z;attrs[key]=sorted([dict(symbol=s,pnl=float(z['contribution'][:,j].sum()),fee=float(z['costs'][:,j].sum())) for j,s in enumerate(symbols)],key=lambda x:x['pnl'])
            print(key,round(stats['cumulative']*100,3),round(stats['sharpe'],3),flush=True)
    # Exact standalone controls against the preceding experiment, same dates.
    for row in read(parent.OUT/'fr25-matched.json'):
        arm={'all':'broadtrend','FR25':'fr25','fr25':'fr25'}.get(row['arm'])
        if arm:
            z=next(r for r in results if r['arm']==arm and r['cost_bp']==row['cost_bp'] and r['delay']==row['delay'])
            if abs(z['cumulative']-row['cumulative'])>1e-10:raise ValueError('Standalone matched control changed')
    r={k:np.diff(v)/v[:-1] for k,v in paths.items()};base=r['fr25_c5d0'];other=r['broadtrend_c5d0'];candidate=r['blend_c5d0']
    rng=np.random.default_rng(2910);boot=[];N=len(base)
    def measure(x):return np.array([x.mean()/x.std(ddof=1)*np.sqrt(252),np.prod(1+x)**(252/len(x))-1])
    for _ in range(1000):
        ix=np.concatenate([(np.arange(21)+i)%N for i in rng.integers(0,N,size=(N+20)//21)])[:N]
        boot.append(measure(candidate[ix])-measure(base[ix]))
    diagnostics=dict(component_correlation=float(np.corrcoef(base,other)[0,1]),
        approximate_fr25_risk_share=float(.7*(.7*np.var(base,ddof=1)+.3*np.cov(base,other)[0,1])/np.var(.7*base+.3*other,ddof=1)),
        bootstrap_difference_95=np.quantile(boot,[.025,.975],axis=0).tolist(),bootstrap_columns=['Sharpe','CAGR'],
        bootstrap_note='Paired circular21-session bootstrap of realized daily returns; not a new strategy replay or selection-adjusted inference.')
    guard=[]
    for row in results:
        if row['arm'] not in ('blend','blend_dynamic'):continue
        base=next(r for r in results if r['arm']=='fr25' and r['cost_bp']==row['cost_bp'] and r['delay']==row['delay'])
        guard.append(dict(arm=row['arm'],cost_bp=row['cost_bp'],delay=row['delay'],sharpe_gain=row['sharpe']-base['sharpe'],
            cagr_gain=row['cagr']-base['cagr'],drawdown_change=row['max_drawdown']-base['max_drawdown'],
            passes=row['sharpe']>base['sharpe'] and row['cagr']>=base['cagr']-.01 and row['max_drawdown']<=base['max_drawdown']+.02))
    write(OUT/'results.json',results);gzwrite(OUT/'paths.json.gz',dict(days=common[start:].tolist(),**paths));gzwrite(OUT/'detail.json.gz',detail)
    write(OUT/'attribution.json',attrs);write(OUT/'diagnostics.json',diagnostics);write(OUT/'assessment.json',guard)
    write(OUT/'validation.json',dict(cases=checks,standalone_controls='Exact cumulative agreement with previous matched studies',input_quote_agreement=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','evaluate']);globals()[p.parse_args().stage]()
