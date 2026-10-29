"""Episode-weighted, decision-conditioned continuation and recovery value models.

Training labels are protected hypothetical paths, not realized strategy alpha.
Actual decisions use only current features and frozen training coefficients.
"""
from copy import deepcopy
import numpy as np
from . import stop_review as parent

VERSION='trained-review-v1'
ARMS=('baseline','stop','review')  # report: protection / price / price+volume
HORIZON=10
RISK_PENALTY=.25
Features=parent.Features
activity=parent.activity


def ema(x,span):
    a=np.empty(len(x));a[0]=x[0]
    for i in range(1,len(x)):a[i]=a[i-1]+2/(span+1)*(x[i]-a[i-1])
    return a


def inputs(f):
    q=activity(f);atr=np.maximum(q['atr'],f.close*1e-4)
    r=np.r_[0,np.diff(np.log(f.close))];r3=np.array([r[max(0,t-2):t+1].sum() for t in range(len(r))])
    v=np.log(f.volume/ema(f.volume,20));location=2*q['location']-1
    q.update(scale=atr/f.close,price=np.column_stack((r/(atr/f.close),r3/(atr/f.close*np.sqrt(3)),
        (f.close-ema(f.close,10))/atr,(ema(f.close,10)-ema(f.close,60))/atr,location)),
        volume=np.column_stack((v,q['pressure'],v*location)))
    return q


def distance(cl,t):
    p=cl['parameters'];return p['wide'] if p['context'] and cl['aligned'][t] else p['tight']


def features(f,q,t,state,kind):
    a=max(q['atr'][t],f.close[t]*1e-4)
    z=np.r_[q['price'][t],(f.close[t]-state['reference'])/a,(state['peak']-f.close[t])/a,
        min(t-state['origin'],60)/20,(f.close[t]-state['level'])/a,float(state['owned'])]
    if kind=='volume':z=np.r_[z,q['volume'][t]]
    elif kind!='price':raise ValueError('Unknown feature family')
    return np.r_[1.,np.clip(z,-5,5)]


def recovery_state(f,cl,q,t,watch):
    risk=f.close[t]*cl['sigma']
    return dict(reference=watch['price'],origin=watch['day'],peak=max(watch['price'],f.close[t]),
        level=f.close[t]-distance(cl,t)*risk,risk=risk,owned=True)


def path_label(f,cl,q,t,state,task,*,cost_bp=5,slip_bp=5,horizon=HORIZON,trace=False):
    """Hypothetical continuation with standing stop and causal HMM handoff.

    H bars after the next opening, terminal mark at the following open. No
    reviewer exits inside the label. Labels are withheld until full H+1 maturity,
    even when an earlier stop makes their outcome observable sooner.
    """
    end=t+horizon+1
    if end>=len(f.days):return None
    entry=float(f.open[t+1]);slip=slip_bp/1e4;scale=q['scale'][t];s=deepcopy(state);states=[]
    if task=='recover':
        if abs(entry-f.close[t])>q['atr'][t]:return dict(y=[0.,0.],maturity=end,cancelled=True,states=[])
        s.update(reference=entry,origin=t+1,peak=entry,risk=entry*cl['sigma'],level=entry-distance(cl,t)*entry*cl['sigma'])
    elif task!='hold':raise ValueError('Unknown decision task')
    exit_price=float(f.open[end]);lowest=entry;scheduled=False;reason='horizon'
    for j in range(t+1,end):
        if scheduled:exit_price=float(f.open[j]);lowest=min(lowest,exit_price);reason='trend';break
        if f.low[j]<=s['level']:
            exit_price=float(min(f.open[j],s['level'])*(1-slip));lowest=min(lowest,exit_price);reason='stop';break
        lowest=min(lowest,float(f.low[j]));s['peak']=max(s['peak'],float(f.close[j]))
        s['level']=max(s['level'],s['peak']-distance(cl,j)*s['risk'])
        if s['owned'] and cl['eligible'][j]:s['owned']=False
        scheduled=bool(not s['owned'] and cl['fast_down'][j])
        if trace and not scheduled:states.append((j,deepcopy(s)))
    else:lowest=min(lowest,exit_price)
    # Gross incremental return: recovery round-trip fees applied at decision time.
    return dict(y=[(exit_price/entry-1)/scale,max(0.,1-lowest/entry)/scale],maturity=end,
        cancelled=False,states=states,exit_price=exit_price,reason=reason)


