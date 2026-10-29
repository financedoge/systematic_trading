"""Causal ranking and self-financing, fractional-share strategy-sleeve portfolios.

Research only. Shadow strategy states are inputs, never reconstructed from the
portfolio's selection or fills. Cash earns zero. No execution authority.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from scipy.stats import rankdata


def rank_accounts(nav, symbols, t, short=63, long=252):
    if t < long:
        return [], None
    x = np.asarray(nav[t-long:t+1], float)
    r = x[1:] / x[:-1] - 1
    valid = (np.isfinite(r).all(axis=0) & (np.std(r, axis=0, ddof=1)>1e-12)
             & (np.std(r[-short:], axis=0, ddof=1)>1e-12)
             & (np.count_nonzero(abs(r)>1e-12, axis=0)>=2))
    js = np.flatnonzero(valid)
    if not len(js):
        return [], r
    v = r[:, js]
    values = np.column_stack((np.prod(1+v[-short:], axis=0)-1,
        np.sqrt(252)*v[-short:].mean(axis=0)/v[-short:].std(axis=0, ddof=1),
        np.prod(1+v, axis=0)-1,
        np.sqrt(252)*v.mean(axis=0)/v.std(axis=0, ddof=1)))
    ranks = np.column_stack([rankdata(values[:, k], method='average') for k in range(4)])
    scores = ((ranks-1)/max(1,len(js)-1)).mean(axis=1)
    names = ('short_return','short_sharpe','long_return','long_sharpe')
    rows = [dict(symbol=symbols[j], index=int(j), score=float(s),
                 **{k:float(z) for k,z in zip(names,vv)}) for j,s,vv in zip(js,scores,values)]
    rows.sort(key=lambda row:(-row['score'],row['symbol']))
    return rows, r


def risk_weights(returns):
    m = returns.shape[1]
    sample = np.atleast_2d(np.cov(returns,rowvar=False,ddof=1))*252
    cov = .5*sample+.5*np.diag(np.diag(sample))
    cov += np.diag(np.maximum(0,.05**2-np.diag(cov)))
    b = np.ones(m)/m
    result = minimize(lambda x:.5*x@cov@x-np.sum(b*np.log(x)),
        1/np.sqrt(np.diag(cov)*m),jac=lambda x:cov@x-b/x,
        bounds=[(1e-9,None)]*m,method='L-BFGS-B',
        options={'ftol':1e-14,'gtol':1e-10,'maxiter':3000})
    w = result.x/result.x.sum()
    error = float(np.max(abs(w*(cov@w)/(w@cov@w)-b)))
    if error>1e-6:
        raise RuntimeError(f'ERC did not converge: {result.message}; error={error}')
    return w,error


def theoretical(weights, desired):
    active = weights*np.asarray(desired,bool)
    return np.r_[active,1-active.sum()]


def target_distance(current,last_adopted):
    return float(np.abs(current-last_adopted).sum())


def rebalance(cash,units,prices,budget,active,fee):
    """Net existing holdings; solve the post-fee capital budget exactly."""
    old = units*prices
    before = float(cash.sum()+old.sum())
    invested = budget*active
    after = before
    for _ in range(100):
        new = before-fee*np.abs(invested*after-old).sum()
        if abs(new-after)<1e-14*max(1,before):
            after = new
            break
        after = new
    delta = invested*after-old
    costs = abs(delta)*fee
    new_units = invested*after/prices
    new_cash = budget*(1-np.asarray(active,bool))*after
    # An empty ranking holds unassigned cash in component zero.
    new_cash[0]+=(1-budget.sum())*after
    assert abs(new_cash.sum()+(new_units*prices).sum()+costs.sum()-before)<1e-10
    return new_cash,new_units,delta,costs


def run(days, symbols, opens, closes, shadows, desired, held, *, start,
        kind='equal', source='strategy', clock='monthly', n=15,
        cost_bp=5, delay=0, short=63, long=252, fixed_targets=None):
    """start is first eligible month-end close; initial trade is later open.

    An adopted membership order is immutable in transit. Daily strategy states
    use the same delayed shadow execution. A pending signal exit takes priority
    when joining. Allocation and signal changes at the same open are netted.
    Dynamic comparisons use last *adopted* (executed) theoretical target, with
    cash, and do not replace that target with drifted actual holdings.
    """
    days=np.asarray(days);opens=np.asarray(opens);closes=np.asarray(closes)
    T,M=opens.shape
    if not (0<=cost_bp<10000 and delay in (0,1) and 0<=start<T-1):
        raise ValueError('Invalid parameters')
    if not (opens.shape==closes.shape==shadows.shape==desired.shape==held.shape):
        raise ValueError('Aligned panel required')
    if not np.isfinite(opens).all() or not np.isfinite(closes).all() or np.min(opens)<=0 or np.min(closes)<=0:
        raise ValueError('No filling unsupported quotes')
    fee=cost_bp/10000
    cash=np.zeros(M);cash[0]=1.;units=np.zeros(M);budget=np.zeros(M)
    adopted=np.r_[np.zeros(M),1.];pending={}
    nav=np.full(T,np.nan);nav[start]=1
    holding=np.zeros((T,M));sleeve=np.zeros((T,M));cash_path=np.full(T,np.nan)
    contribution=np.zeros((T,M));costs=np.zeros((T,M));turnover=np.zeros(T)
    fills=[];decisions=[];adoptions=[];ranks=[];erc_error=0.;ledger_error=0.
    previous_nav=1.;previous_close=closes[start]
    for t in range(start,T):
        if t>start:
            old_units=units.copy()
            # Overnight P&L belongs to the positions carried into this open.
            pnl=old_units*(opens[t]-previous_close)
            if t in pending:
                decision=pending.pop(t);budget=decision['weights'].copy()
                cash,units,delta,charges=rebalance(cash,units,opens[t],budget,held[t],fee)
                adopted=decision['theoretical'].copy()
                adoptions.append(dict(decision=decision['date'],date=str(days[t]),
                    reason=decision['reason'],distance=decision['distance'],
                    weights=budget.tolist(),theoretical=adopted.tolist()))
                reason='allocation'
            else:
                delta=np.zeros(M);charges=np.zeros(M)
                for j in range(M):
                    if units[j]>0 and not held[t,j]:
                        delta[j]=-units[j]*opens[t,j];charges[j]=-delta[j]*fee
                        cash[j]+= -delta[j]-charges[j];units[j]=0
                    elif budget[j]>0 and held[t,j] and cash[j]>0:
                        delta[j]=cash[j]/(1+fee);charges[j]=delta[j]*fee
                        units[j]+=delta[j]/opens[t,j];cash[j]=0
                reason='signal'
            for j in np.flatnonzero(abs(delta)>1e-14):
                fills.append(dict(date=str(days[t]),index=t,symbol=symbols[j],side='buy' if delta[j]>0 else 'sell',
                    units=float(abs(delta[j])/opens[t,j]),price=float(opens[t,j]),
                    notional=float(abs(delta[j])),fee=float(charges[j]),reason=reason))
            pnl+=units*(closes[t]-opens[t])-charges
            contribution[t]=pnl;costs[t]=charges
            turnover[t]=abs(delta).sum()/previous_nav
            nav[t]=cash.sum()+units@closes[t]
            ledger_error=max(ledger_error,abs(nav[t]-previous_nav-pnl.sum()))
            assert cash.min()>-1e-12 and units.min()>-1e-12
        else:
            nav[t]=1
        holding[t]=units*closes[t]/nav[t];sleeve[t]=(cash+units*closes[t])/nav[t]
        cash_path[t]=cash.sum()/nav[t]
        previous_nav=nav[t];previous_close=closes[t]
        # Last observed partial month is not declared a month-end.
        month_end=t+1<T and str(days[t])[:7]!=str(days[t+1])[:7]
        inspect=t==start or month_end or clock=='dynamic'
        if clock=='buyhold' and t!=start:inspect=False
        if not inspect or t+1+delay>=T:continue
        if source=='fixed':
            w=fixed_targets[t].copy();rows=[]
        elif source=='all':
            w=np.ones(M)/M;rows=[]
        else:
            rows,r=rank_accounts(shadows if source=='strategy' else closes,symbols,t,short,long)
            js=[r['index'] for r in rows[:n]];w=np.zeros(M)
            if len(js):
                if kind=='equal':w[js]=1/len(js)
                else:
                    # Risk always refers to net strategy returns, including cash.
                    rr=shadows[t-251:t+1]/shadows[t-252:t]-1
                    ww,err=risk_weights(rr[:,js]);w[js]=ww;erc_error=max(erc_error,err)
        theory=theoretical(w,desired[t]);distance=target_distance(theory,adopted)
        trigger=t==start or month_end or (clock=='dynamic' and distance>=.10-1e-12)
        if trigger and not pending:
            reason='initial' if t==start else 'month-end' if month_end else 'target-change'
            decision=dict(date=str(days[t]),index=t,weights=w,theoretical=theory,reason=reason,distance=distance)
            pending[t+1+delay]=decision
            decisions.append(dict(date=str(days[t]),execution_date=str(days[t+1+delay]),reason=reason,distance=distance,
                                  weights=w.tolist(),theoretical=theory.tolist()))
            if rows:ranks.append(dict(date=str(days[t]),rows=rows))
    ix=slice(start,None)
    if ledger_error>1e-10:raise AssertionError('Daily P&L does not reconcile')
    return dict(days=days[ix].astype(str).tolist(),nav=nav[ix],holdings=holding[ix],sleeves=sleeve[ix],
        cash=cash_path[ix],contribution=contribution[ix],costs=costs[ix],turnover=turnover[ix],
        fills=fills,decisions=decisions,adoptions=adoptions,ranks=ranks,
        erc_error=erc_error,ledger_error=ledger_error,symbols=symbols)


def metrics(path):
    nav=np.asarray(path['nav']);r=nav[1:]/nav[:-1]-1;years=len(r)/252
    dd=1-nav/np.maximum.accumulate(nav);vol=r.std(ddof=1)*np.sqrt(252)
    cagr=float((nav[-1]/nav[0])**(1/years)-1)
    return dict(cumulative=float(nav[-1]/nav[0]-1),cagr=cagr,
        sharpe=float(r.mean()*252/vol) if vol>1e-12 else None,
        volatility=float(vol),max_drawdown=float(dd.max()),
        calmar=cagr/float(dd.max()) if dd.max()>1e-12 else None,
        average_invested=float(1-np.mean(path['cash'][1:])),
        turnover_annual=float(np.sum(path['turnover'][1:])/years),
        cost_bp_annual=float(np.sum(np.sum(path['costs'][1:],axis=1)/nav[:-1])*1e4/years),
        fills=len(path['fills']),allocations=len(path['adoptions']),
        first_signal=path['days'][0],last=path['days'][-1],sessions=len(r),
        max_capital_weight=float(np.max(path['sleeves'][1:])),
        mean_active_count=float(np.mean(np.count_nonzero(path['holdings'][1:]>1e-12,axis=1))),
        mean_effective_invested_count=float(np.mean([
            x.sum()**2/(x@x) if x@x>1e-15 else 0 for x in path['holdings'][1:]])))
