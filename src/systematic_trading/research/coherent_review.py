"""One market forecast, independent of position state, for causal trade review.

The target is the next tradable session's asset return, not a multi-day
counterfactual strategy value. Protective exits remain a separate risk layer.
"""
import numpy as np
from . import stop_review as parent
from . import trained_review as helpers

VERSION='coherent-review-v1'
ARMS=('baseline','stop','review')
MARGIN=.05
CHANGE=.10
Features=parent.Features
activity=parent.activity


def inputs(f):
    q=helpers.inputs(f)
    q['price_x']=np.column_stack((np.ones(len(f.days)),np.clip(q['price'],-5,5)))
    q['volume_x']=np.column_stack((q['price_x'],np.clip(q['volume'],-5,5)))
    return q


def observations(f,q):
    ix=np.arange(max(252,len(f.days)-758),len(f.days)-2)
    return ix,(f.open[ix+2]/f.open[ix+1]-1)/q['scale'][ix]


def regression(x,y,ridge):
    mean=x.mean(0);scale=np.maximum(x.std(0),.1);mean[0]=0;scale[0]=1
    z=(x-mean)/scale;beta=np.zeros(x.shape[1])
    if ridge is None:beta[0]=y.mean()
    else:
        penalty=np.eye(x.shape[1])*ridge;penalty[0,0]=1e-8
        beta=np.linalg.solve(z.T@z+penalty,z.T@y)
    return dict(beta=beta.tolist(),mean=mean.tolist(),scale=scale.tolist(),ridge=ridge,constant=float(y.mean()),rows=len(y))


def predict(model,x):
    return ((x-np.array(model['mean']))/model['scale'])@np.array(model['beta'])