def sample(f,cl,q,t,task,state,group):
    label=path_label(f,cl,q,t,state,task)
    if label is None:return None
    return dict(t=t,maturity=label['maturity'],task=task,state=deepcopy(state),group=group,
        x=features(f,q,t,state,'volume').tolist(),y=label['y'],cancelled=label['cancelled'])


def dataset(f,cl,rule,start):
    q=inputs(f);sim=parent.simulate(f,cl,start=start,rule=rule);out=[];watch=None;current=None;fills={}
    for e in sim['episodes']:fills[e['entry_index']]=e
    sales={e['exit_index']:e for e in sim['episodes'] if e['exit_index'] is not None}
    for t in range(start,len(f.days)-HORIZON-1):
        if t in fills:current=fills[t];watch=None
        if t in sales:watch=dict(day=t,price=sales[t]['exit_price']);current=None
        if sim['held'][t] and sim['desired'][t]:
            e=current;peak=max(e['entry'],float(np.max(f.close[e['entry_index']:t+1])));risk=e['entry']*cl['sigma']
            state=dict(reference=e['entry'],origin=e['entry_index'],peak=peak,
                level=max(sim['stop'][t],peak-distance(cl,t)*risk),risk=risk,owned=False)
            out.append(sample(f,cl,q,t,'hold',state,'held:'+str(e['entry_index'])))
        elif not sim['held'][t] and not sim['desired'][t] and watch and 1<=t-watch['day']<=20:
            state=recovery_state(f,cl,q,t,watch);group='exit:'+str(watch['day'])
            out.append(sample(f,cl,q,t,'recover',state,group))
            # Include held states of hypothetical recoveries. Each exit episode
            # receives one total weight, regardless of the number of overlapping paths.
            path=path_label(f,cl,q,t,state,'recover',trace=True)
            for j,st in path['states']:
                row=sample(f,cl,q,j,'hold',st,'shadow:'+str(watch['day']))
                if row is not None:out.append(row)
    return [r for r in out if r is not None],sim


def weights(rows):
    from collections import Counter
    counts=Counter(r['group'] for r in rows)
    return np.array([1/counts[r['group']] for r in rows])


def fit_model(rows,kind,ridge):
    d=11 if kind=='price' else 14
    if not rows:return dict(beta=np.zeros((d,2)).tolist(),mean=np.zeros(d).tolist(),scale=np.ones(d).tolist(),groups=0,rows=0,ridge=ridge,kind=kind)
    x=np.array([r['x'][:d] for r in rows]);y=np.array([r['y'] for r in rows]);w=weights(rows)
    mean=np.average(x,axis=0,weights=w);scale=np.maximum(np.sqrt(np.average((x-mean)**2,axis=0,weights=w)),.1)
    mean[0]=0;scale[0]=1;z=(x-mean)/scale
    if ridge is None:
        beta=np.zeros((d,2));beta[0]=np.average(y,axis=0,weights=w)
    else:
        penalty=np.eye(d)*ridge;penalty[0,0]=1e-8
        beta=np.linalg.solve(z.T@(w[:,None]*z)+penalty,z.T@(w[:,None]*y))
    return dict(beta=beta.tolist(),mean=mean.tolist(),scale=scale.tolist(),groups=len(set(r['group'] for r in rows)),rows=len(rows),ridge=ridge,kind=kind)


def predict(model,x):
    d=len(model['mean']);return ((np.asarray(x)[:d]-model['mean'])/model['scale'])@np.array(model['beta'])


def value(pred,scale,task,fee):
    gain=pred[0]*scale;draw=max(0.,pred[1])*scale
    if task=='recover':gain=(1+gain)*(1-fee)/(1+fee)-1
    return (gain-RISK_PENALTY*draw)/scale


