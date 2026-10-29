"""Actual cash/share 70/30 allocation, with aggregate ETF order netting."""
import numpy as np
from .trend_sleeve_portfolio import theoretical, target_distance


def rebalance(cash, units, prices, budget, active, fee, groups):
    """Solve post-fee capital; attribute net exchange fees to same-ETF changes."""
    old=units*prices;before=float(cash.sum()+old.sum());after=before
    for _ in range(100):
        delta=budget*active*after-old
        net=np.bincount(groups,weights=delta)
        value=before-fee*np.abs(net).sum()
        if abs(value-after)<1e-14:after=value;break
        after=value
    delta=budget*active*after-old;charges=np.zeros(len(old))
    for group in np.unique(groups):
        js=groups==group;gross=np.abs(delta[js]).sum()
        if gross:charges[js]=fee*abs(delta[js].sum())*np.abs(delta[js])/gross
    newcash=budget*(1-active)*after
    # Unallocated FR25 capital belongs to its cash account (slot zero).
    newcash[0]+=(1-budget.sum())*after
    newunits=budget*active*after/prices
    if abs(newcash.sum()+newunits@prices+charges.sum()-before)>1e-10:
        raise ValueError('Blend capital does not reconcile')
    return newcash,newunits,delta,charges


def run(days,symbols,opens,closes,fr25,bt_desired,bt_held,bt_symbols,*,start,alpha=.7,cost_bp=5,delay=0,clock='monthly'):
    if not 0<=alpha<=1 or delay not in (0,1) or clock not in ('monthly','dynamic') or not 0<=cost_bp<10000:
        raise ValueError('Invalid blend configuration')
    days=np.asarray(days);opens=np.asarray(opens);closes=np.asarray(closes)
    if not np.isfinite(opens).all() or not np.isfinite(closes).all() or (opens<=0).any() or (closes<=0).any():
        raise ValueError('Complete positive quotes required')
    if fr25.shape!=opens.shape or (fr25<0).any() or (fr25.sum(axis=1)>1+1e-10).any():
        raise ValueError('Invalid FR25 targets')
    k=len(symbols);m=len(bt_symbols);idx=[symbols.index(s) for s in bt_symbols]
    groups=np.r_[np.arange(k),idx];op=opens[:,groups];cl=closes[:,groups];M=len(groups)
    cash=np.zeros(M);cash[0]=1.;units=np.zeros(M);adopted=np.r_[np.zeros(k),1.];pending={}
    fee=cost_bp/10000;nav=[];holdings=[];sleeves=[];cash_path=[];turnover=[];costs=[];contribution=[]
    fills=[];decisions=[];adoptions=[];group_capital=[];error=0.;budget=np.zeros(M)
    for t in range(start,len(days)):
        previous=float(cash.sum()+units@cl[t-1]) if t>start else 1.
        old=units.copy();charges=np.zeros(M);delta=np.zeros(M)
        active=np.r_[np.ones(k,bool),bt_held[t]]
        if t in pending:
            decision=pending.pop(t);budget=decision['weights']
            cash,units,delta,charges=rebalance(cash,units,op[t],budget,active,fee,groups)
            adopted=decision['theoretical'];adoptions.append(dict(date=str(days[t]),decision=decision['date'],reason=decision['reason']))
            reason='capital allocation'
        elif t>start:
            for j in range(k,M):
                if units[j]>0 and not active[j]:
                    delta[j]=-units[j]*op[t,j];charges[j]=-delta[j]*fee
                    cash[j]+=-delta[j]-charges[j];units[j]=0
                elif budget[j]>0 and active[j] and cash[j]>0:
                    delta[j]=cash[j]/(1+fee);charges[j]=delta[j]*fee
                    units[j]+=delta[j]/op[t,j];cash[j]=0
            reason='daily signal'
        net=np.bincount(groups,weights=delta,minlength=k);net_fees=np.bincount(groups,weights=charges,minlength=k)
        for j in np.flatnonzero(abs(net)>1e-14):
            fills.append(dict(date=str(days[t]),symbol=symbols[j],side='buy' if net[j]>0 else 'sell',
                units=float(abs(net[j])/opens[t,j]),price=float(opens[t,j]),notional=float(abs(net[j])),fee=float(net_fees[j]),reason=reason))
        value=float(cash.sum()+units@cl[t]);pnl=old*(op[t]-cl[t-1])+units*(cl[t]-op[t])-charges if t>start else np.zeros(M)
        error=max(error,abs(value-previous-pnl.sum()))
        actual=np.bincount(groups,weights=units*cl[t],minlength=k)/value
        sleeve=(cash+units*cl[t])/value
        nav.append(value);cash_path.append(float(cash.sum()/value));holdings.append(actual);sleeves.append(sleeve)
        turnover.append(float(abs(net).sum()/previous));costs.append(np.bincount(groups,weights=charges,minlength=k))
        contribution.append(np.bincount(groups,weights=pnl,minlength=k));group_capital.append([float(sleeve[:k].sum()),float(sleeve[k:].sum())])
        monthend=t+1<len(days) and str(days[t])[:7]!=str(days[t+1])[:7]
        if t+1+delay>=len(days) or pending:continue
        w=np.r_[alpha*fr25[t],np.full(m,(1-alpha)/m)]
        exposure=np.bincount(groups,weights=w*np.r_[np.ones(k),bt_desired[t]],minlength=k)
        theory=np.r_[exposure,1-exposure.sum()];distance=target_distance(theory,adopted)
        if t==start or monthend or (clock=='dynamic' and distance>=.10-1e-12):
            reason='initial' if t==start else 'month-end' if monthend else 'target-change'
            pending[t+1+delay]=dict(weights=w,theoretical=theory,date=str(days[t]),reason=reason)
            decisions.append(dict(date=str(days[t]),execution_date=str(days[t+1+delay]),reason=reason,distance=distance,
                theoretical=theory.tolist()))
        if cash.min() < -1e-10 or units.min() < -1e-10:raise ValueError('Negative blend cash/units')
    if error>1e-10:raise ValueError('Blend daily P&L reconciliation failed')
    return dict(days=days[start:].astype(str).tolist(),symbols=symbols,nav=np.array(nav),cash=np.array(cash_path),
        holdings=np.array(holdings),sleeves=np.array(sleeves),turnover=np.array(turnover),costs=np.array(costs),
        contribution=np.array(contribution),group_capital=group_capital,fills=fills,decisions=decisions,adoptions=adoptions,ledger_error=error)