def fit_family(f,kind):
    q=inputs(f);ix,y=observations(f,q);x=q[kind+'_x'][ix]
    width=min(126,len(ix)//5)
    if width<50:raise ValueError('Insufficient training for three chronological folds')
    folds=[];scores={ridge:[] for ridge in (None,1.,10.,100.)}
    for first in range(len(ix)-3*width,len(ix),width):
        valid=np.arange(first,first+width);train=np.flatnonzero(ix+2<ix[first])
        fold=dict(first=str(f.days[ix[valid[0]]]),last=str(f.days[ix[valid[-1]]]),
            training_last_origin=str(f.days[ix[train[-1]]]),training_last_maturity=str(f.days[ix[train[-1]]+2]),
            rows=len(train),validation_rows=len(valid),losses={})
        for ridge in scores:
            m=regression(x[train],y[train],ridge);error=predict(m,x[valid])-y[valid]
            loss=float(np.mean(error**2));scores[ridge].append(loss);fold['losses'][str(ridge)]=loss
        folds.append(fold)
    candidates=[dict(ridge=k,loss=float(np.mean(v)),fold_losses=v) for k,v in scores.items()]
    chosen=min(candidates,key=lambda r:(r['loss'],r['ridge'] is not None,-(r['ridge'] or 0)))
    control=float(np.mean(scores[None]));wins=sum(a<b for a,b in zip(chosen['fold_losses'],scores[None]))
    enabled=chosen['ridge'] is not None and chosen['loss']<control*.995 and wins>=2
    model=regression(x,y,chosen['ridge'])
    return dict(kind=kind,model=model,enabled=bool(enabled),margin=MARGIN,change=CHANGE,
        selection=dict(candidates=candidates,chosen=chosen['ridge'],folds=folds,fold_wins=wins,
            relative_loss_gain=1-chosen['loss']/control if control>0 else 0.),
        first_origin=str(f.days[ix[0]]),last_origin=str(f.days[ix[-1]]),last_maturity=str(f.days[ix[-1]+2]))


def decisions(score,anchor,scale,fee,margin=MARGIN,change=CHANGE):
    """Same score, disjoint cost-aware actions; equality never triggers."""
    net=((1+score*scale)*(1-fee)/(1+fee)-1)/scale
    return bool(score < -margin and score < anchor-change),bool(net > margin and score > anchor+change)


def simulate(f,cl,*,start,cost_bp=5,delay=0,rule=None,arm='baseline',fit=None,slip_bp=5,
             entry_review=True,exit_review=True,handoff=True,require_change=True,review_interval=1,
             record=False,force_disabled=False,score_override=None):
    if arm=='baseline':return parent.simulate(f,cl,start=start,cost_bp=cost_bp,delay=delay,rule=rule,slip_bp=slip_bp)
    if arm not in ('stop','review') or delay not in (0,1) or fit is None:raise ValueError('Invalid reviewer')
    n=len(f.days);fee=cost_bp/1e4;slip=slip_bp/1e4;lag=1+delay;q=inputs(f);p=cl['parameters']
    score=predict(fit['model'],q[fit['kind']+'_x']) if score_override is None else np.asarray(score_override,float)
    enabled=fit['enabled'] and not force_disabled
    nav=np.full(n,np.nan);stop=nav.copy();hold_value=nav.copy();recover_value=nav.copy();anchor_path=nav.copy()
    owned_path=np.zeros(n,bool);held=owned_path.copy();desired=held.copy();invested=held.copy();review_signal=held.copy()
    cash=1.;units=0.;target=False;armed=True;pending={};fills=[];episodes=[];events=[]
    episode=None;watch=None;level=peak=risk=np.nan;owned=False;buy_anchor=np.nan
    for t in range(start,n):
        sold=False;was_invested=units>0;reasons=[]
        def sell(price,reason,signal,phase,trigger=None):
            nonlocal cash,units,target,armed,level,peak,watch,sold,owned
            if units<=0:raise ValueError('Sell without holding')
            fills.append(dict(session=t,side='sell',units=float(units),price=float(price),fee=float(units*price*fee),phase=phase,trigger=trigger))
            cash+=units*price*(1-fee);units=0.;r=price/episode['entry']*(1-fee)/(1+fee)-1
            episode.update(exit_index=t,exit_price=float(price),exit_signal=signal,exit_reason=reason,exit_policy=0,net_return=float(r))
            # Review starts on a later close. The sale day's close is then known.
            watch=dict(day=t,price=float(price),anchor=float(score[t]));target=False
            if phase!='open':armed=False
            level=peak=np.nan;sold=True;owned=False
        order=pending.pop(t,None)
        if order:
            if order['side']=='buy':
                if units:raise ValueError('Overlapping buy')
                if order['reason']=='exit_review' and abs(f.open[t]-order['signal_close'])>order['signal_atr']:
                    target=False;reasons.append('recovery_open_cancelled')
                else:
                    price=float(f.open[t]);units=cash/(price*(1+fee));cash=0.;peak=price;risk=price*cl['sigma'];level=price-order['distance']*risk
                    watch=None;owned=bool(handoff and order['reason']=='exit_review');buy_anchor=order['score']
                    episode=dict(entry_index=t,entry=price,entry_signal=order['signal'],entry_policy=0,entry_reason=order['reason'],
                        initial_risk_fraction=order['distance']*cl['sigma'],exit_index=None,exit_price=None,exit_signal=None,exit_reason=None,
                        context='up' if cl['aligned'][order['signal']] else 'down' if cl['counter'][order['signal']] else 'uncertain',
                        handoff_index=None,entry_score=float(buy_anchor))
                    episodes.append(episode);fills.append(dict(session=t,side='buy',units=float(units),price=price,fee=float(units*price*fee),phase='open',trigger=None))
            else:sell(float(f.open[t]),order['reason'],order['signal'],'open')
        invested[t]=was_invested or units>0
        if units:
            stop[t]=level
            if f.low[t]<=level:
                trigger=float(level);phase='open_gap' if f.open[t]<=level else 'intraday_stop'
                sell(float(min(f.open[t],level)*(1-slip)),'intraday_protection',t,phase,trigger);pending.clear()
        if units:
            peak=max(peak,float(f.close[t]));level=max(level,peak-helpers.distance(cl,t)*risk)
            if owned and cl['eligible'][t]:owned=False;episode['handoff_index']=t;reasons.append('trend_handoff')
        invalid=reversal=False;active=enabled and (t-start)%review_interval==0
        if units and target and not pending:
            hold_value[t]=score[t];anchor_path[t]=buy_anchor
            invalid=bool(active and entry_review and score[t]<-fit['margin'] and
                (not require_change or score[t]<buy_anchor-fit['change']))
        elif not units and not target and not pending and not sold and watch and 1<=t-watch['day']<=20:
            recover_value[t]=((1+score[t]*q['scale'][t])*(1-fee)/(1+fee)-1)/q['scale'][t];anchor_path[t]=watch['anchor']
            reversal=bool(active and exit_review and recover_value[t]>fit['margin'] and
                (not require_change or score[t]>watch['anchor']+fit['change']))
        if cl['fast_probability'][t,2]<p['reset']:armed=True
        pending_recovery=handoff and any(o['side']=='buy' and o['reason']=='exit_review' for o in pending.values())
        if target and ((not owned and not pending_recovery and cl['fast_down'][t]) or invalid):
            reason='entry_invalidated' if invalid else 'thesis_failed' if cl['thesis_exit'][t] else 'fast_down'
            pending[t+lag]=dict(side='sell',signal=t,reason=reason);target=False;armed=False
            if invalid:reasons.append('entry_invalidated')
        elif not target and not units and not pending and ((armed and cl['eligible'][t]) or reversal):
            recovery=not (armed and cl['eligible'][t]) and reversal
            pending[t+lag]=dict(side='buy',signal=t,distance=helpers.distance(cl,t),reason='exit_review' if recovery else 'ordinary',
                signal_close=float(f.close[t]),signal_atr=float(q['atr'][t]),score=float(score[t]));target=True;armed=False
            if recovery:review_signal[t]=True;reasons.append('exit_reversed')
        if reasons:events.append(dict(session=t,day=str(f.days[t]),reasons=reasons,reset=False,old_policy=0,policy=0,changed=False))
        nav[t]=cash+units*f.close[t];held[t]=units>0;desired[t]=target;owned_path[t]=owned
    return dict(nav=nav,stop=stop,held=held,desired=desired,exposure=held.astype(float),invested_session=invested,
        review_signal=review_signal,reset=np.zeros(n),policy=np.zeros(n),hold_value=hold_value,recover_value=recover_value,
        shared_score=score,decision_anchor=anchor_path,reviewer_owned=owned_path,episodes=episodes,fills=fills,events=events)
