"""Operator-requested N20/N30 extension of the frozen N15 experiment."""
import argparse
import gzip
import json
import numpy as np
import research_trend_sleeve_portfolio as parent
from systematic_trading.research import trend_sleeve_portfolio as model

OUT=parent.ROOT/'research/trend-sleeve-width-20261029-v1'
WORK=parent.ROOT/'var/research/trend-sleeve-width-20261029-v1'


def protocol():
    return dict(identity=OUT.name,request='Operator requests N20 and N30 after seeing N15. Subsequent development experiment, not fresh width validation.',
        parent_protocol=parent.digest(parent.OUT/'protocol.json'),parent_results=parent.digest(parent.OUT/'results.json'),
        shadows=parent.read(parent.OUT/'shadow-validation.json')['shadows'],widths=[20,30],rank_windows=[63,252],
        allocation=['equal','risk'],clock=['monthly','dynamic'],frictions=parent.study.FRICTIONS,
        scope='All same supported risky strategies, dates, warmup, covariance, fees, cash and self-financing execution as N15. Only N changes. Compare N15, N20, N30 and unranked full pool. No ETF/model/rank-threshold fitting or width-specific timing tuning.',
        dynamic='Same cash-inclusive L1>=.10 versus last adopted target, plus month-end. One EW sleeve state flip changes L1 by2/N: N15=.1333,N20=.10,N30=.0667. This changes trigger frequency; monthly isolates width from that interaction.',
        controls='Retain exact N15/all-pool/BIL/FR25 results. Also run same raw-price four-rank, always-invested, equal-capital N20/N30 selectors at all frictions.',
        assessment='Higher net Sharpe with CAGR no more1pp worse and maxDD no more2pp worse vs matched N15; report both eras/sixfrictions, and same comparisons to all-pool sleeves. Show full 15/20/30 curve, cash, effective active breadth, turnover, costs, contribution concentration. No claim of global optimal N.',
        weakest='Same independently running virtual strategies/window: TLTlate/MCHIearly unchanged. Identify actual worstcontributor separately for each width/weight and provide dated fill inspector for all100ETF/era charts.',
        code={str(p.relative_to(parent.ROOT)).replace(chr(92),'/'):parent.digest(p) for p in [parent.Path(__file__),parent.ROOT/'src/systematic_trading/research/trend_sleeve_portfolio.py']})


def prepare():
    parent.load();OUT.mkdir(exist_ok=True);WORK.mkdir(parents=True,exist_ok=True)
    p=parent.study.clean(protocol())
    if (OUT/'protocol.json').exists() and parent.read(OUT/'protocol.json')!=p:raise ValueError('Frozen extension changed')
    parent.write(OUT/'protocol.json',p);print('Frozen width protocol',parent.digest(OUT/'protocol.json'),flush=True)


def evaluate():
    if parent.study.clean(protocol())!=parent.read(OUT/'protocol.json'):raise ValueError('Extension protocol changed')
    if (OUT/'results.json').exists():raise ValueError('Preserve completed width evidence')
    arrays,v=parent.load();rows=[];paths={};detail={};attrs={};ledger=erc=0.
    for era,meta in v['eras'].items():
        symbols=arrays[era+'_symbols'].tolist();js=[j for j,s in enumerate(symbols) if s!='BIL'];symbols=[symbols[j] for j in js]
        days=arrays[era+'_days'];op=arrays[era+'_open'][:,js];cl=arrays[era+'_close'][:,js];start=meta['start']
        paths[era+'_days']=days[start:].tolist()
        for n in (20,30):
            for cost,delay in parent.study.FRICTIONS:
                suffix=f'_c{cost}d{delay}';nav=arrays[era+'_nav'+suffix][:,js];held=arrays[era+'_held'+suffix][:,js];desired=arrays[era+'_desired'+suffix][:,js]
                for arm,kw in [('equal',{}),('risk',dict(kind='risk')),('equal_dynamic',dict(clock='dynamic')),
                               ('risk_dynamic',dict(kind='risk',clock='dynamic')),('raw_momentum',dict(source='raw'))]:
                    active=np.ones_like(held) if arm=='raw_momentum' else held
                    wants=np.ones_like(desired) if arm=='raw_momentum' else desired
                    z=model.run(days,symbols,op,cl,nav,wants,active,start=start,n=n,cost_bp=cost,delay=delay,**kw)
                    key=f'{era}_{arm}_n{n}{suffix}';stats=model.metrics(z);dd=np.array(z['days']);nn=z['nav'];yearly={}
                    for year in sorted(set(d[:4] for d in dd[1:])):
                        ix=np.flatnonzero(np.char.startswith(dd,year)&(np.arange(len(dd))>0));yearly[year]=float(nn[ix[-1]]/nn[ix[0]-1]-1)
                    rows.append(dict(era=era,n=n,arm=arm,cost_bp=cost,delay=delay,**stats,yearly=yearly));paths[key]=nn
                    ledger=max(ledger,parent.ledger_check(z,op,cl,days,symbols,start));erc=max(erc,z['erc_error'])
                    if cost==5 and delay==0 and arm in ('equal','risk','equal_dynamic','risk_dynamic'):
                        detail[key]=z
                        a=[dict(symbol=s,pnl=float(z['contribution'][:,j].sum()),fee=float(z['costs'][:,j].sum()),
                            average_weight=float(z['holdings'][1:,j].mean()),selected_days=int(np.sum(z['sleeves'][1:,j]>1e-12)),
                            fills=sum(f['symbol']==s for f in z['fills'])) for j,s in enumerate(symbols)]
                        attrs[key]=sorted(a,key=lambda x:(x['pnl'],x['symbol']))
                    print('Width',key,round(stats['cumulative']*100,2),round(stats['sharpe'] or 0,3),flush=True)
    parent.write(OUT/'results.json',rows);parent.gzwrite(OUT/'paths.json.gz',paths);parent.gzwrite(OUT/'detail.json.gz',detail);parent.write(OUT/'attribution.json',attrs)
    old=parent.read(parent.OUT/'results.json');lookup={(r['era'],r['arm'],r['cost_bp'],r['delay']):r for r in old};gates=[]
    for r in rows:
        if r['arm']=='raw_momentum':continue
        for name in ('N15','all'):
            arm=r['arm'] if name=='N15' else 'all';b=lookup[r['era'],arm,r['cost_bp'],r['delay']]
            checks=dict(sharpe=r['sharpe']>b['sharpe'],cagr=r['cagr']>=b['cagr']-.01,drawdown=r['max_drawdown']<=b['max_drawdown']+.02)
            gates.append(dict(era=r['era'],n=r['n'],arm=r['arm'],cost_bp=r['cost_bp'],delay=r['delay'],control=name,**checks,passed=all(checks.values())))
    parent.write(OUT/'assessment.json',gates)
    parent.write(OUT/'validation.json',dict(cases=len(rows),independent_ledger_max_error=ledger,erc_max_error=erc,
        contribution_max_error=max(abs(sum(r['pnl'] for r in a)-(detail[k]['nav'][-1]-1)) for k,a in attrs.items()),
        protocol=parent.digest(OUT/'protocol.json'),results=parent.digest(OUT/'results.json'),shadows=v['shadows']))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','evaluate'));globals()[p.parse_args().stage]()
