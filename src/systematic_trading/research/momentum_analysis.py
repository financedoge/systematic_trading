"""Paired calendar inference and reconciled USD research diagnostics."""
from collections import defaultdict
from datetime import date
import math

import numpy as np


def monthly_returns(economic,initial=1000000):
    closes={}
    for row in economic['nav']:
        closes[row['date'][:7]]=float(row['nav'])
    previous=initial;result={}
    for month,nav in sorted(closes.items()):
        result[month]=nav/previous-1;previous=nav
    return result


def statistics(economic,quotes,initial=1000000):
    nav=np.array([initial]+[float(r['nav']) for r in economic['nav']])
    returns=nav[1:]/nav[:-1]-1
    rows=economic['nav'];days=[r['date'] for r in rows]
    years=(date.fromisoformat(days[-1])-date.fromisoformat(days[0])).days/365.25
    fills=defaultdict(list)
    for f in economic['fills']:fills[f['date']].append(f)
    positions={s:0 for s in quotes};cash=initial
    cost,turnover,fees=0.,0.,0.
    annual_cost=defaultdict(float);annual_turnover=defaultdict(float)
    pnl=defaultdict(float);holdings=[];gross=[];effective=[];max_weights=[]
    equity_weight=[];bond_weight=[];exposure=defaultdict(list)
    holding_starts={};closed_durations=[];by_asset_daily={s:[] for s in quotes}
    for i,day in enumerate(days):
        opening=cash+sum(q*float(quotes[s][day]['open']) for s,q in positions.items())
        traded=sum(abs(f['quantity'])*float(f['price']) for f in fills[day])
        fee=sum(float(f['fee']) for f in fills[day])
        if opening<=0:raise ValueError('Nonpositive pretrade NAV')
        c,t=fee/opening*10000,traded/opening
        cost+=c;turnover+=t;fees+=fee;annual_cost[day[:4]]+=c;annual_turnover[day[:4]]+=t
        daily_pnl={s:positions[s]*(float(quotes[s][day]['close'])-(float(quotes[s][days[i-1]]['close']) if i else float(quotes[s][day]['reference']))) for s in quotes}
        for f in fills[day]:
            s=f['symbol'];q=f['quantity'];price=float(f['price'])
            before=positions[s];positions[s]+=q
            if before==0 and positions[s]>0:holding_starts[s]=i
            if before>0 and positions[s]==0:closed_durations.append(i-holding_starts.pop(s))
            cash-=q*price+float(f['fee'])
            daily_pnl[s]+=q*(float(quotes[s][day]['close'])-price)-float(f['fee'])
        calculated=cash+sum(q*float(quotes[s][day]['close']) for s,q in positions.items())
        if abs(calculated-float(rows[i]['nav']))>.02 or abs(cash-float(rows[i]['cash']))>.02:
            raise ValueError('Fill ledger does not reconcile with daily NAV/cash')
        for s,v in daily_pnl.items():pnl[s]+=v;by_asset_daily[s].append(v/nav[i])
        weights={s:positions[s]*float(quotes[s][day]['close'])/calculated for s in quotes}
        for s,w in weights.items():exposure[s].append(w)
        total=sum(weights.values());gross.append(total)
        holdings.append(sum(q>0 for q in positions.values()))
        effective.append(total**2/sum(w*w for w in weights.values()) if total else 0.)
        max_weights.append(max(weights.values()))
        equity_weight.append(sum(weights.get(s,0) for s in ('SPY','VGK','EWJ','EWH','EWY','MCHI')))
        bond_weight.append(sum(weights.get(s,0) for s in ('IEF','TLT','LQD','HYG')))
    if abs(sum(pnl.values())-(nav[-1]-initial))>.02:raise ValueError('Asset PnL does not reconcile')
    monthly=monthly_returns(economic,initial)
    yearly=defaultdict(lambda:1.)
    for month,r in monthly.items():yearly[month[:4]]*=1+r
    return dict(cagr=float((nav[-1]/initial)**(1/years)-1),volatility=float(np.std(returns,ddof=1)*math.sqrt(252)),
        sharpe_zero_cash=float(np.mean(returns)/np.std(returns,ddof=1)*math.sqrt(252)),
        max_drawdown=float(np.min(nav/np.maximum.accumulate(nav)-1)),terminal_nav=float(nav[-1]),
        annual_cost_bps=cost/years,annual_turnover=turnover/years,total_fees_usd=fees,
        calendar_cost_bps=dict(annual_cost),calendar_turnover=dict(annual_turnover),calendar_returns={y:v-1 for y,v in yearly.items()},
        mean_gross=float(np.mean(gross)),mean_cash_weight=float(1-np.mean(gross)),mean_held_count=float(np.mean(holdings)),
        mean_effective_holdings=float(np.mean(effective)),maximum_weight=float(max(max_weights)),days_weight_above_45=sum(w>.450001 for w in max_weights),
        mean_equity_weight=float(np.mean(equity_weight)),mean_bond_weight=float(np.mean(bond_weight)),
        mean_asset_weights={s:float(np.mean(w)) for s,w in exposure.items()},asset_pnl_usd=dict(pnl),
        mean_closed_holding_sessions=float(np.mean(closed_durations)) if closed_durations else None,
        completed_holding_spells=len(closed_durations),open_holding_spells=len(holding_starts),
        monthly=monthly,daily_returns=returns.tolist(),dates=days,asset_daily_contribution=by_asset_daily,
        last_nav=rows[-1],last_held_weights={s:exposure[s][-1] for s in exposure})