def fit_family(rows,kind,split):
    final={};prefix={};selection={}
    for task in ('hold','recover'):
        r=[a for a in rows if a['task']==task];train=[a for a in r if a['maturity']<split];valid=[a for a in r if a['t']>=split]
        candidates=[]
        choices=(None,1.,10.,100.) if len(set(a['group'] for a in train))>=8 else (None,)
        for ridge in choices:
            model=fit_model(train,kind,ridge)
            if valid:
                error=np.array([predict(model,a['x'])-a['y'] for a in valid]);loss=float(np.average(error[:,0]**2+.25*error[:,1]**2,weights=weights(valid)))
            else:loss=1e20
            candidates.append(dict(ridge=ridge,loss=loss,model=model))
        chosen=min(candidates,key=lambda a:(a['loss'],a['ridge'] is not None,-(a['ridge'] or 0)))
        prefix[task]=chosen['model'];final[task]=fit_model(r,kind,chosen['ridge'])
        selection[task]=dict(ridge=chosen['ridge'],validation_loss=chosen['loss'],training_groups=len(set(a['group'] for a in train)),
            validation_groups=len(set(a['group'] for a in valid)),candidates=[{k:v for k,v in a.items() if k!='model'} for a in candidates])
    return dict(kind=kind,models=final,selection=selection),dict(kind=kind,models=prefix)


def simulate(f,cl,*,start,cost_bp=5,delay=0,rule=None,arm='baseline',fit=None,slip_bp=5,
             entry_review=True,exit_review=True,handoff=True,record=False,force_disabled=False):
    if arm=='baseline':return parent.simulate(f,cl,start=start,cost_bp=cost_bp,delay=delay,rule=rule,slip_bp=slip_bp)
    if arm not in ('stop','review') or delay not in (0,1) or fit is None:raise ValueError('Invalid reviewer')
    n=len(f.days);fee=cost_bp/1e4;slip=slip_bp/1e4;lag=1+delay;q=inputs(f);p=cl['parameters']
    margin=fit.get('margin');enabled=margin is not None and not force_disabled
    nav=np.full(n,np.nan);stop=nav.copy();hold_value=nav.copy();recover_value=nav.copy();owned_path=np.zeros(n,bool)
    held=np.zeros(n,bool);desired=held.copy();invested=held.copy();review_signal=held.copy()
    cash=1.;units=0.;target=False;armed=True;pending={};fills=[];episodes=[];events=[];observations=[]
    episode=None;watch=None;level=peak=risk=np.nan;owned=False
    for t in range(start,n):
        sold=False;was_invested=units>0;reasons=[]
        def sell(price,reason,signal,phase,trigger=None):
            nonlocal cash,units,target,armed,level,peak,watch,sold,owned
            fills.append(dict(session=t,side='sell',units=float(units),price=float(price),fee=float(units*price*fee),phase=phase,trigger=trigger))
            cash+=units*price*(1-fee);units=0.;r=price/episode['entry']*(1-fee)/(1+fee)-1
            episode.update(exit_index=t,exit_price=float(price),exit_signal=signal,exit_reason=reason,exit_policy=0,net_return=float(r))
            watch=dict(day=t,price=float(price));target=False
            if phase!='open':armed=False
            level=peak=np.nan;sold=True;owned=False
        order=pending.pop(t,None)
        if order:
            if order['side']=='buy':
                if order['reason']=='exit_review' and abs(f.open[t]-order['signal_close'])>order['signal_atr']:
                    target=False;reasons.append('recovery_open_cancelled')
                else:
                    price=float(f.open[t]);units=cash/(price*(1+fee));cash=0.;peak=price;risk=price*cl['sigma'];level=price-order['distance']*risk
                    watch=None;owned=bool(handoff and order['reason']=='exit_review')
                    episode=dict(entry_index=t,entry=price,entry_signal=order['signal'],entry_policy=0,entry_reason=order['reason'],
                        initial_risk_fraction=order['distance']*cl['sigma'],exit_index=None,exit_price=None,exit_signal=None,exit_reason=None,
                        context='up' if cl['aligned'][order['signal']] else 'down' if cl['counter'][order['signal']] else 'uncertain',handoff_index=None)
                    episodes.append(episode);fills.append(dict(session=t,side='buy',units=float(units),price=price,fee=float(units*price*fee),phase='open',trigger=None))
            else:sell(float(f.open[t]),order['reason'],order['signal'],'open')
        invested[t]=was_invested or units>0
        if units:
            stop[t]=level
            if f.low[t]<=level:
                trigger=float(level);phase='open_gap' if f.open[t]<=level else 'intraday_stop'
                sell(float(min(f.open[t],level)*(1-slip)),'intraday_protection',t,phase,trigger);pending.clear()
        if units:
            peak=max(peak,float(f.close[t]));level=max(level,peak-distance(cl,t)*risk)
            if owned and cl['eligible'][t]:owned=False;episode['handoff_index']=t;reasons.append('trend_handoff')
        task=state=None
        if units and target and not pending:
            task='hold';state=dict(reference=episode['entry'],origin=episode['entry_index'],peak=peak,level=level,risk=risk,owned=owned)
        elif not units and not target and not pending and not sold and watch and 1<=t-watch['day']<=20:
            task='recover';state=recovery_state(f,cl,q,t,watch)
        utility=np.nan
        if task:
            x=features(f,q,t,state,fit['kind']);pred=predict(fit['models'][task],x);utility=value(pred,q['scale'][t],task,fee)
            (hold_value if task=='hold' else recover_value)[t]=utility
            if record:observations.append(dict(t=t,task=task,state=deepcopy(state),x=x.tolist(),prediction=pred.tolist(),utility=float(utility)))
        invalid=bool(enabled and entry_review and task=='hold' and utility < -margin)
        reversal=bool(enabled and exit_review and task=='recover' and utility > margin)
        if cl['fast_probability'][t,2]<p['reset']:armed=True
        if target and ((not owned and cl['fast_down'][t]) or invalid):
            reason='entry_invalidated' if invalid else 'thesis_failed' if cl['thesis_exit'][t] else 'fast_down'
            pending[t+lag]=dict(side='sell',signal=t,reason=reason);target=False;armed=False
            if invalid:reasons.append('entry_invalidated')
        elif not target and not units and not pending and ((armed and cl['eligible'][t]) or reversal):
            # Preserve ordinary entry priority when both models agree to buy.
            recovery=not (armed and cl['eligible'][t]) and reversal
            pending[t+lag]=dict(side='buy',signal=t,distance=distance(cl,t),reason='exit_review' if recovery else 'ordinary',
                signal_close=float(f.close[t]),signal_atr=float(q['atr'][t]));target=True;armed=False
            if recovery:review_signal[t]=True;reasons.append('exit_reversed')
        if reasons:events.append(dict(session=t,day=str(f.days[t]),reasons=reasons,reset=False,old_policy=0,policy=0,changed=False))
        nav[t]=cash+units*f.close[t];held[t]=units>0;desired[t]=target;owned_path[t]=owned
    return dict(nav=nav,stop=stop,held=held,desired=desired,exposure=held.astype(float),invested_session=invested,
        review_signal=review_signal,reset=np.zeros(n),policy=np.zeros(n),hold_value=hold_value,recover_value=recover_value,
        reviewer_owned=owned_path,episodes=episodes,fills=fills,events=events,observations=observations)