def holm(values):
    values=np.asarray(values,dtype=float)
    order=np.argsort(values,kind='stable');result=np.empty(len(values));running=0.
    for k,i in enumerate(order):
        running=max(running,min(1.,values[i]*(len(values)-k)));result[i]=running
    return result


def paired_bootstrap(matrix,block=6,replications=20000,seed=20261001):
    """Joint circular months; NaNs mark genuinely unavailable paired samples.

    Missing samples remain in their calendar locations. Resampled means use
    only jointly observed pairs. No unrelated asset rows inflate sample size.
    """
    matrix=np.asarray(matrix,dtype=float)
    n,m=matrix.shape;valid=np.isfinite(matrix);counts=valid.sum(axis=0)
    totals=np.where(valid,matrix,0.)
    means=np.divide(totals.sum(axis=0),counts,out=np.zeros(m),where=counts>0)
    rng=np.random.default_rng(seed);samples=[]
    for offset in range(0,replications,500):
        size=min(500,replications-offset)
        starts=rng.integers(0,n,size=(size,math.ceil(n/block)))
        idx=((starts[:,:,None]+np.arange(block))%n).reshape(size,-1)[:,:n]
        weights=np.zeros((size,n))
        np.add.at(weights,(np.repeat(np.arange(size),n),idx.ravel()),1)
        denom=weights@valid.astype(float)
        samples.append(np.divide(weights@totals,denom,out=np.full((size,m),np.nan),where=denom>0))
    draws=np.concatenate(samples)
    result=[]
    for j in range(m):
        if counts[j]<12:
            result.append(dict(n=int(counts[j]),mean_annual=None,p=1.,ci95=None));continue
        values=draws[:,j];values=values[np.isfinite(values)]
        raw=(1+np.sum(np.abs(values-means[j])>=abs(means[j])))/(len(values)+1)
        result.append(dict(n=int(counts[j]),mean_annual=float(12*means[j]),p=float(raw),
                           ci95=(12*np.quantile(values,[.025,.975])).tolist()))
    adjusted=holm([r['p'] for r in result])
    for row,p in zip(result,adjusted,strict=True):row['holm_p']=float(p)
    return result


def comparison_matrix(protocol,results,cost=5):
    months=sorted(results['parent-M'][cost]['monthly'])
    matrix=[]
    for c in protocol['comparisons']:
        if c['id'].startswith('transfer') or any(k not in results for k in c['terms']):
            matrix.append([float('nan')]*len(months));continue
        column=[]
        for month in months:
            if any(month not in results[k][cost]['monthly'] for k in c['terms']):column.append(float('nan'))
            else:column.append(sum(w*results[k][cost]['monthly'][month] for k,w in c['terms'].items()))
        matrix.append(column)
    return np.asarray(matrix).T