def shadow_diagnostics(f,cl,sim,fit):
    """Post-replay prequential diagnostic. Never changes real replay decisions."""
    q=inputs(f);by_day={};pending={};states={};scores=[]
    for task in ('hold','recover'):
        m=fit['models'][task];d=len(m['mean']);states[task]=[20*np.eye(d),20*np.array(m['beta'])]
    for r in sim['observations']:by_day[r['t']]=r
    if not by_day:return []
    for t in range(min(by_day),len(f.days)):
        for task,(s,b) in states.items():s*=2**(-1/63);b*=2**(-1/63)
        for old in pending.pop(t,[]):
            task=old['task'];s,b=states[task];x=np.array(old['standard_x']);y=np.array(old['y'])
            scores.append({k:v for k,v in old.items() if k!='standard_x'})
            s+=np.outer(x,x)/HORIZON;b+=np.outer(x,y)/HORIZON
        if t not in by_day:continue
        r=by_day[t];task=r['task'];m=fit['models'][task];x=(np.array(r['x'])-m['mean'])/m['scale']
        s,b=states[task];prediction=x@np.linalg.solve(s+1e-6*np.eye(len(x)),b)
        label=path_label(f,cl,q,t,r['state'],task)
        if label is not None:pending.setdefault(label['maturity'],[]).append(dict(origin=t,maturity=label['maturity'],task=task,
            fixed=r['prediction'],shadow=prediction.tolist(),y=label['y'],standard_x=x.tolist()))
    return scores
